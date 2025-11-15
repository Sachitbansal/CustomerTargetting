"""
Data Fetch - Pathway-based real-time feature calculation with NATS integration
Loads initial data from present_tables, processes NATS stream updates, calculates features
"""

import pathway as pw
from datetime import datetime
import os
import json
import asyncio
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, CZK_TO_USD, PRESENT_PATH

# Set Pathway license
pw.set_license_key("B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3")

PRESENT_TABLES_PATH = PRESENT_PATH
OUTPUT_PATH = "data"


# Define schemas
class ClientSchema(pw.Schema):
    client_id: int
    birth_number: str
    district_id: int | None


class AccountSchema(pw.Schema):
    account_id: int
    district_id: int
    frequency: str
    date: str


class DispSchema(pw.Schema):
    disp_id: int
    client_id: int
    account_id: int
    type: str


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


class LoanSchema(pw.Schema):
    loan_id: float
    account_id: float
    date: float
    amount: float
    duration: int
    payments: float
    status: str


class OrderSchema(pw.Schema):
    order_id: float
    account_id: float
    bank_to: str
    account_to: str
    amount: float
    k_symbol: str


class CardSchema(pw.Schema):
    card_id: int
    disp_id: int
    type: str
    issued: str


class DistrictSchema(pw.Schema):
    A1: str
    A2: str
    A3: str
    A4: int | None
    A5: int | None
    A6: int | None
    A7: int | None
    A8: int | None
    A9: int | None
    A10: float | None
    A11: int | None
    A12: float | None
    A13: float | None
    A14: int | None
    A15: int | None
    A16: int | None


print("="*80)
print("DATA FETCH - PATHWAY + NATS REAL-TIME PIPELINE")
print("="*80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Reading from: {PRESENT_TABLES_PATH}")
print(f"NATS Server: {NATS_SERVER}")
print("="*80 + "\n")

# Read initial data from present_tables (CSV files)
print("Loading initial data from present_tables...")

# Read initial client data (static)
client_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/client.csv",
    schema=ClientSchema,
    mode="static"
)

# Use only present data (streaming handled via NATS publishers separately)
client_table = client_table_present

# Read initial account data (static)
account_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/account.csv",
    schema=AccountSchema,
    mode="static"
)

# Use only present data
account_table = account_table_present

# Read initial disp data (static)
disp_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/disp.csv",
    schema=DispSchema,
    mode="static"
)

# Use only present data
disp_table = disp_table_present

# Read initial transaction data (static)
trans_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/trans.csv",
    schema=TransSchema,
    mode="static"
)

# Use only present data
trans_table = trans_table_present

# Read initial loan data (static)
loan_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/loan.csv",
    schema=LoanSchema,
    mode="static"
)

# Use only present data
loan_table = loan_table_present

# Read initial order data (static)
order_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/order.csv",
    schema=OrderSchema,
    mode="static"
)

# Use only present data
order_table = order_table_present

# Read initial card data (static)
card_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/card.csv",
    schema=CardSchema,
    mode="static"
)

# Use only present data
card_table = card_table_present

# Read initial district data (static)
district_table_present = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/district.csv",
    schema=DistrictSchema,
    mode="static"
)

# Use only present data
district_table = district_table_present

print("✓ Loaded all tables from CSV files (present tables only)\n")

# Convert CZK to USD and cast account_ids to int for joins
trans_table_usd = trans_table.select(
    trans_id=pw.this.trans_id,
    account_id=pw.cast(int, pw.this.account_id),  # Cast float to int
    date=pw.this.date,
    type=pw.this.type,
    operation=pw.this.operation,
    amount=pw.this.amount,
    balance=pw.this.balance,
    k_symbol=pw.this.k_symbol,
    bank=pw.this.bank,
    account=pw.this.account,
    amount_usd=pw.this.amount * CZK_TO_USD,
    balance_usd=pw.this.balance * CZK_TO_USD
)

