"""
Simplified Pathway Real-Time Data Streaming Pipeline

A working version with simplified aggregations that actually runs.
"""

import pathway as pw
from datetime import datetime
import os
import sys

# Pathway License Key
pw.set_license_key("B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3")

# Configuration
PRESENT_TABLES_PATH = "data/present_tables"
OUTPUT_PATH = "data/pathway_output"
CZK_TO_USD = 0.038

os.makedirs(OUTPUT_PATH, exist_ok=True)

print("="*80)
print("PATHWAY REAL-TIME DATA STREAMING PIPELINE (Simplified)")
print("="*80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Source: {PRESENT_TABLES_PATH}/")
print(f"Output: {OUTPUT_PATH}/")
print(f"Press Ctrl+C to stop")
print("="*80 + "\n")

# === SCHEMA DEFINITIONS ===

class ClientSchema(pw.Schema):
    client_id: str
    birth_number: str
    district_id: str


class AccountSchema(pw.Schema):
    account_id: str
    district_id: str
    frequency: str
    date: str


class DispSchema(pw.Schema):
    disp_id: str
    client_id: str
    account_id: str
    type: str


class TransSchema(pw.Schema):
    trans_id: str
    account_id: str
    date: str
    type: str
    operation: str
    amount: float
    balance: float
    k_symbol: str | None
    bank: str | None
    account: str | None


class LoanSchema(pw.Schema):
    loan_id: str
    account_id: str
    date: str
    amount: float
    duration: float
    payments: float
    status: str


class OrderSchema(pw.Schema):
    order_id: str
    account_id: str
    bank_to: str
    account_to: str
    amount: float
    k_symbol: str


class CardSchema(pw.Schema):
    card_id: str
    disp_id: str
    type: str
    issued: str


class DistrictSchema(pw.Schema):
    A1: str
    A2: str
    A3: str
    A4: float
    A5: float
    A6: float
    A7: float
    A8: float
    A9: float
    A10: float
    A11: float
    A12: float
    A13: float
    A14: float
    A15: float
    A16: float


# === CONNECT TO DATA SOURCES ===

print("Connecting to data sources...")

client_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/client.csv",
    schema=ClientSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

account_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/account.csv",
    schema=AccountSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

disp_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/disp.csv",
    schema=DispSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

trans_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/trans.csv",
    schema=TransSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

loan_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/loan.csv",
    schema=LoanSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

order_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/order.csv",
    schema=OrderSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

card_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/card.csv",
    schema=CardSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

district_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/district.csv",
    schema=DistrictSchema,
    mode="streaming",
    autocommit_duration_ms=1000
)

print("✓ Data sources connected\n")

# === TRANSACTION AGGREGATIONS ===

print("Setting up transaction aggregations...")

# Convert to USD
trans_table_usd = trans_table.select(
    *pw.this.without(pw.this.amount, pw.this.balance),
    amount=pw.this.amount * CZK_TO_USD,
    balance=pw.this.balance * CZK_TO_USD
)

# Aggregate all transaction features per account in one go
trans_stats = trans_table_usd.groupby(trans_table_usd.account_id).reduce(
    trans_table_usd.account_id,
    total_transactions=pw.reducers.count(),
    total_incoming=pw.reducers.sum(pw.if_else(trans_table_usd.type == "PRIJEM", trans_table_usd.amount, 0.0)),
    total_outgoing=pw.reducers.sum(pw.if_else(trans_table_usd.type == "VYDAJ", trans_table_usd.amount, 0.0)),
    num_incoming=pw.reducers.sum(pw.if_else(trans_table_usd.type == "PRIJEM", 1, 0)),
    num_outgoing=pw.reducers.sum(pw.if_else(trans_table_usd.type == "VYDAJ", 1, 0)),
    balance_min=pw.reducers.min(trans_table_usd.balance),
    balance_max=pw.reducers.max(trans_table_usd.balance),
    balance_mean=pw.reducers.avg(trans_table_usd.balance),
    unique_k_symbols=pw.reducers.count_distinct(trans_table_usd.k_symbol),
    unique_operations=pw.reducers.count_distinct(trans_table_usd.operation),
    unique_banks=pw.reducers.count_distinct(trans_table_usd.bank),
    first_transaction_date=pw.reducers.min(trans_table_usd.date),
    last_transaction_date=pw.reducers.max(trans_table_usd.date),
)

