import json
from pathlib import Path

from flash_trips.composition import create_app


def main() -> None:
    target = Path("contracts/openapi/openapi.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