loan_table_usd = loan_table.select(
    loan_id=pw.this.loan_id,
    account_id=pw.cast(int, pw.this.account_id),  # Cast float to int
    date=pw.this.date,
    amount=pw.this.amount,
    duration=pw.this.duration,
    payments=pw.this.payments,
    status=pw.this.status,
    amount_usd=pw.this.amount * CZK_TO_USD,
    payments_usd=pw.this.payments * CZK_TO_USD
)

order_table_usd = order_table.select(
    order_id=pw.this.order_id,
    account_id=pw.cast(int, pw.this.account_id),  # Cast float to int
    bank_to=pw.this.bank_to,
    account_to=pw.this.account_to,
    amount=pw.this.amount,
    k_symbol=pw.this.k_symbol,
    amount_usd=pw.this.amount * CZK_TO_USD
)

# Calculate general transaction statistics per account
trans_stats = trans_table_usd.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    total_transactions=pw.reducers.count(),
    unique_k_symbols=pw.reducers.count_distinct(pw.this.k_symbol),
    unique_operations=pw.reducers.count_distinct(pw.this.operation),
    unique_banks=pw.reducers.count_distinct(pw.this.bank),
    balance_min=pw.reducers.min(pw.this.balance_usd),
    balance_max=pw.reducers.max(pw.this.balance_usd),
    balance_mean=pw.reducers.avg(pw.this.balance_usd),
    avg_transaction_amount=pw.reducers.avg(pw.this.amount_usd),
)

# Filter for incoming transactions (PRIJEM) and aggregate
incoming_trans = trans_table_usd.filter(pw.this.type == "PRIJEM")
incoming_stats = incoming_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_incoming=pw.reducers.count(),
    total_incoming=pw.reducers.sum(pw.this.amount_usd),
    avg_incoming=pw.reducers.avg(pw.this.amount_usd),
    min_incoming=pw.reducers.min(pw.this.amount_usd),
    max_incoming=pw.reducers.max(pw.this.amount_usd),
)

# Filter for outgoing transactions (VYDAJ) and aggregate
outgoing_trans = trans_table_usd.filter(pw.this.type == "VYDAJ")
outgoing_stats = outgoing_trans.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_outgoing=pw.reducers.count(),
    total_outgoing=pw.reducers.sum(pw.this.amount_usd),
    avg_outgoing=pw.reducers.avg(pw.this.amount_usd),
    min_outgoing=pw.reducers.min(pw.this.amount_usd),
    max_outgoing=pw.reducers.max(pw.this.amount_usd),
)

# Join general stats with incoming stats
trans_stats = trans_stats.join(
    incoming_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    account_id=pw.left.account_id,
    total_transactions=pw.left.total_transactions,
    unique_k_symbols=pw.left.unique_k_symbols,
    unique_operations=pw.left.unique_operations,
    unique_banks=pw.left.unique_banks,
    balance_min=pw.left.balance_min,
    balance_max=pw.left.balance_max,
    balance_mean=pw.left.balance_mean,
    avg_transaction_amount=pw.left.avg_transaction_amount,
    num_incoming=pw.coalesce(pw.right.num_incoming, 0),
    total_incoming=pw.coalesce(pw.right.total_incoming, 0.0),
    avg_incoming=pw.coalesce(pw.right.avg_incoming, 0.0),
    min_incoming=pw.coalesce(pw.right.min_incoming, 0.0),
    max_incoming=pw.coalesce(pw.right.max_incoming, 0.0),
)