# Calculate derived features
trans_stats = trans_stats.select(
    *pw.this,
    avg_incoming=pw.this.total_incoming / pw.cast(float, pw.this.num_incoming + 1),
    avg_outgoing=pw.this.total_outgoing / pw.cast(float, pw.this.num_outgoing + 1),
    net_cashflow=pw.this.total_incoming - pw.this.total_outgoing,
    incoming_outgoing_ratio=pw.this.total_incoming / (pw.this.total_outgoing + 1.0),
    avg_transaction_amount=(pw.this.total_incoming + pw.this.total_outgoing) / pw.cast(float, pw.this.total_transactions + 1),
    balance_volatility=0.2,  # Placeholder
    transaction_frequency=pw.cast(float, pw.this.total_transactions) / 100.0,  # Approximation
)

print("✓ Transaction aggregations configured\n")

# === LOAN AGGREGATIONS ===

print("Setting up loan aggregations...")

loan_table_usd = loan_table.select(
    *pw.this.without(pw.this.amount, pw.this.payments),
    amount=pw.this.amount * CZK_TO_USD,
    payments=pw.this.payments * CZK_TO_USD
)

loan_stats = loan_table_usd.groupby(loan_table_usd.account_id).reduce(
    loan_table_usd.account_id,
    num_loans=pw.reducers.count(),
    loan_amount_total_usd=pw.reducers.sum(loan_table_usd.amount),
    loan_amount_avg_usd=pw.reducers.avg(loan_table_usd.amount),
    loan_duration_avg=pw.reducers.avg(loan_table_usd.duration),
    loan_payment_avg_usd=pw.reducers.avg(loan_table_usd.payments),
    first_loan_date=pw.reducers.min(loan_table_usd.date),
    last_loan_date=pw.reducers.max(loan_table_usd.date),
    loan_status=pw.reducers.any(loan_table_usd.status),
)

print("✓ Loan aggregations configured\n")

# === ORDER AGGREGATIONS ===

print("Setting up order aggregations...")

order_table_usd = order_table.select(
    *pw.this.without(pw.this.amount),
    amount=pw.this.amount * CZK_TO_USD
)

order_stats = order_table_usd.groupby(order_table_usd.account_id).reduce(
    order_table_usd.account_id,
    num_orders=pw.reducers.count(),
    total_order_amount_usd=pw.reducers.sum(order_table_usd.amount),
    avg_order_amount_usd=pw.reducers.avg(order_table_usd.amount),
    unique_banks_orders=pw.reducers.count_distinct(order_table_usd.bank_to),
)

print("✓ Order aggregations configured\n")

# === CARD AGGREGATIONS ===

print("Setting up card aggregations...")

card_with_client = card_table.join(
    disp_table,
    card_table.disp_id == disp_table.disp_id
).select(
    card_id=card_table.card_id,
    client_id=disp_table.client_id,
    card_type=card_table.type,
    issued=card_table.issued,
)

card_stats = card_with_client.groupby(card_with_client.client_id).reduce(
    card_with_client.client_id,
    num_cards=pw.reducers.count(),
    earliest_card_issue=pw.reducers.min(card_with_client.issued),
)

print("✓ Card aggregations configured\n")

# === BUILD MASTER TABLE ===

print("Building master table...")

# Start with disp (OWNER only) joined with accounts
owner_disp = disp_table.filter(disp_table.type == "OWNER")

account_features = owner_disp.join(
    account_table,
    owner_disp.account_id == account_table.account_id
).select(
    client_id=owner_disp.client_id,
    account_id=owner_disp.account_id,
    disp_id=owner_disp.disp_id,
    district_id=account_table.district_id,
    frequency=account_table.frequency,
)

