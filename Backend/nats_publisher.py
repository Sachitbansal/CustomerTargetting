"""
NATS Publisher - Generates and publishes COMPLETE BATCHES
Publishes one complete batch (6-8 customers) every 3 seconds
"""
import asyncio
import random
import json
import uuid
from datetime import datetime, timedelta
from nats.aio.client import Client as NATS

# Customer data templates
FIRST_NAMES = ['Rahul', 'Priya', 'Amit', 'Neha', 'Suresh', 'Kavita', 'Raj', 'Anita', 'Vikram', 'Pooja',
               'Arun', 'Sunita', 'Deepak', 'Meena', 'Sanjay', 'Rekha', 'Mohan', 'Geeta', 'Ajay', 'Lakshmi',
               'Kiran', 'Divya', 'Ravi', 'Sneha', 'Manoj', 'Swati', 'Nitin', 'Preeti', 'Sachin', 'Nisha']

LAST_NAMES = ['Sharma', 'Patel', 'Singh', 'Kumar', 'Gupta', 'Verma', 'Joshi', 'Rao', 'Reddy', 'Mehta',
              'Agarwal', 'Shah', 'Choudhary', 'Mishra', 'Pandey', 'Iyer', 'Nair', 'Das', 'Bose', 'Sen']

CATEGORIES = ['carLoans', 'mutualFunds', 'nifty', 'others']
PREFIXES = {'carLoans': 'CL', 'mutualFunds': 'MF', 'nifty': 'NF', 'others': 'OT'}

AUDIO_FILES = ['eaxample-1.mpeg', 'example-2.mpeg', 'example-3.mpeg', 'example-4.mpeg']
REPORT_FILES = ['Report_exapmle.pdf']


def generate_batch(batch_number: int):
    """Generate a complete batch with 6-8 customers"""
    category = random.choice(CATEGORIES)
    prefix = PREFIXES[category]
    
    # Random number of customers per batch (6-8)
    num_customers = random.randint(6, 8)
    
    batch_id = f"BATCH-{prefix}-{str(batch_number).zfill(4)}"
    report_id = f"{category}-{str(batch_number).zfill(4)}"
    
    # Generate customers for this batch
    customers = []
    agreed_count = 0
    
    for i in range(1, num_customers + 1):
        user_id = f"{prefix}-{str(batch_number).zfill(3)}-{str(i).zfill(2)}"
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        agreed = random.random() > 0.4  # 60% agreement rate
        
        if agreed:
            agreed_count += 1
        
        customer = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': name,
            'agreed': agreed,
            'call_duration': random.randint(60, 360),
            'call_date': (datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat(),
            'loan_amount': random.randint(100000, 600000),
            'credit_score': random.randint(650, 850),
            'risk_level': 'Low' if agreed and random.randint(650, 850) > 700 else 'Medium' if random.randint(650, 850) > 650 else 'High',
            'audio_file': random.choice(AUDIO_FILES)
        }
        customers.append(customer)
    
    # Complete batch data
    batch_data = {
        'batch_number': batch_number,
        'batch_id': batch_id,
        'report_id': report_id,
        'category': category,
        'timestamp': datetime.now().isoformat(),
        'total_calls': num_customers,
        'successful_calls': agreed_count,
        'report_file': random.choice(REPORT_FILES),
        'customers': customers
    }
    
    return batch_data


async def publish_batches():
    """Publish complete batches to NATS, one every 3 seconds"""
    nc = NATS()
    
    try:
        # Connect to NATS server
        await nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS server at nats://localhost:4222")
        print("📡 Starting to publish COMPLETE batches...")
        print("⏱️  Publishing 1 batch (6-8 customers) every 3 seconds\n")
        
        # Calculate total batches for 1000 customers
        # Average 7 customers per batch = ~143 batches
        total_batches = 150  # Allows for variation in batch sizes
        
        for batch_num in range(1, total_batches + 1):
            # Generate complete batch
            batch_data = generate_batch(batch_num)
            
            # Publish to NATS
            subject = f"batch.calls.{batch_data['category']}"
            message = json.dumps(batch_data).encode()
            
            await nc.publish(subject, message)
            
            # Log batch info
            print(f"[{batch_num}/{total_batches}] 📦 Published BATCH: {batch_data['batch_id']}")
            print(f"   Category: {batch_data['category']}")
            print(f"   Customers: {batch_data['total_calls']}")
            print(f"   Agreed: {batch_data['successful_calls']} ({int(batch_data['successful_calls']/batch_data['total_calls']*100)}%)")
            print(f"   Users: {', '.join([c['user_id'] for c in batch_data['customers'][:3]])}...")
            print()
            
            # Log milestone
            if batch_num % 25 == 0:
                print(f"🎯 Milestone: {batch_num} batches published!\n")
            
            # Wait 3 seconds before next batch
            if batch_num < total_batches:
                await asyncio.sleep(3)
        
        print(f"\n✅ All {total_batches} batches published successfully!")
        print(f"📊 Total customers: ~{total_batches * 7} (average 7 per batch)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await nc.close()


if __name__ == '__main__':
    print("="*70)
    print("🚀 NATS BATCH Publisher - Complete Batches")
    print("="*70)
    print("📦 Total batches to publish: 150")
    print("👥 Customers per batch: 6-8 (random)")
    print("⏱️  Interval: 3 seconds per batch")
    print("⏳ Estimated time: ~7.5 minutes")
    print("📊 Expected total customers: ~1050")
    print("="*70)
    print()
    
    asyncio.run(publish_batches())
