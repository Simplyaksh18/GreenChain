import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    FARMER = "FARMER"
    FPO = "FPO"
    VERIFIER = "VERIFIER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    # Phase 6: optional Ethereum/Polygon wallet address (0x-prefixed, 42 chars)
    wallet_address = Column(String(42), nullable=True, default=None)
    # Phase 15: Google OAuth fields — all nullable/defaulted so existing users are unaffected
    auth_provider     = Column(String(10), nullable=False, default="PASSWORD", server_default="PASSWORD")
    google_sub        = Column(String(200), nullable=True)       # Google user ID (sub)
    profile_photo_url = Column(String(500), nullable=True)       # Google profile picture URL
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships (back-populated by child models)
    fpo_profile    = relationship("FPOProfile", back_populates="user", uselist=False)
    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False)
    farms          = relationship("Farm", back_populates="farmer", foreign_keys="Farm.farmer_id")
    evidence_files = relationship("EvidenceFile", back_populates="uploader", foreign_keys="EvidenceFile.uploaded_by")
    verification_requests = relationship("VerificationRequest", back_populates="verifier", foreign_keys="VerificationRequest.verifier_id")
    carbon_tokens  = relationship("CarbonToken", back_populates="farmer", foreign_keys="CarbonToken.farmer_id")
