import os
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
REPLAYS_DIR = API_ROOT / "replays"
DATA_DIR = REPO_ROOT / "data"


def runs_dir() -> Path:
    return Path(os.environ.get("CANARY_RUNS_DIR", REPO_ROOT / "runs"))
