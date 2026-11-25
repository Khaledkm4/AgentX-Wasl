"""Import this module FIRST in every entrypoint: it pins all caches/temp to D: before torch/HF load."""
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache"
_PINNED = {
    "HF_HOME": CACHE / "hf",
    "HUGGINGFACE_HUB_CACHE": CACHE / "hf" / "hub",
    "SENTENCE_TRANSFORMERS_HOME": CACHE / "hf",
    "TORCH_HOME": CACHE / "torch",
    "PIP_CACHE_DIR": CACHE / "pip",
    "TMP": CACHE / "tmp",
    "TEMP": CACHE / "tmp",
}

from dotenv import load_dotenv  # noqa: E402  (pure-python, writes nothing)

load_dotenv(ROOT / ".env", override=True)
for k, default in _PINNED.items():
    p = Path(os.environ.get(k) or default)
    if not p.is_absolute():
        p = ROOT / p
    if p.drive.upper() != ROOT.drive.upper():  # refuse to write caches outside the project drive
        p = default
    p.mkdir(parents=True, exist_ok=True)
    os.environ[k] = str(p)
os.environ["TMPDIR"] = os.environ["TMP"]
tempfile.tempdir = os.environ["TMP"]

# Local HF models are cached on disk: never touch the Hub at runtime (each HEAD/etag check costs ~0.5-2s per
# file and hangs on flaky networks). Set WASL_ALLOW_DOWNLOAD=1 once to fetch a new model, then remove it.
ALLOW_DOWNLOAD = os.getenv("WASL_ALLOW_DOWNLOAD", "0") == "1"
if not ALLOW_DOWNLOAD:
    for _k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[_k] = "1"
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

EMBED_MODEL = os.getenv("WASL_EMBED_MODEL", "intfloat/multilingual-e5-small")
RERANK_MODEL = os.getenv("WASL_RERANK_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
EMBED_FALLBACK = os.getenv("WASL_EMBED_FALLBACK", "intfloat/multilingual-e5-small")
RERANK_FALLBACK = os.getenv("WASL_RERANK_FALLBACK", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
DB_PATH = ROOT / os.getenv("WASL_DB_PATH", "data/wasl.db")
PLAYBOOK_DIR = ROOT / "data" / "playbooks"
