"""The 4 agents (Clarifier, Requirements, Coordinator, Explainer) + deterministic Final Check.
LLM output is always schema-validated; every agent has a deterministic fallback so the flow never dead-ends."""
import json
import logging
import os
import re
from datetime import date, timedelta
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from wasl import config
from wasl.schemas import Candidate, Need, Practitioner, ProjectCard, SolveResult, TrackedField
from wasl.solver import _avail, _loc

log = logging.getLogger("wasl.agents")

SECTORS = {"film": "إنتاج أفلام", "fashion": "أزياء", "heritage": "تراث ومعارض"}
PHASES_AR = {"pre_production": "ما قبل الإنتاج", "production": "الإنتاج", "post_production": "ما بعد الإنتاج",
             "distribution": "التوزيع", "design": "التصميم", "show": "العرض", "marketing": "التسويق",
             "research": "البحث", "build": "التنفيذ", "operation": "التشغيل"}
CORE = ["sector", "budget", "city", "deadline"]
ASK_ORDER = ["sector", "budget", "city", "deadline", "start_date"]
MAX_TURNS = 5
UNSURE = ("ما أدري", "ما ادري", "مدري", "ماادري", "لا أعرف", "لا اعرف", "ما أعرف", "ما اعرف", "مو متأكد",
          "غير متأكد", "مو عارف", "أي شي", "اي شي", "على راحتك", "انت اختار", "أنت اختار")
CITIES = ["الرياض", "جدة", "الأحساء", "الدمام", "الخبر", "العلا", "أبها", "المدينة المنورة", "مكة", "الطائف", "تبوك"]


# ---------------------------------------------------------------- LLM client
class LLMError(RuntimeError):
    pass


def _strip_fences(txt: str) -> str:
    a, b = txt.find("{"), txt.rfind("}")
    return txt[a: b + 1] if a != -1 and b > a else txt


class LLM:
    """Thin OpenAI-compatible client (OpenAI / OpenRouter / Gemini via LLM_BASE_URL)."""

    def __init__(self, api_key=None, base_url=None, model=None, fast_model=None):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or None
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or None
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.fast_model = fast_model or os.getenv("FAST_MODEL") or self.model
        self._client, self._json_mode = None, True
        # Gemini 2.5 Flash "thinks" by default (dynamic budget): 5-20s of hidden reasoning per call, which is
        # pure overhead for our schema-constrained extraction/writing. "none" disables it on the OpenAI-compat
        # endpoint. Override with LLM_REASONING_EFFORT (low|medium|high), or "default" to send nothing.
        self._effort_env = os.getenv("LLM_REASONING_EFFORT")
        self._effort_ok = True  # flips off if the provider rejects the parameter

    def effort_for(self, model: str) -> str | None:
        if not self._effort_ok:
            return None
        eff = self._effort_env if self._effort_env is not None else ("none" if "gemini-2.5-flash" in model else "")
        return None if eff in ("", "default") else eff

    @property
    def _effort(self) -> str | None:
        return self.effort_for(self.model)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _call(self, msgs, model):
        if self._client is None:
            if not self.api_key:
                raise LLMError("LLM_API_KEY not set")
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=45, max_retries=1)
        kw = {"response_format": {"type": "json_object"}} if self._json_mode else {}
        eff = self.effort_for(model)
        if eff:
            kw["reasoning_effort"] = eff
        try:
            r = self._client.chat.completions.create(model=model, messages=msgs, temperature=0.3, **kw)
        except Exception as e:
            if self._json_mode and "response_format" in str(e):  # provider without JSON mode
                self._json_mode = False
                return self._call(msgs, model)
            if eff and "reasoning" in str(e).lower():  # provider/model without reasoning control
                log.warning("reasoning_effort=%s rejected; retrying without it", eff)
                self._effort_ok = False
                return self._call(msgs, model)
            raise LLMError(f"{type(e).__name__}: {e}") from e
        return r.choices[0].message.content or ""

    def structured(self, system: str, user: str, schema: type[BaseModel], fast: bool = False) -> BaseModel:
        sys = (f"{system}\n\nReply with ONE JSON object only (no prose, no markdown) matching this JSON schema:\n"
               f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}")
        msgs = [{"role": "system", "content": sys}, {"role": "user", "content": user}]
        err = None
        for _ in range(2):
            txt = self._call(msgs, self.fast_model if fast else self.model)
            try:
                return schema.model_validate_json(_strip_fences(txt))
            except ValidationError as e:
                err = e
                msgs += [{"role": "assistant", "content": txt},
                         {"role": "user", "content": f"Invalid: {e.errors()[:3]}. Return the corrected JSON only."}]
        raise LLMError(f"schema validation failed: {err}")


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- 1. Clarifier
SectorT = Literal["film", "fashion", "heritage"]


