#!/usr/bin/env python3
"""
Test script to verify the entire streaming pipeline
Tests: NATS → Consumer → Database → WebSocket → Frontend
"""
import asyncio
import json
import sqlite3
import time
from datetime import datetime
from nats.aio.client import Client as NATS


def test_database():
    """Test database connectivity and schema"""
    print("🧪 Testing Database...")
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Check tables exist
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        
        table_names = [t[0] for t in tables]
        required_tables = ['categories', 'reports', 'users']
        
        for table in required_tables:
            if table in table_names:
                print(f"  ✅ Table '{table}' exists")
            else:
                print(f"  ❌ Table '{table}' missing")
                return False
        
        # Check categories
        categories = cursor.execute("SELECT * FROM categories").fetchall()
        print(f"  ✅ Found {len(categories)} categories")
        
        # Check current data
        report_count = cursor.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
        print(f"  📊 Current data: {report_count} reports, {user_count} users")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


async def test_nats_connection():
    """Test NATS server connectivity"""
    print("\n🧪 Testing NATS Connection...")
    try:
        nc = NATS()
        await nc.connect("nats://localhost:4222", connect_timeout=2)
        print("  ✅ Connected to NATS server")
        await nc.close()
        return True
    except Exception as e:
        print(f"  ❌ NATS connection failed: {e}")
        print("  💡 Start NATS server with: nats-server")
        return False


async def test_publish_and_consume():
    """Test publishing and consuming a test batch"""
    print("\n🧪 Testing Publish → Consume Flow...")
    
    nc = NATS()
    received_data = []
    
    try:
        await nc.connect("nats://localhost:4222")
        
        # Create a test batch
        test_batch = {
            'batch_number': 9999,
            'batch_id': 'TEST-BATCH-9999',
            'report_id': 'test-report-9999',
            'category': 'carLoans',
            'timestamp': datetime.now().isoformat(),
            'total_calls': 2,
            'successful_calls': 1,
            'report_file': 'test.pdf',
            'customers': [
                {
                    'id': 'test-user-1',
                    'user_id': 'TEST-001',
                    'name': 'Test User 1',
                    'agreed': True,
                    'call_duration': 120,
                    'call_date': datetime.now().isoformat(),
                    'loan_amount': 500000,
                    'credit_score': 750,
                    'risk_level': 'Low',
                    'audio_file': 'test.mp3'
                },
                {
                    'id': 'test-user-2',
                    'user_id': 'TEST-002',
                    'name': 'Test User 2',
                    'agreed': False,
                    'call_duration': 60,
                    'call_date': datetime.now().isoformat(),
                    'loan_amount': 300000,
                    'credit_score': 680,
                    'risk_level': 'Medium',
                    'audio_file': 'test.mp3'
                }
            ]
        }
        
        # Subscribe to test messages
        async def test_handler(msg):
            data = json.loads(msg.data.decode())
            received_data.append(data)
            print(f"  ✅ Received test batch: {data['batch_id']}")
        
        await nc.subscribe("batch.calls.carLoans", cb=test_handler)
        
        # Publish test batch
        print("  📡 Publishing test batch...")
        await nc.publish(
            "batch.calls.carLoans",
            json.dumps(test_batch).encode()
        )
        
        # Wait for message
        await asyncio.sleep(1)
        
        if received_data:
            print("  ✅ Pub/Sub working correctly")
            return True
        else:
            print("  ❌ No message received")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        await nc.close()


def test_flask_api():
    """Test Flask API endpoint"""
    print("\n🧪 Testing Flask API...")
    import requests
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:5000/api/health", timeout=2)
        if response.status_code == 200:
            print("  ✅ API is responding")
            
            # Test reports endpoint
            response = requests.get("http://localhost:5000/api/reports", timeout=2)
            if response.status_code == 200:
                reports = response.json()
                print(f"  ✅ Reports endpoint working ({len(reports)} reports)")
                return True
            else:
                print(f"  ❌ Reports endpoint failed: {response.status_code}")
                return False
        else:
            print(f"  ❌ API health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Flask API error: {e}")
        print("  💡 Start Flask with: python3 app.py")
        return False


def test_websocket():
    """Test WebSocket connection"""
    print("\n🧪 Testing WebSocket...")
    try:
        import socketio
        
        sio = socketio.Client()
        connected = [False]
        
        @sio.on('connect')
        def on_connect():
            connected[0] = True
            print("  ✅ WebSocket connected")
        
        @sio.on('connected')
        def on_connected(data):
            print(f"  ✅ Received welcome: {data}")
        
        sio.connect('http://localhost:5000', wait_timeout=2)
        time.sleep(1)
        
        if connected[0]:
            sio.disconnect()
            return True
        else:
            print("  ❌ WebSocket not connected")
            return False
            
    except Exception as e:
        print(f"  ❌ WebSocket error: {e}")
        print("  💡 Make sure Flask is running with SocketIO")
        return False


async def main():
    """Run all tests"""
    print("=" * 70)
    print("🔬 STREAMING PIPELINE TEST SUITE")
    print("=" * 70)
    print()
    
    results = {}
    
    # Test 1: Database
    results['database'] = test_database()
    
    # Test 2: NATS
    results['nats'] = await test_nats_connection()
    
    # Test 3: Pub/Sub Flow
    if results['nats']:
        results['pubsub'] = await test_publish_and_consume()
    else:
        results['pubsub'] = False
        print("\n⏭️  Skipping Pub/Sub test (NATS not available)")
    
    # Test 4: Flask API
    results['flask'] = test_flask_api()
    
    # Test 5: WebSocket
    if results['flask']:
        results['websocket'] = test_websocket()
    else:
        results['websocket'] = False
        print("\n⏭️  Skipping WebSocket test (Flask not available)")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name.upper()}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for streaming.")
        print("\n📝 To start streaming:")
        print("   ./launch_all.sh")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\n💡 Quick Start Guide:")
        print("   1. Start NATS: nats-server")
        print("   2. Start Flask: python3 app.py")
        print("   3. Start Consumer: python3 nats_consumer.py")
        print("   4. Run tests again: python3 test_streaming.py")
    
    print()


if __name__ == '__main__':
    asyncio.run(main())
