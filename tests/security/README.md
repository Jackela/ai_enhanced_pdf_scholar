# Security Testing Suite

This directory contains a comprehensive security testing framework for the AI Enhanced PDF Scholar application, providing automated security assessment capabilities including OWASP Top 10 testing and penetration testing.

## Overview

The security testing suite consists of three main components:

1. **OWASP Security Tests** (`test_security_suite.py`) - Automated testing for OWASP Top 10 2021 vulnerabilities
2. **Penetration Testing** (`test_penetration_testing.py`) - Advanced penetration testing with network reconnaissance and web application testing
3. **Test Orchestrator** (`../scripts/run_security_tests.py`) - Automated test execution and comprehensive reporting

## Features

### OWASP Top 10 2021 Testing
- **A01:2021 – Broken Access Control**
  - Admin endpoint access without authentication
  - Insecure Direct Object Reference (IDOR)
  - Parameter tampering attempts

- **A02:2021 – Cryptographic Failures**
  - HTTPS enforcement verification
  - SSL/TLS configuration analysis
  - Certificate validation
  - Weak cipher detection

- **A03:2021 – Injection**
  - SQL injection testing with 10+ payloads
  - Command injection testing
  - LDAP injection testing
  - NoSQL injection testing

- **A04:2021 – Insecure Design**
  - Password policy enforcement
  - Rate limiting verification
  - Account enumeration testing
  - Business logic flaws

- **A05:2021 – Security Misconfiguration**
  - Debug information exposure
  - Default credentials testing
  - HTTP security headers analysis
  - Directory listing detection

### Advanced Penetration Testing
- **Network Reconnaissance**
  - DNS enumeration and subdomain discovery
  - Port scanning with service detection
  - SSL/TLS security analysis
  - Zone transfer attempts

- **Web Application Testing**
  - Technology stack fingerprinting
  - Directory and file brute forcing
  - Form analysis and CSRF detection
  - Authentication bypass testing
  - Session management vulnerabilities

- **Specialized Attack Vectors**
  - Local File Inclusion (LFI) testing
  - Remote File Inclusion (RFI) testing
  - XML External Entity (XXE) attacks
  - Server-Side Request Forgery (SSRF)
  - Cross-Site Scripting (XSS)

### Additional Security Tests
- **Session Management**
  - Session fixation testing
  - Session timeout validation
  - Concurrent session handling
  - Cookie security attributes

- **Input Validation**
  - XSS payload testing (10+ vectors)
  - Path traversal attempts
  - File upload security
  - Parameter pollution

## Installation & Dependencies

### Required Python Packages
```bash
pip install aiohttp requests beautifulsoup4 cryptography dnspython python-nmap pytest
```

### Optional Tools (for enhanced testing)
- **Nmap** - Network scanning capabilities
- **SSLyze** - Advanced SSL/TLS analysis
- **Burp Suite Community** - Manual testing support

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (optional)
export TEST_BASE_URL="http://localhost:8000"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your_admin_password"
export GOOGLE_API_KEY="your_api_key"
```

## Usage

### Quick Start
```bash
# Run comprehensive security assessment
python scripts/run_security_tests.py --target http://localhost:8000

# Run only OWASP tests
python scripts/run_security_tests.py --target http://localhost:8000 --tests owasp

# Run only penetration tests
python scripts/run_security_tests.py --target http://localhost:8000 --tests pentest
```

### Advanced Usage
```bash
# Custom output directory
python scripts/run_security_tests.py --target https://myapp.com --output /path/to/reports

# Verbose logging
python scripts/run_security_tests.py --target http://localhost:8000 --verbose

# Run with pytest
pytest tests/security/test_security_suite.py -v
pytest tests/security/test_penetration_testing.py -v
```

### Configuration Options

#### SecurityTestConfig
```python
class SecurityTestConfig:
    base_url = "http://localhost:8000"
    api_base = "http://localhost:8000/api/v1"
    timeout = 30
    max_login_attempts = 5
    rate_limit_window = 60
    # ... additional configuration options
```

#### PenetrationTestConfig
```python
class PenetrationTestConfig:
    target_url = "http://localhost:8000"
    port_scan_range = "1-1000"
    max_concurrent_requests = 10
    request_timeout = 30
    # ... additional configuration options