class Extracted(BaseModel):
    sector: SectorT | None = None
    secondary_sectors: list[SectorT] = []  # hybrid projects, e.g. عرض أزياء تراثي = fashion + heritage
    stage: str | None = None
    budget: int | None = Field(None, gt=0)
    city: str | None = None
    start_date: date | None = None
    deadline: date | None = None
    show_date: date | None = None  # official show / launch day, only if the user states it
    assumed: list[str] = []  # fields the user explicitly left to us ("ما أدري")


class ClarifierOut(BaseModel):
    extracted: Extracted = Extracted()
    ask_field: str | None = None
    question: str = ""
    quick_replies: list[str] = []


CLARIFIER_SYS = """You are the intake Clarifier for Wasl (وصل), a warm Saudi creative-project team builder.
From the user's latest message (with the project idea, conversation and current project card as context) extract
facts the user stated: sector, stage, budget (integer SAR; "120 ألف" -> 120000), city (Arabic name), start_date,
deadline and show_date (the official show / launch / opening day, only if explicitly stated) as ISO dates (resolve
relative dates against `today`).

SECTORS — understand the project like a seasoned producer would. Sectors: film (أفلام، وثائقي، تصوير مرئي),
fashion (أزياء، عروض أزياء، مجموعات ملابس), heritage (تراث، معارض، متاحف، أجنحة). Many projects are hybrid:
- "عرض أزياء تراثي" / "مجموعة أزياء مستوحاة من السدو" -> sector=fashion, secondary_sectors=[heritage]
- "فيلم وثائقي عن الحرف التراثية" -> sector=film, secondary_sectors=[heritage]
- "معرض لأزياء المناطق" -> sector=heritage, secondary_sectors=[fashion]
- "تغطية سينمائية لعرض أزياء" -> sector=fashion, secondary_sectors=[film]
`sector` is the primary deliverable (what is actually produced: a show -> fashion, a film -> film, an exhibition/
pavilion -> heritage); every other domain the description clearly implies goes in `secondary_sectors`. When the
idea already implies a sector (even indirectly), set it — NEVER ask the user to choose a sector, and never make
them pick one of two sectors their description already combines.

Never invent values for budget, city or dates: leave them null if not stated. If the user says they don't know
about a field, list it in `assumed`.

Then write exactly ONE short, specific question in warm, natural Saudi Arabic (e.g. "حلو! ..." / "تمام، ...")
for `ask_field` (the field given to you) — only genuinely missing practical constraints (city, budget, timeline,
scale) are worth asking. Acknowledge the hybrid nature in a few words when relevant (e.g. "فكرة حلوة تجمع
الأزياء والتراث!"), then ask about that single field only; never ask two separate things. Give 2-4 short Arabic
quick_replies that answer the field directly (include "ما أدري" when sensible). No English, no lists, no repeated
greetings."""


def is_unsure(text: str) -> bool:
    t = text.strip()
    return any(u in t for u in UNSURE)


def _norm_digits(s: str) -> str:
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("٬", ",")


def heuristic_extract(text: str) -> Extracted:
    """Keyword/regex extraction: LLM-free fallback and quick-reply parser."""
    t = _norm_digits(text)
    out = Extracted()
    kw = {"film": ("فيلم", "وثائقي", "سينما", "تصوير", "إنتاج مرئي"),
          "fashion": ("أزياء", "ازياء", "موضة", "مجموعة ملابس"),
          "heritage": ("معرض", "تراث", "متحف", "جناح")}
    hits = [sec for sec, words in kw.items() if any(w in t for w in words)]
    if hits:
        # the produced artefact is primary (a show is fashion even when "تراثي"); the rest are secondary
        primary = next(s for s in ("fashion", "film", "heritage") if s in hits)
        out.sector, out.secondary_sectors = primary, [s for s in hits if s != primary]
    out.city = next((c for c in CITIES if c in t), None)
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", t)
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(ألف|الف|k|K)?\s*(ريال|SAR)?", re.sub(r"\d{4}-\d{2}-\d{2}", "", t)):
        v = float(m.group(1).replace(",", ""))
        if m.group(2) or m.group(3) or v >= 1000:
            out.budget = int(v * 1000 if m.group(2) else v)
            break
    if dates:
        ds = [date.fromisoformat(d) for d in dates]
        out.deadline = max(ds)
        if len(ds) > 1:
            out.start_date = min(ds)
    return out


QUESTIONS = {
    "sector": ("حلو! عشان أفهمك صح، مشروعك أقرب لأي مجال؟", ["فيلم / إنتاج مرئي", "عرض أزياء", "معرض تراثي"]),
    "budget": ("تمام، كم الميزانية التقريبية اللي في بالك بالريال؟", ["أقل من 50 ألف", "حوالي 100 ألف", "150 ألف أو أكثر", "ما أدري"]),
    "city": ("ممتاز، وين ناوي تنفذ المشروع؟ (المدينة تفرق في اختيار الفريق)", ["الرياض", "جدة", "الأحساء", "العلا"]),
    "deadline": ("طيب، متى تبي المشروع يكون جاهز ويطلع للناس؟", ["خلال شهرين", "خلال 3 أشهر", "خلال 6 أشهر", "ما أدري"]),
    "start_date": ("ومتى تقدر تبدأ الشغل فعلياً؟", ["الشهر الجاي", "بعد شهرين", "ما أدري"]),
}