# Join with outgoing stats
trans_stats = trans_stats.join(
    outgoing_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    account_id=pw.left.account_id,
    total_transactions=pw.left.total_transactions,
    unique_k_symbols=pw.left.unique_k_symbols,
    unique_operations=pw.left.unique_operations,
    unique_banks=pw.left.unique_banks,
    balance_min=pw.left.balance_min,
    balance_max=pw.left.balance_max,
    balance_mean=pw.left.balance_mean,
    avg_transaction_amount=pw.left.avg_transaction_amount,
    num_incoming=pw.left.num_incoming,
    total_incoming=pw.left.total_incoming,
    avg_incoming=pw.left.avg_incoming,
    min_incoming=pw.left.min_incoming,
    max_incoming=pw.left.max_incoming,
    num_outgoing=pw.coalesce(pw.right.num_outgoing, 0),
    total_outgoing=pw.coalesce(pw.right.total_outgoing, 0.0),
    avg_outgoing=pw.coalesce(pw.right.avg_outgoing, 0.0),
    min_outgoing=pw.coalesce(pw.right.min_outgoing, 0.0),
    max_outgoing=pw.coalesce(pw.right.max_outgoing, 0.0),
)

# Loan statistics per account
loan_stats = loan_table_usd.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_loans=pw.reducers.count(),
    loan_amount_total_usd=pw.reducers.sum(pw.this.amount_usd),
    loan_amount_avg_usd=pw.reducers.avg(pw.this.amount_usd),
    loan_amount_min_usd=pw.reducers.min(pw.this.amount_usd),
    loan_amount_max_usd=pw.reducers.max(pw.this.amount_usd),
    loan_duration_avg=pw.reducers.avg(pw.this.duration),
    loan_duration_min=pw.reducers.min(pw.this.duration),
    loan_duration_max=pw.reducers.max(pw.this.duration),
    loan_payment_avg_usd=pw.reducers.avg(pw.this.payments_usd),
    loan_payment_min_usd=pw.reducers.min(pw.this.payments_usd),
    loan_payment_max_usd=pw.reducers.max(pw.this.payments_usd),
)

# Order statistics per account
order_stats = order_table_usd.groupby(pw.this.account_id).reduce(
    account_id=pw.this.account_id,
    num_orders=pw.reducers.count(),
    total_order_amount_usd=pw.reducers.sum(pw.this.amount_usd),
    avg_order_amount_usd=pw.reducers.avg(pw.this.amount_usd),
    min_order_amount_usd=pw.reducers.min(pw.this.amount_usd),
    max_order_amount_usd=pw.reducers.max(pw.this.amount_usd),
    std_order_amount_usd=0.0,  # Placeholder - Pathway doesn't support stddev
    unique_banks_orders=pw.reducers.count_distinct(pw.this.bank_to),
    unique_k_symbols_orders=pw.reducers.count_distinct(pw.this.k_symbol),
)

# Card statistics per disp (then join to client)
card_stats = card_table.groupby(pw.this.disp_id).reduce(
    disp_id=pw.this.disp_id,
    num_cards=pw.reducers.count(),
)

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
    account_date=pw.right.date,
)

# Join with transaction stats (now includes incoming/outgoing)
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
    account_date=pw.left.account_date,
    total_transactions=pw.coalesce(pw.right.total_transactions, 0),
    unique_k_symbols=pw.coalesce(pw.right.unique_k_symbols, 0),
    unique_operations=pw.coalesce(pw.right.unique_operations, 0),
    unique_banks=pw.coalesce(pw.right.unique_banks, 0),
    balance_min=pw.coalesce(pw.right.balance_min, 0.0),
    balance_max=pw.coalesce(pw.right.balance_max, 0.0),
    balance_mean=pw.coalesce(pw.right.balance_mean, 0.0),
    avg_transaction_amount=pw.coalesce(pw.right.avg_transaction_amount, 0.0),
    # Incoming stats
    num_incoming=pw.coalesce(pw.right.num_incoming, 0),
    total_incoming=pw.coalesce(pw.right.total_incoming, 0.0),
    avg_incoming=pw.coalesce(pw.right.avg_incoming, 0.0),
    min_incoming=pw.coalesce(pw.right.min_incoming, 0.0),
    max_incoming=pw.coalesce(pw.right.max_incoming, 0.0),
    # Outgoing stats
    num_outgoing=pw.coalesce(pw.right.num_outgoing, 0),
    total_outgoing=pw.coalesce(pw.right.total_outgoing, 0.0),
    avg_outgoing=pw.coalesce(pw.right.avg_outgoing, 0.0),
    min_outgoing=pw.coalesce(pw.right.min_outgoing, 0.0),
    max_outgoing=pw.coalesce(pw.right.max_outgoing, 0.0),
)

