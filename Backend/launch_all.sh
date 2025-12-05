#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Real-Time Customer Data Streaming System - LAUNCHER${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Navigate to Backend directory
cd "$(dirname "$0")"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping all services...${NC}"
    
    # Kill all background processes started by this script
    if [ ! -z "$NATS_PID" ]; then
        echo "  Stopping NATS server (PID: $NATS_PID)..."
        kill $NATS_PID 2>/dev/null
    fi
    
    if [ ! -z "$FLASK_PID" ]; then
        echo "  Stopping Flask API (PID: $FLASK_PID)..."
        kill $FLASK_PID 2>/dev/null
    fi
    
    if [ ! -z "$CONSUMER_PID" ]; then
        echo "  Stopping NATS Consumer (PID: $CONSUMER_PID)..."
        kill $CONSUMER_PID 2>/dev/null
    fi
    
    if [ ! -z "$PUBLISHER_PID" ]; then
        echo "  Stopping NATS Publisher (PID: $PUBLISHER_PID)..."
        kill $PUBLISHER_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}

# Trap Ctrl+C and cleanup
trap cleanup SIGINT SIGTERM

echo -e "${YELLOW}📋 Pre-flight Checks...${NC}"
echo ""

# Check if NATS server is available
if ! command -v nats-server &> /dev/null; then
    echo -e "${RED}❌ NATS server not found!${NC}"
    echo "Please install NATS server:"
    echo "  wget https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz"
    echo "  tar -xzf nats-server-v2.10.7-linux-amd64.tar.gz"
    echo "  sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/"
    exit 1
fi

# Check Python dependencies
if ! python3 -c "import nats; import flask_socketio" 2>/dev/null; then
    echo -e "${RED}❌ Python dependencies missing!${NC}"
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"
echo ""

# Check and kill processes on required ports
echo -e "${YELLOW}🔍 Checking for port conflicts...${NC}"

# Check port 5000 (Flask)
FLASK_PORT_PID=$(lsof -ti:5000)
if [ ! -z "$FLASK_PORT_PID" ]; then
    echo "  Killing existing process on port 5000 (PID: $FLASK_PORT_PID)..."
    kill -9 $FLASK_PORT_PID 2>/dev/null
    sleep 1
fi

# Check port 4222 (NATS)
NATS_PORT_PID=$(lsof -ti:4222)
if [ ! -z "$NATS_PORT_PID" ]; then
    echo "  Killing existing NATS process on port 4222 (PID: $NATS_PORT_PID)..."
    kill -9 $NATS_PORT_PID 2>/dev/null
    sleep 1
fi

echo -e "${GREEN}✅ Ports are clear${NC}"
echo ""

# Initialize database
echo -e "${YELLOW}🗄️  Initializing database...${NC}"
python3 database.py
echo ""

# Start NATS Server
echo -e "${YELLOW}🚀 Starting NATS Server...${NC}"
nats-server > /dev/null 2>&1 &
NATS_PID=$!
sleep 2

if ps -p $NATS_PID > /dev/null; then
    echo -e "${GREEN}✅ NATS Server started (PID: $NATS_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start NATS Server${NC}"
    exit 1
fi
echo ""

# Start Flask API with WebSocket
echo -e "${YELLOW}🌐 Starting Flask API with WebSocket...${NC}"
python3 app.py > flask.log 2>&1 &
FLASK_PID=$!
sleep 3

if ps -p $FLASK_PID > /dev/null; then
    echo -e "${GREEN}✅ Flask API started (PID: $FLASK_PID)${NC}"
    echo -e "   API: ${BLUE}http://localhost:5000${NC}"
    echo -e "   WebSocket: ${BLUE}ws://localhost:5000${NC}"
else
    echo -e "${RED}❌ Failed to start Flask API${NC}"
    echo "Check flask.log for errors"
    cleanup
    exit 1
fi
echo ""

# Start NATS Consumer
echo -e "${YELLOW}🎧 Starting NATS Consumer (Database Writer)...${NC}"
python3 nats_consumer.py > consumer.log 2>&1 &
CONSUMER_PID=$!
sleep 2

if ps -p $CONSUMER_PID > /dev/null; then
    echo -e "${GREEN}✅ NATS Consumer started (PID: $CONSUMER_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start NATS Consumer${NC}"
    echo "Check consumer.log for errors"
    cleanup
    exit 1
fi
echo ""

# Start NATS Publisher
echo -e "${YELLOW}📡 Starting NATS Publisher (Data Generator)...${NC}"
python3 nats_publisher.py > publisher.log 2>&1 &
PUBLISHER_PID=$!
sleep 2

if ps -p $PUBLISHER_PID > /dev/null; then
    echo -e "${GREEN}✅ NATS Publisher started (PID: $PUBLISHER_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start NATS Publisher${NC}"
    echo "Check publisher.log for errors"
    cleanup
    exit 1
fi
echo ""

echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ ALL SERVICES RUNNING!${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📊 System Status:${NC}"
echo "  🟢 NATS Server     → Port 4222"
echo "  🟢 Flask API       → http://localhost:5000"
echo "  🟢 WebSocket       → Enabled"
echo "  🟢 NATS Consumer   → Listening"
echo "  🟢 NATS Publisher  → Publishing batches every 3 seconds"
echo ""
echo -e "${YELLOW}📁 Log Files:${NC}"
echo "  flask.log      → Flask API logs"
echo "  consumer.log   → NATS Consumer logs"
echo "  publisher.log  → NATS Publisher logs"
echo ""
echo -e "${YELLOW}🎯 Next Steps:${NC}"
echo "  1. Frontend is already running at http://localhost:5173"
echo "  2. Open browser and navigate to the frontend"
echo "  3. Watch new batch cards appear in real-time!"
echo ""
echo -e "${YELLOW}⏱️  Streaming Info:${NC}"
echo "  • Publishing complete batches (6-8 customers each)"
echo "  • New batch every 3 seconds"
echo "  • Total: 150 batches = ~1050 customers"
echo "  • Estimated time: ~7.5 minutes"
echo ""
echo -e "${RED}Press Ctrl+C to stop all services${NC}"
echo ""

# Monitor the publisher process
echo -e "${YELLOW}📈 Streaming in progress...${NC}"
echo ""

# Follow publisher log in real-time
tail -f publisher.log &
TAIL_PID=$!

# Wait for publisher to finish
wait $PUBLISHER_PID

# Stop tail
kill $TAIL_PID 2>/dev/null

echo ""
echo -e "${GREEN}✅ Publishing complete!${NC}"
echo ""
echo -e "${YELLOW}Services are still running. Press Ctrl+C to stop all services.${NC}"

# Keep the script running
while true; do
    sleep 1
done
