# MASTERFILENode/run_enrichment_node.py (Debug Version with Logging)
import pathway as pw
from pathlib import Path
import sys
import time
import psutil
import os
from datetime import datetime
import logging

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

# --- IMPORTS ---
from dataUpdater.schema import MasterSchema
from dataUpdater.logic import calculate_new_state
from transactionPublisher.schema import TxnSchema

# Import metrics
from monitoring.metrics import (
    initialize_metrics,
    get_metrics_manager,
    record_master_match,
    record_transaction_volume,
    update_average_credit_score,
    record_bounced_event,
    record_high_value_event,
    record_enrichment_duration,
    set_nats_connection_status,
    update_nats_queue_depth,
    update_memory_usage,
    record_end_to_end_latency,
    MetricsTimer
)

# --- Configuration ---
MASTERFILE_PATH = PARENT_DIR / "MASTERFILE.csv" 

NATS_URI = "nats://localhost:4222"
NATS_INPUT_TOPIC = "transactions.stream"
NATS_OUTPUT_TOPIC = "updated.Customer"

# Metrics port for Enrichment
METRICS_PORT = 8002

# --- LOGGING SETUP ---
LOG_FILE = PARENT_DIR / "enrichment_debug.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)


def monitor_memory():
    """Background thread to monitor memory usage"""
    import threading
    
    process = psutil.Process(os.getpid())
    metrics_manager = get_metrics_manager()
    
    while True:
        try:
            memory_bytes = process.memory_info().rss
            update_memory_usage("enrichment", memory_bytes)
            metrics_manager.update_component_uptime()
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logger.warning(f"Memory monitoring error: {e}")
            time.sleep(5)