# Join with loan stats
account_features = account_features.join(
    loan_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    disp_id=pw.left.disp_id,
    client_id=pw.left.client_id,
    account_id=pw.left.account_id,
    disp_type=pw.left.disp_type,
    frequency=pw.left.frequency,
    account_date=pw.left.account_date,
    total_transactions=pw.left.total_transactions,
    unique_k_symbols=pw.left.unique_k_symbols,
    unique_operations=pw.left.unique_operations,
    unique_banks=pw.left.unique_banks,
    balance_min=pw.left.balance_min,
    balance_max=pw.left.balance_max,
    balance_mean=pw.left.balance_mean,
    avg_transaction_amount=pw.left.avg_transaction_amount,
    num_incoming=pw.left.num_incoming,
    total_incoming=pw.left.total_incoming,
    avg_incoming=pw.left.avg_incoming,
    min_incoming=pw.left.min_incoming,
    max_incoming=pw.left.max_incoming,
    num_outgoing=pw.left.num_outgoing,
    total_outgoing=pw.left.total_outgoing,
    avg_outgoing=pw.left.avg_outgoing,
    min_outgoing=pw.left.min_outgoing,
    max_outgoing=pw.left.max_outgoing,
    num_loans=pw.coalesce(pw.right.num_loans, 0),
    loan_amount_total_usd=pw.coalesce(pw.right.loan_amount_total_usd, 0.0),
    loan_amount_avg_usd=pw.coalesce(pw.right.loan_amount_avg_usd, 0.0),
    loan_amount_min_usd=pw.coalesce(pw.right.loan_amount_min_usd, 0.0),
    loan_amount_max_usd=pw.coalesce(pw.right.loan_amount_max_usd, 0.0),
    loan_duration_avg=pw.coalesce(pw.right.loan_duration_avg, 0.0),
    loan_duration_min=pw.coalesce(pw.right.loan_duration_min, 0.0),
    loan_duration_max=pw.coalesce(pw.right.loan_duration_max, 0.0),
    loan_payment_avg_usd=pw.coalesce(pw.right.loan_payment_avg_usd, 0.0),
    loan_payment_min_usd=pw.coalesce(pw.right.loan_payment_min_usd, 0.0),
    loan_payment_max_usd=pw.coalesce(pw.right.loan_payment_max_usd, 0.0),
)

