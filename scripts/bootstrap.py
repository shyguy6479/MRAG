"""Create local Compose secrets without printing them or replacing an existing .env."""

import os
import secrets
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parents[1] / ".env"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("# Generated local Compose credentials; do not commit.\n")
        for key in ("POSTGRES_PASSWORD", "GRAFANA_PASSWORD", "ATLAS_API_KEY"):
            stream.write(f"{key}={secrets.token_hex(24)}\n")
    print("Created .env with owner-only permissions. Keep it private.")


if __name__ == "__main__":
    main()
