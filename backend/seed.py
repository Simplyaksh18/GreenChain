"""
Seed script — creates sample users for development.
Run from backend/ directory:
    python seed.py
"""
import sys
import os
from sqlalchemy import text
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.security import hash_password

Base.metadata.create_all(bind=engine)

SEED_USERS = [
    {"name": "Alice Farmer", "email": "farmer@example.com", "role": UserRole.FARMER, "is_approved": True},
    {"name": "Bob FPO",      "email": "fpo@example.com",     "role": UserRole.FPO,     "is_approved": True},
    {"name": "Carol Verify", "email": "verifier@example.com","role": UserRole.VERIFIER, "is_approved": True},
    {"name": "Dave Admin",   "email": "admin@example.com",   "role": UserRole.ADMIN,    "is_approved": True},
]

PASSWORD = "password123"


def seed():
    db = SessionLocal()
    try:
        # Ensure the local dev schema has the custodial wallet columns that the
        # backend routes expect. This is idempotent and only patches missing
        # columns in the current database.
        with engine.begin() as conn:
            cols = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = 'fpo_profiles'"
                    )
                )
            }
            if "wallet_address" not in cols:
                conn.execute(text("ALTER TABLE fpo_profiles ADD COLUMN wallet_address VARCHAR(42)"))
                print("  [DDL]  added fpo_profiles.wallet_address")
            if "vault_identifier" not in cols:
                conn.execute(text("ALTER TABLE fpo_profiles ADD COLUMN vault_identifier VARCHAR(100)"))
                print("  [DDL]  added fpo_profiles.vault_identifier")

        for data in SEED_USERS:
            exists = db.query(User).filter(User.email == data["email"]).first()
            if exists:
                print(f"  [SKIP] {data['email']} already exists")
                continue
            user = User(
                name=data["name"],
                email=data["email"],
                password_hash=hash_password(PASSWORD),
                role=data["role"],
                is_active=True,
                is_approved=data["is_approved"],
            )
            db.add(user)
            print(f"  [ADD]  {data['email']} ({data['role'].value})")

        fpo_user = db.query(User).filter(User.email == "fpo@example.com").first()
        if fpo_user:
            fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == fpo_user.id).first()
            if not fpo_profile:
                db.add(
                    FPOProfile(
                        user_id=fpo_user.id,
                        organization_name="GreenChain FPO",
                        registration_number="FPO-SEED-001",
                        district="Mumbai",
                        state="Maharashtra",
                    )
                )
                print("  [ADD]  fpo@example.com profile")
        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
