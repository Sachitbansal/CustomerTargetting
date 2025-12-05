"""
Database models and initialization for the Targeted Calling application.
"""
import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            prefix TEXT NOT NULL
        )
    ''')
    
    # Reports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL UNIQUE,
            category_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            total_calls INTEGER NOT NULL,
            successful_calls INTEGER NOT NULL,
            report_file TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # Users table (users associated with reports)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            report_id TEXT NOT NULL,
            name TEXT NOT NULL,
            agreed INTEGER NOT NULL,
            call_duration INTEGER NOT NULL,
            call_date TEXT NOT NULL,
            loan_amount REAL NOT NULL,
            credit_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            audio_file TEXT,
            FOREIGN KEY (report_id) REFERENCES reports(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def seed_categories():
    """Seed the categories table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    categories = [
        ('carLoans', 'Car Loans', 'CL'),
        ('mutualFunds', 'Mutual Funds', 'MF'),
        ('nifty', 'Nifty', 'NF'),
        ('others', 'Others', 'OT')
    ]
    
    for cat in categories:
        cursor.execute('''
            INSERT OR IGNORE INTO categories (id, label, prefix)
            VALUES (?, ?, ?)
        ''', cat)
    
    conn.commit()
    conn.close()
    print("Categories seeded!")

if __name__ == '__main__':
    init_db()
    seed_categories()
