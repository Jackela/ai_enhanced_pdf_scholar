# Rate Limiting Documentation

## Overview

The AI Enhanced PDF Scholar API implements comprehensive rate limiting to protect against DoS attacks and ensure fair resource usage. The system supports both IP-based and endpoint-specific rate limiting with Redis-backed distributed storage and in-memory fallback.

## Features

- **Multi-tier Rate Limiting**: Global IP limits + endpoint-specific limits
- **Redis Support**: Distributed rate limiting with automatic fallback to in-memory storage
- **Environment-aware Configuration**: Different limits for development, production, and testing
- **Bypass Mechanisms**: IP and user-agent based bypasses for monitoring and admin access
- **Comprehensive Monitoring**: Real-time metrics, alerts, and suspicious activity detection
- **Graceful Degradation**: Continues serving requests even if rate limiting storage fails

## Configuration

### Environment Variables

```bash
# Redis Configuration (Optional)
REDIS_URL=redis://localhost:6379

# Rate Limiting Overrides
RATE_LIMIT_DISABLE=false                    # Set to 'true' to disable completely
RATE_LIMIT_GLOBAL_LIMIT=1000               # Global requests per hour per IP
RATE_LIMIT_DEFAULT_LIMIT=60                # Default requests per minute
RATE_LIMIT_UPLOAD_LIMIT=10                 # Upload requests per minute
RATE_LIMIT_REDIS_PREFIX=rl:                # Redis key prefix

# Environment Selection
ENVIRONMENT=production                      # production|development|test
```

### Default Rate Limits

#### Production Environment
- **Global Limit**: 500 requests/hour per IP
- **Default Endpoint**: 60 requests/minute per IP
- **Upload Endpoints**: 5 requests/minute per IP
- **Query Endpoints**: 30 requests/minute per IP
- **Read Endpoints**: 100 requests/minute per IP
- **System Health**: 1000 requests/minute per IP

#### Development Environment
- **10x multiplier** applied to all production limits
- **Localhost bypass** enabled for 127.0.0.1, ::1

#### Test Environment
- **100x multiplier** applied to all production limits
- **Full bypasses** for test scenarios

## Endpoint-Specific Limits

| Endpoint Pattern | Production Limit | Description |
|------------------|------------------|-------------|
| `/api/documents/upload` | 5/minute | PDF upload endpoint |
| `/api/library/upload` | 5/minute | Library upload endpoint |
| `/api/rag/query` | 30/minute | RAG query processing |
| `/api/rag/chat` | 50/minute | Chat interactions |
| `/api/documents/query` | 30/minute | Document queries |
| `/api/documents` | 100/minute | Document operations |
| `/api/library` | 100/minute | Library operations |
| `/api/system/health` | 1000/minute | Health checks |
| `/api/system` | 20/minute | Admin operations |

## Rate Limit Headers

Successful responses include rate limiting headers:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1609459200
```

Rate limited responses (429) include additional headers:

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1609459260
Retry-After: 60

{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 60 requests per 60 seconds.",
  "retry_after": 60,
  "limit": 60,
  "remaining": 0,
  "reset": 1609459260
}
```

## Bypass Mechanisms

### IP-based Bypasses

```python
# Development/Test
bypass_ips = {"127.0.0.1", "::1", "localhost"}

# Production (no IP bypasses for security)
bypass_ips = set()
```

### User-Agent Bypasses

```python
bypass_user_agents = {"health-check", "monitor"}
```

Requests with these user agents bypass rate limiting completely.

## Monitoring and Administration

### Admin Endpoints

Access rate limiting administration at `/api/admin/rate-limit/`:

- **GET** `/status` - System status and health
- **GET** `/metrics?window_minutes=60` - Detailed metrics
- **GET** `/ip/{client_ip}?window_minutes=60` - IP analysis
- **GET** `/endpoint?endpoint=/api/documents&window_minutes=60` - Endpoint analysis
- **GET** `/suspicious-ips?window_minutes=60&min_requests=50` - Suspicious activity
- **GET** `/top-endpoints?window_minutes=60&limit=10` - Most accessed endpoints
- **GET** `/top-ips?window_minutes=60&limit=10` - Most active IPs
- **POST** `/export?window_minutes=60&filename=export.json` - Export data
- **DELETE** `/cleanup?hours_to_keep=24` - Clean old events
- **GET** `/health` - Detailed health assessment
- **GET** `/config` - Current configuration

### Metrics Example

```json
{
  "total_requests": 1500,
  "successful_requests": 1200,
  "rate_limited_requests": 280,
  "error_requests": 20,
  "unique_ips": 45,
  "avg_response_time": 0.125,
  "success_rate": 80.0,
  "error_rate": 1.3,
  "rate_limit_effectiveness": 0.85
}
```

### Suspicious IP Detection

The system automatically identifies suspicious IPs based on:

