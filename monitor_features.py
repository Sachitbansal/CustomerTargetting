"""
Feature Monitor
Monitors live feature updates from NATS
"""

import asyncio
import json
from nats.aio.client import Client as NATS
from datetime import datetime

# Configuration
NATS_URL = "nats://localhost:4222/"
FEATURES_TOPIC = "features.customer"


class FeatureMonitor:
    """Monitor and display feature updates"""
    
    def __init__(self):
        self.update_count = {}
        self.total_updates = 0
        
    async def handle_feature_update(self, msg):
        """Handle incoming feature updates"""
        try:
            features = json.loads(msg.data.decode())
            customer_id = features.get('customer_id')
            
            # Track updates
            self.update_count[customer_id] = self.update_count.get(customer_id, 0) + 1
            self.total_updates += 1
            
            # Display update
            print("\n" + "=" * 70)
            print(f"CUSTOMER {customer_id} - Feature Update #{self.update_count[customer_id]}")
            print("=" * 70)
            
            # Transaction counts
            print("\n📊 Transaction Metrics:")
            print(f"  Total Transactions: {features.get('total_transactions', 0)}")
            print(f"  Income Transactions: {features.get('num_income', 0)}")
            print(f"  Expense Transactions: {features.get('num_expense', 0)}")
            
            # Financial metrics
            print("\n💰 Financial Summary:")
            print(f"  Total Income:     ${features.get('total_income', 0):>12,.2f}")
            print(f"  Total Expense:    ${features.get('total_expense', 0):>12,.2f}")
            print(f"  Net Cashflow:     ${features.get('net_cashflow', 0):>12,.2f}")
            print(f"  Current Balance:  ${features.get('balance_current', 0):>12,.2f}")
            
            # Averages
            print("\n📈 Average Amounts:")
            print(f"  Avg Income:       ${features.get('avg_income', 0):>12,.2f}")
            print(f"  Avg Expense:      ${features.get('avg_expense', 0):>12,.2f}")
            print(f"  Avg Transaction:  ${features.get('avg_transaction_size', 0):>12,.2f}")
            
            # Ratios and rates
            print("\n📊 Key Ratios:")
            print(f"  Income/Expense Ratio:   {features.get('income_expense_ratio', 0):>8.2f}")
            print(f"  Spending Rate:          {features.get('spending_rate', 0):>8.2%}")
            print(f"  Balance Volatility:     {features.get('balance_volatility', 0):>8.4f}")
            print(f"  Transaction Frequency:  {features.get('transaction_frequency', 0):>8.2f}/day")
            
            # Category analysis
            print("\n🏷️  Category Analysis:")
            print(f"  Unique Categories:      {features.get('unique_categories', 0)}")
            print(f"  Primary Category:       {features.get('primary_category', 'N/A')}")
            print(f"  Category Concentration: {features.get('category_concentration', 0):>8.2%}")
            
            # Consistency
            print("\n🎯 Consistency Metrics:")
            print(f"  Income Consistency:     {features.get('income_consistency', 0):>8.2f}")
            print(f"  Expense Consistency:    {features.get('expense_consistency', 0):>8.2f}")
            
            print("\n" + "-" * 70)
            print(f"Total Updates Received: {self.total_updates} | Unique Customers: {len(self.update_count)}")
            print("-" * 70)
            
        except Exception as e:
            print(f"Error processing update: {e}")


async def main():
    """Main monitoring function"""
    nc = NATS()
    monitor = FeatureMonitor()
    
    try:
        print("=" * 70)
        print("Real-time Feature Monitor")
        print("=" * 70)
        print(f"\nConnecting to NATS at {NATS_URL}...")
        await nc.connect(NATS_URL)
        print("✓ Connected to NATS\n")
        
        # Subscribe to features
        await nc.subscribe(FEATURES_TOPIC, cb=monitor.handle_feature_update)
        print(f"✓ Subscribed to {FEATURES_TOPIC}")
        
        print("\n" + "=" * 70)
        print("Monitoring live feature updates...")
        print("Waiting for transactions to be published...")
        print("=" * 70)
        print("\nTo send transactions, run:")
        print("  python publish_transactions.py")
        print("\nPress Ctrl+C to stop")
        print("=" * 70 + "\n")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nShutdown requested")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await nc.close()
        print("\n✓ Disconnected from NATS\n")


if __name__ == "__main__":
    asyncio.run(main())