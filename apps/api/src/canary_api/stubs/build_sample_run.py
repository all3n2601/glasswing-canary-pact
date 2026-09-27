from canary_api.paths import REPLAYS_DIR
from canary_api.stubs.run import sample_run


def main() -> None:
    REPLAYS_DIR.mkdir(parents=True, exist_ok=True)
    target = REPLAYS_DIR / "sample_run.json"
    log = sample_run()
    target.write_text(log.model_dump_json(indent=2) + "\n")
    print(f"wrote {len(log.root)} events to {target}")


if __name__ == "__main__":
    main()
