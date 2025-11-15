"""
Stream All Tables to NATS
1. Publishes initial/present data
2. Runs all stream publishers simultaneously
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all streaming functions
from publishers.stream_trans import stream_trans_continuous
from publishers.stream_client import stream_client_continuous
from publishers.stream_account import stream_account_continuous
from publishers.stream_disp import stream_disp_continuous
from publishers.stream_loan import stream_loan_continuous
from publishers.stream_order import stream_order_continuous
from publishers.stream_card import stream_card_continuous
from publishers.stream_district import stream_district_continuous
from publishers.stream_loan_labels import stream_loan_labels_continuous
from publishers.stream_card_labels import stream_card_labels_continuous
from publishers.publish_initial import publish_initial_data


async def run_all_streams():
    """Run all stream publishers concurrently"""
    print("="*80)
    print("STARTING NATS STREAMING PIPELINE")
    print("="*80 + "\n")

    # Step 1: Publish initial/present data
    print("Step 1: Publishing initial/present data...")
    await publish_initial_data()
    print("\n✓ Initial data published successfully\n")

    # Step 2: Start all streaming publishers concurrently
    print("Step 2: Starting continuous streaming for all tables...")
    print("="*80 + "\n")

    tasks = [
        # Different batch sizes and delays for variety
        stream_trans_continuous(batch_size=15, delay=1.5),      # High volume
        stream_client_continuous(batch_size=10, delay=2),
        stream_account_continuous(batch_size=10, delay=2),
        stream_disp_continuous(batch_size=10, delay=2),
        stream_loan_continuous(batch_size=5, delay=2.5),
        stream_order_continuous(batch_size=8, delay=2),
        stream_card_continuous(batch_size=5, delay=3),
        stream_district_continuous(batch_size=5, delay=5),
        stream_loan_labels_continuous(batch_size=5, delay=2.5),
        stream_card_labels_continuous(batch_size=5, delay=3),
    ]

    # Run all tasks concurrently
    await asyncio.gather(*tasks)

    print("\n" + "="*80)
    print("ALL STREAMS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(run_all_streams())
    except KeyboardInterrupt:
        print("\n\n✓ Streaming interrupted by user")
        print("="*80)
