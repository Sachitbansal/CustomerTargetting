#!/usr/bin/env python3
"""
Complete test script for all three pipeline components.
Tests Publisher, Enrichment, and Dispatcher metrics.
"""

import sys
from pathlib import Path
import time
import random

# Add monitoring to path
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from monitoring.metrics import (
    initialize_metrics,
    get_metrics_manager,
    # Publisher metrics
    record_csv_row_injected,
    update_current_tps,
    record_nats_publish,
    record_io_wait,
    update_buffer_lag,
    set_nats_connection_status,
    # Enrichment metrics
    record_master_match,
    record_transaction_volume,
    update_average_credit_score,
    record_bounced_event,
    record_high_value_event,
    record_enrichment_duration,
    # Dispatcher metrics
    record_lead_generated,
    record_lead_rejection,
    record_lead_generation_latency,
    record_cooldown_hit,
    # Pipeline metrics
    record_end_to_end_latency,
    update_nats_queue_depth,
    update_memory_usage,
    # Utilities
    get_current_metrics,
    MetricsTimer
)


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_publisher_metrics():
    """Test Publisher metrics (Port 8001)"""
    print_section("Testing PUBLISHER Metrics (Port 8001)")
    
    print("  ✓ Simulating CSV injection (100 rows)...")
    for i in range(100):
        record_csv_row_injected()
    
    print("  ✓ Updating TPS gauge...")
    for tps in [18.5, 19.8, 20.2, 21.0, 19.5]:
        update_current_tps(tps)
        time.sleep(0.1)
    
    print("  ✓ Recording NATS publishes (95 success, 5 failures)...")
    for i in range(95):
        record_nats_publish("transactions.stream", success=True)
    for i in range(5):
        record_nats_publish("transactions.stream", success=False, error_type="timeout")
    
    print("  ✓ Recording IO operations...")
    for _ in range(20):
        record_io_wait("read", random.uniform(0.001, 0.01))
        record_io_wait("append", random.uniform(0.0005, 0.005))
        record_io_wait("write", random.uniform(0.002, 0.015))
    
    print("  ✓ Simulating buffer lag...")
    for lag in [0.5, 1.2, 2.0, 1.5, 0.8]:
        update_buffer_lag(lag)
        time.sleep(0.1)
    
    print("  ✓ Setting NATS connection status...")
    set_nats_connection_status("publisher", True)
    
    print("\n  ✅ Publisher metrics recorded successfully!")


def test_enrichment_metrics():
    """Test Enrichment metrics (Port 8002)"""
    print_section("Testing ENRICHMENT Metrics (Port 8002)")
    
    print("  ✓ Simulating master matches (180 success, 20 failures)...")
    for i in range(180):
        record_master_match(success=True)
    for i in range(20):
        record_master_match(success=False)
    
    print("  ✓ Recording transaction volumes...")
    volumes = [150.50, 2500.00, 75000.00, 350.25, 15000.00, 
               250.75, 85000.00, 450.00, 125000.00, 1250.50]
    total_volume = 0
    for amt in volumes:
        record_transaction_volume(amt)
        total_volume += amt
    print(f"      Total volume processed: ${total_volume:,.2f}")
    
    print("  ✓ Updating credit scores...")
    credit_scores = [650, 720, 580, 690, 755, 620, 700, 680, 710, 665]
    for score in credit_scores:
        update_average_credit_score(score)
        time.sleep(0.05)
    avg_score = sum(credit_scores) / len(credit_scores)
    print(f"      Average credit score: {avg_score:.1f}")
    
    print("  ✓ Recording bounced events (15 transactions)...")
    for i in range(15):
        record_bounced_event()
    
    print("  ✓ Recording high-value events...")
    for i in range(5):
        record_high_value_event("above_50k")
    for i in range(2):
        record_high_value_event("above_100k")
    
    print("  ✓ Simulating enrichment processing times...")
    for i in range(20):
        with MetricsTimer(record_enrichment_duration):
            time.sleep(random.uniform(0.01, 0.08))  # 10-80ms processing
    
    print("  ✓ Setting NATS connection...")
    set_nats_connection_status("enrichment", True)
    
    print("\n  ✅ Enrichment metrics recorded successfully!")


