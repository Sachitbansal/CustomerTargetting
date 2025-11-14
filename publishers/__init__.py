"""
Publishers Package

This package provides streaming functionality to move data from stream_tables to present_tables.
Each module handles a specific data table with configurable batch sizes and time delays.

Modules:
    - stream_account: Stream account data
    - stream_card: Stream card data
    - stream_card_labels: Stream card labels data
    - stream_client: Stream client data
    - stream_disp: Stream disposition data
    - stream_district: Stream district data
    - stream_loan: Stream loan data
    - stream_loan_labels: Stream loan labels data
    - stream_order: Stream order data
    - stream_trans: Stream transaction data
    - stream_all: Orchestrator to stream all tables

Usage:
    # Stream all tables with default configuration
    python -m publishers.stream_all

    # Stream a single table
    python -m publishers.stream_trans

    # Use in code
    from publishers.stream_all import stream_all_tables
    stream_all_tables(max_iterations=10)
"""

__version__ = '1.0.0'
__author__ = 'TargettedCalling Team'

# Import main streaming functions for easy access
from .stream_account import stream_account, stream_account_continuous
from .stream_card import stream_card, stream_card_continuous
from .stream_card_labels import stream_card_labels, stream_card_labels_continuous
from .stream_client import stream_client, stream_client_continuous
from .stream_disp import stream_disp, stream_disp_continuous
from .stream_district import stream_district, stream_district_continuous
from .stream_loan import stream_loan, stream_loan_continuous
from .stream_loan_labels import stream_loan_labels, stream_loan_labels_continuous
from .stream_order import stream_order, stream_order_continuous
from .stream_trans import stream_trans, stream_trans_continuous
from .stream_all import stream_all_tables, stream_single_iteration_all

__all__ = [
    'stream_account',
    'stream_account_continuous',
    'stream_card',
    'stream_card_continuous',
    'stream_card_labels',
    'stream_card_labels_continuous',
    'stream_client',
    'stream_client_continuous',
    'stream_disp',
    'stream_disp_continuous',
    'stream_district',
    'stream_district_continuous',
    'stream_loan',
    'stream_loan_continuous',
    'stream_loan_labels',
    'stream_loan_labels_continuous',
    'stream_order',
    'stream_order_continuous',
    'stream_trans',
    'stream_trans_continuous',
    'stream_all_tables',
    'stream_single_iteration_all',
]
