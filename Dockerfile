# Wasl backend (FastAPI + local embedding/rerank models + OR-Tools solver) as one container.
# Works on Hugging Face Spaces (Docker SDK, port 7860), Render, Railway, Fly.io, or any Docker host.
# The frontend is served by this container too (at /), and can also be hosted on Vercel (see vercel.json).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=7860
WORKDIR /app

# CPU-only torch keeps the image ~1.5 GB smaller than the default CUDA build
COPY requirements.txt .
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install -r requirements.txt

COPY src ./src
COPY scripts ./scripts
COPY data/playbooks ./data/playbooks

# Bake models + seeded DB (with embeddings) into the image so the container starts offline and fast
RUN WASL_ALLOW_DOWNLOAD=1 python scripts/seed_db.py \
 && WASL_ALLOW_DOWNLOAD=1 python -c "import sys; sys.path.insert(0, 'src'); from wasl.api import preload_models; preload_models()"

# Hugging Face Spaces runs containers as uid 1000; the app writes caches/temp under /app/.cache
RUN useradd -m -u 1000 wasl && chown -R wasl /app
USER wasl

EXPOSE 7860
CMD ["sh", "-c", "uvicorn wasl.api:app --app-dir src --host 0.0.0.0 --port ${PORT}"]
