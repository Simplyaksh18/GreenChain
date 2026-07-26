import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class ActionType(str, enum.Enum):
    REPORT_HASH   = "REPORT_HASH"
    TOKEN_MINT    = "TOKEN_MINT"
    TOKEN_RETIRE  = "TOKEN_RETIRE"
    TOKEN_SUSPEND = "TOKEN_SUSPEND"


MOCK_NETWORK          = "MOCK_POLYGON_AMOY"
MOCK_CONTRACT_ADDRESS = "0xMockGreenChainContract000000000000000000"


class BlockchainTransaction(Base):
    __tablename__ = "blockchain_transactions"

    id                = Column(Integer, primary_key=True, index=True)
    carbon_report_id  = Column(Integer, ForeignKey("carbon_reports.id"), nullable=False, index=True)
    tx_hash           = Column(String(66), nullable=False, unique=True)
    blockchain_network = Column(String(64), nullable=False, default=MOCK_NETWORK)
    contract_address  = Column(String(64), nullable=False, default=MOCK_CONTRACT_ADDRESS)
    action_type       = Column(Enum(ActionType), nullable=False)
    created_at        = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # relationships
    carbon_report = relationship("CarbonReport", back_populates="blockchain_transactions")
