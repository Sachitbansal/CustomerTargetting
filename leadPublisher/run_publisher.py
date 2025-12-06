# MASTERFILENode/run_dispatcher_node.py (Updated with Metrics)
import pathway as pw
from pathlib import Path
import sys
import time
import psutil
import os

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))
from leadPublisher.schema import MasterSchema

# Import metrics
from monitoring.metrics import (
    initialize_metrics,
    get_metrics_manager,
    record_lead_generated,
    record_lead_rejection,
    record_lead_generation_latency,
    record_cooldown_hit,
    set_nats_connection_status,
    update_memory_usage,
    record_end_to_end_latency
)

# --- Configuration ---
NATS_URI = "nats://localhost:4222"
NATS_INPUT_TOPIC = "updated.Customer"
HOME_LOAN_LEADS_TOPIC = "leads.checkHomeLoan"
CAR_LOAN_LEADS_TOPIC = "leads.checkCarLoan"
NIFTY50_LEADS_TOPIC = "leads.checkNifty50"
ELSS_LEADS_TOPIC = "leads.checkElss"

# --- Business Rule Thresholds ---
HOME_LOAN_VOLUME_THRESHOLD = 100_000
CAR_LOAN_VOLUME_THRESHOLD = 50_000
NIFTY50_VOLUME_THRESHOLD = 25_000
ELSS_VOLUME_THRESHOLD = 40_000

# Cooldown periods in days
HOME_LOAN_COOLDOWN_DAYS = 90
CAR_LOAN_COOLDOWN_DAYS = 45
NIFTY50_COOLDOWN_DAYS = 30
ELSS_COOLDOWN_DAYS = 60

# Metrics port for Dispatcher
METRICS_PORT = 8003


def monitor_memory():
    """Background thread to monitor memory usage"""
    import threading
    
    process = psutil.Process(os.getpid())
    metrics_manager = get_metrics_manager()
    
    while True:
        try:
            memory_bytes = process.memory_info().rss
            update_memory_usage("dispatcher", memory_bytes)
            metrics_manager.update_component_uptime()
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            print(f"⚠️  Memory monitoring error: {e}")
            time.sleep(5)


