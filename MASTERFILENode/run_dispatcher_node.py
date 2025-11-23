# MASTERFILENode/run_dispatcher_node.py (Updated)
import pathway as pw
from MASTERFILENode.schema import MasterSchema
from pathlib import Path
import sys

# ... (imports remain the same) ...

# --- Configuration ---
INPUT_STREAM_FILE = "./MASTERFILENode/temp_MASTERFILE_stream.csv"
NATS_URI = "nats://localhost:4222"
HOME_LOAN_LEADS_TOPIC = "leads.checkHomeLoan"
CAR_LOAN_LEADS_TOPIC = "leads.checkCarLoan"
NIFTY50_LEADS_TOPIC = "leads.checkNifty50"
ELSS_LEADS_TOPIC = "leads.checkElss"

# --- Business Rule Thresholds ---
HOME_LOAN_VOLUME_THRESHOLD = 100_000
CAR_LOAN_VOLUME_THRESHOLD = 50_000
NIFTY50_VOLUME_THRESHOLD = 25_000
ELSS_VOLUME_THRESHOLD = 40_000

# NEW: Cooldown periods in days
HOME_LOAN_COOLDOWN_DAYS = 90
CAR_LOAN_COOLDOWN_DAYS = 45
NIFTY50_COOLDOWN_DAYS = 30
ELSS_COOLDOWN_DAYS = 60

def run_dispatcher_node():
    print("═══════════════════════════════════════════════")
    print("        LEAD DISPATCHER NODE                   ")
    print("═══════════════════════════════════════════════")

    updated_customers = pw.io.csv.read(
        INPUT_STREAM_FILE,
        schema=MasterSchema,
        mode="streaming",
        autocommit_duration_ms=100
    )
    print(f"✓ Listening for updated customer profiles from '{INPUT_STREAM_FILE}'")

    # --- Helper function for dynamic cooldown logic ---
    def create_cooldown_filter(last_reach_out_col, cooldown_days):
        cooldown_seconds = cooldown_days * 24 * 3600
        
        # Condition 1: We have never reached out to them.
        is_new_lead = pw.this[last_reach_out_col] == 'never'
        
        # Condition 2: We HAVE reached out, but enough time has passed.
        # We parse the string date and check the time difference in seconds.
        is_ready_for_retry = (pw.this[last_reach_out_col] != 'never') & \
                             ((pw.this.last_update_timestamp - pw.functions.from_iso_format(pw.this[last_reach_out_col])).total_seconds() > cooldown_seconds)
        
        return is_new_lead | is_ready_for_retry

    # 2. --- Apply the business rules for each campaign stream ---
    
    # A) Home Loan Leads
    home_loan_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_home > HOME_LOAN_VOLUME_THRESHOLD) &
        (pw.this.opted_home_loan == 0) &
        create_cooldown_filter('last_reach_out_home_loan', HOME_LOAN_COOLDOWN_DAYS)
    )
    print(f"✓ Home Loan lead rule configured (vol > {HOME_LOAN_VOLUME_THRESHOLD}, cooldown: {HOME_LOAN_COOLDOWN_DAYS} days)")

    # B) Car Loan Leads
    car_loan_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_car > CAR_LOAN_VOLUME_THRESHOLD) &
        (pw.this.opted_car_loan == 0) &
        create_cooldown_filter('last_reach_out_car_loan', CAR_LOAN_COOLDOWN_DAYS)
    )
    print(f"✓ Car Loan lead rule configured (vol > {CAR_LOAN_VOLUME_THRESHOLD}, cooldown: {CAR_LOAN_COOLDOWN_DAYS} days)")

    # C) Nifty50 SIP Leads
    nifty50_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_nifty50 > NIFTY50_VOLUME_THRESHOLD) &
        (pw.this.recommend_nifty50 == 0) &
        create_cooldown_filter('last_reach_out_nifty50', NIFTY50_COOLDOWN_DAYS)
    )
    print(f"✓ Nifty50 lead rule configured (vol > {NIFTY50_VOLUME_THRESHOLD}, cooldown: {NIFTY50_COOLDOWN_DAYS} days)")

    # D) ELSS Leads
    elss_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_elss > ELSS_VOLUME_THRESHOLD) &
        (pw.this.recommend_elss == 0) &
        create_cooldown_filter('last_reach_out_elss', ELSS_COOLDOWN_DAYS)
    )
    print(f"✓ ELSS lead rule configured (vol > {ELSS_VOLUME_THRESHOLD}, cooldown: {ELSS_COOLDOWN_DAYS} days)")

    # 3. --- Write the qualified leads to their respective NATS topics ---
    # ... (This section remains exactly the same) ...
    pw.io.nats.write(home_loan_leads, uri=NATS_URI, topic=HOME_LOAN_LEADS_TOPIC, format="json")
    pw.io.nats.write(car_loan_leads, uri=NATS_URI, topic=CAR_LOAN_LEADS_TOPIC, format="json")
    pw.io.nats.write(nifty50_leads, uri=NATS_URI, topic=NIFTY50_LEADS_TOPIC, format="json")
    pw.io.nats.write(elss_leads, uri=NATS_URI, topic=ELSS_LEADS_TOPIC, format="json")
    
    print("\n✓ Publishing configured for all lead streams.\n")
    pw.run()

if __name__ == "__main__":
    run_dispatcher_node()