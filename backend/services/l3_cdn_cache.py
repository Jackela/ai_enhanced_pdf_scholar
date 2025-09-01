"""
L3 CDN Cache Service
Global content delivery network cache integration with edge optimization.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Union
from urllib.parse import urlencode, urlparse

import aiohttp

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# CDN Configuration
# ============================================================================

class CDNProvider(str, Enum):
    """Supported CDN providers."""
    CLOUDFRONT = "cloudfront"
    CLOUDFLARE = "cloudflare"
    FASTLY = "fastly"
    AZURE_CDN = "azure_cdn"
    GENERIC = "generic"


class ContentType(str, Enum):
    """Content types for CDN caching."""
    STATIC_ASSETS = "static"  # CSS, JS, images
    API_RESPONSES = "api"  # JSON API responses
    DOCUMENTS = "documents"  # PDF, document files
    MEDIA = "media"  # Videos, audio
    DYNAMIC = "dynamic"  # Dynamic content


@dataclass
class CDNConfig:
    """Configuration for L3 CDN cache."""
    provider: CDNProvider = CDNProvider.CLOUDFRONT

    # CDN settings
    distribution_id: str = ""
    domain_name: str = ""
    origin_domain: str = ""

    # AWS CloudFront specific
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"

    # Caching policies
    default_ttl_seconds: int = 86400  # 24 hours
    max_ttl_seconds: int = 31536000  # 1 year
    min_ttl_seconds: int = 300  # 5 minutes

    # Content type specific TTLs
    content_ttls: dict[ContentType, int] = field(default_factory=lambda: {
        ContentType.STATIC_ASSETS: 2592000,  # 30 days
        ContentType.API_RESPONSES: 3600,     # 1 hour
        ContentType.DOCUMENTS: 86400,        # 24 hours
        ContentType.MEDIA: 604800,           # 7 days
        ContentType.DYNAMIC: 300             # 5 minutes
    })

    # Edge locations and routing
    edge_locations: list[str] = field(default_factory=lambda: [
        "us-east-1", "us-west-1", "eu-west-1", "ap-southeast-1"
    ])

    # Performance settings
    enable_compression: bool = True
    enable_http2: bool = True
    enable_ipv6: bool = True

    # Security settings
    enable_ssl: bool = True
    ssl_protocols: list[str] = field(default_factory=lambda: ["TLSv1.2", "TLSv1.3"])

    # Cache behaviors
    query_string_caching: bool = False  # Cache based on query strings
    header_caching: list[str] = field(default_factory=lambda: ["Accept", "Accept-Language"])

    # Monitoring
    enable_real_user_monitoring: bool = True
    enable_access_logs: bool = True


@dataclass
class CDNCacheEntry:
    """CDN cache entry metadata."""
    url: str
    content_type: ContentType
    size_bytes: int
    created_at: datetime
    expires_at: datetime
    etag: str | None = None
    last_modified: datetime | None = None
    cache_hit_ratio: float = 0.0
    edge_location: str | None = None
    compression_enabled: bool = False

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at

    def time_to_expiry(self) -> timedelta:
        """Get time until expiry."""
        return self.expires_at - datetime.utcnow()


# ============================================================================
# CDN Statistics and Analytics
# ============================================================================

@dataclass
class CDNStatistics:
    """CDN performance statistics."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    bytes_served: int = 0
    bytes_transferred: int = 0

    # Performance metrics
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    error_rate_percent: float = 0.0

    # Geographic distribution
    requests_by_region: dict[str, int] = field(default_factory=dict)

    # Content type distribution
    requests_by_content_type: dict[str, int] = field(default_factory=dict)

    # Edge performance
    edge_hit_ratios: dict[str, float] = field(default_factory=dict)

    def calculate_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0

    def calculate_bandwidth_savings(self) -> float:
        """Calculate bandwidth savings percentage."""
        if self.bytes_transferred == 0:
            return 0.0
        return (1 - self.bytes_served / self.bytes_transferred) * 100


# ============================================================================
# L3 CDN Cache Service
# ============================================================================

