import asyncio
import os
from nats.aio.client import Client as NATS

NATS_URI = os.getenv("NATS_SERVERS", "nats://127.0.0.1:4222")
INPUT_TOPIC = "reports.cluster.ready"

async def message_handler(msg):
    """Handle incoming messages"""
    subject = msg.subject
    data = msg.data.decode()
    print(f"[{subject}] Received: {data}")

async def listen():
    """Connect to NATS and subscribe to the topic"""
    nc = NATS()
    
    try:
        # Connect to NATS server
        await nc.connect(NATS_URI)
        print(f"Connected to NATS at {NATS_URI}")
        print(f"Listening on topic: {INPUT_TOPIC}")
        print("-" * 50)
        
        # Subscribe to the topic
        await nc.subscribe(INPUT_TOPIC, cb=message_handler)
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the connection
        await nc.close()

if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\nShutting down...")