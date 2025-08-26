"""
Performance and Load Testing E2E Tests

Tests for system performance, concurrent users, and load handling.
"""

import asyncio
import concurrent.futures
import time
from statistics import mean, median, stdev

import aiohttp
import pytest
from fixtures import *
from playwright.sync_api import Browser, Page


class TestPerformanceAndLoad:
    """Test system performance under various load conditions."""

    @pytest.mark.e2e
    @pytest.mark.performance
    def test_page_load_performance(
        self,
        page: Page,
        page_helper,
        web_server,
        performance_test_data
    ):
        """Test page load performance for key pages."""
        pages_to_test = [
            ('/', 'Home'),
            ('/library', 'Library'),
            ('/upload', 'Upload'),
            ('/rag', 'RAG Query'),
            ('/settings', 'Settings')
        ]

        performance_results = []

        for path, name in pages_to_test:
            # Clear cache and cookies
            page.context.clear_cookies()

            # Measure cold load
            start_time = time.time()
            page.goto(f"{web_server}{path}")
            page.wait_for_load_state('networkidle')
            cold_load_time = time.time() - start_time

            # Get performance metrics
            metrics = page_helper.measure_performance()

            # Measure warm load (cached)
            start_time = time.time()
            page.reload()
            page.wait_for_load_state('networkidle')
            warm_load_time = time.time() - start_time

            performance_results.append({
                'page': name,
                'path': path,
                'cold_load': cold_load_time,
                'warm_load': warm_load_time,
                'dom_content_loaded': metrics['domContentLoaded'] / 1000,
                'load_complete': metrics['loadComplete'] / 1000,
                'resources': metrics['resources']
            })

            # Verify performance thresholds
            assert cold_load_time < 3.0, f"{name} page cold load too slow: {cold_load_time:.2f}s"
            assert warm_load_time < 1.5, f"{name} page warm load too slow: {warm_load_time:.2f}s"

        # Print performance report
        print("\n📊 Page Load Performance Report:")
        print("-" * 60)
        for result in performance_results:
            print(f"\n{result['page']} ({result['path']}):")
            print(f"  Cold Load: {result['cold_load']:.2f}s")
            print(f"  Warm Load: {result['warm_load']:.2f}s")
            print(f"  DOM Ready: {result['dom_content_loaded']:.2f}s")
            print(f"  Resources: {result['resources']}")

    @pytest.mark.e2e
    @pytest.mark.performance
    @pytest.mark.load
    def test_concurrent_user_simulation(
        self,
        browser: Browser,
        web_server,
        performance_test_data,
        test_pdf_files
    ):
        """Simulate multiple concurrent users."""
        user_counts = [5, 10, 25]

        for user_count in user_counts:
            print(f"\n🔧 Testing with {user_count} concurrent users...")

            contexts = []
            pages = []

            # Create multiple browser contexts (users)
            for i in range(user_count):
                context = browser.new_context()
                page = context.new_page()
                contexts.append(context)
                pages.append(page)

            # Simulate concurrent actions
            start_time = time.time()

            # Each user performs different actions
            for i, page in enumerate(pages):
                if i % 3 == 0:
                    # User browsing library
                    page.goto(f"{web_server}/library")
                elif i % 3 == 1:
                    # User uploading document
                    page.goto(f"{web_server}/upload")
                else:
                    # User making RAG queries
                    page.goto(f"{web_server}/rag")

            # Wait for all pages to load
            for page in pages:
                page.wait_for_load_state('networkidle')

            load_time = time.time() - start_time

            print(f"  All {user_count} users loaded in {load_time:.2f}s")
            print(f"  Average per user: {load_time/user_count:.2f}s")

            # Simulate concurrent interactions
            interaction_start = time.time()

            for i, page in enumerate(pages):
                if i % 3 == 0:
                    # Search in library
                    search = page.locator('[data-testid="library-search"]')
                    if search.is_visible():
                        search.fill(f"test query {i}")
                elif i % 3 == 1:
                    # Fill upload form
                    title = page.locator('[data-testid="document-title"]')
                    if title.is_visible():
                        title.fill(f"Document {i}")
                else:
                    # Enter RAG query
                    query = page.locator('[data-testid="rag-query-input"]')
                    if query.is_visible():
                        query.fill(f"Question {i}")

            interaction_time = time.time() - interaction_start
            print(f"  Interactions completed in {interaction_time:.2f}s")

            # Cleanup
            for context in contexts:
                context.close()

            # Verify system remained responsive
            assert load_time < user_count * 2, f"System too slow with {user_count} users"

    @pytest.mark.e2e
    @pytest.mark.performance
    async def test_api_endpoint_performance(
        self,
        web_server,
        performance_test_data
    ):
        """Test API endpoint performance under load."""
        endpoints = [
            ('/api/documents', 'GET'),
            ('/api/documents/1', 'GET'),
            ('/api/health', 'GET'),
        ]

        async def measure_endpoint(session, url, method='GET'):
            """Measure single endpoint response time."""
            start = time.time()
            try:
                async with session.request(method, url) as response:
                    await response.text()
                    return time.time() - start
            except:
                return None

        async def test_endpoint_load(endpoint, method, request_count=100):
            """Test endpoint with multiple concurrent requests."""
            url = f"{web_server}{endpoint}"

            async with aiohttp.ClientSession() as session:
                # Warmup
                await measure_endpoint(session, url, method)

                # Measure concurrent requests
                tasks = []
                for _ in range(request_count):
                    task = measure_endpoint(session, url, method)
                    tasks.append(task)

                response_times = await asyncio.gather(*tasks)

                # Filter out failed requests
                valid_times = [t for t in response_times if t is not None]

                if valid_times:
                    return {
                        'endpoint': endpoint,
                        'method': method,
                        'requests': request_count,
                        'successful': len(valid_times),
                        'failed': request_count - len(valid_times),
                        'avg_time': mean(valid_times),
                        'median_time': median(valid_times),
                        'min_time': min(valid_times),
                        'max_time': max(valid_times),
                        'std_dev': stdev(valid_times) if len(valid_times) > 1 else 0
                    }
                return None

        # Run tests
        results = []
        for endpoint, method in endpoints:
            result = await test_endpoint_load(endpoint, method)
            if result:
                results.append(result)

                # Verify performance thresholds
                assert result['avg_time'] < 1.0, f"{endpoint} average response too slow"
                assert result['failed'] < result['requests'] * 0.1, f"{endpoint} too many failures"

        # Print performance report
        print("\n📊 API Performance Report:")
        print("-" * 80)
        for result in results:
            print(f"\n{result['method']} {result['endpoint']}:")
            print(f"  Requests: {result['successful']}/{result['requests']} successful")
            print(f"  Average: {result['avg_time']*1000:.2f}ms")
            print(f"  Median: {result['median_time']*1000:.2f}ms")
            print(f"  Min/Max: {result['min_time']*1000:.2f}ms / {result['max_time']*1000:.2f}ms")
            print(f"  Std Dev: {result['std_dev']*1000:.2f}ms")

    @pytest.mark.e2e
    @pytest.mark.performance
    def test_file_upload_performance(
        self,
        api_client,
        performance_test_data,
        test_pdf_files
    ):
        """Test file upload performance with various sizes."""
        file_sizes = performance_test_data['file_sizes']
        upload_results = []

        for size_config in file_sizes:
            # Create test file of specific size
            test_file = Path(f"test_{size_config['name']}.pdf")

            # Generate PDF content
            pdf_content = b"%PDF-1.4\n"
            # Add padding to reach target size
            padding_needed = size_config['size'] - len(pdf_content) - 100
            if padding_needed > 0:
                pdf_content += b"1 0 obj\n<</Length %d>>\nstream\n" % padding_needed
                pdf_content += b"X" * padding_needed
                pdf_content += b"\nendstream\nendobj\n"
            pdf_content += b"%%EOF"

            test_file.write_bytes(pdf_content)

            try:
                # Measure upload time
                start_time = time.time()
                response = api_client.upload_file(
                    '/api/documents/upload',
                    test_file
                )
                upload_time = time.time() - start_time

                upload_results.append({
                    'size_name': size_config['name'],
                    'size_bytes': size_config['size'],
                    'size_mb': size_config['size'] / (1024 * 1024),
                    'upload_time': upload_time,
                    'success': response.success,
                    'throughput_mbps': (size_config['size'] / (1024 * 1024)) / upload_time if upload_time > 0 else 0
                })

                # Verify upload performance
                expected_time = size_config['size'] / (1024 * 1024) * 2  # 2 seconds per MB
                assert upload_time < expected_time, f"Upload too slow for {size_config['name']}"

            finally:
                test_file.unlink()

        # Print upload performance report
        print("\n📊 File Upload Performance Report:")
        print("-" * 60)
        for result in upload_results:
            status = "✅" if result['success'] else "❌"
            print(f"\n{result['size_name']} ({result['size_mb']:.2f} MB):")
            print(f"  Status: {status}")
            print(f"  Upload Time: {result['upload_time']:.2f}s")
            print(f"  Throughput: {result['throughput_mbps']:.2f} MB/s")

    @pytest.mark.e2e
    @pytest.mark.performance
    def test_rag_query_performance_under_load(
        self,
        api_client,
        performance_test_data,
        seeded_database
    ):
        """Test RAG query performance with varying complexity and load."""
        query_complexities = performance_test_data['query_complexity']

        # Select some documents for context
        docs_response = api_client.get('/api/documents?limit=10')
        if docs_response.success:
            document_ids = [doc['id'] for doc in docs_response.data[:5]]
        else:
            document_ids = [1, 2, 3, 4, 5]

        query_results = []

        for complexity in query_complexities:
            # Generate query based on complexity
            if complexity['type'] == 'simple':
                query = "What is this about?"
            elif complexity['type'] == 'moderate':
                query = " ".join(["Explain the concept"] + ["in detail"] * 10)
            else:  # complex
                query = " ".join(["Provide comprehensive analysis"] + ["with examples"] * 50)

            # Run multiple queries to get average
            times = []
            for _ in range(5):
                start_time = time.time()
                response = api_client.post(
                    '/api/rag/query',
                    json={
                        'query': query,
                        'document_ids': document_ids
                    }
                )
                query_time = time.time() - start_time
                times.append(query_time)

                time.sleep(0.5)  # Brief pause between queries

            avg_time = mean(times)
            query_results.append({
                'complexity': complexity['type'],
                'expected': complexity['expected_time'],
                'actual': avg_time,
                'times': times,
                'passed': avg_time < complexity['expected_time'] * 1.5
            })

        # Print RAG performance report
        print("\n📊 RAG Query Performance Report:")
        print("-" * 60)
        for result in query_results:
            status = "✅" if result['passed'] else "❌"
            print(f"\n{result['complexity'].capitalize()} Query:")
            print(f"  Expected: {result['expected']:.2f}s")
            print(f"  Actual: {result['actual']:.2f}s {status}")
            print(f"  Min/Max: {min(result['times']):.2f}s / {max(result['times']):.2f}s")

    @pytest.mark.e2e
    @pytest.mark.performance
    @pytest.mark.stress
    def test_system_stress_test(
        self,
        api_client,
        performance_test_data,
        test_pdf_files
    ):
        """Stress test the system with sustained load."""
        print("\n🔥 Starting System Stress Test...")

        stress_duration = 30  # seconds
        start_time = time.time()

        request_counts = {
            'total': 0,
            'successful': 0,
            'failed': 0
        }

        response_times = []

        def make_random_request():
            """Make a random API request."""
            import random

            actions = [
                lambda: api_client.get('/api/documents'),
                lambda: api_client.get('/api/documents/1'),
                lambda: api_client.get('/api/health'),
                lambda: api_client.post('/api/documents/search', json={'q': 'test'}),
            ]

            action = random.choice(actions)
            req_start = time.time()

            try:
                response = action()
                req_time = time.time() - req_start

                request_counts['total'] += 1
                if response.success:
                    request_counts['successful'] += 1
                    response_times.append(req_time)
                else:
                    request_counts['failed'] += 1

                return req_time
            except Exception:
                request_counts['failed'] += 1
                return None

        # Run stress test with thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            while time.time() - start_time < stress_duration:
                future = executor.submit(make_random_request)
                futures.append(future)
                time.sleep(0.01)  # Small delay between submissions

            # Wait for all requests to complete
            concurrent.futures.wait(futures, timeout=10)

        test_duration = time.time() - start_time

        # Calculate statistics
        if response_times:
            avg_response = mean(response_times)
            med_response = median(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
            requests_per_second = request_counts['total'] / test_duration
        else:
            avg_response = med_response = min_response = max_response = 0
            requests_per_second = 0

        # Print stress test report
        print(f"\n📊 Stress Test Results ({test_duration:.1f} seconds):")
        print("-" * 60)
        print(f"Total Requests: {request_counts['total']}")
        print(f"Successful: {request_counts['successful']}")
        print(f"Failed: {request_counts['failed']}")
        print(f"Success Rate: {(request_counts['successful']/request_counts['total']*100):.1f}%")
        print(f"Requests/Second: {requests_per_second:.1f}")

        if response_times:
            print("\nResponse Times:")
            print(f"  Average: {avg_response*1000:.2f}ms")
            print(f"  Median: {med_response*1000:.2f}ms")
            print(f"  Min: {min_response*1000:.2f}ms")
            print(f"  Max: {max_response*1000:.2f}ms")

        # Verify system stability
        assert request_counts['successful'] > request_counts['failed'], "Too many failures under stress"
        assert avg_response < 2.0, "Average response time too high under stress"

    @pytest.mark.e2e
    @pytest.mark.performance
    def test_memory_leak_detection(
        self,
        page: Page,
        api_client,
        web_server
    ):
        """Test for memory leaks during extended usage."""
        print("\n🔍 Testing for Memory Leaks...")

        # Get initial memory usage
        initial_memory = page.evaluate("""() => {
            if (performance.memory) {
                return {
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize
                };
            }
            return null;
        }""")

        if not initial_memory:
            pytest.skip("Browser doesn't support memory profiling")

        # Perform repeated actions
        iterations = 20
        for i in range(iterations):
            # Navigate between pages
            page.goto(f"{web_server}/library")
            page.wait_for_load_state('networkidle')

            page.goto(f"{web_server}/upload")
            page.wait_for_load_state('networkidle')

            page.goto(f"{web_server}/rag")
            page.wait_for_load_state('networkidle')

            # Trigger some JavaScript actions
            page.evaluate("""() => {
                // Create and destroy DOM elements
                for (let i = 0; i < 100; i++) {
                    const div = document.createElement('div');
                    div.innerHTML = 'Test content ' + i;
                    document.body.appendChild(div);
                    document.body.removeChild(div);
                }
            }""")

            # Make API calls
            api_client.get('/api/documents')

            if i % 5 == 0:
                print(f"  Iteration {i+1}/{iterations} completed")

        # Force garbage collection
        page.evaluate("() => { if (window.gc) window.gc(); }")
        time.sleep(2)  # Allow time for GC

        # Get final memory usage
        final_memory = page.evaluate("""() => {
            if (performance.memory) {
                return {
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize
                };
            }
            return null;
        }""")

        # Calculate memory growth
        memory_growth = final_memory['usedJSHeapSize'] - initial_memory['usedJSHeapSize']
        memory_growth_mb = memory_growth / (1024 * 1024)

        print("\n📊 Memory Usage Report:")
        print(f"  Initial: {initial_memory['usedJSHeapSize'] / (1024*1024):.2f} MB")
        print(f"  Final: {final_memory['usedJSHeapSize'] / (1024*1024):.2f} MB")
        print(f"  Growth: {memory_growth_mb:.2f} MB")

        # Check for excessive memory growth (more than 50MB)
        assert memory_growth_mb < 50, f"Potential memory leak detected: {memory_growth_mb:.2f} MB growth"
