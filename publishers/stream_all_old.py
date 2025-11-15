"""
Stream All Tables Orchestrator

This script orchestrates the streaming of all data tables from stream_tables to present_tables.
Each table can have custom batch sizes and time delays configured via arrays.

Usage:
    python stream_all.py

Configuration:
    Modify the STREAM_CONFIG dictionary to customize batch sizes and delays for each table.
"""

import sys
import os
from datetime import datetime

# Add the publishers directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all streaming modules
from stream_account import stream_account
from stream_card import stream_card
from stream_card_labels import stream_card_labels
from stream_client import stream_client
from stream_disp import stream_disp
from stream_district import stream_district
from stream_loan import stream_loan
from stream_loan_labels import stream_loan_labels
from stream_order import stream_order
from stream_trans import stream_trans


# Configuration: Define custom delays (in seconds) for each table
# You can customize these arrays to set different delays for each streaming function
STREAM_CONFIG = {
    'account': {
        'function': stream_account,
        'batch_size': 10,
        'delay': 4.0, 
        'enabled': True
    },
    'card': {
        'function': stream_card,
        'batch_size': 8,
        'delay': 3.0,  
        'enabled': True
    },
    'card_labels': {
        'function': stream_card_labels,
        'batch_size': 8,
        'delay': 6.0,  
        'enabled': True
    },
    'client': {
        'function': stream_client,
        'batch_size': 10,
        'delay': 4.0,  
        'enabled': True
    },
    'disp': {
        'function': stream_disp,
        'batch_size': 10,
        'delay': 2.5,  
        'enabled': True
    },
    'district': {
        'function': stream_district,
        'batch_size': 5,
        'delay': 4.0,  
        'enabled': True
    },
    'loan': {
        'function': stream_loan,
        'batch_size': 5,
        'delay': 5.0,  
        'enabled': True
    },
    'loan_labels': {
        'function': stream_loan_labels,
        'batch_size': 5,
        'delay': 5.0,  
        'enabled': True
    },
    'order': {
        'function': stream_order,
        'batch_size': 10,
        'delay': 6,  
        'enabled': True
    },
    'trans': {
        'function': stream_trans,
        'batch_size': 20,
        'delay': 12,  
        'enabled': True
    }
}


