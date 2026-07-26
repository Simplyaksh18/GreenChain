import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class EvidenceType(str, enum.Enum):
    PHOTO            = "PHOTO"
    VIDEO            = "VIDEO"
    PDF              = "PDF"
    DOCUMENT         = "DOCUMENT"
    SENSOR_EXPORT    = "SENSOR_EXPORT"
    SATELLITE_EXPORT = "SATELLITE_EXPORT"
    DRONE_EXPORT     = "DRONE_EXPORT"
    GIS_BOUNDARY     = "GIS_BOUNDARY"
    OTHER            = "OTHER"


class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    id             = Column(Integer, primary_key=True, index=True)
    farm_id        = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    # nullable — some evidence is farm-level, not tied to a specific crop cycle
    crop_cycle_id  = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True, index=True)
    carbon_report_id = Column(Integer, ForeignKey("carbon_reports.id"), nullable=True, index=True)
    uploaded_by    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Phase 14 — rich file metadata
    evidence_type  = Column(String(30), nullable=True, default="OTHER")
    file_name      = Column(String(500), nullable=True)
    file_mime_type = Column(String(100), nullable=True)
    file_size      = Column(Integer, nullable=True)          # bytes
    storage_path   = Column(String(1024), nullable=True)     # on-disk path relative to uploads root

    # Legacy / URL-based evidence (Phase 4–13)
    file_url       = Column(String(1024), nullable=False, default="")
    file_type      = Column(String(50), nullable=False, default="OTHER")   # legacy alias
    description    = Column(String(512), nullable=True)

    # Phase 13 audit trail
    file_hash      = Column(String(128), nullable=True)      # hex digest
    hash_algorithm = Column(String(20), nullable=True, default="SHA256")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm       = relationship("Farm", back_populates="evidence_files")
    crop_cycle = relationship("CropCycle", back_populates="evidence_files")
    uploader   = relationship("User", back_populates="evidence_files", foreign_keys=[uploaded_by])