def _quick_value(field: str, text: str, card: ProjectCard, today: date):
    t = text.strip()
    start = card.start_date.value or today + timedelta(30)
    table = {
        "sector": {"فيلم / إنتاج مرئي": "film", "عرض أزياء": "fashion", "معرض تراثي": "heritage"},
        "budget": {"أقل من 50 ألف": 40000, "حوالي 100 ألف": 100000, "150 ألف أو أكثر": 150000},
        "deadline": {"خلال شهرين": start + timedelta(60), "خلال 3 أشهر": start + timedelta(90),
                     "خلال 6 أشهر": start + timedelta(180)},
        "start_date": {"الشهر الجاي": today + timedelta(30), "بعد شهرين": today + timedelta(60)},
    }
    if field == "city" and t in CITIES:
        return t
    return table.get(field, {}).get(t)


def default_for(field: str, card: ProjectCard, idea: str, today: date):
    start = card.start_date.value or today + timedelta(30)
    if field == "sector":
        return heuristic_extract(idea).sector or "film"
    if field == "budget":
        return 100000
    if field == "city":
        return heuristic_extract(idea).city or "الرياض"
    if field == "deadline":
        return start + timedelta(90)
    if field == "start_date":
        dl = card.deadline.value
        return max(today + timedelta(7), dl - timedelta(60)) if dl and dl - start < timedelta(21) else start
    if field == "stage":
        return "planning"


def _set(card: ProjectCard, field: str, value, status: str):
    setattr(card, field, type(getattr(card, field))(value=value, status=status))


def _merge(card: ProjectCard, ex: Extracted):
    for f in ["sector", "stage", "budget", "city", "start_date", "deadline", "show_date"]:
        v = getattr(ex, f)
        if v is not None:
            _set(card, f, v, "assumed" if f in ex.assumed else "known")
    if ex.secondary_sectors:
        card.secondary_sectors = sorted(set(card.secondary_sectors) | set(ex.secondary_sectors))
    card.secondary_sectors = [s for s in card.secondary_sectors if s != card.sector.value]


# ---------------------------------------------------------------- 1b. final intake step: work style / vibe
STYLE_FIELD = "style"
STYLE_QUESTION = ("سؤال أخير 🎨 كيف تبي طابع العمل حقك؟ مثلاً: تراثي أصيل، عصري بلمسة تراثية، فخم، أو شبابي — "
                  "اختر من الأزرار أو اكتب الطابع اللي في بالك.")
NO_STYLE, SUGGEST_STYLE = "ما فيه طابع معين", "اقترح لي طابع مناسب"
STYLE_REPLIES = ["تراثي أصيل", "عصري بلمسة تراثية", "فخم", "شبابي", NO_STYLE, "ما أدري", SUGGEST_STYLE]
NO_STYLE_VALUE = "بدون طابع محدد"


class StyleOut(BaseModel):
    style: str = Field(min_length=2, max_length=80)  # short Arabic label, e.g. "عصري بلمسة تراثية"
    rationale: str = ""                              # 1-2 Arabic sentences tailored to the project


STYLE_SYS = """You are the creative director of Wasl (وصل). The entrepreneur asked you to propose a work style /
creative direction for their Saudi cultural project. From the idea, sector(s), city and budget, propose ONE tailored
style: `style` is a short Arabic label (2-6 words, e.g. "عصري بلمسة تراثية", "وثائقي سينمائي هادئ"), `rationale` is
1-2 warm Saudi-Arabic sentences explaining the direction concretely (palette, materials, mood, references to the
project itself). Never invent people or facts."""

_STYLE_FALLBACK = {
    "film": ("وثائقي سينمائي هادئ بإضاءة طبيعية",
             "تصوير قريب من الناس بإضاءة طبيعية وإيقاع مونتاج هادئ، بألوان ترابية دافئة تخلي القصة هي البطل."),
    "fashion": ("عصري بلمسة تراثية",
                "قصّات معاصرة نظيفة مع نقوش وخامات مستوحاة من التراث السعودي (كالسدو والتطريز اليدوي)، ومنصة بإضاءة دافئة تبرز الألوان."),
    "heritage": ("تراثي أصيل بعرض متحفي حديث",
                 "خامات محلية كالحجر والخشب والطين بألوان صحراوية، مع لوحات ثنائية اللغة وإضاءة متحفية مركّزة على القطع."),
}


