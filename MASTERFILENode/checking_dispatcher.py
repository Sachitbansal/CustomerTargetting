#!/usr/bin/env python3
"""
Dispatcher Eligibility Checker
Analyzes temp_MASTERFILE_stream.csv to determine how many customers
qualify for each lead campaign based on dispatcher rules.
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# --- Configuration (Must match run_dispatcher_node.py) ---
TEMP_MASTERFILE = Path("./temp_MASTERFILE_stream.csv")

# Business Rule Thresholds
HOME_LOAN_VOLUME_THRESHOLD = 100_000
CAR_LOAN_VOLUME_THRESHOLD = 50_000
NIFTY50_VOLUME_THRESHOLD = 25_000
ELSS_VOLUME_THRESHOLD = 40_000

# Cooldown periods in days
HOME_LOAN_COOLDOWN_DAYS = 90
CAR_LOAN_COOLDOWN_DAYS = 45
NIFTY50_COOLDOWN_DAYS = 30
ELSS_COOLDOWN_DAYS = 60


def check_cooldown(last_reach_out, last_update, cooldown_days):
    """
    Check if customer is eligible based on cooldown period.
    Returns True if:
    1. Never contacted before (last_reach_out == "never")
    2. Contacted but cooldown period has passed
    """
    if last_reach_out == "never" or pd.isna(last_reach_out):
        return True
    
    try:
        last_contact_date = pd.to_datetime(last_reach_out)
        update_date = pd.to_datetime(last_update)
        days_since_contact = (update_date - last_contact_date).days
        return days_since_contact >= cooldown_days
    except:
        # If parsing fails, assume eligible
        return True


def analyze_dispatcher_eligibility():
    """Main analysis function"""
    
    print("═" * 70)
    print(" " * 20 + "DISPATCHER ELIGIBILITY CHECKER")
    print("═" * 70)
    print()
    
    # Check if file exists
    if not TEMP_MASTERFILE.exists():
        print(f"❌ ERROR: File not found: {TEMP_MASTERFILE}")
        print(f"   Make sure run_enrichment_node.py has generated this file.")
        return
    
    # Load data
    print(f"📂 Loading: {TEMP_MASTERFILE}")
    try:
        df = pd.read_csv(TEMP_MASTERFILE)
        print(f"✓ Loaded {len(df)} customer records")
        print()
    except Exception as e:
        print(f"❌ ERROR loading CSV: {e}")
        return
    
    # Verify required columns exist
    required_cols = [
        'customer_id', 'last_update_timestamp',
        'volTransLastStreamed_home', 'volTransLastStreamed_car',
        'volTransLastStreamed_nifty50', 'volTransLastStreamed_elss',
        'opted_home_loan', 'opted_car_loan',
        'recommend_nifty50', 'recommend_elss',
        'last_reach_out_home_loan', 'last_reach_out_car_loan',
        'last_reach_out_nifty50', 'last_reach_out_elss'
    ]
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ ERROR: Missing required columns: {missing_cols}")
        return
    
    # Convert to datetime
    df['last_update_timestamp'] = pd.to_datetime(df['last_update_timestamp'])
    
    # Initialize counters
    results = {
        'home_loan': {'eligible': 0, 'reasons': []},
        'car_loan': {'eligible': 0, 'reasons': []},
        'nifty50': {'eligible': 0, 'reasons': []},
        'elss': {'eligible': 0, 'reasons': []}
    }
    
    # Analyze each customer
    for idx, row in df.iterrows():
        cust_id = row['customer_id']
        
        # --- HOME LOAN ---
        home_volume_ok = row['volTransLastStreamed_home'] > HOME_LOAN_VOLUME_THRESHOLD
        home_not_opted = row['opted_home_loan'] == 0
        home_cooldown_ok = check_cooldown(
            row['last_reach_out_home_loan'],
            row['last_update_timestamp'],
            HOME_LOAN_COOLDOWN_DAYS
        )
        
        if home_volume_ok and home_not_opted and home_cooldown_ok:
            results['home_loan']['eligible'] += 1
            results['home_loan']['reasons'].append({
                'customer_id': cust_id,
                'volume': row['volTransLastStreamed_home'],
                'last_contact': row['last_reach_out_home_loan']
            })
        
        # --- CAR LOAN ---
        car_volume_ok = row['volTransLastStreamed_car'] > CAR_LOAN_VOLUME_THRESHOLD
        car_not_opted = row['opted_car_loan'] == 0
        car_cooldown_ok = check_cooldown(
            row['last_reach_out_car_loan'],
            row['last_update_timestamp'],
            CAR_LOAN_COOLDOWN_DAYS
        )
        
        if car_volume_ok and car_not_opted and car_cooldown_ok:
            results['car_loan']['eligible'] += 1
            results['car_loan']['reasons'].append({
                'customer_id': cust_id,
                'volume': row['volTransLastStreamed_car'],
                'last_contact': row['last_reach_out_car_loan']
            })
        
        # --- NIFTY50 ---
        nifty_volume_ok = row['volTransLastStreamed_nifty50'] > NIFTY50_VOLUME_THRESHOLD
        nifty_not_recommended = row['recommend_nifty50'] == 0
        nifty_cooldown_ok = check_cooldown(
            row['last_reach_out_nifty50'],
            row['last_update_timestamp'],
            NIFTY50_COOLDOWN_DAYS
        )
        
        if nifty_volume_ok and nifty_not_recommended and nifty_cooldown_ok:
            results['nifty50']['eligible'] += 1
            results['nifty50']['reasons'].append({
                'customer_id': cust_id,
                'volume': row['volTransLastStreamed_nifty50'],
                'last_contact': row['last_reach_out_nifty50']
            })
        
        # --- ELSS ---
        elss_volume_ok = row['volTransLastStreamed_elss'] > ELSS_VOLUME_THRESHOLD
        elss_not_recommended = row['recommend_elss'] == 0
        elss_cooldown_ok = check_cooldown(
            row['last_reach_out_elss'],
            row['last_update_timestamp'],
            ELSS_COOLDOWN_DAYS
        )
        
        if elss_volume_ok and elss_not_recommended and elss_cooldown_ok:
            results['elss']['eligible'] += 1
            results['elss']['reasons'].append({
                'customer_id': cust_id,
                'volume': row['volTransLastStreamed_elss'],
                'last_contact': row['last_reach_out_elss']
            })
    
    # --- PRINT RESULTS ---
    print("─" * 70)
    print(" " * 25 + "ELIGIBILITY SUMMARY")
    print("─" * 70)
    print()
    
    campaigns = [
        ('HOME LOAN', 'home_loan', HOME_LOAN_VOLUME_THRESHOLD, HOME_LOAN_COOLDOWN_DAYS),
        ('CAR LOAN', 'car_loan', CAR_LOAN_VOLUME_THRESHOLD, CAR_LOAN_COOLDOWN_DAYS),
        ('NIFTY50 SIP', 'nifty50', NIFTY50_VOLUME_THRESHOLD, NIFTY50_COOLDOWN_DAYS),
        ('ELSS', 'elss', ELSS_VOLUME_THRESHOLD, ELSS_COOLDOWN_DAYS)
    ]
    
    total_eligible = 0
    
    for campaign_name, key, threshold, cooldown in campaigns:
        count = results[key]['eligible']
        total_eligible += count
        
        print(f"📊 {campaign_name} LEADS")
        print(f"   ├─ Eligible Customers: {count}")
        print(f"   ├─ Volume Threshold: ₹{threshold:,}")
        print(f"   └─ Cooldown Period: {cooldown} days")
        print()
    
    print("─" * 70)
    print(f"✅ TOTAL ELIGIBLE LEADS ACROSS ALL CAMPAIGNS: {total_eligible}")
    print("─" * 70)
    print()
    
    # --- DETAILED BREAKDOWN (Optional) ---
    print("Would you like to see detailed customer breakdown? (y/n): ", end='')
    try:
        show_details = input().strip().lower() == 'y'
    except:
        show_details = False
    
    if show_details:
        print()
        print("=" * 70)
        print(" " * 25 + "DETAILED BREAKDOWN")
        print("=" * 70)
        
        for campaign_name, key, threshold, cooldown in campaigns:
            if results[key]['eligible'] > 0:
                print()
                print(f"\n{campaign_name} - Eligible Customers ({results[key]['eligible']}):")
                print("-" * 70)
                
                for i, customer in enumerate(results[key]['reasons'][:10], 1):  # Show first 10
                    print(f"  {i}. Customer: {customer['customer_id']}")
                    print(f"     Volume: ₹{customer['volume']:,.2f}")
                    print(f"     Last Contact: {customer['last_contact']}")
                    print()
                
                if len(results[key]['reasons']) > 10:
                    print(f"  ... and {len(results[key]['reasons']) - 10} more")
    
    print()
    print("✓ Analysis complete!")


if __name__ == "__main__":
    analyze_dispatcher_eligibility()