#!/bin/bash

echo "======================================"
echo "Real-Time Customer Streaming System"
echo "======================================"
echo ""
echo "This will start the real-time streaming system."
echo "You'll need NATS server running separately."
echo ""
echo "Starting in 3 seconds..."
sleep 3

# Check if NATS is running
if ! nc -z localhost 4222 2>/dev/null; then
    echo "⚠️  WARNING: NATS server not detected on port 4222"
    echo "Please start NATS server in another terminal:"
    echo "  nats-server"
    echo "  OR: docker run -p 4222:4222 nats:latest"
    echo ""
    read -p "Press Enter when NATS is running..."
fi

echo "✅ NATS server detected!"
echo ""
echo "Starting services..."
echo ""

# Start NATS Consumer in background
echo "🎧 Starting NATS Consumer..."
cd "$(dirname "$0")"
python3 nats_consumer.py &
CONSUMER_PID=$!

sleep 2

echo "✅ Consumer started (PID: $CONSUMER_PID)"
echo ""
echo "To start streaming data:"
echo "  python3 nats_publisher.py"
echo ""
echo "Press Ctrl+C to stop the consumer"
echo ""

# Wait for interrupt
trap "echo ''; echo '🛑 Stopping consumer...'; kill $CONSUMER_PID 2>/dev/null; exit" INT TERM

wait $CONSUMER_PID
