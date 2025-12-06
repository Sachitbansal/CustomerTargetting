# Transaction Pipeline Monitoring - Complete Setup Guide

## 🎯 Overview

This monitoring setup provides comprehensive observability for your Transaction → Enrichment → Dispatcher pipeline using Prometheus metrics.

**What's Monitored:**
- ✅ **Publisher**: CSV injection rate, TPS, NATS publishing, IO performance
- ✅ **Enrichment**: Customer matching, credit scoring, transaction volume, processing latency
- ✅ **Dispatcher**: Lead generation by type, rejection reasons, cooldown filters
- ✅ **Pipeline**: End-to-end latency, NATS queue health, component uptime

## 📁 Project Structure

```
your-project/
├── monitoring/
│   ├── metrics.py                # ⭐ Prometheus metrics module
│   ├── prometheus.yml            # ⭐ Prometheus configuration
│   ├── alerts.yml               # Alert rules
│   ├── docker-compose.yml       # Quick start with Docker
│   └── README_MONITORING.md     # This file
├── transactionPublisher/
│   ├── publisher.py             # Updated with metrics
│   ├── streamer.py             # Updated with metrics
│   └── schema.py
├── enrichment/                  # (Part 2)
├── dispatcher/                  # (Part 2)
├── test_metrics.py             # Test script
├── MONITORING_SETUP.md         # Detailed setup guide
└── METRICS_REFERENCE.md        # Metrics quick reference
```

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Dependencies

```bash
pip install prometheus-client psutil
```

### Step 2: Start Prometheus

**Option A: Using Docker Compose (Recommended)**
```bash
cd monitoring
docker-compose up -d
```

**Option B: Using Docker directly**
```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

**Option C: Native binary**
```bash
# Download from https://prometheus.io/download/
./prometheus --config.file=./monitoring/prometheus.yml
```

### Step 3: Test the Metrics Setup

```bash
python test_metrics.py
```

You should see:
```
✅ Metrics server started on http://localhost:8001/metrics
✅ All metric recording functions work correctly
🎉 SUCCESS! Your monitoring setup is ready.
```

### Step 4: Run Your Publisher

```bash
python transactionPublisher/publisher.py
```

### Step 5: View Metrics

**Prometheus UI:** http://localhost:9090

Try these queries:
- `publisher_current_tps` - Current TPS
- `rate(pipeline_record_processing_total{stage="publisher"}[1m])` - Processing rate
- `rate(publisher_nats_messages_published_total[1m])` - NATS publish rate

**Raw Metrics:** http://localhost:8001/metrics

## 📊 Key Dashboards & Queries

### Publisher Health Check

```promql
# Is publisher running at target TPS?
publisher_current_tps >= 18 and publisher_current_tps <= 22

# NATS publish success rate
rate(publisher_nats_messages_published_total[5m]) 
/ 
(rate(publisher_nats_messages_published_total[5m]) + rate(publisher_nats_publish_errors_total[5m]))

# IO performance (should be < 10ms)
histogram_quantile(0.95, rate(publisher_io_wait_duration_seconds_bucket{operation="append"}[5m]))
```

### Pipeline Flow

```promql
# Records per second at each stage
rate(pipeline_record_processing_total[1m])

# Visualize as a stacked area chart to see the "funnel"
```

### Alerting Queries

```promql
# Publisher stopped
rate(pipeline_record_processing_total{stage="publisher"}[1m]) < 1

# NATS disconnected
nats_connection_status{component="publisher"} == 0

# Memory leak suspected
(
  pipeline_component_memory_usage_bytes{component="publisher"} - 
  pipeline_component_memory_usage_bytes{component="publisher"} offset 10m
) > 100000000
```

## 🎨 Metrics Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Pipeline                         │
│                                                          │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐     │
│  │Publisher │─────>│Enrichment│─────>│Dispatcher│     │
│  │:8001     │      │:8002     │      │:8003     │     │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘     │
│       │ metrics         │ metrics         │ metrics    │
└───────┼─────────────────┼─────────────────┼────────────┘
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
                     HTTP /metrics
                          │
                          ▼
                ┌───────────────────┐
                │   Prometheus      │
                │   :9090           │
                │                   │
                │ • Scrapes metrics │
                │ • Evaluates rules │
                │ • Stores TSDB     │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │   Grafana         │  (Part 2)
                │   :3000           │
                │                   │
                │ • Dashboards      │
                │ • Alerts          │
                │ • Visualization   │
                └───────────────────┘
```

## 📈 Available Metrics

### Publisher (Port 8001)
- `pipeline_record_processing_total{stage="publisher"}` - Records processed
- `publisher_current_tps` - Real-time TPS
- `publisher_nats_messages_published_total` - NATS messages
- `publisher_io_wait_duration_seconds` - IO latency
- `pipeline_component_memory_usage_bytes` - Memory usage

### Enrichment (Port 8002) - Coming in Part 2
- `master_match_success_total` / `master_match_fail_total` - Match rates
- `enrichment_total_volume_processed` - Transaction volume
- `enrichment_average_credit_score` - Credit scores
- `enrichment_bounced_events_total` - Bounced transactions

### Dispatcher (Port 8003) - Coming in Part 2
- `dispatcher_leads_generated_total{type}` - Leads by type
- `dispatcher_lead_rejections_total{reason}` - Rejections
- `dispatcher_cooldown_filter_hits_total` - Cooldown hits
- `dispatcher_lead_latency_seconds` - Lead generation latency