class L3CDNCache:
    """
    Global CDN cache service for content delivery optimization.
    """

    def __init__(self, config: CDNConfig):
        """Initialize L3 CDN cache."""
        self.config = config

        # Statistics
        self.stats = CDNStatistics()

        # Cache tracking
        self.cached_urls: dict[str, CDNCacheEntry] = {}
        self.cache_access_log: deque = deque(maxlen=10000)

        # Performance tracking
        self.response_times: deque = deque(maxlen=1000)

        # CDN client initialization
        self._cdn_client = None
        self._http_session: aiohttp.ClientSession | None = None

        # Initialize CDN client based on provider
        self._initialize_cdn_client()

        logger.info(f"L3 CDN Cache initialized with provider: {self.config.provider}")

    def _initialize_cdn_client(self):
        """Initialize CDN provider client."""
        try:
            if self.config.provider == CDNProvider.CLOUDFRONT:
                self._initialize_cloudfront_client()
            elif self.config.provider == CDNProvider.CLOUDFLARE:
                self._initialize_cloudflare_client()
            elif self.config.provider == CDNProvider.FASTLY:
                self._initialize_fastly_client()
            else:
                logger.info("Using generic CDN configuration")

        except Exception as e:
            logger.error(f"Error initializing CDN client: {e}")

    def _initialize_cloudfront_client(self):
        """Initialize AWS CloudFront client."""
        if not BOTO3_AVAILABLE:
            logger.warning("boto3 not available - CloudFront features disabled")
            return

        try:
            session = boto3.Session(
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
                region_name=self.config.aws_region
            )

            self._cdn_client = session.client('cloudfront')
            logger.info("CloudFront client initialized")

        except (NoCredentialsError, ClientError) as e:
            logger.error(f"Failed to initialize CloudFront client: {e}")

    def _initialize_cloudflare_client(self):
        """Initialize Cloudflare client."""
        # Placeholder for Cloudflare API client
        logger.info("Cloudflare client placeholder initialized")

    def _initialize_fastly_client(self):
        """Initialize Fastly client."""
        # Placeholder for Fastly API client
        logger.info("Fastly client placeholder initialized")

    # ========================================================================
    # Core CDN Operations
    # ========================================================================

    async def get_cached_url(
        self,
        original_url: str,
        content_type: ContentType = ContentType.API_RESPONSES,
        query_params: dict[str, Any] | None = None
    ) -> str:
        """Get CDN-cached URL for content."""
        # Generate CDN URL
        cdn_url = self._generate_cdn_url(original_url, query_params)

        # Check if already cached
        if cdn_url in self.cached_urls:
            entry = self.cached_urls[cdn_url]
            if not entry.is_expired():
                await self._log_cache_access(cdn_url, "hit")
                return cdn_url

        # Cache the content
        await self._cache_content(original_url, cdn_url, content_type, query_params)

        return cdn_url

    async def cache_content(
        self,
        content_url: str,
        content_data: bytes,
        content_type: ContentType = ContentType.API_RESPONSES,
        ttl_seconds: int | None = None,
        headers: dict[str, str] | None = None
    ) -> str:
        """Cache content directly to CDN."""
        start_time = time.time()

        try:
            # Generate CDN URL
            cdn_url = self._generate_cdn_url(content_url)

            # Determine TTL
            if ttl_seconds is None:
                ttl_seconds = self.config.content_ttls.get(
                    content_type,
                    self.config.default_ttl_seconds
                )

            # Upload to CDN
            success = await self._upload_to_cdn(
                cdn_url,
                content_data,
                content_type,
                ttl_seconds,
                headers
            )

            if success:
                # Create cache entry
                entry = CDNCacheEntry(
                    url=cdn_url,
                    content_type=content_type,
                    size_bytes=len(content_data),
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
                    compression_enabled=self.config.enable_compression
                )

                self.cached_urls[cdn_url] = entry

                # Update statistics
                self.stats.total_requests += 1
                self.stats.bytes_served += len(content_data)

                response_time = (time.time() - start_time) * 1000
                self.response_times.append(response_time)

                await self._log_cache_access(cdn_url, "cache")

                logger.debug(f"Cached content to CDN: {cdn_url}")
                return cdn_url

            else:
                logger.error(f"Failed to cache content to CDN: {content_url}")
                return content_url  # Return original URL as fallback

        except Exception as e:
            logger.error(f"Error caching content to CDN: {e}")
            return content_url

    async def invalidate_cache(
        self,
        urls: Union[str, list[str]],
        wait_for_completion: bool = False
    ) -> bool:
        """Invalidate cached content on CDN."""
        if isinstance(urls, str):
            urls = [urls]

        try:
            # Convert to CDN URLs if needed
            cdn_urls = []
            for url in urls:
                if url.startswith(f"https://{self.config.domain_name}"):
                    cdn_urls.append(url)
                else:
                    cdn_urls.append(self._generate_cdn_url(url))

            # Perform invalidation based on provider
            success = await self._perform_cdn_invalidation(cdn_urls, wait_for_completion)

            if success:
                # Remove from local tracking
                for cdn_url in cdn_urls:
                    self.cached_urls.pop(cdn_url, None)

                logger.info(f"Invalidated {len(cdn_urls)} URLs from CDN cache")
                return True

            return False

        except Exception as e:
            logger.error(f"Error invalidating CDN cache: {e}")
            return False

    async def prefetch_content(
        self,
        urls: list[str],
        content_type: ContentType = ContentType.API_RESPONSES,
        priority: str = "normal"
    ) -> dict[str, bool]:
        """Prefetch content to CDN edge locations."""
        results = {}

        for url in urls:
            try:
                # Fetch content from origin
                content_data = await self._fetch_origin_content(url)

                if content_data:
                    # Cache to CDN
                    cdn_url = await self.cache_content(url, content_data, content_type)
                    results[url] = cdn_url != url  # True if successfully cached

                    # Trigger edge warming if supported
                    if self.config.provider == CDNProvider.CLOUDFRONT:
                        await self._warm_edge_locations(cdn_url)
                else:
                    results[url] = False

            except Exception as e:
                logger.error(f"Error prefetching content {url}: {e}")
                results[url] = False

        logger.info(f"Prefetched {sum(results.values())}/{len(urls)} URLs")
        return results

    # ========================================================================
    # CDN Provider Integration
    # ========================================================================

    async def _upload_to_cdn(
        self,
        cdn_url: str,
        content_data: bytes,
        content_type: ContentType,
        ttl_seconds: int,
        headers: dict[str, str] | None
    ) -> bool:
        """Upload content to CDN."""
        if self.config.provider == CDNProvider.CLOUDFRONT:
            return await self._upload_to_cloudfront(
                cdn_url, content_data, content_type, ttl_seconds, headers
            )
        else:
            # Generic upload via HTTP
            return await self._upload_via_http(
                cdn_url, content_data, content_type, ttl_seconds, headers
            )

    async def _upload_to_cloudfront(
        self,
        cdn_url: str,
        content_data: bytes,
        content_type: ContentType,
        ttl_seconds: int,
        headers: dict[str, str] | None
    ) -> bool:
        """Upload content to AWS CloudFront via S3."""
        try:
            # CloudFront typically serves content from S3
            # This is a simplified implementation

            if not self._cdn_client:
                return False

            # Extract path from CDN URL
            path = urlparse(cdn_url).path.lstrip('/')

            # Upload to S3 (CloudFront origin)
            if not BOTO3_AVAILABLE:
                logger.warning("boto3 not available - S3 upload skipped")
                return False

            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
                region_name=self.config.aws_region
            )

            # Determine S3 bucket from origin domain
            bucket_name = self.config.origin_domain.split('.')[0]  # Simplified

            # Prepare S3 upload parameters
            upload_params = {
                'Body': content_data,
                'ContentType': self._get_mime_type(content_type),
                'CacheControl': f'max-age={ttl_seconds}',
            }

            if headers:
                upload_params.update(headers)

            # Upload to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=path,
                **upload_params
            )

            logger.debug(f"Uploaded content to S3 for CloudFront: {path}")
            return True

        except Exception as e:
            logger.error(f"Error uploading to CloudFront: {e}")
            return False

    async def _upload_via_http(
        self,
        cdn_url: str,
        content_data: bytes,
        content_type: ContentType,
        ttl_seconds: int,
        headers: dict[str, str] | None
    ) -> bool:
        """Upload content via HTTP (generic CDN)."""
        try:
            if not self._http_session:
                self._http_session = aiohttp.ClientSession()

            upload_headers = {
                'Content-Type': self._get_mime_type(content_type),
                'Cache-Control': f'max-age={ttl_seconds}',
            }

            if headers:
                upload_headers.update(headers)

            async with self._http_session.put(
                cdn_url,
                data=content_data,
                headers=upload_headers
            ) as response:
                return response.status in (200, 201, 204)

        except Exception as e:
            logger.error(f"Error uploading via HTTP: {e}")
            return False

    async def _perform_cdn_invalidation(
        self,
        urls: list[str],
        wait_for_completion: bool
    ) -> bool:
        """Perform CDN invalidation based on provider."""
        if self.config.provider == CDNProvider.CLOUDFRONT:
            return await self._invalidate_cloudfront(urls, wait_for_completion)
        else:
            return await self._invalidate_generic(urls, wait_for_completion)

    async def _invalidate_cloudfront(
        self,
        urls: list[str],
        wait_for_completion: bool
    ) -> bool:
        """Invalidate CloudFront cache."""
        try:
            if not self._cdn_client:
                return False

            # Convert URLs to paths
            paths = []
            for url in urls:
                path = urlparse(url).path
                if not path.startswith('/'):
                    path = '/' + path
                paths.append(path)

            # Create invalidation
            response = self._cdn_client.create_invalidation(
                DistributionId=self.config.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths),
                        'Items': paths
                    },
                    'CallerReference': str(int(time.time()))
                }
            )

            invalidation_id = response['Invalidation']['Id']

            # Wait for completion if requested
            if wait_for_completion:
                await self._wait_for_cloudfront_invalidation(invalidation_id)

            logger.info(f"CloudFront invalidation created: {invalidation_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating CloudFront invalidation: {e}")
            return False

    async def _wait_for_cloudfront_invalidation(self, invalidation_id: str):
        """Wait for CloudFront invalidation to complete."""
        max_wait_time = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = self._cdn_client.get_invalidation(
                    DistributionId=self.config.distribution_id,
                    Id=invalidation_id
                )

                status = response['Invalidation']['Status']

                if status == 'Completed':
                    logger.info(f"CloudFront invalidation {invalidation_id} completed")
                    return

                # Wait before checking again
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error checking invalidation status: {e}")
                break

        logger.warning(f"CloudFront invalidation {invalidation_id} did not complete in time")

    async def _invalidate_generic(self, urls: list[str], wait_for_completion: bool) -> bool:
        """Generic CDN invalidation via HTTP."""
        # This would depend on the specific CDN API
        logger.info(f"Generic CDN invalidation for {len(urls)} URLs")
        return True

    # ========================================================================
    # Content Management
    # ========================================================================

    async def _fetch_origin_content(self, url: str) -> bytes | None:
        """Fetch content from origin server."""
        try:
            if not self._http_session:
                self._http_session = aiohttp.ClientSession()

            async with self._http_session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"Failed to fetch origin content: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching origin content: {e}")
            return None

    async def _warm_edge_locations(self, cdn_url: str):
        """Warm CDN edge locations with content."""
        for edge_location in self.config.edge_locations:
            try:
                # This would make requests to specific edge locations
                # Implementation depends on CDN provider capabilities
                logger.debug(f"Warming edge location {edge_location} for {cdn_url}")

            except Exception as e:
                logger.error(f"Error warming edge location {edge_location}: {e}")

    def _generate_cdn_url(
        self,
        original_url: str,
        query_params: dict[str, Any] | None = None
    ) -> str:
        """Generate CDN URL from original URL."""
        # Parse original URL
        parsed = urlparse(original_url)

        # Build CDN URL
        cdn_path = parsed.path

        # Add query parameters if configured
        if query_params and self.config.query_string_caching:
            cdn_path += "?" + urlencode(query_params)

        # Generate CDN URL
        cdn_url = f"https://{self.config.domain_name}{cdn_path}"

        return cdn_url

    def _get_mime_type(self, content_type: ContentType) -> str:
        """Get MIME type for content type."""
        mime_types = {
            ContentType.STATIC_ASSETS: "text/plain",  # Would be more specific
            ContentType.API_RESPONSES: "application/json",
            ContentType.DOCUMENTS: "application/pdf",
            ContentType.MEDIA: "video/mp4",
            ContentType.DYNAMIC: "text/html"
        }

        return mime_types.get(content_type, "application/octet-stream")

    # ========================================================================
    # Analytics and Monitoring
    # ========================================================================

    async def _log_cache_access(self, url: str, access_type: str):
        """Log cache access for analytics."""
        access_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "access_type": access_type,
            "edge_location": "unknown"  # Would be determined from request
        }

        self.cache_access_log.append(access_record)

        # Update statistics
        if access_type == "hit":
            self.stats.cache_hits += 1
        elif access_type == "miss":
            self.stats.cache_misses += 1

        self.stats.total_requests += 1

    async def get_analytics(self) -> dict[str, Any]:
        """Get CDN analytics and performance metrics."""
        if self.config.provider == CDNProvider.CLOUDFRONT:
            return await self._get_cloudfront_analytics()
        else:
            return await self._get_generic_analytics()

    async def _get_cloudfront_analytics(self) -> dict[str, Any]:
        """Get CloudFront analytics."""
        try:
            if not self._cdn_client:
                return {}

            # Get CloudWatch metrics for the distribution
            if not BOTO3_AVAILABLE:
                logger.warning("boto3 not available - CloudWatch metrics skipped")
                return {}

            cloudwatch = boto3.client(
                'cloudwatch',
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
                region_name='us-east-1'  # CloudFront metrics are in us-east-1
            )

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)

            # Get basic metrics
            metrics = {}

            metric_names = [
                'Requests',
                'BytesDownloaded',
                'CacheHitRate',
                'ErrorRate',
                'OriginLatency'
            ]

            for metric_name in metric_names:
                try:
                    response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/CloudFront',
                        MetricName=metric_name,
                        Dimensions=[
                            {
                                'Name': 'DistributionId',
                                'Value': self.config.distribution_id
                            }
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=3600,  # 1 hour
                        Statistics=['Sum', 'Average']
                    )

                    if response['Datapoints']:
                        latest = max(response['Datapoints'], key=lambda x: x['Timestamp'])
                        if 'Sum' in latest:
                            metrics[metric_name] = latest['Sum']
                        else:
                            metrics[metric_name] = latest['Average']

                except Exception as e:
                    logger.error(f"Error getting metric {metric_name}: {e}")

            return {
                "provider": "cloudfront",
                "distribution_id": self.config.distribution_id,
                "metrics": metrics,
                "time_period": "24_hours"
            }

        except Exception as e:
            logger.error(f"Error getting CloudFront analytics: {e}")
            return {}

    async def _get_generic_analytics(self) -> dict[str, Any]:
        """Get generic CDN analytics from local statistics."""
        # Calculate statistics from local data
        hit_rate = self.stats.calculate_hit_rate()
        bandwidth_savings = self.stats.calculate_bandwidth_savings()

        # Analyze access log
        recent_accesses = list(self.cache_access_log)[-1000:]  # Last 1000 accesses

        access_by_type = defaultdict(int)
        access_by_hour = defaultdict(int)

        for record in recent_accesses:
            access_by_type[record["access_type"]] += 1
            hour = datetime.fromisoformat(record["timestamp"]).hour
            access_by_hour[hour] += 1

        # Calculate response time statistics
        response_time_stats = {}
        if self.response_times:
            times = list(self.response_times)
            response_time_stats = {
                "avg_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times)
            }

        return {
            "provider": self.config.provider.value,
            "hit_rate_percent": round(hit_rate, 2),
            "bandwidth_savings_percent": round(bandwidth_savings, 2),
            "cached_urls_count": len(self.cached_urls),
            "response_time_stats": response_time_stats,
            "access_patterns": {
                "by_type": dict(access_by_type),
                "by_hour": dict(access_by_hour)
            },
            "content_distribution": {
                content_type.value: sum(
                    1 for entry in self.cached_urls.values()
                    if entry.content_type == content_type
                )
                for content_type in ContentType
            }
        }

    def get_cache_status(self) -> dict[str, Any]:
        """Get current cache status."""
        expired_count = sum(1 for entry in self.cached_urls.values() if entry.is_expired())

        return {
            "total_cached_urls": len(self.cached_urls),
            "expired_urls": expired_count,
            "active_urls": len(self.cached_urls) - expired_count,
            "total_cache_size_mb": sum(
                entry.size_bytes for entry in self.cached_urls.values()
            ) / (1024 * 1024),
            "provider": self.config.provider.value,
            "domain": self.config.domain_name,
            "edge_locations": len(self.config.edge_locations),
            "compression_enabled": self.config.enable_compression,
            "ssl_enabled": self.config.enable_ssl
        }

    # ========================================================================
    # Cleanup and Maintenance
    # ========================================================================

    async def cleanup_expired_entries(self):
        """Clean up expired cache entries."""
        expired_urls = [
            url for url, entry in self.cached_urls.items()
            if entry.is_expired()
        ]

        for url in expired_urls:
            del self.cached_urls[url]

        if expired_urls:
            logger.info(f"Cleaned up {len(expired_urls)} expired cache entries")

    async def close(self):
        """Close CDN cache service."""
        if self._http_session:
            await self._http_session.close()

        logger.info("L3 CDN Cache service closed")

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# ============================================================================
# CDN Cache Factory
# ============================================================================

