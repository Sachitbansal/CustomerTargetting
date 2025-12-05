# Real-Time Customer Data Streaming System

This system uses NATS for message streaming, SQLite for data storage, and WebSocket for real-time frontend updates.

## Architecture

```
NATS Publisher → NATS Server → NATS Consumer → SQLite DB → Flask API → WebSocket → Frontend
                                      ↓
                                  Notify Flask
```

## Prerequisites

1. **Install NATS Server** (if not already installed):
   ```bash
   # On Ubuntu/Debian
   wget https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz
   tar -xzf nats-server-v2.10.7-linux-amd64.tar.gz
   sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
   
   # Or using Docker
   docker run -p 4222:4222 -p 8222:8222 nats:latest
   ```

2. **Install Python dependencies**:
   ```bash
   cd Backend
   pip3 install -r requirements.txt
   ```

3. **Install Frontend dependencies**:
   ```bash
   cd Frontend
   npm install
   ```

## Running the System

You need to run **4 terminals** simultaneously:

### Terminal 1: NATS Server
```bash
nats-server
# Or with Docker: docker run -p 4222:4222 -p 8222:8222 nats:latest
```

### Terminal 2: Flask API with WebSocket
```bash
cd Backend
python3 app.py
```

### Terminal 3: NATS Consumer (Database Writer)
```bash
cd Backend
python3 nats_consumer.py
```

### Terminal 4: NATS Publisher (Data Generator)
```bash
cd Backend
python3 nats_publisher.py
```

### Terminal 5: Frontend (React/Vite)
```bash
cd Frontend
npm run dev
```

## How It Works

1. **NATS Publisher** generates 1000 mock customer records
   - Publishes 1 customer every 5 seconds
   - Uses realistic Indian names and data
   - Assigns customers to batches
   - Total time: ~83 minutes (5 seconds × 1000)

2. **NATS Consumer** listens for customer data
   - Subscribes to `customer.calls.*` topics
   - Saves data to SQLite database
   - Creates/updates reports automatically
   - Notifies Flask API via HTTP POST

3. **Flask API** serves data and WebSocket
   - REST API for data queries
   - WebSocket server for real-time updates
   - Broadcasts updates to all connected clients

4. **Frontend** displays data in real-time
   - Connects to WebSocket on page load
   - Auto-updates when new data arrives
   - Shows connection status indicator
   - No page refresh needed!

## Features

✅ **1000 customers** generated and streamed  
✅ **5-second intervals** between customers  
✅ **Real-time updates** without page refresh  
✅ **WebSocket connection** indicator  
✅ **Category-based filtering**  
✅ **Batch organization** (6 customers per batch)  
✅ **Mock audio** and **PDF files** assigned  
✅ **Live statistics** updates  

## Monitoring

- **NATS Server**: http://localhost:8222 (monitoring endpoint)
- **Flask API**: http://localhost:5000
- **Frontend**: http://localhost:3000
- **WebSocket**: Automatic via Socket.IO

## Data Flow Example

1. Publisher creates customer #457:
   ```
   {
     "user_id": "CL-076-01",
     "name": "Rahul Sharma",
     "agreed": true,
     "batch_id": "BATCH-CL-0076"
   }
   ```

2. Consumer receives and saves to SQLite

3. Consumer notifies Flask: `POST /api/notify-update`

4. Flask broadcasts via WebSocket: `customer_update` event

5. Frontend receives update and refreshes reports

6. User sees new card appear automatically! 🎉

## Troubleshooting

**NATS connection failed?**
- Make sure NATS server is running on port 4222
- Check: `nats-server --version`

**WebSocket not connecting?**
- Ensure Flask is running with SocketIO
- Check browser console for errors
- Verify CORS is enabled

**No real-time updates?**
- Check all 5 terminals are running
- Verify NATS consumer is receiving messages
- Check Flask logs for WebSocket connections

## Performance

- **Throughput**: 12 customers/minute
- **Batch creation**: 2 batches/minute
- **Database**: SQLite with indexing
- **WebSocket**: Broadcasts to all clients simultaneously
- **Memory**: Low footprint (~50MB total)

## Next Steps

- Add authentication to WebSocket
- Implement data persistence across restarts
- Add monitoring dashboard
- Scale with NATS JetStream for persistence