# Join with order stats
account_features = account_features.join(
    order_stats,
    pw.left.account_id == pw.right.account_id,
    how=pw.JoinMode.LEFT
).select(
    disp_id=pw.left.disp_id,
    client_id=pw.left.client_id,
    account_id=pw.left.account_id,
    disp_type=pw.left.disp_type,
    frequency=pw.left.frequency,
    account_date=pw.left.account_date,
    total_transactions=pw.left.total_transactions,
    unique_k_symbols=pw.left.unique_k_symbols,
    unique_operations=pw.left.unique_operations,
    unique_banks=pw.left.unique_banks,
    balance_min=pw.left.balance_min,
    balance_max=pw.left.balance_max,
    balance_mean=pw.left.balance_mean,
    avg_transaction_amount=pw.left.avg_transaction_amount,
    num_incoming=pw.left.num_incoming,
    total_incoming=pw.left.total_incoming,
    avg_incoming=pw.left.avg_incoming,
    min_incoming=pw.left.min_incoming,
    max_incoming=pw.left.max_incoming,
    num_outgoing=pw.left.num_outgoing,
    total_outgoing=pw.left.total_outgoing,
    avg_outgoing=pw.left.avg_outgoing,
    min_outgoing=pw.left.min_outgoing,
    max_outgoing=pw.left.max_outgoing,
    num_loans=pw.left.num_loans,
    loan_amount_total_usd=pw.left.loan_amount_total_usd,
    loan_amount_avg_usd=pw.left.loan_amount_avg_usd,
    loan_amount_min_usd=pw.left.loan_amount_min_usd,
    loan_amount_max_usd=pw.left.loan_amount_max_usd,
    loan_duration_avg=pw.left.loan_duration_avg,
    loan_duration_min=pw.left.loan_duration_min,
    loan_duration_max=pw.left.loan_duration_max,
    loan_payment_avg_usd=pw.left.loan_payment_avg_usd,
    loan_payment_min_usd=pw.left.loan_payment_min_usd,
    loan_payment_max_usd=pw.left.loan_payment_max_usd,
    num_orders=pw.coalesce(pw.right.num_orders, 0),
    total_order_amount_usd=pw.coalesce(pw.right.total_order_amount_usd, 0.0),
    avg_order_amount_usd=pw.coalesce(pw.right.avg_order_amount_usd, 0.0),
    min_order_amount_usd=pw.coalesce(pw.right.min_order_amount_usd, 0.0),
    max_order_amount_usd=pw.coalesce(pw.right.max_order_amount_usd, 0.0),
    std_order_amount_usd=pw.coalesce(pw.right.std_order_amount_usd, 0.0),
    unique_banks_orders=pw.coalesce(pw.right.unique_banks_orders, 0),
    unique_k_symbols_orders=pw.coalesce(pw.right.unique_k_symbols_orders, 0),
)

# Join with card stats
account_features = account_features.join(
    card_stats,
    pw.left.disp_id == pw.right.disp_id,
    how=pw.JoinMode.LEFT
).select(
    disp_id=pw.left.disp_id,
    client_id=pw.left.client_id,
    account_id=pw.left.account_id,
    disp_type=pw.left.disp_type,
    frequency=pw.left.frequency,
    account_date=pw.left.account_date,
    total_transactions=pw.left.total_transactions,
    unique_k_symbols=pw.left.unique_k_symbols,
    unique_operations=pw.left.unique_operations,
    unique_banks=pw.left.unique_banks,
    balance_min=pw.left.balance_min,
    balance_max=pw.left.balance_max,
    balance_mean=pw.left.balance_mean,
    avg_transaction_amount=pw.left.avg_transaction_amount,
    num_incoming=pw.left.num_incoming,
    total_incoming=pw.left.total_incoming,
    avg_incoming=pw.left.avg_incoming,
    min_incoming=pw.left.min_incoming,
    max_incoming=pw.left.max_incoming,
    num_outgoing=pw.left.num_outgoing,
    total_outgoing=pw.left.total_outgoing,
    avg_outgoing=pw.left.avg_outgoing,
    min_outgoing=pw.left.min_outgoing,
    max_outgoing=pw.left.max_outgoing,
    num_loans=pw.left.num_loans,
    loan_amount_total_usd=pw.left.loan_amount_total_usd,
    loan_amount_avg_usd=pw.left.loan_amount_avg_usd,
    loan_amount_min_usd=pw.left.loan_amount_min_usd,
    loan_amount_max_usd=pw.left.loan_amount_max_usd,
    loan_duration_avg=pw.left.loan_duration_avg,
    loan_duration_min=pw.left.loan_duration_min,
    loan_duration_max=pw.left.loan_duration_max,
    loan_payment_avg_usd=pw.left.loan_payment_avg_usd,
    loan_payment_min_usd=pw.left.loan_payment_min_usd,
    loan_payment_max_usd=pw.left.loan_payment_max_usd,
    num_orders=pw.left.num_orders,
    total_order_amount_usd=pw.left.total_order_amount_usd,
    avg_order_amount_usd=pw.left.avg_order_amount_usd,
    min_order_amount_usd=pw.left.min_order_amount_usd,
    max_order_amount_usd=pw.left.max_order_amount_usd,
    std_order_amount_usd=pw.left.std_order_amount_usd,
    unique_banks_orders=pw.left.unique_banks_orders,
    unique_k_symbols_orders=pw.left.unique_k_symbols_orders,
    num_cards=pw.coalesce(pw.right.num_cards, 0),
)