def create_cdn_cache(
    provider: CDNProvider = CDNProvider.CLOUDFRONT,
    domain_name: str = "",
    distribution_id: str = "",
    **kwargs
) -> L3CDNCache:
    """Create CDN cache with specified configuration."""
    config = CDNConfig(
        provider=provider,
        domain_name=domain_name,
        distribution_id=distribution_id,
        **kwargs
    )

    return L3CDNCache(config)


# Example usage
if __name__ == "__main__":
    async def main():
        # Create CDN cache
        cdn_config = CDNConfig(
            provider=CDNProvider.CLOUDFRONT,
            domain_name="example.cloudfront.net",
            distribution_id="E1234567890ABC",
            origin_domain="api.example.com"
        )

        cdn_cache = L3CDNCache(cdn_config)

        async with cdn_cache:
            # Cache some content
            content_data = b'{"message": "Hello from CDN!", "timestamp": "2025-01-19"}'

            cdn_url = await cdn_cache.cache_content(
                "https://api.example.com/hello",
                content_data,
                ContentType.API_RESPONSES,
                ttl_seconds=3600
            )

            print(f"Content cached at: {cdn_url}")

            # Get cached URL for future requests
            cached_url = await cdn_cache.get_cached_url(
                "https://api.example.com/hello",
                ContentType.API_RESPONSES
            )

            print(f"Cached URL: {cached_url}")

            # Prefetch multiple URLs
            urls_to_prefetch = [
                "https://api.example.com/users",
                "https://api.example.com/documents"
            ]

            prefetch_results = await cdn_cache.prefetch_content(
                urls_to_prefetch,
                ContentType.API_RESPONSES
            )

            print(f"Prefetch results: {prefetch_results}")

            # Get analytics
            analytics = await cdn_cache.get_analytics()
            print(f"CDN Analytics: {analytics}")

            # Get cache status
            status = cdn_cache.get_cache_status()
            print(f"Cache Status: {status}")

    # Run example
    # asyncio.run(main())
