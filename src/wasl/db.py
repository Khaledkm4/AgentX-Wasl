import json
import sqlite3
from pathlib import Path

import numpy as np

from wasl.config import DB_PATH
from wasl.schemas import Practitioner

SCHEMA = """
CREATE TABLE IF NOT EXISTS practitioners (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 1,
    phone TEXT,
    email TEXT,
    company_name TEXT,
    company_phone TEXT,
    company_email TEXT,
    company_website TEXT,
    gender TEXT
);
CREATE TABLE IF NOT EXISTS embeddings (
    practitioner_id TEXT NOT NULL,
    field TEXT NOT NULL,          -- 'specialty' | 'works'
    model TEXT NOT NULL,
    vec BLOB NOT NULL,
    PRIMARY KEY (practitioner_id, field, model)
);
"""


CONTACT_COLS = ["phone", "email", "company_name", "company_phone", "company_email", "company_website"]
EXTRA_COLS = ["gender"]  # denormalised profile columns added after the first schema


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    have = {r[1] for r in con.execute("PRAGMA table_info(practitioners)")}
    for c in CONTACT_COLS + EXTRA_COLS:  # migrate DBs seeded before these columns existed
        if c not in have:
            con.execute(f"ALTER TABLE practitioners ADD COLUMN {c} TEXT")
    return con


def upsert_practitioners(con, items: list[Practitioner]):
    """`data` (full JSON) is the source of truth; contact columns are denormalised for direct SQL lookups."""
    extra = CONTACT_COLS + EXTRA_COLS
    cols = ", ".join(["id", "data", "is_demo", *extra])
    con.executemany(
        f"INSERT OR REPLACE INTO practitioners ({cols}) VALUES ({', '.join('?' * (3 + len(extra)))})",
        [(p.id, p.model_dump_json(), int(p.is_demo), *(getattr(p, c) for c in extra)) for p in items],
    )
    con.commit()


def load_practitioners(con, include_demo: bool = True) -> dict[str, Practitioner]:
    q = "SELECT data, gender FROM practitioners" + ("" if include_demo else " WHERE is_demo = 0")
    out = {}
    for data, gender in con.execute(q):
        p = Practitioner.model_validate_json(data)
        if p.gender is None and gender in ("male", "female"):  # rows migrated from an older JSON payload
            p.gender = gender
        out[p.id] = p
    return out


def save_embeddings(con, field: str, model: str, ids: list[str], vecs: np.ndarray):
    con.executemany(
        "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?)",
        [(i, field, model, v.astype(np.float32).tobytes()) for i, v in zip(ids, vecs)],
    )
    con.commit()


def load_embeddings(con, field: str, model: str) -> dict[str, np.ndarray]:
    rows = con.execute(
        "SELECT practitioner_id, vec FROM embeddings WHERE field = ? AND model = ?", (field, model)
    )
    return {i: np.frombuffer(b, dtype=np.float32) for i, b in rows}


def specialty_text(p: Practitioner) -> str:
    return "، ".join(p.specialties)


def works_text(p: Practitioner) -> str:
    return " | ".join(f"{w.title} ({w.role}): {w.description}" for w in p.past_works)


def dump_json(items: list[Practitioner]) -> str:
    return json.dumps([p.model_dump(mode="json") for p in items], ensure_ascii=False, indent=1)
