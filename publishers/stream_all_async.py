#!/usr/bin/env python3
"""
Stream All Tables to NATS - Async Mode

Streams data from stream_tables/ to NATS using async publishers.
Each publisher removes rows from stream_tables/ as they publish.

Usage:
    python publishers/stream_all_async.py [--delay SECONDS]
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime

# Add publishers directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import async continuous functions
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


# Configuration for each table publisher
PUBLISHER_CONFIG = {
    'account': {'func': stream_account_continuous, 'batch_size': 10, 'delay': 4.0},
    'card': {'func': stream_card_continuous, 'batch_size': 8, 'delay': 3.0},
    'card_labels': {'func': stream_card_labels_continuous, 'batch_size': 8, 'delay': 6.0},
    'client': {'func': stream_client_continuous, 'batch_size': 10, 'delay': 4.0},
    'disp': {'func': stream_disp_continuous, 'batch_size': 10, 'delay': 2.5},
    'district': {'func': stream_district_continuous, 'batch_size': 5, 'delay': 4.0},
    'loan': {'func': stream_loan_continuous, 'batch_size': 5, 'delay': 5.0},
    'loan_labels': {'func': stream_loan_labels_continuous, 'batch_size': 5, 'delay': 5.0},
    'order': {'func': stream_order_continuous, 'batch_size': 10, 'delay': 6.0},
    'trans': {'func': stream_trans_continuous, 'batch_size': 20, 'delay': 12.0},
}


async def main():
    parser = argparse.ArgumentParser(description='Stream all tables to NATS')
    parser.add_argument('--delay', type=float, help='Override delay for all publishers')
    args = parser.parse_args()

    print("\n" + "="*80)
    print("STREAMING ALL TABLES TO NATS - Async Continuous Mode")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nPublishing data from stream_tables/ to NATS topics")
    print("Rows will be removed from stream_tables/ as they're published")
    print("\nPress Ctrl+C to stop all publishers")
    print("="*80 + "\n")

    # Display configuration
    print("Publisher Configuration:")
    for name, config in PUBLISHER_CONFIG.items():
        delay = args.delay if args.delay else config['delay']
        print(f"  [{name:15s}] Batch: {config['batch_size']:3d} | Delay: {delay:5.1f}s")
    print("\n" + "-"*80 + "\n")

    # Create tasks for all publishers
    tasks = []
    for name, config in PUBLISHER_CONFIG.items():
        delay = args.delay if args.delay else config['delay']
        task = asyncio.create_task(
            config['func'](batch_size=config['batch_size'], delay=delay)
        )
        tasks.append(task)

    # Wait for all tasks (or until interrupted)
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("STOPPING ALL PUBLISHERS")
        print("="*80)

        # Cancel all tasks
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

        print("\n✓ All publishers stopped")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
