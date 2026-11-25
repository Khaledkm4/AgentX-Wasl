import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import date

import numpy as np

from wasl import config, db
from wasl.schemas import Candidate, Need, Practitioner, ProjectCard, ScoreBreakdown

log = logging.getLogger("wasl.retrieval")

WEIGHTS = dict(specialty=0.50, past_work_similarity=0.15, location=0.15, budget=0.10, availability=0.10)
RELEVANCE_FLOOR = 0.35  # drop candidates whose specialty < floor * best specialty for that need


# ---------- vector store ----------
class VectorStore(ABC):
    @abstractmethod
    def add(self, ids: list[str], vecs: np.ndarray): ...

    @abstractmethod
    def search(self, q: np.ndarray, k: int, allowed: set[str] | None = None) -> list[tuple[str, float]]: ...


class NumpyVectorStore(VectorStore):
    def __init__(self):
        self.ids: list[str] = []
        self.mat = np.zeros((0, 0), dtype=np.float32)

    def add(self, ids, vecs):
        vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True).clip(1e-9)
        self.mat = vecs if not self.ids else np.vstack([self.mat, vecs])
        self.ids += list(ids)

    def search(self, q, k, allowed=None):
        q = q / max(np.linalg.norm(q), 1e-9)
        sims = self.mat @ q
        order = [i for i in np.argsort(-sims) if allowed is None or self.ids[i] in allowed]
        return [(self.ids[i], float(sims[i])) for i in order[:k]]


# ---------- models (module singletons) ----------
_embedder = _reranker = None
_names: dict[str, str] = {}
FALLBACKS_USED: list[str] = []


def _load(kind: str, primary: str, fallback: str):
    from sentence_transformers import CrossEncoder, SentenceTransformer
    cls = SentenceTransformer if kind == "embed" else CrossEncoder
    kw = {"max_length": 256} if kind == "rerank" else {}  # profiles are short; caps activation memory
    if not config.ALLOW_DOWNLOAD:
        kw["local_files_only"] = True  # strictly offline: load from the D: cache, no Hub round-trips
    try:
        m = cls(primary, device="cpu", **kw)
        _names[kind] = primary
    except Exception as e:  # OOM / download failure -> explicit, loud fallback
        msg = f"[FALLBACK] {kind} model {primary} failed ({type(e).__name__}: {e}); using {fallback}"
        log.warning(msg)
        print(msg)
        FALLBACKS_USED.append(msg)
        m = cls(fallback, device="cpu", **kw)
        _names[kind] = fallback
    return m


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = _load("embed", config.EMBED_MODEL, config.EMBED_FALLBACK)
    return _embedder


def reranker():
    global _reranker
    if _reranker is None:
        _reranker = _load("rerank", config.RERANK_MODEL, config.RERANK_FALLBACK)
    return _reranker


def active_models() -> dict[str, str]:
    return dict(_names)


def embed(texts: list[str], query: bool = False) -> np.ndarray:
    m = embedder()
    if "e5" in _names["embed"]:
        texts = [("query: " if query else "passage: ") + t for t in texts]
    return m.encode(texts, normalize_embeddings=True, batch_size=16, convert_to_numpy=True)


def rerank(pairs: list[tuple[str, str]]) -> np.ndarray:
    if not pairs:
        return np.zeros(0)
    s = np.asarray(reranker().predict(pairs, batch_size=32, show_progress_bar=False), dtype=np.float32)
    return s if s.min() >= 0 and s.max() <= 1 else 1 / (1 + np.exp(-s))


# ---------- index ----------
def index_all(con: sqlite3.Connection, items: list[Practitioner]):
    ids = [p.id for p in items]
    db.save_embeddings(con, "specialty", _model_name(), ids, embed([db.specialty_text(p) for p in items]))
    db.save_embeddings(con, "works", _model_name(), ids, embed([db.works_text(p) for p in items]))


def _model_name():
    embedder()
    return _names["embed"]


_cache: dict = {}


