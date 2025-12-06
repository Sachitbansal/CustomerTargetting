# Transaction Pipeline Monitoring Setup Guide

## 📁 Directory Structure

```
your-project/
├── monitoring/
│   ├── metrics.py              # Prometheus metrics definitions
│   ├── prometheus.yml          # Prometheus configuration
│   └── alerts.yml             # Alert rules (optional)
├── transactionPublisher/
│   ├── publisher.py           # Updated with metrics
│   ├── streamer.py           # Updated with metrics
│   └── schema.py
├── enrichment/                # (Next part)
└── dispatcher/                # (Next part)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install prometheus-client psutil
```

### 2. Start Prometheus

Using Docker:

```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

Or download Prometheus binary and run:

```bash
prometheus --config.file=./monitoring/prometheus.yml
```

### 3. Run Your Publisher

```bash
python transactionPublisher/publisher.py
```

You should see:
```
✅ Metrics server started on http://localhost:8001/metrics
   Component: publisher
```

### 4. Verify Metrics

Visit: http://localhost:8001/metrics

You should see metrics like:
```
# HELP pipeline_record_processing_total Total records processed by stage
# TYPE pipeline_record_processing_total counter
pipeline_record_processing_total{stage="publisher"} 1234.0

# HELP publisher_current_tps Current transactions per second being published
# TYPE publisher_current_tps gauge
publisher_current_tps 20.5
```

### 5. View in Prometheus

Visit: http://localhost:9090

Try these queries:
- `rate(pipeline_record_processing_total{stage="publisher"}[1m])` - Current TPS
- `publisher_current_tps` - Real-time TPS gauge
- `rate(publisher_nats_messages_published_total[1m])` - NATS publish rate
- `histogram_quantile(0.95, rate(publisher_io_wait_duration_seconds_bucket[5m]))` - 95th percentile IO latency

## 📊 Key Metrics for Publisher

### Processing Rate
- `pipeline_record_processing_total{stage="publisher"}` - Total records injected
- `publisher_csv_rows_injected_total` - CSV rows written
- `publisher_current_tps` - Real-time TPS

### NATS Health
- `publisher_nats_messages_published_total` - Successful publishes
- `publisher_nats_publish_errors_total` - Failed publishes
- `nats_connection_status{component="publisher"}` - Connection status (1=up, 0=down)

### Performance
- `publisher_io_wait_duration_seconds` - File operation latency
- `publisher_buffer_lag_seconds` - Writer vs reader lag
- `pipeline_component_memory_usage_bytes{component="publisher"}` - Memory usage

### System Health
- `pipeline_component_uptime_seconds{component="publisher"}` - Uptime
- `pipeline_component_errors_total{component="publisher"}` - Error count

## 🎯 Recommended Queries

### Is the pipeline healthy?
```promql
# All stages processing at expected rate
rate(pipeline_record_processing_total[1m])
```

### Current TPS vs Target
```promql
# Should be ~20 TPS
publisher_current_tps
```

### NATS publish success rate
```promql
# Should be close to 1.0 (100%)
rate(publisher_nats_messages_published_total[5m]) 
/ 
(rate(publisher_nats_messages_published_total[5m]) + rate(publisher_nats_publish_errors_total[5m]))
```

### IO performance
```promql
# 95th percentile append latency (should be < 10ms)
histogram_quantile(0.95, rate(publisher_io_wait_duration_seconds_bucket{operation="append"}[5m]))
```

### Memory usage trend
```promql
# Bytes over time
pipeline_component_memory_usage_bytes{component="publisher"}
```

## 🚨 Alert Rules (monitoring/alerts.yml)

See the alerts.yml artifact for pre-configured alert rules including:
- **PublisherDown** - No data for 1 minute
- **LowTPS** - Below 18 TPS for 2 minutes
- **HighIOLatency** - Append latency > 50ms
- **NATSPublishFailures** - Publish errors detected
- **MemoryLeak** - Memory growing continuously

## 🔍 Troubleshooting

### Metrics server won't start
**Error:** `Address already in use`

**Solution:** Another process is using port 8001. Either:
1. Stop the other process
2. Change `METRICS_PORT = 8001` to another port in `publisher.py`
3. Update `prometheus.yml` to match the new port

### No metrics in Prometheus
**Check:**
1. Is the metrics endpoint accessible? `curl http://localhost:8001/metrics`
2. Is Prometheus configured correctly? Check `prometheus.yml`
3. Are there errors in Prometheus logs? `docker logs prometheus`
4. Is `host.docker.internal` resolving? (Use `localhost:8001` if not in Docker)

### TPS is 0 or wrong
**Check:**
1. Is the CSV file being read? Look for `[STREAM] wrote X rows`
2. Is the temp file being created? Check `temp_txn_stream.csv`
3. Are there errors in the streamer thread?

## 📈 Next Steps

1. **Add Enrichment metrics** (port 8002)
   - Master match rates
   - Credit score distributions
   - Processing latency

2. **Add Dispatcher metrics** (port 8003)
   - Lead generation by type
   - Rejection reasons
   - Cooldown filter hits

3. **Set up Grafana** (coming in Part 2)
   - Import pre-built dashboards
   - Create custom visualizations
   - Set up alert notifications

## 🔗 Useful Links

- Prometheus: http://localhost:9090
- Publisher Metrics: http://localhost:8001/metrics
- Prometheus Docs: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/