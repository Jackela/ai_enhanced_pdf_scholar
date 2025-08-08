"""
Locust Load Testing Configuration

Provides distributed load testing capabilities using Locust framework.
Run with: locust -f locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging
import random
import json
import time
import io
from typing import Dict, Any
import gevent


class PDFScholarUser(HttpUser):
    """Simulates a user of the PDF Scholar application"""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Called when a user starts"""
        # Create a session for the user
        response = self.client.post("/api/sessions", json={
            "user_id": f"user_{self.environment.runner.user_count}"
        })
        if response.status_code == 200:
            data = response.json()
            self.session_id = data.get("session_id")
        else:
            self.session_id = None
        
        # Prepare test data
        self.test_queries = [
            "machine learning",
            "neural networks",
            "deep learning",
            "computer vision",
            "natural language processing",
            "reinforcement learning",
            "data science",
            "artificial intelligence",
            "transformer models",
            "convolutional networks"
        ]
        
        self.test_documents = []
        for i in range(5):
            content = f"Test Document {i}\n" * 100
            self.test_documents.append(content.encode())
    
    @task(1)
    def health_check(self):
        """Check system health"""
        self.client.get("/health")
    
    @task(10)
    def list_documents(self):
        """List all documents"""
        with self.client.get("/api/documents", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Got status code {response.status_code}")
            else:
                response.success()
    
    @task(5)
    def get_document(self):
        """Get a specific document"""
        doc_id = random.randint(1, 100)
        self.client.get(f"/api/documents/{doc_id}", name="/api/documents/[id]")
    
    @task(3)
    def upload_document(self):
        """Upload a new document"""
        file_content = random.choice(self.test_documents)
        files = {
            'file': (f'test_{random.randint(1000, 9999)}.pdf', 
                    io.BytesIO(file_content), 
                    'application/pdf')
        }
        
        with self.client.post(
            "/api/documents/upload",
            files=files,
            catch_response=True
        ) as response:
            if response.status_code not in [200, 201]:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task(15)
    def simple_rag_query(self):
        """Perform a simple RAG query"""
        query = random.choice(self.test_queries)
        payload = {
            "query": query,
            "k": 5
        }
        
        with self.client.post(
            "/api/rag/query",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Query failed: {response.status_code}")
            elif response.elapsed.total_seconds() > 5:
                response.failure("Query took too long")
    
    @task(5)
    def complex_rag_query(self):
        """Perform a complex RAG query"""
        # Combine multiple queries for complexity
        queries = random.sample(self.test_queries, 2)
        query = " and ".join(queries)
        
        payload = {
            "query": query,
            "k": 10,
            "rerank": True
        }
        
        with self.client.post(
            "/api/rag/query",
            json=payload,
            catch_response=True,
            name="/api/rag/query-complex"
        ) as response:
            if response.status_code != 200:
                response.failure(f"Complex query failed: {response.status_code}")
            elif response.elapsed.total_seconds() > 10:
                response.failure("Complex query took too long")
    
    @task(8)
    def search_citations(self):
        """Search for citations"""
        search_term = random.choice(["neural", "learning", "model", "data", "algorithm"])
        self.client.get(
            f"/api/citations/search?q={search_term}",
            name="/api/citations/search?q=[term]"
        )
    
    @task(5)
    def vector_search(self):
        """Perform vector similarity search"""
        query = random.choice(self.test_queries)
        payload = {
            "query": query,
            "top_k": 10
        }
        
        self.client.post("/api/vectors/search", json=payload)
    
    @task(2)
    def create_citation(self):
        """Create a new citation"""
        payload = {
            "title": f"Test Citation {random.randint(1000, 9999)}",
            "authors": ["Test Author"],
            "year": random.randint(2010, 2024),
            "journal": "Test Journal",
            "doi": f"10.1234/test.{random.randint(1000, 9999)}"
        }
        
        self.client.post("/api/citations", json=payload)
    
    @task(3)
    def get_document_citations(self):
        """Get citations for a document"""
        doc_id = random.randint(1, 50)
        self.client.get(
            f"/api/documents/{doc_id}/citations",
            name="/api/documents/[id]/citations"
        )


class AdminUser(HttpUser):
    """Simulates an admin user with different behavior patterns"""
    
    wait_time = between(2, 8)
    weight = 1  # Lower weight than regular users
    
    @task(5)
    def view_statistics(self):
        """View system statistics"""
        self.client.get("/api/admin/statistics")
    
    @task(3)
    def export_data(self):
        """Export system data"""
        self.client.get("/api/admin/export")
    
    @task(2)
    def system_health(self):
        """Check detailed system health"""
        self.client.get("/api/admin/health/detailed")
    
    @task(10)
    def browse_documents(self):
        """Browse through documents with pagination"""
        page = random.randint(1, 10)
        limit = random.choice([10, 20, 50])
        self.client.get(
            f"/api/documents?page={page}&limit={limit}",
            name="/api/documents?page=[n]&limit=[n]"
        )
    
    @task(5)
    def manage_users(self):
        """User management operations"""
        operations = [
            lambda: self.client.get("/api/admin/users"),
            lambda: self.client.get(f"/api/admin/users/{random.randint(1, 100)}",
                                   name="/api/admin/users/[id]"),
            lambda: self.client.post("/api/admin/users", json={
                "username": f"testuser_{random.randint(1000, 9999)}",
                "role": random.choice(["user", "admin"])
            })
        ]
        random.choice(operations)()


class MobileUser(HttpUser):
    """Simulates mobile users with different patterns"""
    
    wait_time = between(3, 10)  # Mobile users typically have longer wait times
    weight = 2  # Moderate weight
    
    def on_start(self):
        """Mobile-specific initialization"""
        # Set mobile headers
        self.client.headers.update({
            "User-Agent": "MobileApp/1.0",
            "X-Device-Type": "mobile"
        })
        
        self.quick_queries = [
            "summary",
            "abstract",
            "conclusion",
            "introduction",
            "methodology"
        ]
    
    @task(20)
    def quick_search(self):
        """Quick searches typical for mobile users"""
        query = random.choice(self.quick_queries)
        self.client.get(
            f"/api/search/quick?q={query}",
            name="/api/search/quick?q=[query]"
        )
    
    @task(15)
    def view_recent(self):
        """View recent documents"""
        self.client.get("/api/documents/recent")
    
    @task(10)
    def bookmark_document(self):
        """Bookmark a document"""
        doc_id = random.randint(1, 100)
        self.client.post(
            f"/api/documents/{doc_id}/bookmark",
            name="/api/documents/[id]/bookmark"
        )
    
    @task(5)
    def sync_data(self):
        """Sync mobile data"""
        self.client.post("/api/mobile/sync", json={
            "last_sync": "2024-01-01T00:00:00Z",
            "device_id": f"device_{random.randint(1000, 9999)}"
        })


class StressTestUser(HttpUser):
    """User for stress testing with aggressive patterns"""
    
    wait_time = between(0.1, 0.5)  # Very short wait times
    weight = 0  # Disabled by default, enable for stress tests
    
    @task
    def hammer_endpoint(self):
        """Continuously hit various endpoints"""
        endpoints = [
            ("/api/documents", "GET", None),
            ("/api/rag/query", "POST", {"query": "test", "k": 1}),
            ("/api/citations/search?q=test", "GET", None),
            ("/health", "GET", None)
        ]
        
        endpoint, method, payload = random.choice(endpoints)
        
        if method == "GET":
            self.client.get(endpoint)
        else:
            self.client.post(endpoint, json=payload)


# Custom event handlers for detailed metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, 
               context, exception, **kwargs):
    """Custom request handler for detailed logging"""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # Log slow requests
        print(f"Slow request: {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test environment"""
    print("Load test starting...")
    print(f"Target host: {environment.host}")
    print(f"Total users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup and generate report"""
    print("\nLoad test completed!")
    print("Generating performance report...")
    
    # Generate summary statistics
    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Median Response Time: {stats.total.median_response_time:.2f}ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")


# Utility functions for programmatic execution
def run_load_test(
    host: str = "http://localhost:8000",
    users: int = 10,
    spawn_rate: int = 1,
    run_time: str = "60s"
) -> Dict[str, Any]:
    """
    Run load test programmatically
    
    Args:
        host: Target host URL
        users: Number of concurrent users
        spawn_rate: Users spawned per second
        run_time: Test duration (e.g., "60s", "5m", "1h")
    
    Returns:
        Test results dictionary
    """
    setup_logging("INFO", None)
    
    # Create environment
    env = Environment(
        user_classes=[PDFScholarUser, AdminUser, MobileUser],
        host=host
    )
    
    # Start test
    env.runner.start(users, spawn_rate=spawn_rate)
    
    # Parse run time
    if run_time.endswith('s'):
        duration = int(run_time[:-1])
    elif run_time.endswith('m'):
        duration = int(run_time[:-1]) * 60
    elif run_time.endswith('h'):
        duration = int(run_time[:-1]) * 3600
    else:
        duration = int(run_time)
    
    # Run for specified duration
    gevent.spawn_later(duration, lambda: env.runner.quit())
    
    # Start stat printing
    gevent.spawn(stats_printer(env.stats))
    
    # Wait for test to complete
    env.runner.greenlet.join()
    
    # Collect results
    results = {
        "total_requests": env.stats.total.num_requests,
        "total_failures": env.stats.total.num_failures,
        "failure_rate": env.stats.total.fail_ratio,
        "avg_response_time": env.stats.total.avg_response_time,
        "median_response_time": env.stats.total.median_response_time,
        "p95_response_time": env.stats.total.get_response_time_percentile(0.95),
        "p99_response_time": env.stats.total.get_response_time_percentile(0.99),
        "requests_per_second": env.stats.total.current_rps,
        "users": users,
        "duration_seconds": duration
    }
    
    return results


if __name__ == "__main__":
    # Example programmatic execution
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        results = run_load_test(
            host="http://localhost:8000",
            users=50,
            spawn_rate=2,
            run_time="5m"
        )
        
        print("\nLoad Test Results:")
        print(json.dumps(results, indent=2))