See **METRICS_REFERENCE.md** for complete list.

## 🚨 Alert Rules

Alert rules are defined in `monitoring/alerts.yml`. Key alerts include:

| Alert | Condition | Severity |
|-------|-----------|----------|
| `PublisherFlatline` | TPS < 1 for 1 min | Critical |
| `PublisherLowTPS` | TPS < 18 for 2 min | Warning |
| `PublisherNATSFailures` | Publish errors > 0 | Critical |
| `PublisherHighIOLatency` | IO > 50ms (p95) | Warning |
| `EnrichmentHighOrphanRate` | Orphan rate > 5% | Critical |
| `DispatcherLeadFlood` | Leads > 100/min | Warning |
| `PipelineStalled` | Stage mismatch | Critical |

To enable alerts:
1. Uncomment `rule_files` in `prometheus.yml`
2. Set up Alertmanager (optional)
3. Configure notification channels

## 🔧 Customization

### Changing Metric Ports

Edit your component files:

```python
# transactionPublisher/publisher.py
METRICS_PORT = 8001  # Change to your desired port
```

Update `prometheus.yml`:
```yaml
- job_name: 'transaction-publisher'
  static_configs:
    - targets: ['host.docker.internal:8001']  # Match new port
```

### Adding Custom Metrics

In `monitoring/metrics.py`, add your metric:

```python
my_custom_metric = Counter(
    'my_custom_metric_total',
    'Description of metric',
    ['label1', 'label2'],
    registry=_registry
)

def record_custom_metric(label1_val: str, label2_val: str):
    """Record custom metric"""
    my_custom_metric.labels(label1=label1_val, label2=label2_val).inc()
```

In your component:
```python
from monitoring.metrics import record_custom_metric

# In your code
record_custom_metric("value1", "value2")
```

### Adjusting Scrape Intervals

Edit `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s  # Global default

scrape_configs:
  - job_name: 'transaction-publisher'
    scrape_interval: 5s  # Override for this job
```

## 🐛 Troubleshooting

### Issue: "Address already in use"

**Cause:** Port 8001 is being used by another process.

**Solution:**
```bash
# Find process using port
lsof -i :8001

# Kill it or change your port
# In publisher.py:
METRICS_PORT = 8011  # Different port
```

### Issue: Prometheus shows "Target Down"

**Checks:**
1. Is your component running? `curl http://localhost:8001/metrics`
2. Is Docker networking correct? Try `localhost:8001` instead of `host.docker.internal:8001`
3. Are firewalls blocking the port?

**Debug:**
```bash
# Test from inside Prometheus container
docker exec -it prometheus wget -O- http://host.docker.internal:8001/metrics
```

### Issue: No metrics showing up

**Checks:**
1. Are metrics being recorded? Add debug prints:
   ```python
   print(f"Recording metric: {value}")
   record_csv_row_injected()
   ```
2. Is the metrics server started? Look for:
   ```
   ✅ Metrics server started on http://localhost:8001/metrics
   ```
3. Check Prometheus logs:
   ```bash
   docker logs prometheus
   ```

### Issue: Metrics are stale

**Cause:** Prometheus scrape interval is too long.

**Solution:** Reduce `scrape_interval` in `prometheus.yml` to 5s or 10s.

## 📚 Additional Resources

- **MONITORING_SETUP.md** - Detailed setup instructions
- **METRICS_REFERENCE.md** - Complete metrics reference with queries
- **test_metrics.py** - Test script to verify setup
- **Prometheus Docs:** https://prometheus.io/docs/
- **PromQL Guide:** https://prometheus.io/docs/prometheus/latest/querying/basics/

## 🎯 Next Steps

### Phase 1: Publisher ✅ (Current)
- [x] Metrics module created
- [x] Publisher instrumented
- [x] Prometheus configured
- [x] Basic alerts defined

### Phase 2: Enrichment (Next)
- [ ] Add enrichment metrics
- [ ] Instrument join operations
- [ ] Track match rates
- [ ] Monitor credit scoring

### Phase 3: Dispatcher
- [ ] Add lead generation metrics
- [ ] Track rejection reasons
- [ ] Monitor cooldown filters
- [ ] Measure conversion rates

### Phase 4: Grafana Dashboards
- [ ] Create control room dashboard
- [ ] Add business KPI panels
- [ ] Set up alert notifications
- [ ] Create custom views

## 💡 Best Practices

1. **Keep metrics lightweight** - Don't add metrics in tight loops
2. **Use labels wisely** - Don't create unbounded label cardinality
3. **Monitor the monitors** - Check Prometheus health regularly
4. **Set meaningful alerts** - Avoid alert fatigue
5. **Document custom metrics** - Update METRICS_REFERENCE.md
6. **Test before deploy** - Use test_metrics.py to validate
7. **Version control** - Commit prometheus.yml and alerts.yml

## 🤝 Contributing

When adding new metrics:
1. Add metric definition to `monitoring/metrics.py`
2. Add recording function with docstring
3. Update `METRICS_REFERENCE.md` with query examples
4. Add corresponding alert rule if needed
5. Test with `test_metrics.py`

## 📞 Support

For issues or questions:
1. Check **Troubleshooting** section above
2. Review Prometheus logs: `docker logs prometheus`
3. Test metrics endpoint: `curl http://localhost:8001/metrics`
4. Verify configuration: `promtool check config prometheus.yml`

---

**🎉 Congratulations!** Your transaction pipeline now has production-grade monitoring. Ready for Part 2 (Enrichment & Dispatcher)?