import json
import signal
import sys
import threading
from pathlib import Path
from types import FrameType

from tests.identity.local_issuer import serving_local_oidc_issuer


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: local_provider.py <status-file>")

    stopped = threading.Event()

    def stop(_signum: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    with serving_local_oidc_issuer() as issuer:
        status_path = Path(sys.argv[1])
        status_path.write_text(
            json.dumps(
                {
                    "ca_file": str(issuer.ca_file),
                    "discovery_url": issuer.discovery_endpoint,
                    "issuer": issuer.issuer,
                    "jwks_uri": issuer.jwks_uri,
                }
            )
        )
        stopped.wait()
        status_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