# Add calculated fields WITHOUT using *pw.this (which causes zero values bug)
account_features = account_features.select(
    # Explicitly list all existing columns
    disp_id=pw.this.disp_id,
    client_id=pw.this.client_id,
    account_id=pw.this.account_id,
    disp_type=pw.this.disp_type,
    frequency=pw.this.frequency,
    account_date=pw.this.account_date,
    total_transactions=pw.this.total_transactions,
    unique_k_symbols=pw.this.unique_k_symbols,
    unique_operations=pw.this.unique_operations,
    unique_banks=pw.this.unique_banks,
    balance_min=pw.this.balance_min,
    balance_max=pw.this.balance_max,
    balance_mean=pw.this.balance_mean,
    avg_transaction_amount=pw.this.avg_transaction_amount,
    num_incoming=pw.this.num_incoming,
    total_incoming=pw.this.total_incoming,
    avg_incoming=pw.this.avg_incoming,
    min_incoming=pw.this.min_incoming,
    max_incoming=pw.this.max_incoming,
    num_outgoing=pw.this.num_outgoing,
    total_outgoing=pw.this.total_outgoing,
    avg_outgoing=pw.this.avg_outgoing,
    min_outgoing=pw.this.min_outgoing,
    max_outgoing=pw.this.max_outgoing,
    num_loans=pw.this.num_loans,
    loan_amount_total_usd=pw.this.loan_amount_total_usd,
    loan_amount_avg_usd=pw.this.loan_amount_avg_usd,
    loan_amount_min_usd=pw.this.loan_amount_min_usd,
    loan_amount_max_usd=pw.this.loan_amount_max_usd,
    loan_duration_avg=pw.this.loan_duration_avg,
    loan_duration_min=pw.this.loan_duration_min,
    loan_duration_max=pw.this.loan_duration_max,
    loan_payment_avg_usd=pw.this.loan_payment_avg_usd,
    loan_payment_min_usd=pw.this.loan_payment_min_usd,
    loan_payment_max_usd=pw.this.loan_payment_max_usd,
    num_orders=pw.this.num_orders,
    total_order_amount_usd=pw.this.total_order_amount_usd,
    avg_order_amount_usd=pw.this.avg_order_amount_usd,
    min_order_amount_usd=pw.this.min_order_amount_usd,
    max_order_amount_usd=pw.this.max_order_amount_usd,
    std_order_amount_usd=pw.this.std_order_amount_usd,
    unique_banks_orders=pw.this.unique_banks_orders,
    unique_k_symbols_orders=pw.this.unique_k_symbols_orders,
    num_cards=pw.this.num_cards,
    # Add new calculated fields
    net_cashflow=pw.this.total_incoming - pw.this.total_outgoing,
    incoming_outgoing_ratio=pw.if_else(
        pw.this.total_outgoing > 0,
        pw.this.total_incoming / pw.this.total_outgoing,
        0.0
    ),
    balance_median=pw.this.balance_mean,  # Approximation
    transaction_span_days=0,  # Placeholder
    transaction_frequency=pw.this.total_transactions / 30.0,
    balance_volatility=0.0,  # Placeholder
    std_incoming=0.0,  # Placeholder - Pathway doesn't support stddev
    std_outgoing=0.0,  # Placeholder - Pathway doesn't support stddev
    incoming_volatility=0.0,  # Placeholder - requires stddev
    outgoing_volatility=0.0,  # Placeholder - requires stddev
    max_to_avg_incoming_ratio=pw.if_else(
        pw.this.avg_incoming > 0,
        pw.this.max_incoming / pw.this.avg_incoming,
        0.0
    ),
    max_to_avg_outgoing_ratio=pw.if_else(
        pw.this.avg_outgoing > 0,
        pw.this.max_outgoing / pw.this.avg_outgoing,
        0.0
    ),
)