def suggest_style(llm, st) -> StyleOut:
    c = st.card
    try:
        out = llm.structured(STYLE_SYS, _j({"project_idea": st.idea, "sector": c.sector.value,
                                            "secondary_sectors": c.secondary_sectors, "city": c.city.value,
                                            "budget": c.budget.value}), StyleOut, fast=True)
        if out.style.strip():
            return out
        raise LLMError("empty style")
    except Exception as e:  # any provider/stub failure -> grounded per-sector proposal
        log.warning("style suggestion LLM failed, using sector default: %s", e)
    style, why = _STYLE_FALLBACK.get(c.sector.value or "", _STYLE_FALLBACK["heritage"])
    if "heritage" in c.secondary_sectors and "تراث" not in style:
        style += " بروح تراثية"
    return StyleOut(style=style, rationale=why)


def _style_turn(llm, st, message: str):
    t, card = message.strip(), st.card
    if t == NO_STYLE or "ما فيه طابع" in t or "بدون طابع" in t:
        _set(card, "style", NO_STYLE_VALUE, "known")
        st.style_rationale = ""
    elif t == SUGGEST_STYLE or "اقترح" in t or is_unsure(t):
        sug = suggest_style(llm, st)
        _set(card, "style", sug.style.strip(), "assumed")
        lead = "اقترحت لك طابع" if not is_unsure(t) else "ولا يهمك! اقترحت لك طابع"
        st.style_rationale = f"{lead} «{sug.style.strip()}» 🎨 {sug.rationale.strip()}".strip()
    else:
        _set(card, "style", t[:120], "known")
        st.style_rationale = ""
    if card.style.value != NO_STYLE_VALUE:
        st.style_notes = card.style.value  # feeds Requirements / Explainer / Advisor prompts
    if st.style_rationale:
        st.history.append({"role": "assistant", "text": st.style_rationale})


def _ask_style(st) -> bool:
    st.pending_field, st.question, st.quick_replies = STYLE_FIELD, STYLE_QUESTION, list(STYLE_REPLIES)
    st.history.append({"role": "assistant", "text": STYLE_QUESTION})
    return False


def clarify(llm, st, message: str, today: date) -> bool:
    """One Clarifier turn. Mutates st (card, pending_field, question, quick_replies). Returns True when intake is done.
    The last step (after the practical constraints) always asks for the desired work style unless it is known."""
    st.turns += 1
    st.history.append({"role": "user", "text": message})
    card, f, out = st.card, st.pending_field, None
    if f == STYLE_FIELD:
        _style_turn(llm, st, message)
        st.pending_field, st.question, st.quick_replies = None, None, []
        return True
    quick = _quick_value(f, message, card, today) if f else None
    if f and quick is not None:
        _set(card, f, quick, "known")
    elif f and is_unsure(message):
        _set(card, f, default_for(f, card, st.idea, today), "assumed")
    else:
        nxt = f or next((x for x in ASK_ORDER if getattr(card, x).status == "missing"), None)
        try:
            out = llm.structured(CLARIFIER_SYS, _j({
                "today": today, "project_idea": st.idea, "style_notes": st.style_notes, "history": st.history[-6:],
                "current_card": card.model_dump(mode="json", exclude={"needs"}), "latest_message": message,
                "ask_field": nxt}), ClarifierOut, fast=True)
            ex = out.extracted
        except LLMError as e:
            log.warning("clarifier LLM failed, using heuristics: %s", e)
            ex = heuristic_extract(message)
        if ex.sector is None or not ex.secondary_sectors:  # keyword backstop: never ask for a sector we can see
            h = heuristic_extract(message)
            if ex.sector is None and card.sector.status == "missing":
                ex.sector = h.sector
            ex.secondary_sectors = list(ex.secondary_sectors) or [s for s in h.secondary_sectors if s != ex.sector]
        _merge(card, ex)
        for a in ex.assumed:
            if a in ASK_ORDER and getattr(card, a).status == "missing":
                _set(card, a, default_for(a, card, st.idea, today), "assumed")
    if card.deadline.value and card.start_date.value and card.deadline.value <= card.start_date.value:
        _set(card, "deadline", card.start_date.value + timedelta(90), "assumed")

    missing = [x for x in ASK_ORDER if getattr(card, x).status == "missing"]
    if not any(x in CORE for x in missing) or st.turns >= MAX_TURNS:
        for x in missing + (["stage"] if card.stage.status == "missing" else []):
            _set(card, x, default_for(x, card, st.idea, today), "assumed")
        if card.show_date.value is None or (card.start_date.value and card.show_date.value < card.start_date.value):
            _set(card, "show_date", card.deadline.value, "assumed")  # launch on delivery unless told otherwise
        st.pending_field, st.question, st.quick_replies = None, None, []
        if card.style.status == "missing":
            return _ask_style(st)
        return True
    nxt = missing[0]
    q, opts = QUESTIONS[nxt]
    if out and out.ask_field == nxt and out.question.strip():
        q = out.question.strip()
        if 2 <= len(out.quick_replies) <= 4:
            opts = out.quick_replies
    st.pending_field, st.question, st.quick_replies = nxt, q, opts
    st.history.append({"role": "assistant", "text": q})
    return False