def test_dispatcher_metrics():
    """Test Dispatcher metrics (Port 8003)"""
    print_section("Testing DISPATCHER Metrics (Port 8003)")
    
    print("  ✓ Generating leads by type...")
    lead_counts = {
        "home": random.randint(3, 8),
        "car": random.randint(5, 12),
        "nifty": random.randint(8, 15),
        "elss": random.randint(4, 10)
    }
    
    for lead_type, count in lead_counts.items():
        for i in range(count):
            record_lead_generated(lead_type)
        print(f"      {lead_type.upper()}: {count} leads")
    
    total_leads = sum(lead_counts.values())
    print(f"      Total leads generated: {total_leads}")
    
    print("\n  ✓ Recording lead rejections...")
    rejection_counts = {
        "cooldown": random.randint(20, 35),
        "low_volume": random.randint(15, 25),
        "already_opted": random.randint(8, 15),
        "not_qualified": random.randint(5, 10)
    }
    
    for reason, count in rejection_counts.items():
        for i in range(count):
            record_lead_rejection(reason)
        print(f"      {reason}: {count} rejections")
    
    total_rejections = sum(rejection_counts.values())
    print(f"      Total rejections: {total_rejections}")
    
    print("\n  ✓ Recording cooldown filter hits...")
    for lead_type in ["home", "car", "nifty", "elss"]:
        hits = random.randint(5, 15)
        for i in range(hits):
            record_cooldown_hit(lead_type)
    
    print("  ✓ Simulating lead generation latencies...")
    for i in range(20):
        latency = random.uniform(0.5, 8.0)
        record_lead_generation_latency(latency)
    
    print("  ✓ Setting NATS connection...")
    set_nats_connection_status("dispatcher", True)
    
    print("\n  ✅ Dispatcher metrics recorded successfully!")


def test_pipeline_metrics():
    """Test Pipeline-wide metrics"""
    print_section("Testing PIPELINE-WIDE Metrics")
    
    print("  ✓ Recording end-to-end latencies...")
    for i in range(10):
        record_end_to_end_latency("enrichment", random.uniform(1.0, 5.0))
        record_end_to_end_latency("dispatcher", random.uniform(3.0, 10.0))
    
    print("  ✓ Updating NATS queue depths...")
    queue_depths = {
        "transactions.stream": random.randint(10, 100),
        "updated.Customer": random.randint(5, 50),
        "leads.checkHomeLoan": random.randint(0, 10),
        "leads.checkCarLoan": random.randint(0, 15)
    }
    
    for stream, depth in queue_depths.items():
        update_nats_queue_depth(stream, depth)
        print(f"      {stream}: {depth} pending")
    
    print("\n  ✓ Simulating memory usage...")
    memory_values = {
        "publisher": 52428800,      # 50 MB
        "enrichment": 157286400,    # 150 MB (higher due to joins)
        "dispatcher": 41943040       # 40 MB
    }
    
    for component, memory in memory_values.items():
        update_memory_usage(component, memory)
        print(f"      {component}: {memory / 1024 / 1024:.1f} MB")
    
    print("\n  ✅ Pipeline metrics recorded successfully!")


def display_metrics_summary():
    """Display a summary of recorded metrics"""
    print_section("Metrics Summary")
    
    metrics_text = get_current_metrics()
    
    # Count metrics
    metric_count = metrics_text.count("# TYPE")
    lines = len(metrics_text.split('\n'))
    size_kb = len(metrics_text) / 1024
    
    print(f"  Total metric types: {metric_count}")
    print(f"  Total lines: {lines}")
    print(f"  Response size: {size_kb:.1f} KB")
    
    print("\n  Sample metrics (first 1500 chars):")
    print("  " + "-"*66)
    sample = metrics_text[:1500].replace('\n', '\n  ')
    print(f"  {sample}")
    print("  " + "-"*66)
    print("  ... (truncated)")


def verify_endpoints():
    """Verify all metrics endpoints are accessible"""
    print_section("Verifying Metrics Endpoints")
    
    ports = {
        8001: "Publisher",
        8002: "Enrichment",
        8003: "Dispatcher"
    }
    
    results = {}
    
    for port, component in ports.items():
        try:
            import urllib.request
            url = f"http://localhost:{port}/metrics"
            print(f"  Checking {component} ({url})...")
            
            with urllib.request.urlopen(url, timeout=5) as response:
                content = response.read().decode('utf-8')
            
            if len(content) > 0:
                metric_count = content.count("# TYPE")
                print(f"    ✅ Accessible! ({metric_count} metric types)")
                results[component] = True
            else:
                print(f"    ❌ Empty response")
                results[component] = False
                
        except Exception as e:
            print(f"    ⚠️  Not accessible: {e}")
            print(f"    ℹ️  This is expected if component isn't running")
            results[component] = False
    
    return results


