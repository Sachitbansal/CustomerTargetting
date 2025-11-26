# publisher/schema.py (Updated)
import pathway as pw

class TxnSchema(pw.Schema):
    customer_id: str
    txn_datetime: str  # Using str for CSV compatibility
    txn_amount: float
    txn_type: str
    balance_after_txn: float
    bounced_flag: bool
    txn_category: str