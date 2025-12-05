# Real-Time Streaming System - Setup & Verification

## What Was Fixed

### 🐛 Problem
The frontend WebSocket listener was expecting a different data structure than what the NATS consumer was sending, causing new batches not to appear on the frontend automatically.

### ✅ Solution
1. **Fixed Frontend WebSocket Handler** (`Reports.tsx`)
   - Updated to match the NATS consumer's data structure
   - Now correctly handles `type: 'new_batch'` messages
   - Added duplicate prevention to avoid showing the same batch twice
   - Improved logging for debugging

2. **Created Launch Script** (`launch_all.sh`)
   - Automatically starts all required services in the correct order
   - Includes health checks for each service
   - Proper cleanup on exit (Ctrl+C)
   - Real-time log monitoring

3. **Created Test Suite** (`test_streaming.py`)
   - Validates database connectivity
   - Tests NATS server connection
   - Verifies pub/sub flow
   - Checks Flask API endpoints
   - Tests WebSocket connections

## 🚀 Quick Start

### Option 1: Automated Launch (Recommended)

```bash
cd Backend
./launch_all.sh
```

This single command will:
- ✅ Start NATS server
- ✅ Start Flask API with WebSocket
- ✅ Start NATS Consumer (database writer)
- ✅ Start NATS Publisher (data generator)
- ✅ Show real-time streaming logs

The frontend is already running at http://localhost:5173 - just open it in your browser!

### Option 2: Manual Start (for debugging)

**Terminal 1 - NATS Server:**
```bash
nats-server
```

**Terminal 2 - Flask API:**
```bash
cd Backend
python3 app.py
```

**Terminal 3 - NATS Consumer:**
```bash
cd Backend
python3 nats_consumer.py
```

**Terminal 4 - NATS Publisher:**
```bash
cd Backend
python3 nats_publisher.py
```

**Frontend** (already running):
```bash
# Already running on http://localhost:5173
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
cd Backend
python3 test_streaming.py
```

This will test:
- 🗄️ Database connectivity and schema
- 🔌 NATS server connection
- 📡 Publish/Subscribe flow
- 🌐 Flask API endpoints
- 🔄 WebSocket connections

## 📊 How It Works

### Data Flow
```
NATS Publisher (every 3 seconds)
    ↓
    Generates complete batch (6-8 customers)
    ↓
NATS Server (nats://localhost:4222)
    ↓
    Subject: batch.calls.{category}
    ↓
NATS Consumer
    ↓
    Saves to SQLite database
    ↓
    Sends HTTP POST to Flask
    ↓
Flask API (/api/notify-update)
    ↓
    Emits WebSocket event: 'customer_update'
    ↓
Frontend (React/Socket.IO)
    ↓
    New batch card appears automatically! 🎉
```

### Data Structure

**NATS Message (Complete Batch):**
```json
{
  "batch_number": 42,
  "batch_id": "BATCH-CL-0042",
  "report_id": "carLoans-0042",
  "category": "carLoans",
  "timestamp": "2025-12-06T01:30:00",
  "total_calls": 7,
  "successful_calls": 4,
  "report_file": "Report_example.pdf",
  "customers": [
    {
      "id": "unique-uuid",
      "user_id": "CL-042-01",
      "name": "Rahul Sharma",
      "agreed": true,
      "call_duration": 180,
      "call_date": "2025-12-06T01:28:00",
      "loan_amount": 450000,
      "credit_score": 750,
      "risk_level": "Low",
      "audio_file": "example-1.mpeg"
    }
    // ... 6-7 more customers
  ]
}
```

**WebSocket Event:**
```json
{
  "type": "new_batch",
  "is_new_report": true,
  "batch_number": 42,
  "category": "carLoans",
  "customer_count": 7,
  "report": {
    "id": "carLoans-0042",
    "batch_id": "BATCH-CL-0042",
    "category_id": "carLoans",
    "timestamp": "2025-12-06T01:30:00",
    "total_calls": 7,
    "successful_calls": 4,
    "report_file": "Report_example.pdf",
    "category_label": "Car Loans",
    "category_prefix": "CL",
    "userIds": ["CL-042-01", "CL-042-02", ...]
  }
}
```