def stream_all_tables(max_iterations=None, verbose=True):
    """
    Stream all tables simultaneously in a round-robin fashion.

    Parameters:
    -----------
    max_iterations : int or None
        Maximum number of iterations per table. None means run until all streams are empty.
    verbose : bool
        Print detailed progress information

    Returns:
    --------
    dict : Summary statistics for all tables
    """
    print("\n" + "="*80)
    print("STREAMING ALL TABLES - Round Robin Mode")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Max iterations per table: {max_iterations if max_iterations else 'Unlimited'}")
    print("="*80 + "\n")

    # Display configuration
    if verbose:
        print("Configuration:")
        for table_name, config in STREAM_CONFIG.items():
            if config['enabled']:
                print(f"  [{table_name.upper():15s}] Batch: {config['batch_size']:3d} | Delay: {config['delay']:4.1f}s")
        print("\n" + "-"*80 + "\n")

    # Track statistics for each table
    stats = {}
    for table_name in STREAM_CONFIG.keys():
        stats[table_name] = {
            'iterations': 0,
            'total_rows_added': 0,
            'finished': False,
            'errors': []
        }

    iteration = 0
    all_finished = False

    while not all_finished:
        iteration += 1

        if verbose and iteration > 1:
            print(f"\n{'─'*80}")
            print(f"Iteration {iteration}")
            print(f"{'─'*80}\n")

        # Check if max iterations reached
        if max_iterations and iteration > max_iterations:
            print(f"\nReached maximum iterations ({max_iterations}). Stopping all streams.")
            break

        # Stream each table
        active_streams = 0
        for table_name, config in STREAM_CONFIG.items():
            # Skip if disabled or already finished
            if not config['enabled'] or stats[table_name]['finished']:
                continue

            # Execute streaming function
            try:
                result = config['function'](
                    batch_size=config['batch_size'],
                    delay=config['delay']
                )

                # Update statistics
                if 'error' in result:
                    stats[table_name]['errors'].append(result['error'])
                    stats[table_name]['finished'] = True
                else:
                    stats[table_name]['iterations'] += 1
                    stats[table_name]['total_rows_added'] += result.get('rows_added', 0)

                    # Check if stream is empty
                    if result.get('remaining_stream', 0) == 0:
                        stats[table_name]['finished'] = True
                        if verbose:
                            print(f"  [{table_name.upper()}] Stream completed!")
                    else:
                        active_streams += 1

            except Exception as e:
                print(f"  [ERROR] {table_name.upper()}: {str(e)}")
                stats[table_name]['errors'].append(str(e))
                stats[table_name]['finished'] = True

        # Check if all streams are finished
        all_finished = (active_streams == 0)

    # Print final summary
    print("\n" + "="*80)
    print("STREAMING COMPLETE - SUMMARY")
    print("="*80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total iterations: {iteration}")
    print("="*80 + "\n")

    # Print detailed statistics
    print("Table Statistics:")
    print(f"{'Table':<15} {'Iterations':<12} {'Rows Added':<12} {'Status':<10}")
    print("-"*80)

    total_rows = 0
    for table_name, table_stats in stats.items():
        status = 'Error' if table_stats['errors'] else ('Complete' if table_stats['finished'] else 'Active')
        print(f"{table_name.upper():<15} {table_stats['iterations']:<12} {table_stats['total_rows_added']:<12} {status:<10}")
        total_rows += table_stats['total_rows_added']

    print("-"*80)
    print(f"{'TOTAL':<15} {'':<12} {total_rows:<12}")
    print("="*80 + "\n")

    # Print errors if any
    errors_found = False
    for table_name, table_stats in stats.items():
        if table_stats['errors']:
            if not errors_found:
                print("Errors encountered:")
                errors_found = True
            print(f"  [{table_name.upper()}]: {', '.join(table_stats['errors'])}")

    if errors_found:
        print("\n" + "="*80 + "\n")

    return stats


def stream_single_iteration_all():
    """
    Stream a single batch from each table (useful for testing).

    Returns:
    --------
    dict : Results from each table
    """
    print("\n" + "="*80)
    print("STREAMING ALL TABLES - Single Iteration Mode")
    print("="*80 + "\n")

    results = {}

    for table_name, config in STREAM_CONFIG.items():
        if not config['enabled']:
            continue

        print(f"\nStreaming {table_name.upper()}...")
        try:
            result = config['function'](
                batch_size=config['batch_size'],
                delay=config['delay']
            )
            results[table_name] = result
        except Exception as e:
            print(f"  [ERROR] {table_name.upper()}: {str(e)}")
            results[table_name] = {'error': str(e)}

    print("\n" + "="*80 + "\n")
    return results


if __name__ == "__main__":
    """
    Main execution block

    To customize delays, modify the STREAM_CONFIG dictionary above.

    Examples of custom delay configurations:

    # Fast streaming for transactions
    STREAM_CONFIG['trans']['delay'] = 0.5

    # Slow streaming for loans
    STREAM_CONFIG['loan']['delay'] = 10.0

    # Disable a specific table
    STREAM_CONFIG['district']['enabled'] = False

    # Custom batch size for client data
    STREAM_CONFIG['client']['batch_size'] = 50
    """

    import argparse

    parser = argparse.ArgumentParser(description='Stream data from stream_tables to present_tables')
    parser.add_argument('--mode', choices=['continuous', 'single'], default='continuous',
                        help='Streaming mode: continuous or single iteration (default: continuous)')
    parser.add_argument('--max-iterations', type=int, default=None,
                        help='Maximum iterations per table (default: unlimited)')
    parser.add_argument('--quiet', action='store_true',
                        help='Reduce output verbosity')

    args = parser.parse_args()

    if args.mode == 'single':
        # Single iteration mode - stream one batch from each table
        stream_single_iteration_all()
    else:
        # Continuous mode - stream until all tables are empty
        stream_all_tables(
            max_iterations=args.max_iterations,
            verbose=not args.quiet
        )