# Aggregate to client level
client_features = account_features.groupby(pw.this.client_id).reduce(
    client_id=pw.this.client_id,
    num_accounts=pw.reducers.count(),
    account_id=pw.reducers.any(pw.this.account_id),
    frequency=pw.reducers.any(pw.this.frequency),
    # Transaction aggregates
    total_transactions=pw.reducers.sum(pw.this.total_transactions),
    num_incoming=pw.reducers.sum(pw.this.num_incoming),
    num_outgoing=pw.reducers.sum(pw.this.num_outgoing),
    total_incoming=pw.reducers.sum(pw.this.total_incoming),
    total_outgoing=pw.reducers.sum(pw.this.total_outgoing),
    avg_incoming=pw.reducers.avg(pw.this.avg_incoming),
    avg_outgoing=pw.reducers.avg(pw.this.avg_outgoing),
    std_incoming=pw.reducers.avg(pw.this.std_incoming),  # Averaged placeholder
    std_outgoing=pw.reducers.avg(pw.this.std_outgoing),  # Averaged placeholder
    min_incoming=pw.reducers.min(pw.this.min_incoming),
    min_outgoing=pw.reducers.min(pw.this.min_outgoing),
    max_incoming=pw.reducers.max(pw.this.max_incoming),
    max_outgoing=pw.reducers.max(pw.this.max_outgoing),
    balance_min=pw.reducers.min(pw.this.balance_min),
    balance_max=pw.reducers.max(pw.this.balance_max),
    balance_mean=pw.reducers.avg(pw.this.balance_mean),
    balance_median=pw.reducers.avg(pw.this.balance_median),
    unique_k_symbols=pw.reducers.sum(pw.this.unique_k_symbols),
    unique_operations=pw.reducers.sum(pw.this.unique_operations),
    unique_banks=pw.reducers.sum(pw.this.unique_banks),
    net_cashflow=pw.reducers.sum(pw.this.net_cashflow),
    incoming_outgoing_ratio=pw.reducers.avg(pw.this.incoming_outgoing_ratio),
    avg_transaction_amount=pw.reducers.avg(pw.this.avg_transaction_amount),
    transaction_frequency=pw.reducers.avg(pw.this.transaction_frequency),
    # Loan aggregates
    num_loans=pw.reducers.sum(pw.this.num_loans),
    loan_amount_total_usd=pw.reducers.sum(pw.this.loan_amount_total_usd),
    loan_amount_avg_usd=pw.reducers.avg(pw.this.loan_amount_avg_usd),
    loan_amount_min_usd=pw.reducers.min(pw.this.loan_amount_min_usd),
    loan_amount_max_usd=pw.reducers.max(pw.this.loan_amount_max_usd),
    loan_duration_avg=pw.reducers.avg(pw.this.loan_duration_avg),
    loan_duration_min=pw.reducers.min(pw.this.loan_duration_min),
    loan_duration_max=pw.reducers.max(pw.this.loan_duration_max),
    loan_payment_avg_usd=pw.reducers.avg(pw.this.loan_payment_avg_usd),
    loan_payment_min_usd=pw.reducers.min(pw.this.loan_payment_min_usd),
    loan_payment_max_usd=pw.reducers.max(pw.this.loan_payment_max_usd),
    # Order aggregates
    num_orders=pw.reducers.sum(pw.this.num_orders),
    total_order_amount_usd=pw.reducers.sum(pw.this.total_order_amount_usd),
    avg_order_amount_usd=pw.reducers.avg(pw.this.avg_order_amount_usd),
    min_order_amount_usd=pw.reducers.min(pw.this.min_order_amount_usd),
    max_order_amount_usd=pw.reducers.max(pw.this.max_order_amount_usd),
    std_order_amount_usd=pw.reducers.avg(pw.this.std_order_amount_usd),  # Averaged placeholder
    unique_banks_orders=pw.reducers.sum(pw.this.unique_banks_orders),
    unique_k_symbols_orders=pw.reducers.sum(pw.this.unique_k_symbols_orders),
    # Card aggregates
    num_cards=pw.reducers.sum(pw.this.num_cards),
    # Volatility
    incoming_volatility=pw.reducers.avg(pw.this.incoming_volatility),
    outgoing_volatility=pw.reducers.avg(pw.this.outgoing_volatility),
    max_to_avg_incoming_ratio=pw.reducers.avg(pw.this.max_to_avg_incoming_ratio),
    max_to_avg_outgoing_ratio=pw.reducers.avg(pw.this.max_to_avg_outgoing_ratio),
)

