from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class FPOProfile(Base):
    __tablename__ = "fpo_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    organization_name = Column(String(255), nullable=False)
    registration_number = Column(String(100), unique=True, nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    # Phase 9: custodial vault fields
    wallet_address    = Column(String(42), nullable=True, default=None)   # 0x-prefixed EVM address
    vault_identifier  = Column(String(100), nullable=True, default=None)  # Human label, e.g. "FPO-VAULT-001"
    # Phase 10A: wallet verification fields
    wallet_verified    = Column(Boolean, nullable=False, default=False)
    wallet_verified_at = Column(DateTime(timezone=True), nullable=True)
    wallet_network     = Column(String(50), nullable=True)               # e.g. "POLYGON_AMOY", "ETHEREUM_MAINNET"
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="fpo_profile", foreign_keys=[user_id])
    farms = relationship("Farm", back_populates="fpo", foreign_keys="Farm.fpo_id")
