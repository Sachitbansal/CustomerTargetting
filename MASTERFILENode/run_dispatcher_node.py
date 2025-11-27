# MASTERFILENode/run_dispatcher_node.py (Fixed)
import pathway as pw
# --- PATH SETUP ---
from pathlib import Path
import sys
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))
from MASTERFILENode.schema import MasterSchema

# --- Configuration ---
INPUT_STREAM_FILE = "./temp_MASTERFILE_stream.csv"
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

    # Convert last_update_timestamp from string to datetime
    updated_customers = updated_customers.with_columns(
        last_update_timestamp=updated_customers.last_update_timestamp.dt.strptime(fmt="%Y-%m-%d")
    )
    
    # Convert all last_reach_out columns from string to datetime (handling "never")
    # First, we'll add columns that parse the dates when they're not "never"
    updated_customers = updated_customers.with_columns(
        last_reach_out_home_loan_dt=pw.if_else(
            updated_customers.last_reach_out_home_loan == "never",
            None,  # None for never reached out
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

    # --- Helper function for dynamic cooldown logic (FIXED) ---
    def create_cooldown_filter(last_reach_out_col, last_reach_out_dt_col, cooldown_days):
        # Condition 1: We have never reached out to them (datetime column is None)
        is_new_lead = pw.this[last_reach_out_dt_col].is_none()
        
        # Condition 2: We HAVE reached out, but enough time has passed
        # FIX: Only calculate time_diff when last_reach_out_dt_col is NOT None
        # We use pw.if_else to handle the nullable datetime
        days_since_last_contact = pw.if_else(
            pw.this[last_reach_out_dt_col].is_none(),
            999999,  # Set a very large number if never contacted (will pass cooldown)
            (pw.this.last_update_timestamp - pw.this[last_reach_out_dt_col]).dt.days()
        )
        
        # Check if enough days have passed
        is_ready_for_retry = days_since_last_contact >= cooldown_days
        
        return is_ready_for_retry

    # 2. --- Apply the business rules for each campaign stream ---
    
    # A) Home Loan Leads
    home_loan_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_home > HOME_LOAN_VOLUME_THRESHOLD) &
        (pw.this.opted_home_loan == 0) &
        create_cooldown_filter('last_reach_out_home_loan', 'last_reach_out_home_loan_dt', HOME_LOAN_COOLDOWN_DAYS)
    )
    print(f"✓ Home Loan lead rule configured (vol > {HOME_LOAN_VOLUME_THRESHOLD}, cooldown: {HOME_LOAN_COOLDOWN_DAYS} days)")

    # B) Car Loan Leads
    car_loan_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_car > CAR_LOAN_VOLUME_THRESHOLD) &
        (pw.this.opted_car_loan == 0) &
        create_cooldown_filter('last_reach_out_car_loan', 'last_reach_out_car_loan_dt', CAR_LOAN_COOLDOWN_DAYS)
    )
    print(f"✓ Car Loan lead rule configured (vol > {CAR_LOAN_VOLUME_THRESHOLD}, cooldown: {CAR_LOAN_COOLDOWN_DAYS} days)")

    # C) Nifty50 SIP Leads
    nifty50_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_nifty50 > NIFTY50_VOLUME_THRESHOLD) &
        (pw.this.recommend_nifty50 == 0) &
        create_cooldown_filter('last_reach_out_nifty50', 'last_reach_out_nifty50_dt', NIFTY50_COOLDOWN_DAYS)
    )
    print(f"✓ Nifty50 lead rule configured (vol > {NIFTY50_VOLUME_THRESHOLD}, cooldown: {NIFTY50_COOLDOWN_DAYS} days)")

    # D) ELSS Leads
    elss_leads = updated_customers.filter(
        (pw.this.volTransLastStreamed_elss > ELSS_VOLUME_THRESHOLD) &
        (pw.this.recommend_elss == 0) &
        create_cooldown_filter('last_reach_out_elss', 'last_reach_out_elss_dt', ELSS_COOLDOWN_DAYS)
    )
    print(f"✓ ELSS lead rule configured (vol > {ELSS_VOLUME_THRESHOLD}, cooldown: {ELSS_COOLDOWN_DAYS} days)")

    # 3. --- Write the qualified leads to their respective NATS topics ---
    pw.io.nats.write(home_loan_leads, uri=NATS_URI, topic=HOME_LOAN_LEADS_TOPIC, format="json")
    pw.io.nats.write(car_loan_leads, uri=NATS_URI, topic=CAR_LOAN_LEADS_TOPIC, format="json")
    pw.io.nats.write(nifty50_leads, uri=NATS_URI, topic=NIFTY50_LEADS_TOPIC, format="json")
    pw.io.nats.write(elss_leads, uri=NATS_URI, topic=ELSS_LEADS_TOPIC, format="json")
    
    print("\n✓ Publishing configured for all lead streams.\n")
    pw.run()

if __name__ == "__main__":
    run_dispatcher_node()