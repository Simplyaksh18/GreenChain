from datetime import datetime
from pydantic import BaseModel
from app.models.blockchain_transaction import ActionType


class BlockchainTransactionResponse(BaseModel):
    id: int
    carbon_report_id: int
    tx_hash: str
    blockchain_network: str
    contract_address: str
    action_type: ActionType
    created_at: datetime

    model_config = {"from_attributes": True}
