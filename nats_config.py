"""
NATS Configuration for Real-Time Data Streaming
"""

# NATS Server Configuration
NATS_SERVER = "nats://localhost:4222"

# NATS Subjects (Topics)
SUBJECTS = {
    'client': 'banking.tables.client',
    'account': 'banking.tables.account',
    'disp': 'banking.tables.disp',
    'trans': 'banking.tables.trans',
    'loan': 'banking.tables.loan',
    'order': 'banking.tables.order',
    'card': 'banking.tables.card',
    'district': 'banking.tables.district',
    'loan_labels': 'banking.tables.loan_labels',
    'card_labels': 'banking.tables.card_labels',
    'client_features': 'banking.features.client'
}

# Data paths
STREAM_PATH = "data/stream_tables"
PRESENT_PATH = "data/present_tables"
OUTPUT_PATH = "data"

# Streaming configuration
BATCH_SIZE = 10
DELAY_SECONDS = 2
CZK_TO_USD = 0.038