# Join with transaction stats
account_features = account_features.join(
    trans_stats,
    account_features.account_id == trans_stats.account_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    total_transactions=pw.right.total_transactions,
    total_incoming=pw.right.total_incoming,
    total_outgoing=pw.right.total_outgoing,
    num_incoming=pw.right.num_incoming,
    num_outgoing=pw.right.num_outgoing,
    balance_min=pw.right.balance_min,
    balance_max=pw.right.balance_max,
    balance_mean=pw.right.balance_mean,
    unique_k_symbols=pw.right.unique_k_symbols,
    unique_operations=pw.right.unique_operations,
    unique_banks=pw.right.unique_banks,
    first_transaction_date=pw.right.first_transaction_date,
    last_transaction_date=pw.right.last_transaction_date,
    avg_incoming=pw.right.avg_incoming,
    avg_outgoing=pw.right.avg_outgoing,
    net_cashflow=pw.right.net_cashflow,
    incoming_outgoing_ratio=pw.right.incoming_outgoing_ratio,
    avg_transaction_amount=pw.right.avg_transaction_amount,
    balance_volatility=pw.right.balance_volatility,
    transaction_frequency=pw.right.transaction_frequency,
)

# Join with loan stats
account_features = account_features.join(
    loan_stats,
    account_features.account_id == loan_stats.account_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    num_loans=pw.right.num_loans,
    loan_amount_total_usd=pw.right.loan_amount_total_usd,
    loan_amount_avg_usd=pw.right.loan_amount_avg_usd,
    loan_duration_avg=pw.right.loan_duration_avg,
    loan_payment_avg_usd=pw.right.loan_payment_avg_usd,
    first_loan_date=pw.right.first_loan_date,
    last_loan_date=pw.right.last_loan_date,
    loan_status=pw.right.loan_status,
)

# Join with order stats
account_features = account_features.join(
    order_stats,
    account_features.account_id == order_stats.account_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    num_orders=pw.right.num_orders,
    total_order_amount_usd=pw.right.total_order_amount_usd,
    avg_order_amount_usd=pw.right.avg_order_amount_usd,
    unique_banks_orders=pw.right.unique_banks_orders,
)

# Handle nullable columns before aggregation
account_features_cleaned = account_features.select(
    client_id=pw.this.client_id,
    account_id=pw.this.account_id,
    disp_id=pw.this.disp_id,
    district_id=pw.this.district_id,
    frequency=pw.this.frequency,
    total_transactions=pw.coalesce(pw.this.total_transactions, 0),
    total_incoming=pw.coalesce(pw.this.total_incoming, 0.0),
    total_outgoing=pw.coalesce(pw.this.total_outgoing, 0.0),
    num_incoming=pw.coalesce(pw.this.num_incoming, 0),
    num_outgoing=pw.coalesce(pw.this.num_outgoing, 0),
    balance_min=pw.coalesce(pw.this.balance_min, 0.0),
    balance_max=pw.coalesce(pw.this.balance_max, 0.0),
    balance_mean=pw.coalesce(pw.this.balance_mean, 0.0),
    unique_k_symbols=pw.coalesce(pw.this.unique_k_symbols, 0),
    unique_operations=pw.coalesce(pw.this.unique_operations, 0),
    unique_banks=pw.coalesce(pw.this.unique_banks, 0),
    first_transaction_date=pw.this.first_transaction_date,
    last_transaction_date=pw.this.last_transaction_date,
    avg_incoming=pw.coalesce(pw.this.avg_incoming, 0.0),
    avg_outgoing=pw.coalesce(pw.this.avg_outgoing, 0.0),
    net_cashflow=pw.coalesce(pw.this.net_cashflow, 0.0),
    incoming_outgoing_ratio=pw.coalesce(pw.this.incoming_outgoing_ratio, 0.0),
    avg_transaction_amount=pw.coalesce(pw.this.avg_transaction_amount, 0.0),
    balance_volatility=pw.coalesce(pw.this.balance_volatility, 0.0),
    transaction_frequency=pw.coalesce(pw.this.transaction_frequency, 0.0),
    num_loans=pw.coalesce(pw.this.num_loans, 0),
    loan_amount_total_usd=pw.coalesce(pw.this.loan_amount_total_usd, 0.0),
    loan_amount_avg_usd=pw.coalesce(pw.this.loan_amount_avg_usd, 0.0),
    loan_duration_avg=pw.coalesce(pw.this.loan_duration_avg, 0.0),
    loan_payment_avg_usd=pw.coalesce(pw.this.loan_payment_avg_usd, 0.0),
    first_loan_date=pw.this.first_loan_date,
    last_loan_date=pw.this.last_loan_date,
    loan_status=pw.this.loan_status,
    num_orders=pw.coalesce(pw.this.num_orders, 0),
    total_order_amount_usd=pw.coalesce(pw.this.total_order_amount_usd, 0.0),
    avg_order_amount_usd=pw.coalesce(pw.this.avg_order_amount_usd, 0.0),
    unique_banks_orders=pw.coalesce(pw.this.unique_banks_orders, 0),
)

