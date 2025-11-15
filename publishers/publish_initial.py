"""
Publish Initial/Present Data to NATS
Clears existing data and sends all present_tables data to NATS
"""

import asyncio
import pandas as pd
import json
import os
from nats.aio.client import Client as NATS
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nats_config import NATS_SERVER, SUBJECTS, PRESENT_PATH


async def publish_initial_data():
    """Publish all data from present_tables to NATS as initial state"""

    # Connect to NATS
    nc = NATS()
    await nc.connect(NATS_SERVER)
    print(f"✓ Connected to NATS at {NATS_SERVER}")
    print("="*80)
    print("PUBLISHING INITIAL/PRESENT DATA TO NATS")
    print("="*80 + "\n")

    # Define tables to publish
    tables = {
        'client': 'client.csv',
        'account': 'account.csv',
        'disp': 'disp.csv',
        'trans': 'trans.csv',
        'loan': 'loan.csv',
        'order': 'order.csv',
        'card': 'card.csv',
        'district': 'district.csv',
        'loan_labels': 'loan_labels.csv',
        'card_labels': 'card_labels.csv'
    }

    total_published = {}

    for table_name, filename in tables.items():
        file_path = os.path.join(PRESENT_PATH, filename)

        if not os.path.exists(file_path):
            print(f"⚠ {filename} not found, skipping...")
            continue

        try:
            # Read CSV
            df = pd.read_csv(file_path)
            subject = SUBJECTS[table_name]
            count = 0

            print(f"Publishing {table_name}...")

            # Publish each row
            for _, row in df.iterrows():
                message = row.to_dict()
                json_msg = json.dumps(message, default=str)
                await nc.publish(subject, json_msg.encode())
                count += 1

                # Print progress every 100 rows
                if count % 100 == 0:
                    print(f"  {count} rows published...", end='\r')

            total_published[table_name] = count
            print(f"✓ {table_name}: Published {count} rows to {subject}       ")

        except Exception as e:
            print(f"✗ Error publishing {table_name}: {e}")

    await nc.close()

    print("\n" + "="*80)
    print("INITIAL DATA PUBLISHING COMPLETE")
    print("="*80)
    print("\nSummary:")
    for table, count in total_published.items():
        print(f"  {table:20s}: {count:6d} rows")
    print(f"\nTotal rows published: {sum(total_published.values())}")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(publish_initial_data())
