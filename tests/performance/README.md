# Performance Testing Suite

Comprehensive performance testing framework for AI Enhanced PDF Scholar, providing concurrent user simulation, load testing, benchmarking, and resource monitoring capabilities.

## Features

### 🚀 Concurrent User Testing
- Simulate multiple simultaneous users
- Various load patterns (gradual, spike, sustained, wave)
- Mixed workload scenarios
- Real-world usage simulation

### 📊 API Benchmarking
- Endpoint performance baselines
- Response time percentiles (P50, P95, P99)
- Throughput measurements
- Performance regression detection

### 💾 Resource Monitoring
- Memory usage tracking and leak detection
- CPU utilization patterns
- Database connection pool monitoring
- File handle and network tracking
- Garbage collection analysis

### 🔥 Load Testing (Locust)
- Distributed load testing
- Multiple user behavior patterns
- Real-time metrics dashboard
- Scalability validation

## Installation

```bash
# Install performance testing dependencies
pip install -r tests/performance/requirements.txt
```

## Quick Start

### Run All Performance Tests
```bash
python tests/performance/run_performance_tests.py --all
```

### Run Specific Test Categories

```bash
# Concurrent user tests only
python tests/performance/run_performance_tests.py --concurrent

# API benchmarks only
python tests/performance/run_performance_tests.py --benchmarks

# Resource monitoring only
python tests/performance/run_performance_tests.py --resources

# Locust load tests
python tests/performance/run_performance_tests.py --locust --users 100 --duration 5m
```

### Establish Performance Baselines
```bash
python tests/performance/run_performance_tests.py --benchmarks --baseline
```

## Test Modules

### 1. Concurrent User Testing (`test_concurrent_users.py`)

Simulates various concurrent user scenarios:

```python
# Run standalone
python -m pytest tests/performance/test_concurrent_users.py -v

# Run specific scenario
python -m pytest tests/performance/test_concurrent_users.py::test_concurrent_gradual_load -v
```

**Scenarios:**
- **Gradual Load Increase**: Ramp up from 1 to 50 users over 3 minutes
- **Spike Load**: Sudden 5x traffic spike
- **Sustained Load**: 30 users for 10 minutes (endurance test)
- **Document Upload Storm**: 25 users uploading simultaneously
- **Query Burst**: Concurrent RAG queries with step increases
- **Heavy Computation**: Complex queries under load
- **Wave Pattern**: Simulates daily usage patterns

### 2. API Benchmarking (`test_api_benchmarks.py`)

Establishes and monitors API endpoint performance:

```python
# Establish baselines
import asyncio
from tests.performance.test_api_benchmarks import APIBenchmarkTest

async def establish():
    test = APIBenchmarkTest()
    await test.establish_baselines(iterations=1000)

asyncio.run(establish())
```

**Monitored Endpoints:**
- Health checks
- Document operations (CRUD)
- RAG queries (simple and complex)
- Citation management
- Vector search
- Session management

### 3. Resource Monitoring (`test_resource_monitoring.py`)

Tracks system resource usage:

```python
# Run resource tests
python -m pytest tests/performance/test_resource_monitoring.py -v
```

**Monitored Resources:**
- Memory (RSS, VMS, heap)
- CPU utilization
- Thread count
- Open files/connections
- Disk I/O
- Network bandwidth
- Database connections
- Python GC statistics

### 4. Locust Load Testing (`locustfile.py`)

Distributed load testing with web UI:

```bash
# Start Locust web UI
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Headless mode
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    --users 100 \
    --spawn-rate 2 \
    --run-time 5m
```

**User Types:**
- `PDFScholarUser`: Standard user behavior
- `AdminUser`: Administrative operations
- `MobileUser`: Mobile app patterns
- `StressTestUser`: Aggressive testing

## Performance Metrics

### Response Time Metrics
- **Mean**: Average response time
- **Median (P50)**: 50th percentile
- **P95**: 95th percentile
- **P99**: 99th percentile
- **Standard Deviation**: Response time variation

### Throughput Metrics
- **Requests/Second**: Overall throughput
- **Success Rate**: Percentage of successful requests
- **Error Rate**: Percentage of failed requests
- **Concurrent Users**: Active user count

### Resource Metrics
- **Memory Usage**: Current, peak, and growth
- **CPU Usage**: Average and peak utilization
- **Database Connections**: Pool usage and saturation
- **Network I/O**: Bandwidth consumption

## Configuration

### Performance Thresholds (`pytest.ini`)

