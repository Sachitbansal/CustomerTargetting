"""
Debug script to trace full data flow to client_features
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

class DispSchema(pw.Schema):
    disp_id: int
    client_id: int
    account_id: int
    type: str

class AccountSchema(pw.Schema):
    account_id: int
    district_id: int
    frequency: str
    date: str

# Read tables
trans_table = pw.io.csv.read(f"{PRESENT_PATH}/trans.csv", schema=TransSchema, mode="static")
disp_table = pw.io.csv.read(f"{PRESENT_PATH}/disp.csv", schema=DispSchema, mode="static")
account_table = pw.io.csv.read(f"{PRESENT_PATH}/account.csv", schema=AccountSchema, mode="static")

# Convert transactions
trans_table_usd = trans_table.select(
    trans_id=pw.this.trans_id,
    account_id=pw.cast(int, pw.this.account_id),
    type=pw.this.type,
    amount_usd=pw.this.amount * CZK_TO_USD,
)

# Incoming stats
incoming_trans = trans_table_usd.filter(pw.this.type == "PRIJEM")
incoming_stats = incoming_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_incoming=pw.reducers.count(),
    total_incoming=pw.reducers.sum(pw.this.amount_usd),
)

# Outgoing stats
outgoing_trans = trans_table_usd.filter(pw.this.type == "VYDAJ")
outgoing_stats = outgoing_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_outgoing=pw.reducers.count(),
    total_outgoing=pw.reducers.sum(pw.this.amount_usd),
)

# General trans stats
trans_stats = trans_table_usd.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    total_transactions=pw.reducers.count(),
)

# Join with incoming
trans_stats = trans_stats.join(
    incoming_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    account_id=pw.left.account_id,
    total_transactions=pw.left.total_transactions,
    num_incoming=pw.coalesce(pw.right.num_incoming, 0),
    total_incoming=pw.coalesce(pw.right.total_incoming, 0.0),
)

# Join with outgoing
trans_stats = trans_stats.join(
    outgoing_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    account_id=pw.left.account_id,
    total_transactions=pw.left.total_transactions,
    num_incoming=pw.left.num_incoming,
    total_incoming=pw.left.total_incoming,
    num_outgoing=pw.coalesce(pw.right.num_outgoing, 0),
    total_outgoing=pw.coalesce(pw.right.total_outgoing, 0.0),
)

print("Step 1: Created trans_stats with incoming/outgoing")

# Join disp with account
disp_with_account = disp_table.join(
    account_table,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    disp_id=pw.left.disp_id,
    client_id=pw.left.client_id,
    account_id=pw.left.account_id,
    disp_type=pw.left.type,
    frequency=pw.right.frequency,
)

print("Step 2: Created disp_with_account")

# Join with trans stats
account_features = disp_with_account.join(
    trans_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    disp_id=pw.left.disp_id,
    client_id=pw.left.client_id,
    account_id=pw.left.account_id,
    disp_type=pw.left.disp_type,
    frequency=pw.left.frequency,
    total_transactions=pw.coalesce(pw.right.total_transactions, 0),
    num_incoming=pw.coalesce(pw.right.num_incoming, 0),
    total_incoming=pw.coalesce(pw.right.total_incoming, 0.0),
    num_outgoing=pw.coalesce(pw.right.num_outgoing, 0),
    total_outgoing=pw.coalesce(pw.right.total_outgoing, 0.0),
)

print("Step 3: Created account_features, writing to CSV...")
pw.io.csv.write(account_features, "data/debug_account_features.csv")

# Aggregate to client level
client_features = account_features.groupby(pw.this.client_id).reduce(
    client_id=pw.this.client_id,
    num_accounts=pw.reducers.count(),
    total_transactions=pw.reducers.sum(pw.this.total_transactions),
    num_incoming=pw.reducers.sum(pw.this.num_incoming),
    total_incoming=pw.reducers.sum(pw.this.total_incoming),
    num_outgoing=pw.reducers.sum(pw.this.num_outgoing),
    total_outgoing=pw.reducers.sum(pw.this.total_outgoing),
)

print("Step 4: Created client_features, writing to CSV...")
pw.io.csv.write(client_features, "data/debug_client_features.csv")

print("Running computation...")
pw.run()
print("Done!")
