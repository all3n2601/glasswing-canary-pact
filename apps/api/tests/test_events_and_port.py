import os
import subprocess
import sys

from canary_api import engine_port, runtime


def test_runtime_has_no_stub_engine_switch(client) -> None:
    assert client.get("/company").json()["organization"]["id"] == "org_northstar"


def test_real_engine_does_not_crash_at_import() -> None:
    result = subprocess.run([sys.executable, "-c", "import canary_api.app"],
                            env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_real_clone_with_edges_keeps_extraction_method() -> None:
    twin = runtime.twin()
    agent_edge = twin.edges[0].model_copy(update={"id": "e_agent_probe", "extraction_method": "agent"})
    cloned = engine_port.clone_with_edges(twin, [agent_edge])
    assert next(e for e in cloned.edges if e.id == "e_agent_probe").extraction_method == "agent"
    assert "e_agent_probe" not in {e.id for e in twin.edges}
