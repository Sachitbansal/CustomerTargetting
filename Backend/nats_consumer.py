"""
NATS Consumer - Subscribes to COMPLETE BATCH data and updates SQLite database
Also emits WebSocket events for real-time frontend updates
"""
import asyncio
import json
from nats.aio.client import Client as NATS
from database import get_db_connection
import requests

# WebSocket notification URL
WEBSOCKET_NOTIFY_URL = "http://localhost:5000/api/notify-update"


def save_batch_to_db(batch_data):
    """Save complete batch data to SQLite"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        report_id = batch_data['report_id']
        batch_id = batch_data['batch_id']
        category = batch_data['category']
        
        # Insert report
        cursor.execute('''
            INSERT OR REPLACE INTO reports (id, batch_id, category_id, timestamp, total_calls, successful_calls, report_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (report_id, batch_id, category, batch_data['timestamp'], 
              batch_data['total_calls'], batch_data['successful_calls'], batch_data['report_file']))
        
        # Insert all customers in this batch
        user_ids = []
        for customer in batch_data['customers']:
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (id, user_id, report_id, name, agreed, call_duration, call_date, 
                 loan_amount, credit_score, risk_level, audio_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (customer['id'], customer['user_id'], report_id, 
                  customer['name'], 1 if customer['agreed'] else 0, 
                  customer['call_duration'], customer['call_date'],
                  customer['loan_amount'], customer['credit_score'], 
                  customer['risk_level'], customer['audio_file']))
            
            user_ids.append(customer['user_id'])
        
        conn.commit()
        
        # Get complete report data for WebSocket
        report_data = cursor.execute('''
            SELECT r.*, c.label as category_label, c.prefix as category_prefix
            FROM reports r
            JOIN categories c ON r.category_id = c.id
            WHERE r.id = ?
        ''', (report_id,)).fetchone()
        
        # Notify WebSocket clients with complete NEW batch
        try:
            notification_data = {
                'type': 'new_batch',
                'is_new_report': True,  # Always new batch
                'batch_number': batch_data['batch_number'],
                'report': {
                    'id': report_data['id'],
                    'batch_id': report_data['batch_id'],
                    'category_id': report_data['category_id'],
                    'timestamp': report_data['timestamp'],
                    'total_calls': report_data['total_calls'],
                    'successful_calls': report_data['successful_calls'],
                    'report_file': report_data['report_file'],
                    'category_label': report_data['category_label'],
                    'category_prefix': report_data['category_prefix'],
                    'userIds': user_ids
                },
                'category': category,
                'customer_count': len(batch_data['customers'])
            }
            
            requests.post(WEBSOCKET_NOTIFY_URL, json=notification_data, timeout=1)
        except Exception as e:
            print(f"⚠️  WebSocket notification failed: {e}")
        
        return True, len(batch_data['customers'])
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        return False, 0
    finally:
        conn.close()


async def subscribe_to_batches():
    """Subscribe to NATS and process incoming batch data"""
    nc = NATS()
    
    try:
        # Connect to NATS
        await nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS server")
        print("👂 Subscribing to batch.calls.* topics")
        print("💾 Ready to save COMPLETE batches to SQLite\n")
        
        batch_count = 0
        total_customers = 0
        
        async def message_handler(msg):
            """Handle incoming batch messages"""
            nonlocal batch_count, total_customers
            
            try:
                batch_data = json.loads(msg.data.decode())
                
                # Save complete batch to database
                success, customer_count = save_batch_to_db(batch_data)
                
                if success:
                    batch_count += 1
                    total_customers += customer_count
                    
                    print(f" Batch #{batch_count}: {batch_data['batch_id']}")
                    print(f"   Category: {batch_data['category']}")
                    print(f"   Customers: {customer_count}")
                    print(f"   Agreed: {batch_data['successful_calls']}/{batch_data['total_calls']}")
                    print(f"   Total saved: {total_customers} customers in {batch_count} batches")
                    print()
                else:
                    print(f"Failed to save batch: {batch_data['batch_id']}")
                    
            except Exception as e:
                print(f" Error processing message: {e}")
        
        # Subscribe to all batch call topics
        await nc.subscribe("batch.calls.*", cb=message_handler)
        
        print("🎧 Listening for COMPLETE batches... (Press Ctrl+C to stop)\n")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\nShutting down consumer...")
        print(f" Final Stats: {batch_count} batches, {total_customers} customers saved")
    except Exception as e:
        print(f" Error: {e}")
    finally:
        await nc.close()


if __name__ == '__main__':
    print("="*70)
    print("NATS BATCH Consumer")
    print("="*70)
    print("Saves COMPLETE batches to SQLite database")
    print("Sends real-time updates via WebSocket")
    print("Each batch = NEW report card on frontend")
    print("="*70)
    print()
    
    asyncio.run(subscribe_to_batches())