# Join with client info
client_features = client_features.join(
    client_table,
    pw.left.client_id == pw.right.client_id,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    birth_number=pw.coalesce(pw.right.birth_number, ""),
    client_district_id=pw.coalesce(pw.right.district_id, 0),
    district_id_str=pw.cast(str, pw.coalesce(pw.right.district_id, 0)),  # Cast to string for district join
)

# Join with district
final_features = client_features.join(
    district_table,
    pw.left.district_id_str == pw.right.A1,
    how=pw.JoinMode.LEFT
).select(
    *pw.left,
    district_id=pw.left.client_district_id,  # Rename back to district_id
    A1=pw.right.A1,
    A2=pw.right.A2,
    A3=pw.right.A3,
    A4=pw.coalesce(pw.right.A4, 0),
    A5=pw.coalesce(pw.right.A5, 0),
    A6=pw.coalesce(pw.right.A6, 0),
    A7=pw.coalesce(pw.right.A7, 0),
    A8=pw.coalesce(pw.right.A8, 0),
    A9=pw.coalesce(pw.right.A9, 0),
    A10=pw.coalesce(pw.right.A10, 0.0),
    A11=pw.coalesce(pw.right.A11, 0),
    A12=pw.coalesce(pw.right.A12, 0.0),
    A13=pw.coalesce(pw.right.A13, 0.0),
    A14=pw.coalesce(pw.right.A14, 0),
    A15=pw.coalesce(pw.right.A15, 0),
    A16=pw.coalesce(pw.right.A16, 0),
)

# Add placeholder columns for missing features
final_features = final_features.select(
    *pw.this,
    balance_std=0.0,
    median_incoming=pw.this.avg_incoming,  # Approximation using average
    median_outgoing=pw.this.avg_outgoing,  # Approximation using average
    transaction_span_days=0,
    balance_volatility=0.0,
    first_transaction_date="",
    last_transaction_date="",
    first_loan_date="",
    last_loan_date="",
    loan_status_all="",
    loan_id="",
    order_id="",
    trans_id="",
    card_id="",
    earliest_card_issue="",
    latest_card_issue="",
    num_classic_cards=0,
    num_junior_cards=0,
    num_gold_cards=0,
    car_loan=0,
    personal_loan=0,
    business_loan=0,
    home_loan=0,
    gold_card=0,
    classic_card=0,
    junior_card=0,
)

# Write to CSV
pw.io.csv.write(final_features, f"{OUTPUT_PATH}/client_features.csv")

print("✓ Feature calculation pipeline configured")
print(f"✓ Output will be written to: {OUTPUT_PATH}/client_features.csv")
print("\n" + "="*80)
print("STARTING BATCH PROCESSING MODE")
print("="*80)
print("Pipeline will process:")
print("  - Data from present_tables/")
print("  - Output to data/client_features.csv")
print("\nNote: For streaming updates, use NATS publishers separately")
print("Press Ctrl+C to stop")
print("="*80 + "\n")

# Run the computation in batch mode
pw.run()