def run_enrichment_node():
    print("═══════════════════════════════════════════════")
    print("        CUSTOMER 360 ENRICHMENT NODE           ")
    print("═══════════════════════════════════════════════")
    logger.info("=" * 60)
    logger.info("ENRICHMENT NODE STARTING - DEBUG MODE")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 60)
    
    # Initialize Prometheus metrics
    metrics_manager = initialize_metrics("enrichment", port=METRICS_PORT)
    print()
    
    # Start memory monitoring thread
    import threading
    memory_thread = threading.Thread(target=monitor_memory, daemon=True)
    memory_thread.start()

    if not MASTERFILE_PATH.exists():
        logger.error(f"MASTERFILE not found: {MASTERFILE_PATH}")
        print(f"ERROR: Could not find {MASTERFILE_PATH}")
        metrics_manager.record_error("masterfile_not_found")
        return

    try:
        # Set NATS connection status
        set_nats_connection_status("enrichment", True)
        
        # 1. --- Load MASTERFILE ---
        logger.info(f"Loading MASTERFILE from: {MASTERFILE_PATH}")
        master_data = pw.io.csv.read(
            str(MASTERFILE_PATH),
            schema=MasterSchema,
            mode="static"
        ).with_id_from(pw.this.customer_id)
        
        # Add debug logging to master data
        @pw.udf
        def log_master_record(customer_id: str) -> str:
            """Log each master record loaded"""
            logger.info(f"[MASTER] Loaded customer: {customer_id}")
            return customer_id
        
        master_data = master_data.with_columns(
            _master_logged=log_master_record(pw.this.customer_id)
        )
        
        # 1b. Convert Master Dates (CSV format: YYYY-MM-DD)
        master_data = master_data.with_columns(
            last_update_timestamp=master_data.last_update_timestamp.dt.strptime(fmt="%Y-%m-%d")
        )
        
        logger.info("✓ MASTERFILE loaded and date conversion complete")

        # 2. --- Load TRANSACTIONS (streaming data) ---
        logger.info(f"Connecting to NATS: {NATS_URI}, topic: {NATS_INPUT_TOPIC}")
        transactions = pw.io.nats.read(
            uri=NATS_URI,
            topic=NATS_INPUT_TOPIC,
            schema=TxnSchema,
            format="json",
            autocommit_duration_ms=100
        )
        
        # 2a. Add ingestion timestamp with logging
        @pw.udf
        def get_ingestion_timestamp_with_log(customer_id: str, amount: float, category: str, txn_type: str, bounced: bool) -> int:
            """Return current timestamp and log transaction"""
            timestamp = int(time.time() * 1000)
            logger.info(f"[TRANSACTION] Ingested - Customer: {customer_id}, Type: {txn_type}, Amount: {amount}, Category: {category}, Bounced: {bounced}, Timestamp: {timestamp}")
            return timestamp
        
        transactions = transactions.with_columns(
            _ingestion_time=get_ingestion_timestamp_with_log(
                pw.this.customer_id,
                pw.this.txn_amount,
                pw.this.txn_category,
                pw.this.txn_type,
                pw.this.bounced_flag
            )
        )
        
        # 2b. Convert Transaction Dates
        transactions = transactions.with_columns(
            txn_datetime=transactions.txn_datetime.dt.strptime(fmt="%Y-%m-%d")
        )
        
        logger.info("✓ Connected to NATS and transaction logging enabled")
        print(f"✓ Connected to NATS '{NATS_INPUT_TOPIC}' and MASTERFILE")

        # 3. --- AGGREGATE Transactions with Metrics Tracking ---
        logger.info("Setting up transaction aggregation...")
        
        # First, add absolute value column for easier aggregation
        transactions = transactions.with_columns(
            abs_amount=pw.if_else(pw.this.txn_amount < 0, -pw.this.txn_amount, pw.this.txn_amount)
        )
        
        # Add UDFs to track metrics during aggregation
        @pw.udf
        def track_transaction_metrics(customer_id: str, amount: float, bounced: bool) -> float:
            """Track enrichment metrics for each transaction - returns amount for use downstream"""
            logger.debug(f"[METRICS] Tracking transaction - Customer: {customer_id}, Amount: {amount}, Bounced: {bounced}")
            
            # Record transaction volume
            record_transaction_volume(abs(amount))
            
            # Record bounced events
            if bounced:
                record_bounced_event(component="enrichment")
                logger.info(f"[BOUNCED] Customer {customer_id} had bounced transaction")
            
            # Record high-value transactions
            if abs(amount) > 50000:
                record_high_value_event("above_50k")
                logger.info(f"[HIGH_VALUE] Customer {customer_id} transaction > 50K: {amount}")
            if abs(amount) > 100000:
                record_high_value_event("above_100k")
                logger.info(f"[HIGH_VALUE] Customer {customer_id} transaction > 100K: {amount}")
            
            return abs(amount)
        
        # Track metrics for each transaction AND use the result
        transactions = transactions.with_columns(
            _tracked_amount=track_transaction_metrics(
                pw.this.customer_id, 
                pw.this.txn_amount, 
                pw.this.bounced_flag
            )
        )
        
        # Aggregate transactions and preserve earliest ingestion time
        @pw.udf
        def log_aggregation(customer_id: str, count: int, total: float) -> int:
            """Log aggregation results"""
            logger.info(f"[AGGREGATION] Customer: {customer_id}, Txn Count: {count}, Total Amount: {total}")
            return count
        
        txn_stats = transactions.groupby(pw.this.customer_id).reduce(
            customer_id=pw.this.customer_id,
            
            # Preserve earliest ingestion timestamp for latency calculation
            _earliest_ingestion=pw.reducers.min(pw.this._ingestion_time),
            
            # Simple Counts and Sums
            num_new_txns=pw.reducers.count(),
            total_amount_change=pw.reducers.sum(pw.this.txn_amount),
            vol_increase=pw.reducers.sum(pw.this._tracked_amount),
            
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
        
        # Log aggregation results
        txn_stats = txn_stats.with_columns(
            _agg_logged=log_aggregation(
                pw.this.customer_id,
                pw.this.num_new_txns,
                pw.this.total_amount_change
            )
        )
        
        logger.info("✓ Transaction aggregation configured")

        # 4. --- JOIN Master + Stats with DETAILED LOGGING ---
        logger.info("Attempting to join MASTERFILE with transaction stats...")
        logger.info("This is the CRITICAL step - checking if joins actually happen...")
        
        @pw.udf
        def log_before_join_master(customer_id: str) -> str:
            """Log master side before join"""
            logger.info(f"[PRE-JOIN MASTER] Customer {customer_id} exists in MASTERFILE")
            return customer_id
        
        @pw.udf
        def log_before_join_txn(customer_id: str) -> str:
            """Log transaction side before join"""
            logger.info(f"[PRE-JOIN TXN] Customer {customer_id} has aggregated transactions")
            return customer_id
        
        # Log both sides before join
        master_data = master_data.with_columns(
            _pre_join_master=log_before_join_master(pw.this.customer_id)
        )
        
        txn_stats = txn_stats.with_columns(
            _pre_join_txn=log_before_join_txn(pw.this.customer_id)
        )
        
        # Perform the join
        combined_data = master_data.join(
            txn_stats,
            pw.left.customer_id == pw.right.customer_id,
            how=pw.JoinMode.INNER
        ).select(
            *pw.left,
            *pw.right.without(pw.this.customer_id),
        )
        
        # Log AFTER join to confirm it happened
        @pw.udf
        def log_successful_join(customer_id: str, num_txns: int) -> str:
            """Log successful join"""
            logger.info(f"[✓ JOIN SUCCESS] Customer {customer_id} matched! Processing {num_txns} transactions")
            try:
                record_master_match(success=True)  # Track metrics here
                logger.info(f"[METRICS] Successfully recorded master_match for {customer_id}")
            except Exception as e:
                logger.error(f"[METRICS ERROR] Failed to record master_match: {e}")
            return customer_id
        
        combined_data = combined_data.with_columns(
            _join_success=log_successful_join(pw.this.customer_id, pw.this.num_new_txns)
        )
        
        logger.info("✓ Join operation configured with logging")

        # 5. --- CALCULATE New State ---
        logger.info("Calculating new customer state...")
        
        # First, ensure join tracking is executed by filtering on it
        combined_data_tracked = combined_data.filter(
            pw.this._join_success == pw.this.customer_id  # Always true, forces UDF execution
        )
        
        updated_customers = combined_data_tracked.select(
            **calculate_new_state(combined_data_tracked)
        )
        
        # Log enrichment completion
        @pw.udf
        def log_enrichment_complete(customer_id: str, credit_score: float) -> int:
            """Log enrichment completion"""
            timestamp = int(time.time() * 1000)
            logger.info(f"[ENRICHMENT COMPLETE] Customer {customer_id}, New Credit Score: {credit_score:.2f}")
            return timestamp
        
        updated_customers = updated_customers.with_columns(
            _processing_end=log_enrichment_complete(
                pw.this.customer_id,
                pw.this.final_credit_score
            )
        )
        
        logger.info("✓ Enrichment logic configured")
        
        # 6. --- Track Latency (simplified for debugging) ---
        @pw.udf
        def track_latency_simple(customer_id: str, credit_score: float) -> str:
            """Simplified latency tracking with logging"""
            logger.info(f"[LATENCY TRACKED] Customer {customer_id}")
            update_average_credit_score(credit_score)
            return customer_id
        
        updated_customers = updated_customers.with_columns(
            _latency_tracked=track_latency_simple(
                pw.this.customer_id,
                pw.this.final_credit_score
            )
        )
        
        # Force execution with filter
        updated_customers = updated_customers.filter(
            pw.this._latency_tracked == pw.this.customer_id
        )
        
        # 7. --- Convert datetime back to simple date string format for JSON ---
        updated_customers_final = updated_customers.with_columns(
            last_update_timestamp=updated_customers.last_update_timestamp.dt.strftime(fmt="%Y-%m-%d")
        )
        
        # Log final output
        @pw.udf
        def log_output(customer_id: str) -> str:
            """Log each output record"""
            logger.info(f"[OUTPUT] Publishing customer {customer_id} to NATS")
            return customer_id
        
        updated_customers_final = updated_customers_final.with_columns(
            _output_logged=log_output(pw.this.customer_id)
        )
        
        # Remove internal tracking columns before output
        updated_customers_output = updated_customers_final.without(
            pw.this._processing_end,
            pw.this._latency_tracked,
            pw.this._output_logged
        )
        
        logger.info("✓ Enrichment pipeline fully configured with comprehensive logging")
        print("✓ Enrichment pipeline configured with latency tracking")
        print(f"✓ Metrics available at: http://localhost:{METRICS_PORT}/metrics")
        print(f"✓ DEBUG LOG: {LOG_FILE}")
        print("=" * 60)
        print("WATCHING FOR ACTIVITY - Check log file for details")
        print("=" * 60)
        
        # 8. --- Write OUTPUT to NATS ---
        pw.io.nats.write(
            updated_customers_output,
            uri=NATS_URI,
            topic=NATS_OUTPUT_TOPIC,
            format="json"
        )
        logger.info(f"✓ Output configured to NATS topic '{NATS_OUTPUT_TOPIC}'")
        print(f"✓ Publishing updated customers to NATS topic '{NATS_OUTPUT_TOPIC}'\n")

        logger.info("=" * 60)
        logger.info("STARTING PATHWAY RUNTIME - Waiting for transactions...")
        logger.info("=" * 60)
        
        pw.run()
        
    except Exception as e:
        logger.error(f"Enrichment error: {e}", exc_info=True)
        print(f"❌ Enrichment error: {e}")
        set_nats_connection_status("enrichment", False)
        metrics_manager.record_error(type(e).__name__)
        raise


if __name__ == "__main__":
    run_enrichment_node()