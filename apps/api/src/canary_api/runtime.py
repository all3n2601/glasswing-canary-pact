from functools import cache

from contracts_py.twin import OrganizationSettings, Twin

from canary_api import engine_port
from canary_api.events import EventBus
from canary_api.paths import DATA_DIR, runs_dir

bus = EventBus(runs_dir())
_twins: dict[str, Twin] = {}


def twin() -> Twin:
    impl = engine_port.engine_impl()
    if impl not in _twins:
        _twins[impl] = engine_port.load_twin(
            DATA_DIR / "novacorp.json",
            DATA_DIR / "documents.json",
            DATA_DIR / "artifacts" / "snippets.json",
        )
    return _twins[impl]


@cache
def _settings(organization_id: str) -> OrganizationSettings:
    return OrganizationSettings(organization_id=organization_id)


def settings() -> OrganizationSettings:
    return _settings(twin().organization.id)