def _state():
    if not _cache:
        con = db.connect()
        prs = db.load_practitioners(con)
        spec = db.load_embeddings(con, "specialty", _model_name())
        if set(spec) != set(prs):  # missing / different-model embeddings -> recompute once
            index_all(con, list(prs.values()))
            spec = db.load_embeddings(con, "specialty", _model_name())
        works = db.load_embeddings(con, "works", _model_name())
        vs = NumpyVectorStore()
        ids = list(prs)
        vs.add(ids, np.stack([spec[i] for i in ids]))
        _cache.update(prs=prs, vs=vs, works=works)
    return _cache


def practitioners() -> dict[str, Practitioner]:
    return _state()["prs"]


# ---------- scoring helpers ----------
def coverage(p: Practitioner, win: tuple[date, date]) -> float:
    s, e = win
    total = (e - s).days + 1
    covered = sum(max(0, (min(e, b) - max(s, a)).days + 1) for a, b in p.availability)
    return min(1.0, covered / total)


def is_available(p: Practitioner, win: tuple[date, date]) -> bool:
    return any(a <= win[0] and win[1] <= b for a, b in p.availability)


def location_ok(p: Practitioner, need: Need, city: str | None, allow_remote: bool = False) -> bool:
    return city is None or p.city == city or (p.remote_ok and (need.remote_ok or allow_remote))


def est_cost(p: Practitioner) -> int:
    return (p.price_min + p.price_max) // 2


def _budget_share(need: Need, card: ProjectCard) -> float | None:
    if card.budget.value is None:
        return None
    tot = sum(n.importance for n in card.needs) or need.importance or 1
    return card.budget.value * (need.importance or 1) / tot


def _query(need: Need, card: ProjectCard) -> str:
    ctx = f"مشروع {card.sector.value or need.sector} في {card.city.value or ''} - مرحلة {need.phase}"
    return f"{need.role}. {need.reason} ({ctx})"


# ---------- search ----------
def search_all(needs: list[Need], card: ProjectCard, k: int = 10) -> dict[str, list[Candidate]]:
    st = _state()
    prs, vs, works = st["prs"], st["vs"], st["works"]
    city = card.city.value
    queries = [_query(n, card) for n in needs]
    qv = embed(queries, query=True)

    pools: list[list[tuple[str, float]]] = []
    pairs: list[tuple[str, str]] = []
    for n, q, v in zip(needs, queries, qv):
        allowed = {i for i, p in prs.items() if n.sector in p.sectors}  # hard filter: exists + sector only
        pool = vs.search(v, k=max(3 * k, 30), allowed=allowed)
        pools.append(pool)
        pairs += [(q, f"{prs[i].name}: {db.specialty_text(prs[i])}. {db.works_text(prs[i])}") for i, _ in pool]
    rr = rerank(pairs)  # single batched pass for every need

    out, off = {}, 0
    for n, v, pool in zip(needs, qv, pools):
        scores = rr[off: off + len(pool)]
        off += len(pool)
        share = _budget_share(n, card)
        cands = []
        for (pid, cos), r in zip(pool, scores):
            p = prs[pid]
            cost = est_cost(p)
            loc = location_ok(p, n, city)
            b = ScoreBreakdown(
                specialty=round(float(0.7 * r + 0.3 * max(cos, 0)), 4),
                past_work_similarity=round(float(max(works[pid] @ v, 0)), 4) if pid in works else 0.0,
                location=1.0 if city is None or p.city == city else (0.6 if loc else 0.0),
                budget=1.0 if share is None or cost <= share else round(max(0.0, 1 - (cost - share) / share), 4),
                availability=round(coverage(p, n.phase_window), 4),
            )
            score = sum(WEIGHTS[f] * getattr(b, f) for f in WEIGHTS)
            cands.append(Candidate(practitioner_id=pid, need_id=n.id, estimated_cost=cost, score=round(score, 4),
                                   score_breakdown=b, is_available=is_available(p, n.phase_window),
                                   location_match=loc))
        if cands:
            best = max(c.score_breakdown.specialty for c in cands)
            cands = [c for c in cands if c.score_breakdown.specialty >= RELEVANCE_FLOOR * best]
        out[n.id] = sorted(cands, key=lambda c: -c.score)[:k]
    return out


def search(need: Need, card: ProjectCard, k: int = 10) -> list[Candidate]:
    return search_all([need], card, k)[need.id]