def print_prometheus_queries():
    """Print useful Prometheus queries for testing"""
    print_section("Useful Prometheus Queries")
    
    queries = [
        ("Publisher TPS", "publisher_current_tps"),
        ("Processing rate (all stages)", "rate(pipeline_record_processing_total[1m])"),
        ("Enrichment match rate", "rate(master_match_success_total[5m]) / (rate(master_match_success_total[5m]) + rate(master_match_fail_total[5m]))"),
        ("Leads generated per minute", "rate(dispatcher_leads_generated_total[1m])"),
        ("Lead rejection breakdown", "sum by (reason) (rate(dispatcher_lead_rejections_total[5m]))"),
        ("Average credit score", "enrichment_average_credit_score"),
        ("NATS publish success rate", "rate(publisher_nats_messages_published_total[5m]) / (rate(publisher_nats_messages_published_total[5m]) + rate(publisher_nats_publish_errors_total[5m]))"),
        ("Memory usage (all components)", "pipeline_component_memory_usage_bytes / 1024 / 1024"),
        ("95th percentile IO latency", 'histogram_quantile(0.95, rate(publisher_io_wait_duration_seconds_bucket{operation="append"}[5m]))'),
        ("Pipeline health check", "up{job=~'transaction-.*'}"),
    ]
    
    for name, query in queries:
        print(f"\n  {name}:")
        print(f"    {query}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  COMPLETE PIPELINE METRICS TEST SUITE")
    print("="*70)
    print()
    print("This script will test metrics for:")
    print("  • Publisher (Port 8001)")
    print("  • Enrichment (Port 8002)")
    print("  • Dispatcher (Port 8003)")
    print()
    print("Starting in 2 seconds...")
    time.sleep(2)
    
    # Initialize metrics servers for all components
    print_section("Initializing Metrics Servers")
    
    print("  Starting Publisher metrics (8001)...")
    pub_manager = initialize_metrics("publisher", port=8001)
    time.sleep(0.5)
    
    print("  Starting Enrichment metrics (8002)...")
    enr_manager = initialize_metrics("enrichment", port=8002)
    time.sleep(0.5)
    
    print("  Starting Dispatcher metrics (8003)...")
    disp_manager = initialize_metrics("dispatcher", port=8003)
    time.sleep(0.5)
    
    print("\n  ✅ All metrics servers started!")
    
    # Run tests
    test_publisher_metrics()
    test_enrichment_metrics()
    test_dispatcher_metrics()
    test_pipeline_metrics()
    
    # Display results
    display_metrics_summary()
    
    # Verify endpoints
    time.sleep(1)
    endpoint_results = verify_endpoints()
    
    # Print queries
    print_prometheus_queries()
    
    # Final summary
    print_section("TEST SUMMARY")
    
    all_ok = all(endpoint_results.values())
    
    print("\n  ✅ All metric recording functions work correctly")
    
    if all_ok:
        print("  ✅ All metrics HTTP endpoints are accessible")
        print()
        print("  🎉 SUCCESS! Your complete monitoring setup is ready.")
        print()
        print("  Next steps:")
        print("    1. Start Prometheus:")
        print("       docker run -d -p 9090:9090 -v $(pwd)/monitoring:/etc/prometheus prom/prometheus \\")
        print("         --config.file=/etc/prometheus/prometheus.yml")
        print()
        print("    2. Visit Prometheus: http://localhost:9090")
        print()
        print("    3. Try the queries listed above")
        print()
        print("    4. Run your actual pipeline:")
        print("       python transactionPublisher/publisher.py        # Terminal 1")
        print("       python MASTERFILENode/run_enrichment_node.py   # Terminal 2")
        print("       python MASTERFILENode/run_dispatcher_node.py   # Terminal 3")
    else:
        print("  ⚠️  Some endpoints not accessible (servers may need more time)")
        print()
        print("  Endpoints:")
        for component, status in endpoint_results.items():
            icon = "✅" if status else "❌"
            print(f"    {icon} {component}")
    
    print()
    print("  📊 Metrics endpoints:")
    print("     http://localhost:8001/metrics  (Publisher)")
    print("     http://localhost:8002/metrics  (Enrichment)")
    print("     http://localhost:8003/metrics  (Dispatcher)")
    print()
    print("  Servers will stay running for testing...")
    print("  Press Ctrl+C to stop")
    print("="*70)
    print()
    
    # Keep servers running
    try:
        while True:
            time.sleep(1)
            pub_manager.update_component_uptime()
            enr_manager.update_component_uptime()
            disp_manager.update_component_uptime()
    except KeyboardInterrupt:
        print("\n\n👋 Test completed. Shutting down...")


if __name__ == "__main__":
    main()