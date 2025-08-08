"""
API Fixtures for E2E Testing

Provides API client fixtures and utilities for testing API endpoints.
"""

import pytest
import requests
from typing import Dict, Any, Optional, Generator
import json
from pathlib import Path
import time
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class APIResponse:
    """Enhanced API response wrapper."""
    status_code: int
    json_data: Optional[Dict[str, Any]]
    text: str
    headers: Dict[str, str]
    elapsed_time: float
    request_url: str
    request_method: str
    
    @property
    def success(self) -> bool:
        """Check if the response was successful."""
        return 200 <= self.status_code < 300
    
    @property
    def data(self) -> Any:
        """Get the data field from JSON response."""
        if self.json_data and "data" in self.json_data:
            return self.json_data["data"]
        return self.json_data
    
    @property
    def message(self) -> Optional[str]:
        """Get the message field from JSON response."""
        if self.json_data and "message" in self.json_data:
            return self.json_data["message"]
        return None
    
    @property
    def error(self) -> Optional[str]:
        """Get the error field from JSON response."""
        if self.json_data and "error" in self.json_data:
            return self.json_data["error"]
        return None


class APIClient:
    """
    Enhanced API client for E2E testing with comprehensive features.
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.auth_token = None
        self.request_history = []
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'E2E-Test-Client/1.0',
            'Accept': 'application/json',
        })
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> APIResponse:
        """
        Make an HTTP request with enhanced error handling and logging.
        """
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        # Add auth header if authenticated
        if self.auth_token:
            kwargs.setdefault('headers', {})['Authorization'] = f'Bearer {self.auth_token}'
        
        # Set default timeout
        kwargs.setdefault('timeout', self.timeout)
        
        # Make request
        start_time = time.time()
        try:
            response = self.session.request(method, url, **kwargs)
            elapsed_time = time.time() - start_time
            
            # Try to parse JSON
            try:
                json_data = response.json()
            except (json.JSONDecodeError, ValueError):
                json_data = None
            
            # Create response object
            api_response = APIResponse(
                status_code=response.status_code,
                json_data=json_data,
                text=response.text,
                headers=dict(response.headers),
                elapsed_time=elapsed_time,
                request_url=url,
                request_method=method
            )
            
            # Log request
            self.request_history.append({
                'timestamp': time.time(),
                'method': method,
                'url': url,
                'status_code': response.status_code,
                'elapsed_time': elapsed_time
            })
            
            return api_response
            
        except requests.exceptions.RequestException as e:
            # Log failed request
            self.request_history.append({
                'timestamp': time.time(),
                'method': method,
                'url': url,
                'error': str(e),
                'elapsed_time': time.time() - start_time
            })
            raise
    
    def get(self, endpoint: str, **kwargs) -> APIResponse:
        """Make a GET request."""
        return self._make_request('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> APIResponse:
        """Make a POST request."""
        return self._make_request('POST', endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> APIResponse:
        """Make a PUT request."""
        return self._make_request('PUT', endpoint, **kwargs)
    
    def patch(self, endpoint: str, **kwargs) -> APIResponse:
        """Make a PATCH request."""
        return self._make_request('PATCH', endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> APIResponse:
        """Make a DELETE request."""
        return self._make_request('DELETE', endpoint, **kwargs)
    
    def upload_file(
        self,
        endpoint: str,
        file_path: Path,
        field_name: str = 'file',
        additional_data: Dict[str, Any] = None
    ) -> APIResponse:
        """
        Upload a file with optional additional form data.
        """
        with open(file_path, 'rb') as f:
            files = {field_name: (file_path.name, f, 'application/pdf')}
            data = additional_data or {}
            return self.post(endpoint, files=files, data=data)
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with the API and store the token.
        """
        response = self.post('/auth/login', json={
            'username': username,
            'password': password
        })
        
        if response.success and response.data:
            self.auth_token = response.data.get('token')
            return True
        return False
    
    def logout(self) -> bool:
        """
        Logout and clear the authentication token.
        """
        if self.auth_token:
            response = self.post('/auth/logout')
            self.auth_token = None
            return response.success
        return True
    
    def wait_for_status(
        self,
        endpoint: str,
        expected_status: str,
        timeout: int = 30,
        poll_interval: int = 1
    ) -> bool:
        """
        Poll an endpoint until it returns the expected status.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.get(endpoint)
            if response.success and response.data:
                if response.data.get('status') == expected_status:
                    return True
            time.sleep(poll_interval)
        return False
    
    def batch_request(
        self,
        requests_data: list[Dict[str, Any]]
    ) -> list[APIResponse]:
        """
        Execute multiple requests in sequence.
        """
        responses = []
        for req in requests_data:
            method = req.get('method', 'GET')
            endpoint = req['endpoint']
            kwargs = req.get('kwargs', {})
            response = self._make_request(method, endpoint, **kwargs)
            responses.append(response)
        return responses
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for all requests made.
        """
        if not self.request_history:
            return {}
        
        elapsed_times = [req['elapsed_time'] for req in self.request_history if 'elapsed_time' in req]
        status_codes = [req.get('status_code', 0) for req in self.request_history]
        
        return {
            'total_requests': len(self.request_history),
            'successful_requests': sum(1 for code in status_codes if 200 <= code < 300),
            'failed_requests': sum(1 for req in self.request_history if 'error' in req),
            'average_response_time': sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0,
            'min_response_time': min(elapsed_times) if elapsed_times else 0,
            'max_response_time': max(elapsed_times) if elapsed_times else 0,
            'status_code_distribution': {
                code: status_codes.count(code) 
                for code in set(status_codes) if code != 0
            }
        }


