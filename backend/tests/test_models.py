"""
Phase 1 — Model tests
Tests SQLAlchemy User model: creation, constraints, defaults.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.user import User, UserRole
from app.security import hash_password, verify_password


class TestUserModel:
    def test_create_farmer(self, db):
        user = User(
            name="Test Farmer",
            email="testfarmer@model.com",
            password_hash=hash_password("pass1234"),
            role=UserRole.FARMER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.name == "Test Farmer"
        assert user.email == "testfarmer@model.com"
        assert user.role == UserRole.FARMER
        assert user.is_active is True
        assert user.is_approved is False  # default
        assert user.created_at is not None

    def test_create_all_roles(self, db):
        for i, role in enumerate(UserRole):
            user = User(
                name=f"User {role.value}",
                email=f"{role.value.lower()}_{i}@model.com",
                password_hash=hash_password("pass1234"),
                role=role,
            )
            db.add(user)
        db.commit()
        count = db.query(User).count()
        assert count == len(UserRole)

    def test_email_unique_constraint(self, db):
        u1 = User(name="U1", email="dup@model.com", password_hash="h", role=UserRole.FARMER)
        u2 = User(name="U2", email="dup@model.com", password_hash="h", role=UserRole.FPO)
        db.add(u1)
        db.commit()
        db.add(u2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_password_hashing(self, db):
        plain = "mysecurepassword"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_is_active_default_true(self, db):
        user = User(
            name="Active Default",
            email="activedefault@model.com",
            password_hash="h",
            role=UserRole.FARMER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.is_active is True

    def test_is_approved_default_false(self, db):
        user = User(
            name="Unapproved",
            email="unapproved@model.com",
            password_hash="h",
            role=UserRole.VERIFIER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.is_approved is False

    def test_user_repr_fields(self, db):
        user = User(
            name="Field Check",
            email="fields@model.com",
            password_hash="h",
            role=UserRole.ADMIN,
            is_approved=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.role == UserRole.ADMIN
        assert user.is_approved is True
