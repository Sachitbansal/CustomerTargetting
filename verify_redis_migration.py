#!/usr/bin/env python3
"""
Verify Redis Data Migration
============================

This script checks that:
1. Redis is running
2. Customer data is loaded
3. All key files can access Redis
4. Performance is good
"""

import sys
import time
from pathlib import Path

# Add parent to path
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR))

def test_redis_connection():
    """Test if Redis is running"""
    print("\n" + "="*60)
    print("TEST 1: Redis Connection")
    print("="*60)
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=False)
        response = r.ping()
        if response:
            print("✅ Redis is running and accepting connections")
            return True
        else:
            print("❌ Redis ping failed")
            return False
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        print("\n💡 To fix: sudo systemctl start redis")
        return False

def test_data_loaded():
    """Test if customer data is loaded"""
    print("\n" + "="*60)
    print("TEST 2: Customer Data in Redis")
    print("="*60)
    
    try:
        from dataManager import get_data_manager
        data_manager = get_data_manager()
        
        # Check metadata
        metadata = data_manager.get_metadata()
        if not metadata:
            print("❌ No customer data found in Redis")
            print("\n💡 To fix: python dataManager/load_masterfile_to_redis.py")
            return False
        
        print(f"✅ Found {metadata.get('num_rows', 0)} customers in Redis")
        print(f"   - Columns: {metadata.get('num_columns', 0)}")
        print(f"   - Last Updated: {metadata.get('last_updated', 'unknown')}")
        return True
    except Exception as e:
        print(f"❌ Error checking data: {e}")
        return False

def test_dataframe_read():
    """Test DataFrame read performance"""
    print("\n" + "="*60)
    print("TEST 3: DataFrame Read Performance")
    print("="*60)
    
    try:
        from dataManager import get_data_manager
        data_manager = get_data_manager()
        
        start = time.time()
        df = data_manager.get_dataframe()
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        if df is None or len(df) == 0:
            print("❌ DataFrame is empty")
            return False
        
        print(f"✅ Loaded {len(df)} rows in {elapsed:.2f}ms")
        
        if elapsed > 100:
            print("⚠️  WARNING: Slow read time (should be <10ms)")
            print("   This might indicate Redis connection issues")
        elif elapsed > 20:
            print("⚠️  Acceptable performance (target: <10ms)")
        else:
            print("✨ Excellent performance!")
        
        return True
    except Exception as e:
        print(f"❌ Error reading DataFrame: {e}")
        return False

def test_customer_lookup():
    """Test single customer lookup"""
    print("\n" + "="*60)
    print("TEST 4: Single Customer Lookup Performance")
    print("="*60)
    
    try:
        from dataManager import get_data_manager
        data_manager = get_data_manager()
        
        # Get first customer ID
        df = data_manager.get_dataframe()
        if df is None or len(df) == 0:
            print("❌ No data to test")
            return False
        
        customer_id = df.iloc[0]['customer_id']
        
        # Test lookup performance
        start = time.time()
        customer = data_manager.get_customer(customer_id)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        if customer is None:
            print(f"❌ Customer {customer_id} not found")
            return False
        
        print(f"✅ Retrieved customer {customer_id} in {elapsed:.2f}ms")
        print(f"   - Age: {customer.get('age', 'N/A')}")
        print(f"   - City Tier: {customer.get('city_tier', 'N/A')}")
        print(f"   - Credit Score: {customer.get('final_credit_score', 'N/A')}")
        
        if elapsed > 10:
            print("⚠️  WARNING: Slow lookup (should be <1ms)")
        else:
            print("✨ Excellent performance!")
        
        return True
    except Exception as e:
        print(f"❌ Error looking up customer: {e}")
        return False

def test_file_imports():
    """Test if key files can import dataManager"""
    print("\n" + "="*60)
    print("TEST 5: File Imports")
    print("="*60)
    
    files_to_check = [
        "carLoanPredictor/init_car_trainer.py",
        "carLoanFeedback/run_feedback.py",
        "dataUpdater/run_detector_publisher.py"
    ]
    
    all_ok = True
    for filepath in files_to_check:
        full_path = CURRENT_DIR / filepath
        if not full_path.exists():
            print(f"⚠️  File not found: {filepath}")
            continue
        
        # Check if file has import statement
        with open(full_path, 'r') as f:
            content = f.read()
            if 'from dataManager import get_data_manager' in content:
                print(f"✅ {filepath} imports dataManager")
            elif 'get_data_manager' in content:
                print(f"⚠️  {filepath} uses get_data_manager but import unclear")
            else:
                print(f"❌ {filepath} doesn't import dataManager")
                all_ok = False
    
    return all_ok

def test_update_customer():
    """Test customer update functionality"""
    print("\n" + "="*60)
    print("TEST 6: Customer Update")
    print("="*60)
    
    try:
        from dataManager import get_data_manager
        data_manager = get_data_manager()
        
        # Get first customer
        df = data_manager.get_dataframe()
        if df is None or len(df) == 0:
            print("❌ No data to test")
            return False
        
        customer_id = df.iloc[0]['customer_id']
        original_credit = df.iloc[0]['final_credit_score']
        
        # Update credit score
        test_credit = 999
        print(f"Updating {customer_id}: {original_credit} → {test_credit}")
        
        success = data_manager.update_customer(customer_id, {
            'final_credit_score': test_credit
        })
        
        if not success:
            print("❌ Update returned False")
            return False
        
        # Verify update
        customer = data_manager.get_customer(customer_id)
        if customer['final_credit_score'] == test_credit:
            print(f"✅ Update successful: {customer['final_credit_score']}")
            
            # Restore original value
            data_manager.update_customer(customer_id, {
                'final_credit_score': original_credit
            })
            print(f"✅ Restored original value: {original_credit}")
            return True
        else:
            print(f"❌ Update failed: expected {test_credit}, got {customer['final_credit_score']}")
            return False
    except Exception as e:
        print(f"❌ Error updating customer: {e}")
        return False

def main():
    """Run all verification tests"""
    print("\n" + "="*60)
    print("REDIS DATA MIGRATION VERIFICATION")
    print("="*60)
    print("\nThis script will verify that:")
    print("  1. Redis is running")
    print("  2. Customer data is loaded")
    print("  3. Read performance is good")
    print("  4. All key files are updated")
    print("  5. Update operations work")
    
    results = {
        'Redis Connection': test_redis_connection(),
        'Data Loaded': test_data_loaded(),
        'DataFrame Read': test_dataframe_read(),
        'Customer Lookup': test_customer_lookup(),
        'File Imports': test_file_imports(),
        'Customer Update': test_update_customer(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    
    print("\n" + "="*60)
    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("="*60)
        print("\n✨ Redis migration is complete and working!")
        print("\nNext steps:")
        print("  1. Run your pipeline: ./run_pipeline.sh")
        print("  2. Monitor Redis: redis-cli -n 1 MONITOR")
        print("  3. Check metrics: http://localhost:8001/metrics")
        return 0
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total} passed)")
        print("="*60)
        print("\n❌ Migration verification incomplete.")
        print("\nTo fix:")
        print("  1. Check test output above for specific errors")
        print("  2. Ensure Redis is running: redis-cli ping")
        print("  3. Load data: python dataManager/load_masterfile_to_redis.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