```ini
[pytest]
# Performance thresholds
max_response_time_ms = 1000.0
max_p95_ms = 2000.0
max_p99_ms = 5000.0
min_throughput_rps = 10.0
max_error_rate_percent = 1.0
max_memory_mb = 1024.0
max_cpu_percent = 80.0
```

### Load Patterns

```python
from tests.performance.base_performance import LoadPattern, LoadTestScenario

scenario = LoadTestScenario(
    name="Custom Load Test",
    pattern=LoadPattern.RAMP_UP,  # or SPIKE, CONSTANT, STEP, WAVE, RANDOM
    duration_seconds=300,
    max_users=50,
    ramp_up_time=60,
    requests_per_user=10,
    think_time_ms=2000
)
```

## Reports

Performance tests generate multiple report formats:

### JSON Report
```json
{
  "concurrent_tests": {
    "gradual_load_increase": {
      "success": true,
      "metrics": {
        "response_time_ms": 245.3,
        "p95_ms": 412.5,
        "throughput_rps": 42.7
      }
    }
  }
}
```

### HTML Report
Interactive HTML dashboard with charts and metrics visualization.

### Text Summary
Console-friendly summary of key metrics and violations.

## Continuous Integration

### GitHub Actions Integration

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  performance:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r tests/performance/requirements.txt
    
    - name: Start application
      run: |
        uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        sleep 5
    
    - name: Run performance tests
      run: |
        python tests/performance/run_performance_tests.py \
          --benchmarks \
          --concurrent \
          --resources
    
    - name: Upload reports
      uses: actions/upload-artifact@v3
      with:
        name: performance-reports
        path: performance_reports/
```

## Performance Optimization Tips

### Memory Optimization
1. **Connection Pooling**: Use connection pools for database
2. **Caching**: Implement Redis/memory caching
3. **Streaming**: Use streaming for large file uploads
4. **Garbage Collection**: Tune Python GC settings

### Throughput Optimization
1. **Async Operations**: Use async/await throughout
2. **Batch Processing**: Group similar operations
3. **Rate Limiting**: Implement proper rate limiting
4. **Load Balancing**: Distribute load across instances

### Database Optimization
1. **Indexing**: Ensure proper database indexes
2. **Query Optimization**: Use query profiling
3. **Connection Limits**: Set appropriate pool sizes
4. **Caching**: Cache frequent queries

## Troubleshooting

### Common Issues

**High Memory Usage**
```python
# Check for memory leaks
from tests.performance.test_resource_monitoring import ResourceTestSuite

suite = ResourceTestSuite()
results = await suite.test_memory_leak_detection()
```

**Slow Response Times**
```python
# Profile specific endpoints
from tests.performance.test_api_benchmarks import APIBenchmarkTest

test = APIBenchmarkTest()
metrics = await test.benchmark_endpoint(endpoint_config)
```

**Database Bottlenecks**
```python
# Monitor connection pool
from tests.performance.test_resource_monitoring import DatabaseConnectionMonitor

monitor = DatabaseConnectionMonitor()
summary = monitor.monitor_pool(duration_seconds=60)
```

## Best Practices

1. **Baseline First**: Always establish performance baselines before optimization
2. **Regular Testing**: Run performance tests regularly (nightly/weekly)
3. **Incremental Load**: Start with low load and gradually increase
4. **Monitor Trends**: Track performance metrics over time
5. **Test in Production-like Environment**: Use similar hardware/network
6. **Document Thresholds**: Clearly define acceptable performance levels
7. **Automate Regression Detection**: Set up alerts for performance degradation

## Advanced Usage

### Custom Load Patterns

```python
from tests.performance.base_performance import LoadTestScenario, ConcurrentUserSimulator

async def custom_user_action(session, user_id):
    # Define custom user behavior
    response = await session.get(f"/api/custom/{user_id}")
    return response

scenario = LoadTestScenario(
    name="Custom Scenario",
    pattern=LoadPattern.WAVE,
    duration_seconds=600,
    max_users=100
)

async with ConcurrentUserSimulator(base_url, scenario) as simulator:
    metrics = await simulator.run_load_test(custom_user_action)
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run performance test
await test.run_scenario(scenario, action)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Contributing

When adding new performance tests:

1. Follow the existing test structure
2. Document test scenarios clearly
3. Set appropriate thresholds
4. Include in CI/CD pipeline
5. Update this README

## License

Part of AI Enhanced PDF Scholar project.