- **High rate limiting percentage** (>50%)
- **Excessive request rate** (>100 requests/minute)
- **Single user agent** usage
- **Endpoint scanning** behavior (>10 different endpoints)

## Redis Integration

### Setup

1. **Install Redis**:
   ```bash
   # Ubuntu/Debian
   sudo apt install redis-server

   # macOS
   brew install redis

   # Windows
   # Use Redis for Windows or Docker
   ```

2. **Configure Redis URL**:
   ```bash
   export REDIS_URL=redis://localhost:6379
   # Or with authentication:
   export REDIS_URL=redis://:password@host:6379
   ```

3. **Verify Connection**:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

### Redis Features

- **Sliding window counters** for accurate rate limiting
- **Automatic key expiration** to prevent memory leaks
- **Distributed rate limiting** across multiple application instances
- **Graceful fallback** to in-memory storage if Redis is unavailable

## Performance Testing

Use the included performance test script:

```bash
# Install dependencies
pip install aiohttp

# Run various tests
python scripts/test_rate_limiting.py --help

# Burst test (100 requests quickly)
python scripts/test_rate_limiting.py --test burst --requests 100

# Sustained load test (10 RPS for 30 seconds)
python scripts/test_rate_limiting.py --test sustained --rps 10 --duration 30

# Multi-IP test (10 IPs, 10 requests each)
python scripts/test_rate_limiting.py --test multi-ip --ips 10

# Test endpoint-specific limits
python scripts/test_rate_limiting.py --test endpoints

# Run all tests
python scripts/test_rate_limiting.py --test all
```

### Example Performance Results

```
Results for /api/documents
====================================
Total Requests:       100
Successful (200):     60 (60.0%)
Rate Limited (429):   40 (40.0%)
Errors:               0 (0.0%)
Avg Response Time:    125.5ms
Min Response Time:    15.2ms
Max Response Time:    250.8ms
Throughput:           45.2 requests/sec
Rate Limit Effectiveness: 100.0%
```

## Security Considerations

### DoS Protection

- **Multiple rate limiting layers** (global + endpoint-specific)
- **Automatic suspicious IP detection** and alerting
- **Configurable block durations** after limits exceeded
- **No bypasses in production** for security

### Memory Management

- **Automatic cleanup** of expired rate limiting data
- **Configurable event retention** (default 24 hours)
- **Memory limits** on in-memory storage (10,000 events default)

### Data Privacy

- **IP address anonymization** options (not implemented yet)
- **Configurable logging levels** to control data retention
- **Secure Redis connections** with authentication support

## Troubleshooting

### Common Issues

1. **Rate limiting not working**:
   - Check if `RATE_LIMIT_DISABLE=true` is set
   - Verify middleware is properly installed
   - Check for IP bypass configuration

2. **Redis connection errors**:
   - Verify Redis server is running: `redis-cli ping`
   - Check Redis URL format and credentials
   - System will fallback to in-memory storage

3. **High memory usage**:
   - Clean old events: `GET /api/admin/rate-limit/cleanup`
   - Reduce event retention period
   - Consider using Redis instead of in-memory storage

4. **False positives for legitimate users**:
   - Adjust rate limits for specific endpoints
   - Consider user-agent bypasses for legitimate bots
   - Review and adjust suspicion detection thresholds

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger("backend.api.middleware.rate_limiting").setLevel(logging.DEBUG)
```

## Future Enhancements

- **User-based rate limiting** (post-authentication)
- **Dynamic rate limit adjustment** based on system load
- **Geolocation-based rate limiting**
- **Machine learning-based anomaly detection**
- **Integration with external monitoring systems** (Prometheus, Grafana)
- **Rate limiting for WebSocket connections**
- **IP whitelist/blacklist management via API**

## API Integration Examples

### Check Rate Limit Status (Python)

```python
import requests

response = requests.get("http://localhost:8000/api/admin/rate-limit/status")
status = response.json()

if status["status"] == "active":
    print(f"Rate limiting active, {status['total_events_recorded']} events recorded")
else:
    print("Rate limiting not active")
```

### Monitor Suspicious Activity

```python
import requests

response = requests.get(
    "http://localhost:8000/api/admin/rate-limit/suspicious-ips",
    params={"window_minutes": 60, "min_requests": 20}
)

for ip_data in response.json():
    if ip_data["suspicion_score"] >= 5:
        print(f"High suspicion IP: {ip_data['client_ip']} "
              f"({ip_data['total_requests']} requests, "
              f"{ip_data['rate_limited_percentage']:.1f}% rate limited)")
```

### Export Rate Limiting Data

```python
import requests

response = requests.post(
    "http://localhost:8000/api/admin/rate-limit/export",
    params={"window_minutes": 1440, "filename": "daily_rate_limits.json"}
)

if response.status_code == 200:
    print("Rate limiting data exported successfully")
```