```

## Test Results & Reporting

### Output Formats
The security testing suite generates multiple report formats:

1. **JSON Report** - Complete technical details
2. **HTML Report** - Executive-friendly dashboard
3. **CSV Export** - Vulnerability tracking spreadsheet
4. **Executive Summary** - High-level text summary

### Sample Report Structure
```json
{
  "summary": {
    "overall_security_score": 85.0,
    "total_vulnerabilities": 3,
    "vulnerability_breakdown": {
      "critical": 0,
      "high": 1,
      "medium": 2,
      "low": 0
    },
    "pass_rate_percent": 92.5
  },
  "vulnerabilities": [...],
  "recommendations": [...],
  "compliance_status": {...}
}
```

### Risk Scoring
- **Critical (0-40)**: Immediate action required
- **High (41-60)**: Priority remediation needed  
- **Medium (61-80)**: Planned remediation recommended
- **Low (81-95)**: Minor issues, good posture
- **Secure (96-100)**: Excellent security posture

## Security Test Categories

### Authentication & Authorization
- JWT token validation
- Role-based access control
- Session management
- Password policies
- Multi-factor authentication (if implemented)

### Input Validation & Injection
- SQL injection (parameterized queries)
- NoSQL injection
- Command injection
- LDAP injection
- XPath injection
- Template injection

### Data Protection
- Encryption at rest
- Encryption in transit
- Sensitive data exposure
- Data validation
- Output encoding

### Network Security
- TLS/SSL configuration
- HTTP security headers
- Network segmentation
- Port security
- Service hardening

### Application Security
- Business logic flaws
- File upload vulnerabilities
- XML processing security
- API security
- Cross-origin resource sharing (CORS)

## Compliance Mapping

### OWASP Top 10 2021
- A01: Broken Access Control ✓
- A02: Cryptographic Failures ✓  
- A03: Injection ✓
- A04: Insecure Design ✓
- A05: Security Misconfiguration ✓
- A06: Vulnerable Components (Manual review)
- A07: Authentication Failures ✓
- A08: Software Integrity Failures (CI/CD)
- A09: Logging Failures ✓
- A10: SSRF ✓

### Industry Standards
- **PCI DSS**: Payment card security requirements
- **NIST Cybersecurity Framework**: Risk management
- **ISO 27001**: Information security management
- **GDPR**: Data protection compliance

## Customization & Extension

### Adding Custom Tests
```python
class CustomSecurityTests(SecurityTestBase):
    async def test_custom_vulnerability(self) -> SecurityTestResult:
        result = SecurityTestResult("Custom_Test")
        
        # Your custom test logic
        try:
            # Test implementation
            result.add_passed_test("Custom test passed")
        except Exception as e:
            result.add_vulnerability({
                'severity': 'high',
                'type': 'Custom Vulnerability',
                'description': 'Custom vulnerability found'
            })
        
        result.finalize()
        return result
```

### Custom Payloads
```python
# Add to SecurityTestConfig
custom_payloads = [
    "custom_payload_1",
    "custom_payload_2"
]
```

### Integration with CI/CD
```yaml
# GitHub Actions example
- name: Security Testing
  run: |
    python scripts/run_security_tests.py --target ${{ env.APP_URL }}
    # Fail build if critical vulnerabilities found
    if [ -f security_reports/vulnerabilities_*.csv ]; then
      critical_count=$(grep -c ",critical," security_reports/vulnerabilities_*.csv || echo "0")
      if [ "$critical_count" -gt "0" ]; then
        echo "Critical vulnerabilities found: $critical_count"
        exit 1
      fi
    fi
```

## Security Testing Best Practices

### Pre-Testing Checklist
- [ ] Application is in a test environment
- [ ] Database contains only test data
- [ ] Network monitoring is in place
- [ ] Legal approval obtained (for external testing)
- [ ] Backup and recovery procedures verified

### During Testing
- [ ] Monitor application performance
- [ ] Log all test activities
- [ ] Coordinate with development team
- [ ] Document false positives
- [ ] Verify findings manually

### Post-Testing
- [ ] Generate comprehensive reports
- [ ] Prioritize vulnerabilities by business impact
- [ ] Create remediation timeline
- [ ] Schedule follow-up testing
- [ ] Update security documentation

## Troubleshooting

### Common Issues

#### Connection Errors
```bash
# Check target accessibility
curl -I http://localhost:8000

# Verify SSL certificate (if HTTPS)
openssl s_client -connect localhost:443 -servername localhost
```

#### Authentication Failures
```bash
# Test manual login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

#### Permission Errors
```bash
# Ensure proper file permissions
chmod +x scripts/run_security_tests.py
```

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

### Adding New Tests
1. Create test class inheriting from `SecurityTestBase`
2. Implement test methods returning `SecurityTestResult`
3. Add to test runner configuration
4. Update documentation

### Code Standards
- Follow PEP 8 style guidelines
- Add comprehensive docstrings
- Include error handling
- Write unit tests for test components
- Update README for new features

## Disclaimer

**Important Security Notice:**
- This testing suite is designed for authorized security testing only
- Only test applications you own or have explicit permission to test
- Some tests may impact application performance
- Always test in non-production environments first
- Follow responsible disclosure for any vulnerabilities found

## License

This security testing suite is part of the AI Enhanced PDF Scholar project and follows the same licensing terms. Use responsibly and in accordance with applicable laws and regulations.

## Support

For issues, questions, or contributions:
1. Check existing GitHub issues
2. Review documentation thoroughly  
3. Create detailed issue reports
4. Include reproduction steps and environment details
5. Follow security disclosure guidelines for vulnerabilities