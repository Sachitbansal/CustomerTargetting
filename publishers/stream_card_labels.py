"""
NATS Publisher for Card Labels Data
Streams card_labels.csv from stream_tables to NATS
"""

import asyncio
import pandas as pd
import json
import os
from nats.aio.client import Client as NATS
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nats_config import NATS_SERVER, SUBJECTS, STREAM_PATH


async def stream_card_labels_continuous(batch_size=5, delay=3):
    """Stream card_labels data continuously"""
    nc = NATS()
    await nc.connect(NATS_SERVER)

    stream_file = os.path.join(STREAM_PATH, "card_labels.csv")
    subject = SUBJECTS['card_labels']

    print(f"[CARD_LABELS] Streaming from {stream_file} to {subject}")

    iteration = 0
    total_published = 0

    while True:
        if not os.path.exists(stream_file):
            print(f"[CARD_LABELS] Stream file not found, waiting...")
            await asyncio.sleep(5)
            continue

        try:
            df = pd.read_csv(stream_file)

            if len(df) == 0:
                print(f"[CARD_LABELS] Stream empty, stopping")
                break

            # Get batch
            rows_to_publish = min(batch_size, len(df))
            batch = df.head(rows_to_publish)

            # Publish to NATS
            for _, row in batch.iterrows():
                message = row.to_dict()
                json_msg = json.dumps(message, default=str)
                await nc.publish(subject, json_msg.encode())

            # Update file
            remaining = df.iloc[rows_to_publish:]
            remaining.to_csv(stream_file, index=False)

            iteration += 1
            total_published += rows_to_publish

            print(f"[CARD_LABELS] Iter {iteration}: Published {rows_to_publish} rows | Remaining: {len(remaining)} | Total: {total_published}")

            await asyncio.sleep(delay)

        except Exception as e:
            print(f"[CARD_LABELS] Error: {e}")
            await asyncio.sleep(5)

    await nc.close()
    print(f"[CARD_LABELS] Complete. Published {total_published} total rows")


if __name__ == "__main__":
    asyncio.run(stream_card_labels_continuous(batch_size=5, delay=3))