# ---------------------------------------------------------------- 2. Requirements
class NeedDraft(BaseModel):
    role: str
    reason: str
    consequence_if_ignored: str = ""
    importance: float = Field(0.7, ge=0, le=1)
    confidence: float = Field(0.7, ge=0, le=1)
    phase: str
    start: date | None = None
    end: date | None = None
    remote_ok: bool = False
    mentioned: bool = True
    sector: str | None = None  # set only for a role taken from a secondary_playbooks entry


class RequirementsOut(BaseModel):
    needs: list[NeedDraft]


REQUIREMENTS_SYS = """You are the Requirements agent for Wasl. Given a project card, the user's idea and a sector
playbook, list the 3-6 practitioner roles this project needs. `role` MUST be copied EXACTLY from the playbook's
typical_roles[].role (never invent or rename a role, e.g. no translator if it isn't listed; we only staff listed
roles). Include roles the user mentioned (mentioned=true) AND important listed roles they forgot (mentioned=false,
with a concrete consequence_if_ignored, using commonly_forgotten_needs when relevant). Extra advice that is not a
listed role (translation, permits, insurance...) belongs in `reason`/`consequence_if_ignored` text only.
Write reason and consequence in plain Arabic. `phase` must be one of the playbook phases. start/end must lie inside
[start_date, deadline] and follow the phase order. remote_ok=true only for work that can be done remotely
(editing, design, research), never for on-site work. importance/confidence in [0,1].
Hybrid projects: if `secondary_playbooks` is non-empty, the project also draws on those sectors (e.g. a fashion
show rooted in heritage). You MAY add at most 2 roles copied EXACTLY from a secondary playbook's typical_roles
when the main playbook doesn't already cover that expertise; set `sector` to that playbook's sector for them and
use a main-playbook phase. Leave `sector` null for main-playbook roles."""


def _canon_role(role: str, typical: list[str]) -> str | None:
    """Map a drafted role onto a playbook typical role (exact, or its first two words appear in the draft)."""
    r = role.strip()
    if r in typical:
        return r
    words = set(r.split())
    for t in typical:
        if set(t.split()[:2]) <= words:
            return t
    return None


def load_playbook(sector: str) -> dict:
    p = config.PLAYBOOK_DIR / f"{sector}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {"phases": [], "typical_roles": []}