@pytest.fixture
def api_client(web_server) -> Generator[APIClient, None, None]:
    """
    Provide an API client for testing.
    """
    client = APIClient(web_server)
    yield client
    # Cleanup
    client.session.close()


@pytest.fixture
def authenticated_api_client(api_client, test_user_data) -> APIClient:
    """
    Provide an authenticated API client.
    """
    user = test_user_data['regular']
    api_client.authenticate(user['username'], user['password'])
    return api_client


@pytest.fixture
def admin_api_client(api_client, test_user_data) -> APIClient:
    """
    Provide an admin-authenticated API client.
    """
    admin = test_user_data['admin']
    api_client.authenticate(admin['username'], admin['password'])
    return api_client


class WebSocketClient:
    """
    WebSocket client for testing real-time features.
    """
    
    def __init__(self, url: str):
        import websocket
        self.url = url
        self.ws = None
        self.messages = []
        self.is_connected = False
        
    def connect(self):
        """Connect to WebSocket server."""
        import websocket
        self.ws = websocket.WebSocket()
        self.ws.connect(self.url)
        self.is_connected = True
        
    def send(self, message: Dict[str, Any]):
        """Send a message to the WebSocket server."""
        if not self.is_connected:
            self.connect()
        self.ws.send(json.dumps(message))
        
    def receive(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Receive a message from the WebSocket server."""
        if not self.is_connected:
            return None
        
        self.ws.settimeout(timeout)
        try:
            message = self.ws.recv()
            parsed = json.loads(message)
            self.messages.append(parsed)
            return parsed
        except Exception:
            return None
    
    def close(self):
        """Close the WebSocket connection."""
        if self.ws:
            self.ws.close()
        self.is_connected = False


@pytest.fixture
def websocket_client(web_server) -> Generator[WebSocketClient, None, None]:
    """
    Provide a WebSocket client for testing real-time features.
    """
    ws_url = web_server.replace('http://', 'ws://') + '/ws'
    client = WebSocketClient(ws_url)
    yield client
    client.close()


class MockAPIServer:
    """
    Mock API server for testing without a real backend.
    """
    
    def __init__(self):
        self.responses = {}
        self.request_log = []
        
    def register_response(
        self,
        method: str,
        endpoint: str,
        response_data: Dict[str, Any],
        status_code: int = 200,
        delay: float = 0
    ):
        """Register a mock response for a specific endpoint."""
        key = f"{method}:{endpoint}"
        self.responses[key] = {
            'data': response_data,
            'status_code': status_code,
            'delay': delay
        }
    
    def get_response(self, method: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get the mock response for an endpoint."""
        key = f"{method}:{endpoint}"
        if key in self.responses:
            response = self.responses[key]
            if response['delay'] > 0:
                time.sleep(response['delay'])
            return response
        return None
    
    def log_request(self, method: str, endpoint: str, data: Any = None):
        """Log a request for verification."""
        self.request_log.append({
            'timestamp': time.time(),
            'method': method,
            'endpoint': endpoint,
            'data': data
        })
    
    def verify_request_made(
        self,
        method: str,
        endpoint: str,
        times: int = 1
    ) -> bool:
        """Verify that a specific request was made."""
        count = sum(
            1 for req in self.request_log
            if req['method'] == method and req['endpoint'] == endpoint
        )
        return count == times


@pytest.fixture
def mock_api_server() -> MockAPIServer:
    """
    Provide a mock API server for testing.
    """
    return MockAPIServer()