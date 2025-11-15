#!/usr/bin/env python3
"""
Stream All Tables to NATS (Async Continuous Mode)

This script launches all table publishers using async continuous functions
that properly publish to NATS and modify stream_tables CSV files.

Usage:
    python publishers/stream_all_nats.py
"""

import asyncio
import sys
import os

# Add the publishers directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all continuous streaming functions
from stream_account import stream_account_continuous
from stream_card import stream_card_continuous
from stream_card_labels import stream_card_labels_continuous
from stream_client import stream_client_continuous
from stream_disp import stream_disp_continuous
from stream_district import stream_district_continuous
from stream_loan import stream_loan_continuous
from stream_loan_labels import stream_loan_labels_continuous
from stream_order import stream_order_continuous
from stream_trans import stream_trans_continuous


async def main():
    """Run all publishers concurrently"""

    print("\n" + "="*80)
    print("STARTING ALL NATS PUBLISHERS - Async Continuous Mode")
    print("="*80)
    print("This will stream data from stream_tables/ to NATS topics")
    print("Each publisher will remove rows from stream_tables/ as they're published")
    print("\nPress Ctrl+C to stop all publishers")
    print("="*80 + "\n")

    # Create tasks for all publishers
    tasks = [
        asyncio.create_task(stream_account_continuous(batch_size=10, delay=4.0)),
        asyncio.create_task(stream_card_continuous(batch_size=8, delay=3.0)),
        asyncio.create_task(stream_card_labels_continuous(batch_size=8, delay=6.0)),
        asyncio.create_task(stream_client_continuous(batch_size=10, delay=4.0)),
        asyncio.create_task(stream_disp_continuous(batch_size=10, delay=2.5)),
        asyncio.create_task(stream_district_continuous(batch_size=5, delay=4.0)),
        asyncio.create_task(stream_loan_continuous(batch_size=5, delay=5.0)),
        asyncio.create_task(stream_loan_labels_continuous(batch_size=5, delay=5.0)),
        asyncio.create_task(stream_order_continuous(batch_size=10, delay=6.0)),
        asyncio.create_task(stream_trans_continuous(batch_size=20, delay=12.0)),
    ]

    # Wait for all tasks to complete (or until interrupted)
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\nStopping all publishers...")
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("All publishers stopped.")


if __name__ == "__main__":
    asyncio.run(main())
