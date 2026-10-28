"""Operator commands: `python -m app.cli seed` and `python -m app.cli grant-role EMAIL ROLE`."""
import sys

from sqlalchemy import select

from . import audit
from .db import SessionLocal
from .models import User, UserRole
from .permissions import Role
from .seed import seed


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    with SessionLocal() as db:
        if argv[0] == "seed":
            seed(db)
            print("Seeded jurisdictions, plans and feature flags.")
            return 0
        if argv[0] == "grant-role" and len(argv) == 3:
            email, role = argv[1].lower(), argv[2]
            if role not in Role._value2member_map_:
                print(f"Unknown role {role}. Choose from: {', '.join(Role)}")
                return 2
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                print(f"No user with email {email}; register first.")
                return 1
            if role not in user.role_names:
                user.roles.append(UserRole(role=role))
                audit.record(db, "cli.role_granted", actor_id=None, target_type="user", target_id=user.id,
                             details={"role": role})
                db.commit()
            print(f"{email} now has roles: {', '.join(sorted(user.role_names))}")
            return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
