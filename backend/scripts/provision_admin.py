"""CLI utility for one-time initial administrator provisioning (`Aayan`).

Reads INITIAL_ADMIN_PASSWORD exclusively from the backend environment.
Never exposes or logs the password.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import transaction
from app.services.admin_auth_service import AdminProvisioningError, provision_initial_admin


def main() -> int:
    try:
        with transaction() as db:
            result = provision_initial_admin(db)
        if result["created"]:
            print(f"Initial administrator '{result['username']}' provisioned (must_change_password=True).")
        else:
            print(
                f"Initial administrator '{result['username']}' is already provisioned. "
                "One-time provisioning is disabled."
            )
        return 0
    except AdminProvisioningError as exc:
        print(f"Provisioning error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