# Aggregate to client level
client_features = account_features_cleaned.groupby(account_features_cleaned.client_id).reduce(
    account_features_cleaned.client_id,
    num_accounts=pw.reducers.count(),
    total_transactions=pw.reducers.sum(account_features_cleaned.total_transactions),
    total_incoming=pw.reducers.sum(account_features_cleaned.total_incoming),
    total_outgoing=pw.reducers.sum(account_features_cleaned.total_outgoing),
    num_incoming=pw.reducers.sum(account_features_cleaned.num_incoming),
    num_outgoing=pw.reducers.sum(account_features_cleaned.num_outgoing),
    balance_mean=pw.reducers.avg(account_features_cleaned.balance_mean),
    balance_min=pw.reducers.min(account_features_cleaned.balance_min),
    balance_max=pw.reducers.max(account_features_cleaned.balance_max),
    avg_incoming=pw.reducers.avg(account_features_cleaned.avg_incoming),
    avg_outgoing=pw.reducers.avg(account_features_cleaned.avg_outgoing),
    net_cashflow=pw.reducers.sum(account_features_cleaned.net_cashflow),
    incoming_outgoing_ratio=pw.reducers.avg(account_features_cleaned.incoming_outgoing_ratio),
    avg_transaction_amount=pw.reducers.avg(account_features_cleaned.avg_transaction_amount),
    unique_k_symbols=pw.reducers.sum(account_features_cleaned.unique_k_symbols),
    unique_operations=pw.reducers.sum(account_features_cleaned.unique_operations),
    unique_banks=pw.reducers.sum(account_features_cleaned.unique_banks),
    first_transaction_date=pw.reducers.min(account_features_cleaned.first_transaction_date),
    last_transaction_date=pw.reducers.max(account_features_cleaned.last_transaction_date),
    num_loans=pw.reducers.sum(account_features_cleaned.num_loans),
    loan_amount_total_usd=pw.reducers.sum(account_features_cleaned.loan_amount_total_usd),
    loan_amount_avg_usd=pw.reducers.avg(account_features_cleaned.loan_amount_avg_usd),
    loan_duration_avg=pw.reducers.avg(account_features_cleaned.loan_duration_avg),
    loan_payment_avg_usd=pw.reducers.avg(account_features_cleaned.loan_payment_avg_usd),
    first_loan_date=pw.reducers.min(account_features_cleaned.first_loan_date),
    last_loan_date=pw.reducers.max(account_features_cleaned.last_loan_date),
    num_orders=pw.reducers.sum(account_features_cleaned.num_orders),
    total_order_amount_usd=pw.reducers.sum(account_features_cleaned.total_order_amount_usd),
    avg_order_amount_usd=pw.reducers.avg(account_features_cleaned.avg_order_amount_usd),
    unique_banks_orders=pw.reducers.sum(account_features_cleaned.unique_banks_orders),
    frequency=pw.reducers.any(account_features_cleaned.frequency),
    loan_status=pw.reducers.any(account_features_cleaned.loan_status),
    district_id=pw.reducers.any(account_features_cleaned.district_id),
)

