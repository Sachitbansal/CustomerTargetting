"""
Debug script to check incoming/outgoing aggregation
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

print("Step 1: Reading transactions...")

# Convert to USD and cast account_id
trans_table_usd = trans_table.select(
    trans_id=pw.this.trans_id,
    account_id=pw.cast(int, pw.this.account_id),
    type=pw.this.type,
    amount_usd=pw.this.amount * CZK_TO_USD,
)

# Filter for incoming transactions
incoming_trans = trans_table_usd.filter(pw.this.type == "PRIJEM")
print("Step 2: Filtered incoming transactions")

# Aggregate incoming
incoming_stats = incoming_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_incoming=pw.reducers.count(),
    total_incoming=pw.reducers.sum(pw.this.amount_usd),
    avg_incoming=pw.reducers.avg(pw.this.amount_usd),
)

print("Step 3: Writing incoming stats to CSV...")

# Write to CSV
pw.io.csv.write(incoming_stats, "data/debug_incoming_stats.csv")

# Filter for outgoing transactions
outgoing_trans = trans_table_usd.filter(pw.this.type == "VYDAJ")
print("Step 4: Filtered outgoing transactions")

# Aggregate outgoing
outgoing_stats = outgoing_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_outgoing=pw.reducers.count(),
    total_outgoing=pw.reducers.sum(pw.this.amount_usd),
    avg_outgoing=pw.reducers.avg(pw.this.amount_usd),
)

print("Step 5: Writing outgoing stats to CSV...")

# Write to CSV
pw.io.csv.write(outgoing_stats, "data/debug_outgoing_stats.csv")

print("Running computation...")
pw.run()
print("Done!")
