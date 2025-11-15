"""
Print Features - Subscribe to client_features on NATS and save to CSV
"""

import asyncio
import pandas as pd
import json
import os
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, OUTPUT_PATH
from datetime import datetime


class FeaturePrinter:
    def __init__(self, output_file="client_features.csv"):
        self.nc = None
        self.output_file = os.path.join(OUTPUT_PATH, output_file)
        self.features_buffer = []
        self.total_received = 0
        self.last_save_time = datetime.now()

        # Create output directory
        os.makedirs(OUTPUT_PATH, exist_ok=True)

    async def connect(self):
        """Connect to NATS server"""
        self.nc = NATS()
        try:
            await self.nc.connect(NATS_SERVER)
            print(f"✓ Connected to NATS server at {NATS_SERVER}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to NATS: {e}")
            print(f"\nPlease start NATS server first:")
            print(f"  docker run -p 4222:4222 -p 8222:8222 nats:latest")
            return False

    async def disconnect(self):
        """Disconnect from NATS server"""
        if self.nc:
            await self.nc.close()
            print("✓ Disconnected from NATS")

    def save_to_csv(self):
        """Save buffered features to CSV"""
        if len(self.features_buffer) == 0:
            return

        # Convert to DataFrame
        df = pd.DataFrame(self.features_buffer)

        # Remove duplicates (keep latest)
        if 'client_id' in df.columns:
            df = df.drop_duplicates(subset=['client_id'], keep='last')

        # Save to CSV
        df.to_csv(self.output_file, index=False)

        print(f"✓ Saved {len(df)} client features to {self.output_file}")
        print(f"  Total messages received: {self.total_received}")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Clear buffer
        self.features_buffer = []
        self.last_save_time = datetime.now()

    async def subscribe_to_features(self):
        """Subscribe to client_features subject"""
        subject = SUBJECTS['client_features']

        async def message_handler(msg):
            # Parse JSON message
            data = json.loads(msg.data.decode())

            # Add to buffer
            self.features_buffer.append(data)
            self.total_received += 1

            print(f"[FEATURES] Received feature #{self.total_received} | Buffer size: {len(self.features_buffer)}")

            # Save every 100 messages or every 30 seconds
            time_since_save = (datetime.now() - self.last_save_time).total_seconds()

            if len(self.features_buffer) >= 100 or time_since_save >= 30:
                self.save_to_csv()

        # Subscribe
        await self.nc.subscribe(subject, cb=message_handler)
        print(f"✓ Subscribed to {subject}")
        print(f"✓ Will save features to {self.output_file}\n")

    async def run(self):
        """Main run loop"""
        print("="*80)
        print("PRINT FEATURES - SAVE CLIENT FEATURES TO CSV")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print(f"Output file: {self.output_file}")
        print("="*80 + "\n")

        # Connect
        if not await self.connect():
            return

        # Subscribe
        await self.subscribe_to_features()

        print("Listening for client features...\n")

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✓ Interrupted by user")
            # Save any remaining features
            if len(self.features_buffer) > 0:
                print("\nSaving remaining features...")
                self.save_to_csv()
        finally:
            await self.disconnect()


async def main():
    printer = FeaturePrinter()
    await printer.run()


if __name__ == "__main__":
    asyncio.run(main())