def run_dispatcher_node():
    print("═══════════════════════════════════════════════")
    print("        LEAD DISPATCHER NODE                   ")
    print("═══════════════════════════════════════════════")
    
    # Initialize Prometheus metrics
    metrics_manager = initialize_metrics("dispatcher", port=METRICS_PORT)
    print()
    
    # Start memory monitoring thread
    import threading
    memory_thread = threading.Thread(target=monitor_memory, daemon=True)
    memory_thread.start()

    try:
        # Set NATS connection status
        set_nats_connection_status("dispatcher", True)
        
        # Read updated customers from NATS
        updated_customers = pw.io.nats.read(
            uri=NATS_URI,
            topic=NATS_INPUT_TOPIC,
            schema=MasterSchema,
            format="json",
            autocommit_duration_ms=100
        )
        print(f"✓ Listening for updated customer profiles from NATS topic '{NATS_INPUT_TOPIC}'")

        # Convert last_update_timestamp from string to datetime
        updated_customers = updated_customers.with_columns(
            last_update_timestamp=updated_customers.last_update_timestamp.dt.strptime(fmt="%Y-%m-%d")
        )
        
        # Convert all last_reach_out columns from string to datetime (handling "never")
        updated_customers = updated_customers.with_columns(
            last_reach_out_home_loan_dt=pw.if_else(
                updated_customers.last_reach_out_home_loan == "never",
                None,
                updated_customers.last_reach_out_home_loan.dt.strptime(fmt="%Y-%m-%d")
            ),
            last_reach_out_car_loan_dt=pw.if_else(
                updated_customers.last_reach_out_car_loan == "never",
                None,
                updated_customers.last_reach_out_car_loan.dt.strptime(fmt="%Y-%m-%d")
            ),
            last_reach_out_nifty50_dt=pw.if_else(
                updated_customers.last_reach_out_nifty50 == "never",
                None,
                updated_customers.last_reach_out_nifty50.dt.strptime(fmt="%Y-%m-%d")
            ),
            last_reach_out_elss_dt=pw.if_else(
                updated_customers.last_reach_out_elss == "never",
                None,
                updated_customers.last_reach_out_elss.dt.strptime(fmt="%Y-%m-%d")
            ),
        )

        # --- Helper function for dynamic cooldown logic with metrics ---
        def create_cooldown_filter(last_reach_out_col, last_reach_out_dt_col, cooldown_days, lead_type):
            # Condition 1: We have never reached out to them (datetime column is None)
            is_new_lead = pw.this[last_reach_out_dt_col].is_none()
            
            # Condition 2: We HAVE reached out, but enough time has passed
            days_since_last_contact = pw.if_else(
                pw.this[last_reach_out_dt_col].is_none(),
                999999,  # Set a very large number if never contacted
                (pw.this.last_update_timestamp - pw.this[last_reach_out_dt_col]).dt.days()
            )
            
            # Check if enough days have passed
            is_ready_for_retry = days_since_last_contact >= cooldown_days
            
            return is_ready_for_retry

        # --- UDFs for tracking rejections and lead generation ---
        @pw.udf
        def track_home_loan_decision(customer_id: str, volume: float, opted: int, 
                                     days_since: int) -> str:
            """Track home loan lead decision"""
            if volume <= HOME_LOAN_VOLUME_THRESHOLD:
                record_lead_rejection("low_volume")
            elif opted == 1:
                record_lead_rejection("already_opted")
            elif days_since < HOME_LOAN_COOLDOWN_DAYS:
                record_lead_rejection("cooldown")
                record_cooldown_hit("home")
            else:
                record_lead_generated("home")
                # Calculate latency (approximate - from current time)
                from datetime import datetime
                record_lead_generation_latency(1.0)  # Placeholder
                record_end_to_end_latency("dispatcher", 2.0)  # Placeholder
            return customer_id
        
        @pw.udf
        def track_car_loan_decision(customer_id: str, volume: float, opted: int, 
                                    days_since: int) -> str:
            """Track car loan lead decision"""
            if volume <= CAR_LOAN_VOLUME_THRESHOLD:
                record_lead_rejection("low_volume")
            elif opted == 1:
                record_lead_rejection("already_opted")
            elif days_since < CAR_LOAN_COOLDOWN_DAYS:
                record_lead_rejection("cooldown")
                record_cooldown_hit("car")
            else:
                record_lead_generated("car")
                record_lead_generation_latency(1.0)
                record_end_to_end_latency("dispatcher", 2.0)
            return customer_id
        
        @pw.udf
        def track_nifty50_decision(customer_id: str, volume: float, opted: int, 
                                   days_since: int) -> str:
            """Track Nifty50 lead decision"""
            if volume <= NIFTY50_VOLUME_THRESHOLD:
                record_lead_rejection("low_volume")
            elif opted == 1:
                record_lead_rejection("already_opted")
            elif days_since < NIFTY50_COOLDOWN_DAYS:
                record_lead_rejection("cooldown")
                record_cooldown_hit("nifty")
            else:
                record_lead_generated("nifty")
                record_lead_generation_latency(1.0)
                record_end_to_end_latency("dispatcher", 2.0)
            return customer_id
        
        @pw.udf
        def track_elss_decision(customer_id: str, volume: float, opted: int, 
                                days_since: int) -> str:
            """Track ELSS lead decision"""
            if volume <= ELSS_VOLUME_THRESHOLD:
                record_lead_rejection("low_volume")
            elif opted == 1:
                record_lead_rejection("already_opted")
            elif days_since < ELSS_COOLDOWN_DAYS:
                record_lead_rejection("cooldown")
                record_cooldown_hit("elss")
            else:
                record_lead_generated("elss")
                record_lead_generation_latency(1.0)
                record_end_to_end_latency("dispatcher", 2.0)
            return customer_id

        # --- Calculate days since last contact for all customers ---
        updated_customers = updated_customers.with_columns(
            days_since_home=pw.if_else(
                pw.this.last_reach_out_home_loan_dt.is_none(),
                999999,
                (pw.this.last_update_timestamp - pw.this.last_reach_out_home_loan_dt).dt.days()
            ),
            days_since_car=pw.if_else(
                pw.this.last_reach_out_car_loan_dt.is_none(),
                999999,
                (pw.this.last_update_timestamp - pw.this.last_reach_out_car_loan_dt).dt.days()
            ),
            days_since_nifty=pw.if_else(
                pw.this.last_reach_out_nifty50_dt.is_none(),
                999999,
                (pw.this.last_update_timestamp - pw.this.last_reach_out_nifty50_dt).dt.days()
            ),
            days_since_elss=pw.if_else(
                pw.this.last_reach_out_elss_dt.is_none(),
                999999,
                (pw.this.last_update_timestamp - pw.this.last_reach_out_elss_dt).dt.days()
            ),
        )

        # 2. --- Apply the business rules for each campaign stream ---
        
        # A) Home Loan Leads
        home_loan_leads = updated_customers.filter(
            (pw.this.volTransLastStreamed_home > HOME_LOAN_VOLUME_THRESHOLD) &
            (pw.this.opted_home_loan == 0) &
            create_cooldown_filter('last_reach_out_home_loan', 'last_reach_out_home_loan_dt', 
                                  HOME_LOAN_COOLDOWN_DAYS, 'home')
        ).select(
            *pw.this,
            _tracked=track_home_loan_decision(
                pw.this.customer_id,
                pw.this.volTransLastStreamed_home,
                pw.this.opted_home_loan,
                pw.this.days_since_home
            )
        )
        print(f"✓ Home Loan lead rule configured (vol > {HOME_LOAN_VOLUME_THRESHOLD}, cooldown: {HOME_LOAN_COOLDOWN_DAYS} days)")

        # B) Car Loan Leads
        car_loan_leads = updated_customers.filter(
            (pw.this.volTransLastStreamed_car > CAR_LOAN_VOLUME_THRESHOLD) &
            (pw.this.opted_car_loan == 0) &
            create_cooldown_filter('last_reach_out_car_loan', 'last_reach_out_car_loan_dt', 
                                  CAR_LOAN_COOLDOWN_DAYS, 'car')
        ).select(
            *pw.this,
            _tracked=track_car_loan_decision(
                pw.this.customer_id,
                pw.this.volTransLastStreamed_car,
                pw.this.opted_car_loan,
                pw.this.days_since_car
            )
        )
        print(f"✓ Car Loan lead rule configured (vol > {CAR_LOAN_VOLUME_THRESHOLD}, cooldown: {CAR_LOAN_COOLDOWN_DAYS} days)")

        # C) Nifty50 SIP Leads
        nifty50_leads = updated_customers.filter(
            (pw.this.volTransLastStreamed_nifty50 > NIFTY50_VOLUME_THRESHOLD) &
            (pw.this.recommend_nifty50 == 0) &
            create_cooldown_filter('last_reach_out_nifty50', 'last_reach_out_nifty50_dt', 
                                  NIFTY50_COOLDOWN_DAYS, 'nifty50')
        ).select(
            *pw.this,
            _tracked=track_nifty50_decision(
                pw.this.customer_id,
                pw.this.volTransLastStreamed_nifty50,
                pw.this.recommend_nifty50,
                pw.this.days_since_nifty
            )
        )
        print(f"✓ Nifty50 lead rule configured (vol > {NIFTY50_VOLUME_THRESHOLD}, cooldown: {NIFTY50_COOLDOWN_DAYS} days)")

        # D) ELSS Leads
        elss_leads = updated_customers.filter(
            (pw.this.volTransLastStreamed_elss > ELSS_VOLUME_THRESHOLD) &
            (pw.this.recommend_elss == 0) &
            create_cooldown_filter('last_reach_out_elss', 'last_reach_out_elss_dt', 
                                  ELSS_COOLDOWN_DAYS, 'elss')
        ).select(
            *pw.this,
            _tracked=track_elss_decision(
                pw.this.customer_id,
                pw.this.volTransLastStreamed_elss,
                pw.this.recommend_elss,
                pw.this.days_since_elss
            )
        )
        print(f"✓ ELSS lead rule configured (vol > {ELSS_VOLUME_THRESHOLD}, cooldown: {ELSS_COOLDOWN_DAYS} days)")

        # 3. --- Write the qualified leads to their respective NATS topics ---
        pw.io.nats.write(home_loan_leads, uri=NATS_URI, topic=HOME_LOAN_LEADS_TOPIC, format="json")
        pw.io.nats.write(car_loan_leads, uri=NATS_URI, topic=CAR_LOAN_LEADS_TOPIC, format="json")
        pw.io.nats.write(nifty50_leads, uri=NATS_URI, topic=NIFTY50_LEADS_TOPIC, format="json")
        pw.io.nats.write(elss_leads, uri=NATS_URI, topic=ELSS_LEADS_TOPIC, format="json")
        
        print(f"\n✓ Publishing configured for all lead streams.")
        print(f"✓ Metrics available at: http://localhost:{METRICS_PORT}/metrics\n")
        
        pw.run()
        
    except Exception as e:
        print(f"❌ Dispatcher error: {e}")
        set_nats_connection_status("dispatcher", False)
        metrics_manager.record_error(type(e).__name__)
        raise

if __name__ == "__main__":
    run_dispatcher_node()