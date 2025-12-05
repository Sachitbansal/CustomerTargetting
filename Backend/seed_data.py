"""
Data seeding script - generates mock data using audio and PDF files from mock folders.
"""
import os
import random
import uuid
from datetime import datetime, timedelta
from database import get_db_connection, init_db, seed_categories

# Paths
BACKEND_DIR = os.path.dirname(__file__)
MOCK_AUDIO_DIR = os.path.join(BACKEND_DIR, 'mock audio')
MOCK_REPORTS_DIR = os.path.join(BACKEND_DIR, 'mock reports')

def get_mock_files():
    """Get list of mock audio and report files."""
    audio_files = []
    report_files = []
    
    if os.path.exists(MOCK_AUDIO_DIR):
        audio_files = [f for f in os.listdir(MOCK_AUDIO_DIR) if f.endswith(('.mp3', '.mpeg', '.wav'))]
    
    if os.path.exists(MOCK_REPORTS_DIR):
        report_files = [f for f in os.listdir(MOCK_REPORTS_DIR) if f.endswith('.pdf')]
    
    return audio_files, report_files

def generate_reports_data():
    """Generate mock reports data for all categories."""
    audio_files, report_files = get_mock_files()
    
    categories = ['carLoans', 'mutualFunds', 'nifty', 'others']
    prefixes = {'carLoans': 'CL', 'mutualFunds': 'MF', 'nifty': 'NF', 'others': 'OT'}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM reports')
    conn.commit()
    
    first_names = ['Rahul', 'Priya', 'Amit', 'Neha', 'Suresh', 'Kavita', 'Raj', 'Anita', 'Vikram', 'Pooja', 
                   'Arun', 'Sunita', 'Deepak', 'Meena', 'Sanjay', 'Rekha', 'Mohan', 'Geeta', 'Ajay', 'Lakshmi']
    last_names = ['Sharma', 'Patel', 'Singh', 'Kumar', 'Gupta', 'Verma', 'Joshi', 'Rao', 'Reddy', 'Mehta',
                  'Agarwal', 'Shah', 'Choudhary', 'Mishra', 'Pandey', 'Iyer', 'Nair', 'Das', 'Bose', 'Sen']
    
    for category in categories:
        prefix = prefixes[category]
        
        # Generate 8 reports per category
        for i in range(1, 9):
            report_id = f"{category}-{i}"
            batch_id = f"BATCH-{prefix}-{str(i).zfill(4)}"
            
            # Random timestamp within last 7 days
            days_ago = random.uniform(0, 7)
            timestamp = datetime.now() - timedelta(days=days_ago)
            
            # Random report file
            report_file = random.choice(report_files) if report_files else None
            
            # 6 users per report
            total_calls = 6
            successful_calls = random.randint(2, 5)
            
            # Insert report
            cursor.execute('''
                INSERT INTO reports (id, batch_id, category_id, timestamp, total_calls, successful_calls, report_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (report_id, batch_id, category, timestamp.isoformat(), total_calls, successful_calls, report_file))
            
            # Generate users for this report
            successful_count = 0
            for j in range(1, 7):
                user_uuid = str(uuid.uuid4())
                user_id = f"{prefix}-{str(i).zfill(3)}-{str(j).zfill(2)}"
                
                # Determine if agreed (ensuring we match successful_calls count)
                if successful_count < successful_calls and j <= total_calls - (successful_calls - successful_count):
                    agreed = random.random() > 0.4
                    if agreed:
                        successful_count += 1
                elif successful_count < successful_calls:
                    agreed = True
                    successful_count += 1
                else:
                    agreed = False
                
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                call_duration = random.randint(60, 360)  # 1-6 minutes
                call_date = timestamp - timedelta(hours=random.randint(0, 24))
                loan_amount = random.randint(100000, 600000)
                credit_score = random.randint(650, 850)
                risk_level = 'Low' if agreed and credit_score > 700 else 'Medium' if credit_score > 650 else 'High'
                
                # Assign random audio file
                audio_file = random.choice(audio_files) if audio_files else None
                
                cursor.execute('''
                    INSERT INTO users (id, user_id, report_id, name, agreed, call_duration, call_date, 
                                      loan_amount, credit_score, risk_level, audio_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_uuid, user_id, report_id, name, 1 if agreed else 0, call_duration, 
                      call_date.isoformat(), loan_amount, credit_score, risk_level, audio_file))
    
    conn.commit()
    conn.close()
    print("Data seeded successfully!")
    print(f"Created {4 * 8} reports with {4 * 8 * 6} users")

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    seed_categories()
    print("\nGenerating mock data...")
    generate_reports_data()
    print("\nDone!")