## 🔍 Monitoring

### Real-Time Indicators
- **Green dot** 🟢 = WebSocket connected and receiving updates
- **Red dot** 🔴 = WebSocket disconnected (check backend)
- **Last Update** = Shows most recent batch received

### Log Files (when using launch_all.sh)
- `flask.log` - Flask API and WebSocket events
- `consumer.log` - Database writes and NATS messages
- `publisher.log` - Batch generation and publishing

### Service Ports
- NATS Server: `4222` (client), `8222` (monitoring)
- Flask API: `5000`
- WebSocket: `ws://localhost:5000`
- Frontend: `5173` (Vite dev server)

## 📈 Streaming Metrics

- **Batch Frequency:** 1 batch every 3 seconds
- **Batch Size:** 6-8 customers (random)
- **Total Batches:** 150
- **Total Customers:** ~1,050
- **Total Duration:** ~7.5 minutes
- **Agreement Rate:** ~60% (random)

## 🔧 Troubleshooting

### No batches appearing on frontend?

1. **Check WebSocket Connection:**
   - Look for green 🟢 indicator in top-right
   - Open browser console (F12) and check for WebSocket logs
   - Should see: "✅ Connected to WebSocket"

2. **Check Backend Services:**
   ```bash
   # Should see all 4 services
   ps aux | grep -E "(nats-server|app.py|nats_consumer|nats_publisher)"
   ```

3. **Check Logs:**
   ```bash
   # If using launch_all.sh
   tail -f flask.log
   tail -f consumer.log
   tail -f publisher.log
   ```

4. **Test Individual Components:**
   ```bash
   python3 test_streaming.py
   ```

### "Failed to fetch reports" error?

- Make sure Flask is running: `python3 app.py`
- Check Flask is on port 5000: `curl http://localhost:5000/api/health`
- Verify CORS is enabled (should be by default)

### NATS connection refused?

- Start NATS server: `nats-server`
- Verify it's running: `ps aux | grep nats-server`
- Test connection: `nc -zv localhost 4222`

### Database errors?

- Initialize database: `python3 database.py`
- Check file exists: `ls -la database.db`
- Test connectivity: `sqlite3 database.db "SELECT COUNT(*) FROM reports;"`

## 🎯 Success Criteria

When everything is working correctly, you should see:

1. ✅ **Green WebSocket indicator** on frontend
2. ✅ **New batch cards appearing** every ~3 seconds
3. ✅ **No page refresh needed** - real-time updates
4. ✅ **Batch numbers incrementing** (BATCH-XX-0001, BATCH-XX-0002, etc.)
5. ✅ **Correct category filtering** (only current category shows updates)
6. ✅ **Last update showing** batch information in top-right

## 📝 Development Notes

### Key Files Modified
- `Frontend/src/components/Reports.tsx` - Fixed WebSocket event handler
- `Backend/nats_consumer.py` - Sends complete batch data via WebSocket
- `Backend/app.py` - Flask API with SocketIO support

### Architecture Decisions
- **Batching:** Publisher sends complete batches (not individual customers) to reduce message volume
- **WebSocket:** Uses Socket.IO for automatic reconnection and fallback transports
- **Database:** SQLite for simplicity; easily upgradeable to PostgreSQL if needed
- **NATS:** Lightweight message broker, could be upgraded to JetStream for persistence

## 🚧 Future Enhancements

- [ ] Add authentication to WebSocket connections
- [ ] Implement message persistence with NATS JetStream
- [ ] Add monitoring dashboard for system health
- [ ] Support for filtering real-time updates by category
- [ ] Batch replay functionality
- [ ] Export capabilities (CSV, Excel)

## 📚 References

- [NATS Documentation](https://docs.nats.io/)
- [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
- [Socket.IO Client](https://socket.io/docs/v4/client-api/)

---

**Last Updated:** 2025-12-06  
**Status:** ✅ Fully Functional
