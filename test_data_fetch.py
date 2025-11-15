"""
Test Script for data_fetch.py

This script helps verify that the Pathway pipeline is set up correctly
and can process a small sample of data.

Usage:
    python test_data_fetch.py
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path

print("="*80)
print("DATA_FETCH.PY TEST SCRIPT")
print("="*80 + "\n")

# === 1. Check if Pathway is installed ===
print("1. Checking Pathway installation...")
try:
    import pathway as pw
    print(f"   ✓ Pathway {pw.__version__} is installed")

    # Set license key
    pw.set_license_key("B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3")
    print(f"   ✓ License key configured\n")
except ImportError:
    print("   ✗ Pathway is not installed!")
    print("   Install it with: pip install pathway")
    sys.exit(1)

# === 2. Check if present_tables directory exists ===
print("2. Checking data directories...")
present_path = Path("data/present_tables")
stream_path = Path("data/stream_tables")
output_path = Path("data/pathway_output")

if not present_path.exists():
    print(f"   ✗ {present_path} does not exist!")
    print("   Please run the data preprocessing scripts first.")
    sys.exit(1)
else:
    print(f"   ✓ {present_path} exists")

if not stream_path.exists():
    print(f"   ! {stream_path} does not exist (optional)")
else:
    print(f"   ✓ {stream_path} exists")

# Create output directory if it doesn't exist
output_path.mkdir(parents=True, exist_ok=True)
print(f"   ✓ {output_path} created/exists\n")

# === 3. Check CSV files ===
print("3. Checking CSV files in present_tables...")
required_files = [
    'client.csv', 'account.csv', 'disp.csv', 'trans.csv',
    'loan.csv', 'order.csv', 'card.csv', 'district.csv'
]

missing_files = []
for file in required_files:
    file_path = present_path / file
    if not file_path.exists():
        missing_files.append(file)
        print(f"   ✗ {file} not found")
    else:
        # Check if file has data
        try:
            df = pd.read_csv(file_path)
            row_count = len(df)
            print(f"   ✓ {file:<20} ({row_count:,} rows)")
        except Exception as e:
            print(f"   ! {file:<20} (error reading: {e})")

if missing_files:
    print(f"\n   Warning: {len(missing_files)} files are missing:")
    for f in missing_files:
        print(f"     - {f}")
    print("\n   The pipeline may not work correctly without all files.")
else:
    print("\n   ✓ All required CSV files are present")

# === 4. Test CSV schema ===
print("\n4. Validating CSV schemas...")

# Test trans.csv schema
trans_file = present_path / "trans.csv"
if trans_file.exists():
    try:
        trans_df = pd.read_csv(trans_file, nrows=5)
        required_cols = ['trans_id', 'account_id', 'date', 'type', 'amount', 'balance']
        missing_cols = [col for col in required_cols if col not in trans_df.columns]

        if missing_cols:
            print(f"   ✗ trans.csv missing columns: {missing_cols}")
        else:
            print(f"   ✓ trans.csv schema is valid")
            print(f"      Columns: {trans_df.columns.tolist()}")
    except Exception as e:
        print(f"   ! Error reading trans.csv: {e}")

# Test client.csv schema
client_file = present_path / "client.csv"
if client_file.exists():
    try:
        client_df = pd.read_csv(client_file, nrows=5)
        required_cols = ['client_id', 'birth_number', 'district_id']
        missing_cols = [col for col in required_cols if col not in client_df.columns]

        if missing_cols:
            print(f"   ✗ client.csv missing columns: {missing_cols}")
        else:
            print(f"   ✓ client.csv schema is valid")
    except Exception as e:
        print(f"   ! Error reading client.csv: {e}")

# === 5. Check if data_fetch.py exists ===
print("\n5. Checking data_fetch.py...")
if not Path("data_fetch.py").exists():
    print("   ✗ data_fetch.py not found!")
    sys.exit(1)
else:
    print("   ✓ data_fetch.py exists")

# === 6. Syntax check ===
print("\n6. Checking data_fetch.py syntax...")
try:
    import py_compile
    py_compile.compile("data_fetch.py", doraise=True)
    print("   ✓ data_fetch.py syntax is valid")
except py_compile.PyCompileError as e:
    print(f"   ✗ Syntax error in data_fetch.py:")
    print(f"      {e}")
    sys.exit(1)

# === 7. Test import ===
print("\n7. Testing Pathway connectors...")
try:
    from pathway.io import csv
    print("   ✓ Pathway CSV connector available")
except ImportError as e:
    print(f"   ✗ Error importing Pathway modules: {e}")
    sys.exit(1)

# === 8. Summary ===
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

if not missing_files:
    print("\n✓ All checks passed!")
    print("\nYou can now run the pipeline:")
    print("  python data_fetch.py")
    print("\nOr test with publishers:")
    print("  # Terminal 1:")
    print("  python publishers/stream_all.py --mode single")
    print("\n  # Terminal 2:")
    print("  python data_fetch.py")
else:
    print("\n! Some checks failed. Please fix the issues above before running.")

print("\n" + "="*80)

# === 9. Offer to create sample data ===
if missing_files:
    response = input("\nDo you want to create sample CSV files for testing? (y/n): ")
    if response.lower() == 'y':
        print("\nCreating sample data...")

        # Create minimal sample data
        if 'client.csv' in missing_files:
            pd.DataFrame({
                'client_id': ['1', '2', '3'],
                'birth_number': ['700101', '800202', '900303'],
                'district_id': ['1', '2', '1']
            }).to_csv(present_path / 'client.csv', index=False)
            print("  ✓ Created client.csv")

        if 'district.csv' in missing_files:
            pd.DataFrame({
                'A1': ['1', '2'],
                'A2': ['Prague', 'Brno'],
                'A3': ['Central', 'South'],
                'A4': [1000000, 500000],
                'A5': [10, 20],
                'A6': [15, 25],
                'A7': [20, 30],
                'A8': [30, 20],
                'A9': [5, 3],
                'A10': [90.0, 80.0],
                'A11': [50000, 45000],
                'A12': [2.5, 3.0],
                'A13': [2.3, 2.8],
                'A14': [150, 140],
                'A15': [1000, 800],
                'A16': [950, 780]
            }).to_csv(present_path / 'district.csv', index=False)
            print("  ✓ Created district.csv")

        if 'account.csv' in missing_files:
            pd.DataFrame({
                'account_id': ['1', '2', '3'],
                'district_id': ['1', '2', '1'],
                'frequency': ['POPLATEK MESICNE', 'POPLATEK MESICNE', 'POPLATEK TYDNE'],
                'date': ['1995-01-01', '1995-02-01', '1995-03-01']
            }).to_csv(present_path / 'account.csv', index=False)
            print("  ✓ Created account.csv")

        if 'disp.csv' in missing_files:
            pd.DataFrame({
                'disp_id': ['1', '2', '3'],
                'client_id': ['1', '2', '3'],
                'account_id': ['1', '2', '3'],
                'type': ['OWNER', 'OWNER', 'OWNER']
            }).to_csv(present_path / 'disp.csv', index=False)
            print("  ✓ Created disp.csv")

        if 'trans.csv' in missing_files:
            pd.DataFrame({
                'trans_id': ['1', '2', '3', '4', '5'],
                'account_id': ['1', '1', '2', '2', '3'],
                'date': ['1995-01-01', '1995-01-15', '1995-02-01', '1995-02-15', '1995-03-01'],
                'type': ['PRIJEM', 'VYDAJ', 'PRIJEM', 'VYDAJ', 'PRIJEM'],
                'operation': ['VKLAD', 'VYBER', 'VKLAD', 'VYBER', 'VKLAD'],
                'amount': [1000.0, 500.0, 2000.0, 800.0, 1500.0],
                'balance': [1000.0, 500.0, 2000.0, 1200.0, 1500.0],
                'k_symbol': ['', '', '', '', ''],
                'bank': ['', '', '', '', ''],
                'account': ['', '', '', '', '']
            }).to_csv(present_path / 'trans.csv', index=False)
            print("  ✓ Created trans.csv")

        if 'loan.csv' in missing_files:
            pd.DataFrame({
                'loan_id': ['1', '2'],
                'account_id': ['1', '2'],
                'date': ['1995-06-01', '1995-07-01'],
                'amount': [50000.0, 75000.0],
                'duration': [24.0, 36.0],
                'payments': [2200.0, 2300.0],
                'status': ['A', 'B']
            }).to_csv(present_path / 'loan.csv', index=False)
            print("  ✓ Created loan.csv")

        if 'order.csv' in missing_files:
            pd.DataFrame({
                'order_id': ['1', '2'],
                'account_id': ['1', '2'],
                'bank_to': ['AB', 'CD'],
                'account_to': ['12345', '67890'],
                'amount': [1000.0, 2000.0],
                'k_symbol': ['SIPO', 'UVER']
            }).to_csv(present_path / 'order.csv', index=False)
            print("  ✓ Created order.csv")

        if 'card.csv' in missing_files:
            pd.DataFrame({
                'card_id': ['1', '2'],
                'disp_id': ['1', '2'],
                'type': ['classic', 'gold'],
                'issued': ['1995-01-01 00:00:00', '1995-02-01 00:00:00']
            }).to_csv(present_path / 'card.csv', index=False)
            print("  ✓ Created card.csv")

        print("\n✓ Sample data created successfully!")
        print("\nYou can now run: python data_fetch.py")
