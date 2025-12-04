# MASTERFILENode/run_enrichment_node.py (NATS Output Version)
import pathway as pw
from pathlib import Path
import sys

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

# --- IMPORTS ---
from dataUpdater.schema import MasterSchema
from dataUpdater.logic import calculate_new_state
from transactionPublisher.schema import TxnSchema

# --- Configuration ---
MASTERFILE_PATH = PARENT_DIR / "MASTERFILE.csv" 

NATS_URI = "nats://localhost:4222"
NATS_INPUT_TOPIC = "transactions.stream"
NATS_OUTPUT_TOPIC = "updated.Customer"

def run_enrichment_node():
    print("═══════════════════════════════════════════════")
    print("        CUSTOMER 360 ENRICHMENT NODE           ")
    print("═══════════════════════════════════════════════")

    if not MASTERFILE_PATH.exists():
        print(f"ERROR: Could not find {MASTERFILE_PATH}")
        return

    # 1. --- Load MASTERFILE ---
    master_data = pw.io.csv.read(
        str(MASTERFILE_PATH),
        schema=MasterSchema,
        mode="static"
    ).with_id_from(pw.this.customer_id)
    
    # 1b. Convert Master Dates (CSV format: YYYY-MM-DD)
    master_data = master_data.with_columns(
        last_update_timestamp=master_data.last_update_timestamp.dt.strptime(fmt="%Y-%m-%d")
    )

    # 2. --- Load TRANSACTIONS ---
    transactions = pw.io.nats.read(
        uri=NATS_URI,
        topic=NATS_INPUT_TOPIC,
        schema=TxnSchema,
        format="json",
        autocommit_duration_ms=100
    )
    
    # 2b. Convert Transaction Dates
    # Parse simple date format from publisher (YYYY-MM-DD)
    transactions = transactions.with_columns(
        txn_datetime=transactions.txn_datetime.dt.strptime(fmt="%Y-%m-%d")
    )
    
    print(f"✓ Connected to NATS '{NATS_INPUT_TOPIC}' and MASTERFILE")

    # 3. --- AGGREGATE Transactions ---
    # First, add absolute value column for easier aggregation
    transactions = transactions.with_columns(
        abs_amount=pw.if_else(pw.this.txn_amount < 0, -pw.this.txn_amount, pw.this.txn_amount)
    )
    
    txn_stats = transactions.groupby(pw.this.customer_id).reduce(
        customer_id=pw.this.customer_id,
        
        # Simple Counts and Sums
        num_new_txns=pw.reducers.count(),
        total_amount_change=pw.reducers.sum(pw.this.txn_amount),
        vol_increase=pw.reducers.sum(pw.this.abs_amount),
        
        bounced_count_change=pw.reducers.sum(pw.cast(int, pw.this.bounced_flag)),
        
        max_txn_time=pw.reducers.max(pw.this.txn_datetime),
        
        # Conditional Count: Successful Debits
        successful_debits_count=pw.reducers.sum(
            pw.if_else(
                (pw.this.txn_amount < 0) & (pw.this.bounced_flag == False),
                1, 
                0
            )
        ),
        
        # Conditional Sums: Category Spend (using abs_amount)
        fuel_spend_change=pw.reducers.sum(
            pw.if_else(pw.this.txn_category == "Fuel", pw.this.abs_amount, 0.0)
        ),
        transport_spend_change=pw.reducers.sum(
            pw.if_else(pw.this.txn_category == "Transport", pw.this.abs_amount, 0.0)
        ),
        investment_debit_change=pw.reducers.sum(
            pw.if_else(pw.this.txn_category == "Investment", pw.this.abs_amount, 0.0)
        ),
    )

    # 4. --- JOIN Master + Stats ---
    # Simple join - only processes customers who have transactions
    # (This is fine for your use case since you're only enriching when new txns arrive)
    combined_data = master_data.join(
        txn_stats,
        pw.left.customer_id == pw.right.customer_id
    )

    # 5. --- CALCULATE New State ---
    updated_customers = combined_data.select(
        **calculate_new_state(combined_data)
    )
    
    # 5b. --- Convert datetime back to simple date string format for JSON ---
    # This ensures consistent date format in NATS messages
    updated_customers = updated_customers.with_columns(
        last_update_timestamp=updated_customers.last_update_timestamp.dt.strftime(fmt="%Y-%m-%d")
    )
    
    print("✓ Enrichment pipeline configured (Group -> Reduce -> Join -> Select)")
    
    # 6. --- Write OUTPUT to NATS ---
    pw.io.nats.write(
        updated_customers,
        uri=NATS_URI,
        topic=NATS_OUTPUT_TOPIC,
        format="json"
    )
    print(f"✓ Publishing updated customers to NATS topic '{NATS_OUTPUT_TOPIC}'\n")

    pw.run()

if __name__ == "__main__":
    run_enrichment_node()