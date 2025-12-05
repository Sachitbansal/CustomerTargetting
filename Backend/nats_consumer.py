"""
NATS Consumer - Subscribes to customer data and updates SQLite database
Also emits WebSocket events for real-time frontend updates
"""
import asyncio
import json
from nats.aio.client import Client as NATS
from database import get_db_connection
import requests

# WebSocket notification URL
WEBSOCKET_NOTIFY_URL = "http://localhost:5000/api/notify-update"


def save_customer_to_db(customer_data):
    """Save customer data to SQLite and update/create report"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if report exists
        report = cursor.execute('''
            SELECT id FROM reports WHERE batch_id = ?
        ''', (customer_data['batch_id'],)).fetchone()
        
        if not report:
            # Create new report
            report_id = f"{customer_data['category']}-{customer_data['batch_id'].split('-')[-1]}"
            cursor.execute('''
                INSERT INTO reports (id, batch_id, category_id, timestamp, total_calls, successful_calls, report_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (report_id, customer_data['batch_id'], customer_data['category'], 
                  customer_data['timestamp'], 0, 0, customer_data['report_file']))
            report_id = report_id
            is_new_report = True
        else:
            report_id = report['id']
            is_new_report = False
        
        # Insert user
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (id, user_id, report_id, name, agreed, call_duration, call_date, 
             loan_amount, credit_score, risk_level, audio_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_data['id'], customer_data['user_id'], report_id, 
              customer_data['name'], 1 if customer_data['agreed'] else 0, 
              customer_data['call_duration'], customer_data['call_date'],
              customer_data['loan_amount'], customer_data['credit_score'], 
              customer_data['risk_level'], customer_data['audio_file']))
        
        # Update report stats
        stats = cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN agreed = 1 THEN 1 ELSE 0 END) as successful
            FROM users WHERE report_id = ?
        ''', (report_id,)).fetchone()
        
        cursor.execute('''
            UPDATE reports 
            SET total_calls = ?, successful_calls = ?
            WHERE id = ?
        ''', (stats['total'], stats['successful'], report_id))
        
        conn.commit()
        
        # Get complete report data for WebSocket
        report_data = cursor.execute('''
            SELECT r.*, c.label as category_label, c.prefix as category_prefix
            FROM reports r
            JOIN categories c ON r.category_id = c.id
            WHERE r.id = ?
        ''', (report_id,)).fetchone()
        
        # Get all user IDs for this report
        user_ids = cursor.execute('''
            SELECT user_id FROM users WHERE report_id = ?
        ''', (report_id,)).fetchall()
        
        # Notify WebSocket clients with complete report data
        try:
            notification_data = {
                'type': 'customer_added',
                'is_new_report': is_new_report,
                'customer': customer_data,
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
                    'userIds': [u['user_id'] for u in user_ids]
                },
                'category': customer_data['category']
            }
            
            requests.post(WEBSOCKET_NOTIFY_URL, json=notification_data, timeout=1)
        except:
            pass  # Silently fail if WebSocket server is not available
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


async def subscribe_to_customers():
    """Subscribe to NATS and process incoming customer data"""
    nc = NATS()
    
    try:
        # Connect to NATS
        await nc.connect("nats://localhost:4222")
        print("✅ Connected to NATS server")
        print("👂 Subscribing to customer.calls.* topics")
        print("💾 Ready to save data to SQLite\n")
        
        async def message_handler(msg):
            """Handle incoming messages"""
            try:
                customer_data = json.loads(msg.data.decode())
                
                # Save to database
                success = save_customer_to_db(customer_data)
                
                if success:
                    print(f"✅ Saved: {customer_data['user_id']} | "
                          f"{customer_data['name']} | "
                          f"Batch: {customer_data['batch_id']} | "
                          f"Category: {customer_data['category']}")
                else:
                    print(f"❌ Failed to save: {customer_data['user_id']}")
                    
            except Exception as e:
                print(f"❌ Error processing message: {e}")
        
        # Subscribe to all customer call topics
        await nc.subscribe("customer.calls.*", cb=message_handler)
        
        print("🎧 Listening for messages... (Press Ctrl+C to stop)\n")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down consumer...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await nc.close()


if __name__ == '__main__':
    print("="*60)
    print("🎧 NATS Customer Data Consumer")
    print("="*60)
    print("💾 Saves to SQLite database")
    print("📡 Sends real-time updates via WebSocket")
    print("="*60)
    print()
    
    asyncio.run(subscribe_to_customers())