# Join with client base
master_table = client_table.join(
    client_features,
    client_table.client_id == client_features.client_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    num_accounts=pw.right.num_accounts,
    total_transactions=pw.right.total_transactions,
    total_incoming=pw.right.total_incoming,
    total_outgoing=pw.right.total_outgoing,
    num_incoming=pw.right.num_incoming,
    num_outgoing=pw.right.num_outgoing,
    balance_mean=pw.right.balance_mean,
    balance_min=pw.right.balance_min,
    balance_max=pw.right.balance_max,
    avg_incoming=pw.right.avg_incoming,
    avg_outgoing=pw.right.avg_outgoing,
    net_cashflow=pw.right.net_cashflow,
    incoming_outgoing_ratio=pw.right.incoming_outgoing_ratio,
    avg_transaction_amount=pw.right.avg_transaction_amount,
    unique_k_symbols=pw.right.unique_k_symbols,
    unique_operations=pw.right.unique_operations,
    unique_banks=pw.right.unique_banks,
    first_transaction_date=pw.right.first_transaction_date,
    last_transaction_date=pw.right.last_transaction_date,
    num_loans=pw.right.num_loans,
    loan_amount_total_usd=pw.right.loan_amount_total_usd,
    loan_amount_avg_usd=pw.right.loan_amount_avg_usd,
    loan_duration_avg=pw.right.loan_duration_avg,
    loan_payment_avg_usd=pw.right.loan_payment_avg_usd,
    first_loan_date=pw.right.first_loan_date,
    last_loan_date=pw.right.last_loan_date,
    num_orders=pw.right.num_orders,
    total_order_amount_usd=pw.right.total_order_amount_usd,
    avg_order_amount_usd=pw.right.avg_order_amount_usd,
    unique_banks_orders=pw.right.unique_banks_orders,
    frequency=pw.right.frequency,
    loan_status=pw.right.loan_status,
)

# Join with card stats
master_table = master_table.join(
    card_stats,
    master_table.client_id == card_stats.client_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    num_cards=pw.right.num_cards,
    earliest_card_issue=pw.right.earliest_card_issue,
)

# Join with district info
master_table = master_table.join(
    district_table,
    master_table.district_id == district_table.A1,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    A1=pw.right.A1,
    A2=pw.right.A2,
    A3=pw.right.A3,
    A4=pw.right.A4,
    A11=pw.right.A11,
)

print("✓ Master table configured\n")

# === OUTPUT ===

print("Setting up outputs...")

pw.io.csv.write(master_table, f"{OUTPUT_PATH}/master_table.csv")
pw.io.csv.write(trans_stats, f"{OUTPUT_PATH}/transaction_stats.csv")
pw.io.csv.write(loan_stats, f"{OUTPUT_PATH}/loan_stats.csv")
pw.io.csv.write(client_features, f"{OUTPUT_PATH}/client_features.csv")

# JSON Lines summary
pw.io.jsonlines.write(
    master_table.select(
        client_id=pw.this.client_id,
        num_accounts=pw.this.num_accounts,
        balance_mean=pw.this.balance_mean,
        total_incoming=pw.this.total_incoming,
        total_outgoing=pw.this.total_outgoing,
        net_cashflow=pw.this.net_cashflow,
    ),
    f"{OUTPUT_PATH}/master_summary.jsonl"
)

print("✓ Outputs configured\n")

print("="*80)
print("PIPELINE READY - Starting...")
print("="*80)
print(f"\nOutputs: {OUTPUT_PATH}/")
print("  - master_table.csv")
print("  - transaction_stats.csv")
print("  - loan_stats.csv")
print("  - client_features.csv")
print("  - master_summary.jsonl")
print("\nPress Ctrl+C to stop\n")
print("="*80 + "\n")

# === RUN ===

try:
    pw.run()
except KeyboardInterrupt:
    print("\n" + "="*80)
    print("Pipeline stopped")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    sys.exit(0)
