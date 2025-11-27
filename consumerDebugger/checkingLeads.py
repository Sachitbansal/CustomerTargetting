#!/usr/bin/env python3
"""
Complete Lead Printer - Displays ALL fields from incoming leads
"""

import pathway as pw
import sys
from pathlib import Path
from datetime import datetime

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

from MASTERFILENode.schema import MasterSchema

# --- Configuration ---
NATS_URI = "nats://localhost:4222"

def run_complete_printer(topic_name: str):
    """Listen and print ALL lead fields in real-time"""
    
    print("═" * 100)
    print(" " * 40 + "COMPLETE LEAD PRINTER")
    print("═" * 100)
    print(f"📡 Listening to: {topic_name}")
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 100)
    print()

    # Read from NATS
    leads = pw.io.nats.read(
        uri=NATS_URI,
        topic=topic_name,
        schema=MasterSchema,
        format="json",
        autocommit_duration_ms=100
    )

    # Create a formatted output string with ALL fields
    formatted = leads.select(
        output=pw.apply_with_type(
            lambda cid, age, gender, marital, dep, emp, occ, edu, city, income, acc_age, init_cs, loans, emi, 
                   credit_lim, init_util, init_bal, init_sav, auto, invest,
                   txn_30d, high_txn, bounced, final_bal, fuel, transport, inv_debit, final_cs,
                   dti, sav, inc_lim, txn_int, age_dep, score_inc,
                   opt_home, opt_car, rec_nif, rec_elss,
                   vol_home, vol_car, vol_elss, vol_nif,
                   last_home, last_car, last_nif, last_elss, last_upd: (
                f"\n{'=' * 100}\n"
                f"🎯 NEW LEAD RECEIVED\n"
                f"{'=' * 100}\n"
                f"\n📋 IDENTITY & DEMOGRAPHICS\n"
                f"{'-' * 100}\n"
                f"  Customer ID:          {cid}\n"
                f"  Age:                  {age}\n"
                f"  Gender:               {gender}\n"
                f"  Marital Status:       {marital}\n"
                f"  Dependents:           {dep}\n"
                f"  Employment Type:      {emp}\n"
                f"  Occupation:           {occ}\n"
                f"  Education Level:      {edu}\n"
                f"  City Tier:            {city}\n"
                f"\n💰 FINANCIAL PROFILE\n"
                f"{'-' * 100}\n"
                f"  Yearly Income:        ₹{income:,.2f}\n"
                f"  Account Age (months): {acc_age}\n"
                f"  Initial Credit Score: {init_cs}\n"
                f"  Final Credit Score:   {final_cs}\n"
                f"  Existing Loans Count: {loans}\n"
                f"  Monthly EMI Total:    ₹{emi:,.2f}\n"
                f"  Total Credit Limit:   ₹{credit_lim:,.2f}\n"
                f"  Has Auto Loan:        {auto}\n"
                f"  Has Investment Acct:  {invest}\n"
                f"\n💳 ACCOUNT BALANCES & UTILIZATION\n"
                f"{'-' * 100}\n"
                f"  Initial Avg Balance:  ₹{init_bal:,.2f}\n"
                f"  Final Avg Balance:    ₹{final_bal:,.2f}\n"
                f"  Initial Savings Rate: {init_sav:.4f}\n"
                f"  Current Savings Rate: {sav:.4f}\n"
                f"  Init Credit Util:     {init_util:.4f}\n"
                f"\n📊 TRANSACTION METRICS (Last 30 Days)\n"
                f"{'-' * 100}\n"
                f"  Transaction Count:    {txn_30d:.0f}\n"
                f"  High Value Txns:      {high_txn:.0f}\n"
                f"  Bounced Txns:         {bounced:.0f}\n"
                f"  Monthly Fuel Spend:   ₹{fuel:,.2f}\n"
                f"  Transport Spend:      ₹{transport:,.2f}\n"
                f"  Investment Debits:    ₹{inv_debit:,.2f}\n"
                f"\n📈 DERIVED FEATURES\n"
                f"{'-' * 100}\n"
                f"  DTI Ratio:            {dti:.4f}\n"
                f"  Income to Limit:      {inc_lim:.4f}\n"
                f"  Transaction Intensity:{txn_int:.4f}\n"
                f"  Age × Dependents:     {age_dep:.2f}\n"
                f"  Score × Log(Income):  {score_inc:.4f}\n"
                f"\n🎯 TARGET FLAGS\n"
                f"{'-' * 100}\n"
                f"  Opted Home Loan:      {opt_home}\n"
                f"  Opted Car Loan:       {opt_car}\n"
                f"  Recommend Nifty50:    {rec_nif}\n"
                f"  Recommend ELSS:       {rec_elss}\n"
                f"\n📊 VOLUME TRACKERS\n"
                f"{'-' * 100}\n"
                f"  Vol Home Loan:        ₹{vol_home:,.2f}\n"
                f"  Vol Car Loan:         ₹{vol_car:,.2f}\n"
                f"  Vol Nifty50:          ₹{vol_nif:,.2f}\n"
                f"  Vol ELSS:             ₹{vol_elss:,.2f}\n"
                f"\n📅 TRACKING TIMESTAMPS\n"
                f"{'-' * 100}\n"
                f"  Last Reach Out (Home):   {last_home}\n"
                f"  Last Reach Out (Car):    {last_car}\n"
                f"  Last Reach Out (Nifty):  {last_nif}\n"
                f"  Last Reach Out (ELSS):   {last_elss}\n"
                f"  Last Update Timestamp:   {last_upd}\n"
                f"{'=' * 100}\n\n"
            ),
            str,
            # Identity & Demographics
            pw.this.customer_id, pw.this.age, pw.this.gender, pw.this.marital_status, 
            pw.this.dependents_count, pw.this.employment_type, pw.this.occupation, 
            pw.this.education_level, pw.this.city_tier, pw.this.yearly_income, 
            # Financial Profile
            pw.this.account_age_months, pw.this.initial_credit_score, pw.this.existing_loans_count,
            pw.this.existing_loan_monthly_EMI_total, pw.this.total_credit_limit, 
            pw.this.initial_credit_utilization_ratio, pw.this.initial_avg_monthly_balance,
            pw.this.initial_savings_rate, pw.this.has_existing_auto_loan, 
            pw.this.has_existing_investment_account,
            # Transaction Metrics
            pw.this.txn_count_last_30d, pw.this.high_value_txn_count_30d, 
            pw.this.bounced_txn_count, pw.this.final_avg_monthly_balance,
            pw.this.monthly_fuel_spend, pw.this.monthly_transport_service_spend,
            pw.this.avg_monthly_investment_debit, pw.this.final_credit_score,
            # Derived Features
            pw.this.dti_ratio, pw.this.savings_rate, pw.this.income_to_limit,
            pw.this.txn_intensity, pw.this.age_x_dependents, pw.this.score_x_log_income,
            # Target Flags
            pw.this.opted_home_loan, pw.this.opted_car_loan, 
            pw.this.recommend_nifty50, pw.this.recommend_elss,
            # Volume Trackers
            pw.this.volTransLastStreamed_home, pw.this.volTransLastStreamed_car,
            pw.this.volTransLastStreamed_elss, pw.this.volTransLastStreamed_nifty50,
            # Tracking Timestamps
            pw.this.last_reach_out_home_loan, pw.this.last_reach_out_car_loan,
            pw.this.last_reach_out_nifty50, pw.this.last_reach_out_elss,
            pw.this.last_update_timestamp,
        )
    )

    # Print to console using debug method
    # Write to a temporary file that we can tail
    output_file = CURRENT_DIR / f"leads_{topic_name.replace('.', '_')}_detailed.jsonl"
    pw.io.jsonlines.write(formatted, str(output_file))
    
    print(f"✓ Writing detailed output to: {output_file}")
    print("✓ In another terminal, run: tail -f " + str(output_file))
    print("✓ Printer is running... Waiting for leads to arrive")
    print("✓ Press Ctrl+C to stop\n")
    
    # Run
    try:
        pw.run()
    except KeyboardInterrupt:
        print("\n\n✓ Stopped by user")


if __name__ == "__main__":
    topics = {
        "home": "leads.checkHomeLoan",
        "car": "leads.checkCarLoan",
        "nifty50": "leads.checkNifty50",
        "elss": "leads.checkElss",
    }
    
    if len(sys.argv) < 2:
        print("Usage: python complete_lead_printer.py <topic>\n")
        print("Shortcuts:")
        for key, val in topics.items():
            print(f"  {key:10s} → {val}")
        print("\nOr use full topic name:")
        print("  python complete_lead_printer.py leads.checkHomeLoan")
        sys.exit(1)
    
    arg = sys.argv[1]
    topic = topics.get(arg, arg)
    
    run_complete_printer(topic)