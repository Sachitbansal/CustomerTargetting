# publisher/schema.py (Updated)
import pathway as pw
from datetime import datetime

class TxnSchema(pw.Schema):
    customer_id: str
    txn_datetime: datetime  # <--- Changed from str to datetime
    txn_amount: float
    txn_type: str
    balance_after_txn: float
    bounced_flag: bool
    txn_category: str