"""
Transaction Publisher
Publishes transactions to NATS for live processing
"""

import asyncio
import json
import pandas as pd
from nats.aio.client import Client as NATS
from datetime import datetime

# Configuration
NATS_URL = "nats://localhost:4222/"
TRANSACTION_TOPIC = "transactions.live"


async def publish_transactions(csv_file="data/live_transactions.csv"):
    """
    Publish transactions from CSV to NATS
    """
    nc = NATS()
    
    try:
        # Connect to NATS
        print("=" * 70)
        print("Transaction Publisher")
        print("=" * 70)
        print(f"\nConnecting to NATS at {NATS_URL}...")
        await nc.connect(NATS_URL)
        print("✓ Connected to NATS\n")
        
        # Load transactions
        print(f"Loading transactions from {csv_file}...")
        df = pd.read_csv(csv_file)
        print(f"✓ Loaded {len(df)} transactions\n")
        
        print("Publishing transactions...")
        print("-" * 70)
        
        for idx, row in df.iterrows():
            # Convert row to dictionary
            transaction = {
                'trans_id': int(row['trans_id']),
                'customer_id': int(row['customer_id']),
                'timestamp': int(row['timestamp']),
                'trans_type': str(row['trans_type']),
                'category': str(row['category']),
                'amount': float(row['amount']),
                'balance': float(row['balance'])
            }
            
            # Publish to NATS
            message = json.dumps(transaction).encode('utf-8')
            await nc.publish(TRANSACTION_TOPIC, message)
            
            print(f"[{idx+1}/{len(df)}] Published: Customer {transaction['customer_id']} | "
                  f"{transaction['trans_type']} | {transaction['category']} | "
                  f"${transaction['amount']:.2f}")
            
            # Small delay between transactions to simulate real-time
            await asyncio.sleep(0.5)
        
        print("-" * 70)
        print(f"\n✓ Published {len(df)} transactions successfully!")
        print(f"  Topic: {TRANSACTION_TOPIC}")
        print(f"  Check output/customer_features_live.csv for computed features")
        
    except FileNotFoundError:
        print(f"\nError: File {csv_file} not found!")
        print("Please run 'python generate_sample_data.py' first to create sample data.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await nc.close()
        print("\n✓ Disconnected from NATS\n")


async def publish_single_transaction(customer_id, trans_type, category, amount):
    """
    Publish a single transaction
    """
    nc = NATS()
    
    try:
        await nc.connect(NATS_URL)
        
        transaction = {
            'trans_id': int(datetime.now().timestamp()),
            'customer_id': customer_id,
            'timestamp': int(datetime.now().timestamp()),
            'trans_type': trans_type,
            'category': category,
            'amount': amount,
            'balance': 10000.0  # Placeholder
        }
        
        message = json.dumps(transaction).encode('utf-8')
        await nc.publish(TRANSACTION_TOPIC, message)
        
        print(f"✓ Published: Customer {customer_id} | {trans_type} | ${amount:.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await nc.close()


async def main():
    """
    Main function with options
    """
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "single":
            # Publish single transaction
            customer_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            trans_type = sys.argv[3] if len(sys.argv) > 3 else "INCOME"
            category = sys.argv[4] if len(sys.argv) > 4 else "Salary"
            amount = float(sys.argv[5]) if len(sys.argv) > 5 else 1000.0
            
            await publish_single_transaction(customer_id, trans_type, category, amount)
        else:
            # Publish from custom file
            await publish_transactions(sys.argv[1])
    else:
        # Default: publish from live_transactions.csv
        await publish_transactions()


if __name__ == "__main__":
    print("\nUsage:")
    print("  python publish_transactions.py                    # Publish from data/live_transactions.csv")
    print("  python publish_transactions.py <csv_file>         # Publish from custom CSV")
    print("  python publish_transactions.py single <id> <type> <category> <amount>  # Single transaction")
    print()
    
    asyncio.run(main())