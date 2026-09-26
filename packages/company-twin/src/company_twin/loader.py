import json
from pathlib import Path

from .models import CompanyTwin


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "synthetic_company.json"


def load_company_twin(path: str | Path | None = None) -> CompanyTwin:
    fixture_path = Path(path) if path else default_fixture_path()
    return CompanyTwin.model_validate(json.loads(fixture_path.read_text()))

