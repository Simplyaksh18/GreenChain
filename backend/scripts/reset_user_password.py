"""
Reset a user's password from the command line (administrative use only).

Usage:
    python scripts/reset_user_password.py --email user@example.com --password NewPass123

This script:
  - normalizes the email (lowercase, strip)
  - hashes the new password with the application's own hasher
  - updates only the user's password_hash
  - never logs the password or the resulting hash
  - exits non-zero if the user is not found or on any failure

It is intentionally NOT importable as a router or endpoint — this is a
manual operator tool. Never expose it over HTTP.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.database import SessionLocal
from app.models.user import User
from app.security import get_password_hash


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset a GreenChain user's password (admin CLI)."
    )
    parser.add_argument("--email", required=True, help="User email (case-insensitive)")
    parser.add_argument("--password", required=True, help="New plaintext password")
    return parser.parse_args(argv)


def reset_password(email: str, new_password: str) -> int:
    normalized = (email or "").strip().lower()
    if not normalized:
        print("ERROR: email is required", file=sys.stderr)
        return 2
    if not new_password or len(new_password) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        return 2

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == normalized).first()
        if not user:
            print(f"ERROR: no user with email {normalized}", file=sys.stderr)
            return 1

        new_hash = get_password_hash(new_password)
        # bcrypt hashes are always 60 chars; guard against a broken hasher.
        if not new_hash or len(new_hash) < 20:
            print("ERROR: generated hash is invalid", file=sys.stderr)
            return 3

        user.password_hash = new_hash
        session.commit()
        print(f"OK: password updated for {normalized} (user_id={user.id})")
        return 0
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"ERROR: {type(exc).__name__} while updating password", file=sys.stderr)
        return 4
    finally:
        session.close()


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    return reset_password(args.email, args.password)


if __name__ == "__main__":
    raise SystemExit(main())
