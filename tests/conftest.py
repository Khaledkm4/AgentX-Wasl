import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wasl.config  # noqa: E402,F401  pins caches/temp to D: before torch/HF load
