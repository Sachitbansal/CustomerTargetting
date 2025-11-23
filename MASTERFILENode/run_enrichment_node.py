# MASTERFILENode/run_enrichment_node.py
import pathway as pw
from MASTERFILENode.schema import MasterSchema
from MASTERFILENode.logic import update_customer_profile
from pathlib import Path
import sys

# Ensure root directory is in path for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
# Import the transaction schema from the publisher
from transactionPublisher.schema import TxnSchema

# --- Configuration ---
MASTERFILE_PATH = "./MASTERFILE.csv"
TEMP_OUTPUT_STREAM_FILE = "./MASTERFILENode/temp_MASTERFILE_stream.csv"
NATS_URI = "nats://localhost:4222"
NATS_TOPIC = "transactions.stream"

def run_enrichment_node():
    print("═══════════════════════════════════════════════")
    print("        CUSTOMER 360 ENRICHMENT NODE           ")
    print("═══════════════════════════════════════════════")

    # 1. --- Load the initial state from MASTERFILE.csv ---
    # This becomes our stateful table that we will update in real-time.
    master_data = pw.io.csv.read(
        MASTERFILE_PATH,
        schema=MasterSchema,
        mode="static",
        key="customer_id"
    )
    print(f"✓ Initialized state with {master_data.shape[0]} customers from '{MASTERFILE_PATH}'")

    # 2. --- Connect to the NATS transaction stream ---
    transactions = pw.io.nats.read(
        uri=NATS_URI,
        topic=NATS_TOPIC,
        schema=TxnSchema,
        format="json",
        autocommit_duration_ms=100
    )
    print(f"✓ Listening for transactions on NATS topic '{NATS_TOPIC}'")

    # 3. --- Join the transaction stream with the master data state ---
    # This enriches the transaction with the customer's current profile.
    enriched_transactions = master_data.join(
        transactions,
        on=pw.left.customer_id == pw.right.customer_id
    )

    # 4. --- Apply the update logic ---
    # The `update` method is key. It applies our logic function to modify the state
    # for each customer who has new transactions.
    updated_customers = master_data.update(
        enriched_transactions,
        mapper=update_customer_profile
    )
    print("✓ Update logic is configured. Ready to process transactions.")
    
    # 5. --- Write ONLY the updated rows to the output temp file ---
    # `updated_customers` is a stream that contains only the customer profiles
    # that were modified in a given time window.
    pw.io.csv.write(
        updated_customers,
        TEMP_OUTPUT_STREAM_FILE,
        mode="streaming"
    )
    print(f"✓ Will write updated customer profiles to '{TEMP_OUTPUT_STREAM_FILE}'\n")

    # 6. --- Run the Pathway pipeline ---
    pw.run()

if __name__ == "__main__":
    run_enrichment_node()