#!/usr/bin/env python3
"""
Column Checker for temp_MASTERFILE_stream.csv
Verifies that all required columns exist for the dispatcher node
"""

import pandas as pd
from pathlib import Path

# Expected columns by dispatcher
REQUIRED_COLUMNS = [
    # Identity & Timestamp
    'customer_id',
    'last_update_timestamp',
    
    # Volume trackers (CRITICAL for dispatcher)
    'volTransLastStreamed_home',
    'volTransLastStreamed_car',
    'volTransLastStreamed_nifty50',
    'volTransLastStreamed_elss',
    
    # Opt-in flags (CRITICAL for dispatcher)
    'opted_home_loan',
    'opted_car_loan',
    'recommend_nifty50',
    'recommend_elss',
    
    # Last reach out tracking (CRITICAL for dispatcher)
    'last_reach_out_home_loan',
    'last_reach_out_car_loan',
    'last_reach_out_nifty50',
    'last_reach_out_elss',
]

def check_csv_columns():
    """Check if temp_MASTERFILE_stream.csv has all required columns"""
    
    csv_path = Path("./temp_MASTERFILE_stream.csv")
    
    print("═" * 70)
    print(" " * 20 + "CSV COLUMN CHECKER")
    print("═" * 70)
    print()
    
    if not csv_path.exists():
        print(f"❌ ERROR: File not found: {csv_path}")
        print(f"   Run enrichment node first to generate this file.")
        return
    
    print(f"📂 Checking: {csv_path}")
    print()
    
    try:
        # Read just the header
        df = pd.read_csv(csv_path, nrows=0)
        actual_columns = list(df.columns)
        
        print(f"✓ File loaded successfully")
        print(f"✓ Found {len(actual_columns)} columns in CSV")
        print()
        
        # Check for missing required columns
        missing = [col for col in REQUIRED_COLUMNS if col not in actual_columns]
        extra = [col for col in actual_columns if col not in REQUIRED_COLUMNS]
        
        print("─" * 70)
        print("REQUIRED COLUMNS CHECK:")
        print("─" * 70)
        
        if not missing:
            print("✅ ALL REQUIRED COLUMNS PRESENT!")
            print()
            for col in REQUIRED_COLUMNS:
                print(f"   ✓ {col}")
        else:
            print(f"❌ MISSING {len(missing)} REQUIRED COLUMNS:")
            print()
            for col in missing:
                print(f"   ✗ {col}")
        
        print()
        print("─" * 70)
        print("ACTUAL COLUMNS IN CSV:")
        print("─" * 70)
        
        for i, col in enumerate(actual_columns, 1):
            status = "✓" if col in REQUIRED_COLUMNS else "•"
            print(f"   {status} {i:2d}. {col}")
        
        if extra and len(actual_columns) > len(REQUIRED_COLUMNS):
            print()
            print(f"ℹ️  CSV has {len(extra)} additional columns (this is OK)")
        
        print()
        print("─" * 70)
        
        if missing:
            print()
            print("🔧 FIX REQUIRED:")
            print("   Update MASTERFILENode/logic.py to include these columns:")
            print()
            for col in missing:
                print(f'   "{col}": joined_data.{col},')
            print()
        else:
            print()
            print("✅ CSV is ready for dispatcher node!")
            print()
        
        # Try to read a few rows to check data
        print("─" * 70)
        print("SAMPLE DATA CHECK (first row):")
        print("─" * 70)
        
        df_sample = pd.read_csv(csv_path, nrows=1)
        
        for col in REQUIRED_COLUMNS[:5]:  # Show first 5 required columns
            if col in df_sample.columns:
                value = df_sample[col].iloc[0]
                print(f"   {col}: {value}")
        
        print("   ...")
        print()
        
    except Exception as e:
        print(f"❌ ERROR reading CSV: {e}")
        return
    
    print("✓ Check complete!")
    print()


if __name__ == "__main__":
    check_csv_columns()