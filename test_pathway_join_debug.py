"""
Debug script to check if joining works correctly
"""
import pathway as pw
from nats_config import CZK_TO_USD, PRESENT_PATH

pw.set_license_key("B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3")

class TransSchema(pw.Schema):
    trans_id: float
    account_id: float
    date: float
    type: str
    operation: str
    amount: float
    balance: float
    k_symbol: str
    bank: str
    account: str

# Read transactions
trans_table = pw.io.csv.read(
    f"{PRESENT_PATH}/trans.csv",
    schema=TransSchema,
    mode="static"
)

# Convert to USD and cast account_id
trans_table_usd = trans_table.select(
    trans_id=pw.this.trans_id,
    account_id=pw.cast(int, pw.this.account_id),
    type=pw.this.type,
    amount_usd=pw.this.amount * CZK_TO_USD,
    balance_usd=pw.this.balance * CZK_TO_USD,
)

# General stats
trans_stats = trans_table_usd.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    total_transactions=pw.reducers.count(),
    balance_max=pw.reducers.max(pw.this.balance_usd),
)

print("Step 1: Created general trans_stats")

# Incoming stats
incoming_trans = trans_table_usd.filter(pw.this.type == "PRIJEM")
incoming_stats = incoming_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_incoming=pw.reducers.count(),
    total_incoming=pw.reducers.sum(pw.this.amount_usd),
)

print("Step 2: Created incoming_stats")

# Join with incoming stats
trans_stats = trans_stats.join(
    incoming_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    account_id=pw.left.account_id,
    total_transactions=pw.left.total_transactions,
    balance_max=pw.left.balance_max,
    num_incoming=pw.coalesce(pw.right.num_incoming, 0),
    total_incoming=pw.coalesce(pw.right.total_incoming, 0.0),
)

print("Step 3: Joined with incoming_stats, writing to CSV...")

# Write to CSV
pw.io.csv.write(trans_stats, "data/debug_trans_stats_joined.csv")

print("Running computation...")
pw.run()
print("Done!")
