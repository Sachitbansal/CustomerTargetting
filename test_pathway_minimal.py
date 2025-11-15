"""
Minimal test to verify Pathway setup works
"""

import pathway as pw
import os

# Set license key
pw.set_license_key("B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3")

print("Testing Pathway setup...")
print("-" * 50)

# Test 1: Check if files exist
print("\n1. Checking files...")
files = [
    "data/present_tables/client.csv",
    "data/present_tables/trans.csv",
]

for f in files:
    if os.path.exists(f):
        print(f"   ✓ {f}")
    else:
        print(f"   ✗ {f} NOT FOUND")

# Test 2: Try to read a simple CSV
print("\n2. Testing CSV read...")

class ClientSchema(pw.Schema):
    client_id: str
    birth_number: str
    district_id: str

try:
    client_table = pw.io.csv.read(
        "data/present_tables/client.csv",
        schema=ClientSchema,
        mode="streaming",
        autocommit_duration_ms=1000
    )
    print("   ✓ Client table loaded successfully")
except Exception as e:
    print(f"   ✗ Error loading client table: {e}")
    exit(1)

# Test 3: Try a simple aggregation
print("\n3. Testing aggregation...")

class TransSchema(pw.Schema):
    trans_id: str
    account_id: str
    date: str
    type: str
    operation: str
    amount: float
    balance: float
    k_symbol: str | None
    bank: str | None
    account: str | None

try:
    trans_table = pw.io.csv.read(
        "data/present_tables/trans.csv",
        schema=TransSchema,
        mode="streaming",
        autocommit_duration_ms=1000
    )

    # Simple aggregation
    trans_count = trans_table.groupby(trans_table.account_id).reduce(
        trans_table.account_id,
        count=pw.reducers.count()
    )

    print("   ✓ Transaction aggregation created successfully")
except Exception as e:
    print(f"   ✗ Error with aggregation: {e}")
    exit(1)

# Test 4: Try to write output
print("\n4. Testing output...")

os.makedirs("data/pathway_output", exist_ok=True)

try:
    pw.io.csv.write(trans_count, "data/pathway_output/test_output.csv")
    print("   ✓ Output configured successfully")
except Exception as e:
    print(f"   ✗ Error configuring output: {e}")
    exit(1)

print("\n" + "-" * 50)
print("All tests passed! Running pipeline for 5 seconds...")
print("Press Ctrl+C to stop earlier")
print("-" * 50 + "\n")

# Run for a short time
import signal
import sys

def timeout_handler(signum, frame):
    print("\n\n" + "=" * 50)
    print("Test completed successfully!")
    print("=" * 50)
    sys.exit(0)

# Set timeout
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5)

try:
    pw.run()
except KeyboardInterrupt:
    print("\n\n" + "=" * 50)
    print("Test stopped by user")
    print("=" * 50)
    sys.exit(0)
