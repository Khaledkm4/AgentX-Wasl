"""FastAPI backend + static UI at /. Run: .cache/venv/Scripts/python -m uvicorn wasl.api:app --app-dir src --port 8000"""
import wasl.config  # noqa: F401  pins caches/temp to D: before torch/HF load

import logging
import os
import time
from datetime import date
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wasl.agents import LLM
from wasl.orchestrator import FlowError, Orchestrator, Pin, SessionState
from wasl.schemas import Need

log = logging.getLogger("wasl.api")
SESSIONS: dict[str, SessionState] = {}
STATIC = Path(__file__).parent / "static"


def preload_models() -> float:
    from wasl import retrieval
    t = time.time()
    prs = retrieval.practitioners()          # loads embedder + DB + vectors
    # warm with a realistic batch (profile-length texts, full batch): a 1-pair warm-up left the first real
    # build paying ~2s of one-off kernel/allocator setup
    from wasl import db
    docs = [f"{p.name}: {db.specialty_text(p)}. {db.works_text(p)}" for p in list(prs.values())[:32]]
    retrieval.embed(["مخرج أفلام وثائقية"] * 8, query=True)
    retrieval.rerank([("مخرج أفلام وثائقية. إخراج فيلم وثائقي قصير", d) for d in docs])
    return time.time() - t


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "orch", None) is None:
        app.state.orch = Orchestrator(LLM())
    app.state.models_loaded = False
    if os.getenv("WASL_PRELOAD", "1") == "1":
        secs = preload_models()
        app.state.models_loaded = True
        log.warning("models preloaded in %.1fs", secs)
    yield


app = FastAPI(title="Wasl API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


class StartIn(BaseModel):
    idea: str = Field(min_length=3)
    style_notes: str = ""


class MessageIn(BaseModel):
    text: str = Field(min_length=1)


class BuildIn(BaseModel):
    needs: list[Need] | None = None
    drop_need_ids: list[str] = []
    pins: list[Pin] | None = None  # suggested members to build the team around (None = keep current)


class WhatIfIn(BaseModel):
    budget: int | None = Field(None, gt=0)
    deadline_shift_days: int | None = None
    allow_remote: bool | None = None
    pins: list[Pin] | None = None


class CardEditIn(BaseModel):
    start_date: date | None = None
    show_date: date | None = None   # تاريخ يوم العرض الرسمي
    deadline: date | None = None


class ConcessionIn(BaseModel):
    concession_id: str


def _orch() -> Orchestrator:
    return app.state.orch


def _get(sid: str) -> SessionState:
    st = SESSIONS.get(sid)
    if st is None:
        raise HTTPException(404, "session not found")
    return st


def _run(fn, *a, **kw) -> dict:
    try:
        st = fn(*a, **kw)
    except FlowError as e:
        raise HTTPException(409, str(e))
    return _orch().view(st)


@app.get("/api/health")
def health():
    llm = _orch().llm
    return {"status": "ok", "models_loaded": bool(getattr(app.state, "models_loaded", False)),
            "llm_configured": bool(getattr(llm, "enabled", True)), "sessions": len(SESSIONS)}


@app.get("/api/practitioners")
def practitioners():
    prs = _orch().prs
    return [{"id": p.id, "name": p.name, "type": p.type, "specialty": "، ".join(p.specialties),
             "specialties": p.specialties, "sectors": p.sectors, "city": p.city, "remote_ok": p.remote_ok,
             "typical_fee_min": p.price_min, "typical_fee_max": p.price_max,
             "is_rising_talent": p.is_rising_talent, "verified_license": p.verified_license,
             "gender": p.gender, "availability": [[str(a), str(b)] for a, b in p.availability],
             "contact": p.contact(),
             "collaborators": [{"id": c, "name": prs[c].name} for c in sorted(p.collaborators) if c in prs],
             "past_works": [w.model_dump() for w in p.past_works]}
            for p in sorted(prs.values(), key=lambda p: p.id)]


@app.post("/api/sessions")
def start(body: StartIn):
    st = _orch().start(body.idea, body.style_notes)
    SESSIONS[st.id] = st
    return _orch().view(st)


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return _orch().view(_get(sid))


@app.post("/api/sessions/{sid}/message")
def message(sid: str, body: MessageIn):
    return _run(_orch().message, _get(sid), body.text)


@app.post("/api/sessions/{sid}/card")
def edit_card(sid: str, body: CardEditIn):
    """Edit start / official show / delivery dates; schedule, team, report and critical deadlines follow."""
    return _run(_orch().update_card, _get(sid), body.start_date, body.show_date, body.deadline)


@app.post("/api/sessions/{sid}/build-team")
def build_team(sid: str, body: BuildIn | None = None):
    body = body or BuildIn()
    return _run(_orch().build_team, _get(sid), body.needs, body.drop_need_ids, body.pins)


@app.post("/api/sessions/{sid}/what-if")
def what_if(sid: str, body: WhatIfIn):
    return _run(_orch().what_if, _get(sid), body.budget, body.deadline_shift_days, body.allow_remote, body.pins)


@app.post("/api/sessions/{sid}/reject/{need_id}")
def reject(sid: str, need_id: str):
    return _run(_orch().reject, _get(sid), need_id)


@app.post("/api/sessions/{sid}/apply-concession")
def apply_concession(sid: str, body: ConcessionIn):
    return _run(_orch().apply_concession, _get(sid), body.concession_id)
