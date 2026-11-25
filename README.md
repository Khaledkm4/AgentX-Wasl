# Wasl (وصل) — Phases 1–6

Data layer, retrieval, CP-SAT team solver, the 4 agents, and the FastAPI backend. The frontend comes later.

```bash
powershell -File scripts/setup_d_only.ps1          # venv + pip/HF/torch caches + tmp, all in .cache/
cp .env.example .env                               # models + cache paths (enforced again in config.py)
.cache/venv/Scripts/python scripts/seed_db.py      # 32 demo profiles + embeddings -> data/wasl.db
.cache/venv/Scripts/python scripts/demo_search.py  # top candidates for the 3 sample cases
.cache/venv/Scripts/python -m pytest -q            # unit + e2e (add -m "not e2e" to skip the model tests)
.cache/venv/Scripts/python -m uvicorn wasl.api:app --app-dir src --port 8000   # API (preloads models at boot)
.cache/venv/Scripts/python scripts/smoke_live.py   # optional: one real LLM flow (needs LLM_API_KEY)
```

- `src/wasl/schemas.py`: Pydantic models. `db.py`: generic SQLite loader (`is_demo` column, so real data can be loaded the same way).
- `retrieval.py`: bge-m3 cosine search behind a `VectorStore` ABC, one batched bge-reranker pass, and a weighted score.
- `solver.py`: CP-SAT assignment, then backups, then a diagnosis of the minimum concessions when no team fits.
- `data/playbooks/*.yaml`: roles, phases, permits, and commonly forgotten needs per sector.
- `agents.py`: Clarifier, Requirements, Coordinator, Explainer and the deterministic Final Check. Every LLM output is schema-validated, and each agent falls back to heuristics, the playbook, or templates when the LLM is unavailable.
- `orchestrator.py`: an explicit state machine (`clarifying -> needs_review -> built | infeasible`) over `SessionState`.
- `api.py`: `/api/health`, `/api/sessions`, `.../message`, `.../build-team`, `.../what-if`, `.../reject/{need_id}`, `.../apply-concession`.
