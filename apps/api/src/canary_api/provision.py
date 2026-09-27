"""Load a validated company fixture and create its organization-bound login."""

import argparse
import secrets
from pathlib import Path

from contracts_py.api import SignupRequest, UserRole

from canary_api import engine_port, storage
from canary_api.auth import UserStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--twin", type=Path, required=True)
    parser.add_argument("--snippets", type=Path)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=[r.value for r in UserRole], default="viewer")
    args = parser.parse_args()
    password = secrets.token_urlsafe(24)
    signup = SignupRequest(email=args.email, password=password, display_name=args.display_name)
    twin = engine_port.load_twin(args.twin, args.snippets)
    errors = [issue for issue in engine_port.validate_twin(twin) if issue.severity == "error"]
    if errors:
        parser.error(f"Invalid twin: {errors[0].message}")
    backend = storage.current()
    try:
        if storage.database_url() and not isinstance(backend, storage.PostgresStorage):
            parser.error("Configured database is unavailable; refusing to provision into fallback files")
        users = UserStore(backend)
        if users.exists(signup.email):
            parser.error("Email already exists; choose a new login")
        if twin.organization.id in backend.organization_ids():
            parser.error("Organization already exists; refusing to replace its active data")
        backend.save_twin(twin)
        user = users.create(signup, role=UserRole(args.role), organization_id=twin.organization.id)
        if users.authenticate(signup.email, password) != user:
            raise RuntimeError("Login verification failed")
        print(f"Organization: {twin.organization.display_name} ({twin.organization.id})")
        print(f"Departments: {len(twin.department_profiles)}; entities: {len(twin.entities)}; "
              f"dependencies: {len(twin.edges)}; documents: {len(twin.documents)}; evidence: {len(twin.evidence)}")
        print(f"Email: {user.email}\nPassword: {password}\nRole: {user.role.value}")
    finally:
        storage.close()


if __name__ == "__main__":
    main()