def _phase_windows(phases: list[str], start: date, end: date) -> dict[str, tuple[date, date]]:
    n = max(len(phases), 1)
    span = max((end - start).days, n)
    out = {}
    for i, ph in enumerate(phases):
        a = start + timedelta(span * i // n)
        b = start + timedelta(span * (i + 1) // n - (0 if i == n - 1 else 1))
        out[ph] = (a, max(a, b))
    return out


def _fallback_needs(card: ProjectCard, idea: str, pb: dict) -> list[NeedDraft]:
    forgotten = {x["role"]: x["why"] for x in pb.get("commonly_forgotten_needs", [])}
    out = []
    for r in pb.get("typical_roles", []):
        if r["importance"] < 0.6:
            continue
        said = any(w in idea for w in r["role"].split() if len(w) > 2)
        out.append(NeedDraft(role=r["role"], phase=r["phase"], importance=r["importance"], confidence=0.6,
                             reason=f"دور أساسي في مشاريع {SECTORS.get(card.sector.value, '')}",
                             consequence_if_ignored=forgotten.get(r["role"], ""), mentioned=said,
                             remote_ok=r["phase"] in ("post_production", "design", "research")))
    return out


def requirements(llm, st) -> list[Need]:
    card, sector = st.card, st.card.sector.value
    pb = load_playbook(sector)
    sec_pbs = {s: load_playbook(s) for s in card.secondary_sectors if s != sector}
    start, end = card.start_date.value, card.deadline.value
    try:
        drafts = llm.structured(REQUIREMENTS_SYS, _j({
            "project_idea": st.idea, "style_notes": st.style_notes,
            "card": card.model_dump(mode="json", exclude={"needs"}), "playbook": pb,
            "secondary_playbooks": [{"sector": s, "typical_roles": p.get("typical_roles", [])}
                                    for s, p in sec_pbs.items()]}), RequirementsOut).needs
        if not drafts:
            raise LLMError("no needs")
    except LLMError as e:
        log.warning("requirements LLM failed, using playbook: %s", e)
        drafts = _fallback_needs(card, st.idea, pb)
    typical = [r["role"] for r in pb.get("typical_roles", [])]
    order = pb.get("phases") or []
    if typical:
        kept, seen, extra = [], set(), 0
        for d in drafts:
            ds = d.sector if d.sector in sec_pbs else None
            c = _canon_role(d.role, [r["role"] for r in sec_pbs[ds].get("typical_roles", [])] if ds else typical)
            if c is None and ds:  # mislabelled sector: try the main playbook
                ds, c = None, _canon_role(d.role, typical)
            if c is None:
                st.events.append(f"اقتراح إضافي (خارج أدوار الدليل): {d.role}")
            elif c not in seen and not (ds and extra >= 2):
                seen.add(c)
                extra += bool(ds)
                upd = {"role": c, "sector": ds}
                if ds and d.phase not in order:
                    upd["phase"] = order[0] if order else d.phase
                kept.append(d.model_copy(update=upd))
        drafts = kept or _fallback_needs(card, st.idea, pb)
    drafts = drafts[:6]
    used = sorted({d.phase for d in drafts}, key=lambda p: order.index(p) if p in order else 99)
    wins = _phase_windows(used, start, end)
    forgotten = {x["role"]: x["why"] for x in pb.get("commonly_forgotten_needs", [])}
    needs = []
    for i, d in enumerate(drafts):
        a, b = max(d.start or start, start), min(d.end or end, end)
        if not (d.start and d.end) or a > b:
            a, b = wins[d.phase]
        cons = d.consequence_if_ignored or forgotten.get(d.role, "")
        if not d.mentioned and not cons:
            cons = "قد يتأثر المشروع جودةً أو جدولاً"
        needs.append(Need(id=f"n{i + 1}", role=d.role, sector=d.sector or sector, reason=d.reason,
                          consequence_if_ignored=cons,
                          importance=d.importance, confidence=d.confidence, phase=d.phase, phase_window=(a, b),
                          remote_ok=d.remote_ok, mentioned=d.mentioned))
    return needs


# ---------------------------------------------------------------- 3. Coordinator
class ConcessionOption(BaseModel):
    id: str
    kind: Literal["extra_budget_sar", "shift_days", "allow_remote_needs"]
    value: int | list[str]
    label: str
    detail: str = ""


def _role(needs: dict[str, Need], nid: str) -> str:
    return needs[nid].role if nid in needs else nid


def explain_blocking(res: SolveResult, needs: dict[str, Need], city: str | None) -> list[str]:
    out = []
    for b in res.blocking_constraints:
        nid = b.split(":")[0]
        if "pinned practitioner" in b:
            out.append(f"العضو المقترح لدور «{_role(needs, nid)}» ما يمكن تثبيته (مثبّت على أكثر من دور أو غير متاح كمرشح).")
        elif "no candidates retrieved" in b:
            out.append(f"ما لقينا أي مرشح مناسب لدور «{_role(needs, nid)}».")
        elif "no candidate available" in b:
            out.append(f"ما فيه مرشح متاح لدور «{_role(needs, nid)}» في الفترة المطلوبة.")
        elif "located in" in b:
            out.append(f"المرشحين المتاحين لدور «{_role(needs, nid)}» خارج {city or 'المدينة'} والعمل عن بُعد غير مسموح.")
        elif b.startswith("budget"):
            m = re.search(r"(\d+) > (\d+)", b)
            out.append(f"أرخص فريق ممكن يكلف {int(m.group(1)):,} ريال والميزانية {int(m.group(2)):,} ريال." if m
                       else "الميزانية ما تكفي لأي فريق مكتمل.")
        elif "double-booking" in b:
            out.append("نفس الشخص هو الخيار الوحيد لأكثر من دور، والشخص الواحد ما يأخذ إلا دور واحد.")
        else:
            out.append(b)
    return out


def concession_options(res: SolveResult, needs: dict[str, Need]) -> list[ConcessionOption]:
    out = []
    for i, c in enumerate(res.min_concessions):
        if c.kind == "extra_budget_sar":
            label = f"زيادة الميزانية {c.value:,} ريال"
        elif c.kind == "shift_days":
            label = f"تأجيل الجدول {c.value} يوم"
        else:
            label = "السماح بالعمل عن بُعد لدور: " + "، ".join(_role(needs, n) for n in c.value)
        out.append(ConcessionOption(id=f"c{i + 1}", kind=c.kind, value=c.value, label=label, detail=c.detail))
    return out


# ---------------------------------------------------------------- 4. Explainer
class ExplainOut(BaseModel):
    explanations: dict[str, str]  # need_id -> Arabic justification
    brief_intro: str = ""


EXPLAINER_SYS = """You are the Explainer for Wasl. For each member write 1-2 concise sentences in plain Arabic
explaining why they fit their role. Use ONLY the facts given: their past_works (quote work titles exactly inside
«»), is_rising_talent, collaborators_in_team and score_breakdown. Never mention any person or work not present in
the facts. Key `explanations` by need_id. If a member has `out_of_scope` (not null), end their explanation with one
short, friendly sentence saying their fee includes a small extra (the given surcharge) because the work is outside
their usual scope, e.g. "وأُضيفت إضافة بسيطة على الأتعاب لكونه خارج نطاق عمله المعتاد". If `need_brief_intro` is
true, also write `brief_intro`: 2-3 sentences in Arabic summarising the project for a message to the team (no names)."""

OOS_MARK = "خارج نطاق عمله المعتاد"


def member_facts(nid: str, need: Need, p: Practitioner, c: Candidate | None, team_ids: set[str],
                 prs: dict[str, Practitioner], oos=None) -> dict:
    return {"need_id": nid, "role": need.role, "name": p.name, "city": p.city,
            "past_works": [w.model_dump(include={"title", "year", "role", "description"}) for w in p.past_works],
            "is_rising_talent": p.is_rising_talent,
            "collaborators_in_team": [prs[x].name for x in sorted(p.collaborators & team_ids) if x in prs],
            "score_breakdown": c.score_breakdown.model_dump() if c else None,
            "out_of_scope": {"surcharge_sar": oos.surcharge, "reason": oos.reason, "note": oos.note_ar} if oos else None}


def _with_oos_note(text: str, f: dict) -> str:
    o = f.get("out_of_scope")
    if not o or OOS_MARK in text:
        return text
    return f"{text.rstrip()} {o['note']}"


def template_explanation(f: dict) -> str:
    w = f["past_works"][0] if f["past_works"] else None
    s = f"{f['name']} ({f['city']}) مناسب لدور {f['role']}"
    if w:
        s += f"، ومن أعماله «{w['title']}» ({w['year']}) بدور {w['role']}"
    if f["is_rising_talent"]:
        s += "، وهو من المواهب الصاعدة"
    if f["collaborators_in_team"]:
        s += f"، وسبق له العمل مع {' و'.join(f['collaborators_in_team'])}"
    sb = f["score_breakdown"]
    if sb:
        s += f". التوافق مع التخصص {sb['specialty']:.0%} والتوفر {sb['availability']:.0%}"
    return _with_oos_note(s + ".", f)


def explain(llm, members: list[dict], project: dict, need_intro: bool) -> ExplainOut:
    try:
        out = llm.structured(EXPLAINER_SYS, _j({"project": project, "members": members,
                                                "need_brief_intro": need_intro}), ExplainOut)
    except LLMError as e:
        log.warning("explainer LLM failed, using templates: %s", e)
        out = ExplainOut(explanations={})
    for f in members:
        if not out.explanations.get(f["need_id"], "").strip():
            out.explanations[f["need_id"]] = template_explanation(f)
        else:
            out.explanations[f["need_id"]] = _with_oos_note(out.explanations[f["need_id"]], f)
    return out


# ---------------------------------------------------------------- 5. Advisor (post-build consultation)
class AdvisorOut(BaseModel):
    answer: str
    quick_replies: list[str] = []


ADVISOR_SYS = """You are the Wasl (وصل) project Advisor: a seasoned Saudi cultural-production consultant who stays with
the user after their team is built. You receive the full project context — card, selected team (roles, members,
fees, any out-of-scope surcharge, backups, why each was chosen), budget breakdown, phased timeline, the sector
playbook (phases, permits, commonly forgotten needs) and, if no team fits yet, the blocking reasons and
concessions — plus the recent consultation history and the user's new message.
Answer in warm, natural, concise Saudi Arabic (switch to English only if the user writes in English), 2-6 short
sentences or a few compact bullet lines. Be concrete and grounded: use ONLY members, numbers, dates and permits
present in the context; never invent people, works or prices. You can explain the workflow and hand-offs between
members, suggest how to sequence phases, flag risks, advise on contracts/permits, and propose adjustments — for
changes to budget, schedule, remote work, swapping or pinning a member, tell the user exactly which control to use
(شريط «ماذا لو؟» للميزانية/الجدول/العمل عن بُعد، زر «محاكاة رفض العضو» للتبديل بالبديل، «اقترح عضواً» للتثبيت).
Give 0-3 short follow-up quick_replies the user might tap next (Arabic)."""


def _fallback_advice(ctx: dict, question: str) -> AdvisorOut:
    q = question
    lines = []
    team = ctx.get("team") or []
    b = ctx.get("budget_breakdown") or {}
    if any(w in q for w in ("ميزان", "تكلف", "سعر", "أتعاب", "budget", "cost")) and b:
        lines.append(f"تكلفة الفريق {b.get('team_cost', 0):,} ريال من ميزانية {b.get('budget', 0):,} ريال "
                     f"(المتبقي {b.get('remaining', 0):,} ريال).")
        lines += [f"- {m['role']}: {m['member']} ~{m['cost']:,} ريال" + (" (تشمل إضافة بسيطة لكونه خارج نطاق عمله المعتاد)"
                                                                          if m.get("out_of_scope") else "") for m in team]
    elif any(w in q for w in ("تصريح", "تصاريح", "رخص", "permit")):
        ps = ctx.get("playbook", {}).get("permits", [])
        lines.append("التصاريح المطلوبة عادةً: " + ("، ".join(ps) if ps else "لا توجد تصاريح مسجلة لهذا القطاع."))
    elif ctx.get("timeline"):
        lines.append("تسلسل العمل المقترح:")
        lines += [f"- {t['phase_ar']} ({t['start']} ← {t['end']}): " + "، ".join(
            f"{r} ({m})" for r, m in zip(t["roles"], t["members"])) for t in ctx["timeline"]]
    else:
        lines += ctx.get("blocking") or ["ما فيه فريق مكتمل بعد."]
    lines.append("تقدر تعدّل الميزانية أو الجدول من شريط «ماذا لو؟»، أو تبدّل أي عضو بالبديل.")
    return AdvisorOut(answer="\n".join(lines), quick_replies=["كيف أوزع الميزانية؟", "وش تسلسل العمل بين الفريق؟", "وش التصاريح المطلوبة؟"])


def consult(llm, ctx: dict, history: list[dict], message: str) -> AdvisorOut:
    try:
        out = llm.structured(ADVISOR_SYS, _j({"project": ctx, "history": history[-8:], "message": message}),
                             AdvisorOut, fast=True)
        if not out.answer.strip():
            raise LLMError("empty advice")
        out.quick_replies = [q for q in out.quick_replies if q.strip()][:3]
        return out
    except LLMError as e:
        log.warning("advisor LLM failed, using grounded summary: %s", e)
        return _fallback_advice(ctx, message)


# ---------------------------------------------------------------- Final Check (deterministic)
QUOTED = re.compile(r"«([^»]+)»")


def check_team(res: SolveResult, needs: list[Need], budget: int | None, city: str | None,
               cands: dict[str, list[Candidate]], prs: dict[str, Practitioner],
               pinned: set[str] = frozenset()) -> list[str]:
    """pinned: need ids whose primary was chosen by the user (availability/location not enforced for them)."""
    issues = []
    t = res.team
    if not res.feasible or t is None:
        return ["no feasible team"]
    cost = {(c.need_id, c.practitioner_id): c.estimated_cost for cs in cands.values() for c in cs}
    for n in needs:
        pid = t.assignments.get(n.id)
        if pid is None:
            issues.append(f"{n.id}: unassigned")
            continue
        for kind, x in (("assigned", pid), ("backup", t.backups.get(n.id))):
            if x is None:
                continue
            if x not in prs:
                issues.append(f"{n.id}: {kind} {x} not in DB")
                continue
            if kind == "assigned" and n.id in pinned:
                continue
            if not _avail(prs[x], n.phase_window):
                issues.append(f"{n.id}: {kind} {x} unavailable")
            in_scope = _loc(prs[x], n, city)
            flagged = kind == "assigned" and n.id in t.out_of_scope
            if not in_scope and not flagged:
                issues.append(f"{n.id}: {kind} {x} location mismatch")
            elif flagged and (in_scope or t.out_of_scope[n.id].surcharge <= 0):
                issues.append(f"{n.id}: out-of-scope flag inconsistent")
        if t.backups.get(n.id) == pid:
            issues.append(f"{n.id}: backup equals primary")
    if len(set(t.assignments.values())) < len(t.assignments):
        issues.append("same practitioner assigned to more than one role")
    total = sum(t.cost_of(n, cost.get((n, p), 0)) for n, p in t.assignments.items())
    if total != t.total_cost:
        issues.append(f"total_cost {t.total_cost} != sum {total}")
    if budget is not None and t.total_cost > budget:
        issues.append(f"total_cost {t.total_cost} > budget {budget}")
    return issues


def check_texts(texts: dict[str, str], team: dict[str, str], prs: dict[str, Practitioner],
                backups: dict[str, str] | None = None) -> list[str]:
    """Names: only team members (and their real DB collaborators) may appear. «Titles»: must be real names/works."""
    issues = []
    team_ids = set(team.values()) | set((backups or {}).values())
    for nid, txt in texts.items():
        pid = team.get(nid)
        allowed = team_ids | (prs[pid].collaborators if pid in prs else set())
        for p in prs.values():
            if p.id not in allowed and p.name in txt:
                issues.append(f"{nid}: mentions non-team practitioner {p.name}")
        known = {w.title for x in allowed if x in prs for w in prs[x].past_works} | {prs[x].name for x in allowed if x in prs}
        for q in QUOTED.findall(txt):
            if q.strip() not in known:
                issues.append(f"{nid}: unknown quoted title «{q}»")
    return issues
