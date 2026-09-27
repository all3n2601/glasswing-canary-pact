"""Entry point for the ablation evals: `uv run python -m canary_api.eval_cli --mode mock|replay|live`."""

from agent_orchestration import evals

from canary_api import engine_port, runtime
from canary_api.stubs.twin import sample_brief


def main(argv: list[str] | None = None) -> int:
    return evals.main(argv, engine=engine_port, twin=runtime.twin(), brief=sample_brief(), settings=runtime.settings(),
                      engine_impl=engine_port.engine_impl(), twin_impl=engine_port.twin_impl(),
                      llm_factory=runtime.build_llm)


if __name__ == "__main__":
    raise SystemExit(main())
