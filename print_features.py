import asyncio
import pandas as pd
import json
import os
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, OUTPUT_PATH
from datetime import datetime

class FeatureGrabber:
    def __init__(self, output_file="client_features.csv", listen_seconds=5):
        self.nc = None
        self.output_file = os.path.join(OUTPUT_PATH, output_file)
        self.features_buffer = []
        self.listen_seconds = listen_seconds  # How long to listen for (in seconds)
        os.makedirs(OUTPUT_PATH, exist_ok=True)

    async def connect(self):
        self.nc = NATS()
        await self.nc.connect(NATS_SERVER)
        print(f"✓ Connected to NATS server at {NATS_SERVER}")

    async def disconnect(self):
        if self.nc:
            await self.nc.close()
            print("✓ Disconnected from NATS")

    def save_to_csv(self):
        if len(self.features_buffer) == 0:
            print("No features to save.")
            return
        df = pd.DataFrame(self.features_buffer)
        if 'client_id' in df.columns:
            df = df.drop_duplicates(subset=['client_id'], keep='last')
        df.to_csv(self.output_file, index=False)
        print(f"✓ Saved {len(df)} client features to {self.output_file}")

    async def fetch_snapshot(self):
        subject = SUBJECTS['client_features']
        print(f"Subscribing to {subject} for {self.listen_seconds} seconds...")

        async def message_handler(msg):
            data = json.loads(msg.data.decode())
            self.features_buffer.append(data)
            print(f"[FEATURES] Received feature (total buffer: {len(self.features_buffer)})")

        # Subscribe and collect messages for given duration
        sid = await self.nc.subscribe(subject, cb=message_handler)
        await asyncio.sleep(self.listen_seconds)
        print("✓ Stopped subscription.")

    async def run(self):
        print("="*80)
        print("PRINT FEATURES SNAPSHOT - SAVE CLIENT FEATURES TO CSV")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print(f"Output file: {self.output_file}")
        print(f"Listening for {self.listen_seconds} seconds for available feature messages.")
        print("="*80 + "\n")
        await self.connect()
        await self.fetch_snapshot()
        self.save_to_csv()
        await self.disconnect()

async def main():
    grabber = FeatureGrabber(listen_seconds=10) 
    await grabber.run()

if __name__ == "__main__":
    asyncio.run(main())