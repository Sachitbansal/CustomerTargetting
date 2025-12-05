#!/usr/bin/env python3
"""
Quick Test Script - Publishes 10 customers (for testing)
"""
import asyncio
import random
import json
import uuid
from datetime import datetime, timedelta
from nats.aio.client import Client as NATS

FIRST_NAMES = ['Rahul', 'Priya', 'Amit', 'Neha', 'Suresh']
LAST_NAMES = ['Sharma', 'Patel', 'Singh', 'Kumar', 'Gupta']
CATEGORIES = ['carLoans', 'mutualFunds', 'nifty', 'others']
PREFIXES = {'carLoans': 'CL', 'mutualFunds': 'MF', 'nifty': 'NF', 'others': 'OT'}
AUDIO_FILES = ['eaxample-1.mpeg', 'example-2.mpeg', 'example-3.mpeg', 'example-4.mpeg']
REPORT_FILES = ['Report_exapmle.pdf']

def generate_customer_data(customer_number: int):
    category = random.choice(CATEGORIES)
    prefix = PREFIXES[category]
    batch_number = (customer_number // 6) + 1
    user_position = (customer_number % 6) + 1
    
    batch_id = f"BATCH-{prefix}-{str(batch_number).zfill(4)}"
    user_id = f"{prefix}-{str(batch_number).zfill(3)}-{str(user_position).zfill(2)}"
    
    return {
        'customer_number': customer_number,
        'batch_id': batch_id,
        'category': category,
        'user_id': user_id,
        'name': f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        'agreed': random.random() > 0.4,
        'call_duration': random.randint(60, 360),
        'call_date': (datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat(),
        'loan_amount': random.randint(100000, 600000),
        'credit_score': random.randint(650, 850),
        'risk_level': random.choice(['Low', 'Medium', 'High']),
        'audio_file': random.choice(AUDIO_FILES),
        'report_file': random.choice(REPORT_FILES),
        'timestamp': datetime.now().isoformat(),
        'id': str(uuid.uuid4())
    }

async def test_publish():
    nc = NATS()
    
    try:
        await nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS")
        print("📡 Publishing 10 test customers...\n")
        
        for i in range(1, 11):
            customer_data = generate_customer_data(i + 1000)  # Start from 1000
            subject = f"customer.calls.{customer_data['category']}"
            message = json.dumps(customer_data).encode()
            
            await nc.publish(subject, message)
            
            print(f"[{i}/10] 📤 {customer_data['user_id']} | "
                  f"{customer_data['name']} | "
                  f"Batch: {customer_data['batch_id']} | "
                  f"{'✅' if customer_data['agreed'] else '❌'}")
            
            await asyncio.sleep(2)  # 2 seconds between each
        
        print("\n✅ Test complete! Check your frontend!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure NATS server is running: nats-server")
    finally:
        await nc.close()

if __name__ == '__main__':
    print("="*50)
    print("🧪 Quick Test - 10 Customers")
    print("="*50)
    print()
    asyncio.run(test_publish())
