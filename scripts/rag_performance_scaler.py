#!/usr/bin/env python3
"""
RAG Performance-Aware Scaling System
====================================

Intelligent auto-scaling system specifically optimized for RAG (Retrieval-Augmented Generation)
workloads. Takes into account RAG query complexity, vector index size, document processing
queues, and answer quality to make optimal scaling decisions.

Features:
- RAG query complexity analysis
- Vector index optimization for scaling
- Document processing queue management
- Answer quality preservation during scaling
- Cost-aware scaling for AI workloads
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np
from prometheus_api_client import PrometheusConnect

# Kubernetes client
try:
    from kubernetes import client, config
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class RAGWorkloadProfile:
    """Profile of current RAG workload characteristics"""
    query_complexity_score: float  # 0-1, higher = more complex
    average_query_time_ms: float
    p95_query_time_ms: float
    index_size_mb: float
    active_documents: int
    processing_queue_depth: int
    cache_hit_rate: float
    answer_quality_score: float  # 0-1, higher = better quality
    concurrent_queries: int
    memory_per_query_mb: float

@dataclass
class RAGScalingDecision:
    """RAG-specific scaling decision"""
    timestamp: datetime
    current_replicas: int
    recommended_replicas: int
    workload_profile: RAGWorkloadProfile
    scaling_factors: dict[str, float]
    confidence: float
    expected_query_time_improvement_ms: float
    expected_quality_impact: float  # -1 to 1, negative = quality decrease
    cost_impact_per_hour: float
    reasoning: str

class RAGWorkloadAnalyzer:
    """Analyze RAG workload characteristics for optimal scaling"""

    def __init__(self, prometheus_url: str = "http://prometheus:9090"):
        self.prometheus = PrometheusConnect(url=prometheus_url, disable_ssl=True)

        # RAG-specific query patterns
        self.rag_queries = {
            # Query performance metrics
            'rag_query_rate': 'rate(rag_queries_total[5m])',
            'rag_query_duration_p50': 'histogram_quantile(0.50, rate(rag_query_duration_seconds_bucket[5m]))',
            'rag_query_duration_p95': 'histogram_quantile(0.95, rate(rag_query_duration_seconds_bucket[5m]))',
            'rag_query_duration_p99': 'histogram_quantile(0.99, rate(rag_query_duration_seconds_bucket[5m]))',

            # Vector search metrics
            'vector_search_time_p95': 'histogram_quantile(0.95, rate(vector_search_duration_seconds_bucket[5m]))',
            'vector_similarity_threshold': 'avg(vector_similarity_score)',
            'vector_index_size_mb': 'vector_index_size_bytes / 1024 / 1024',
            'vector_search_results_count': 'avg(vector_search_results_returned)',

            # Document processing metrics
            'document_processing_queue_depth': 'document_processing_queue_depth',
            'document_processing_rate': 'rate(documents_processed_total[5m])',
            'document_processing_errors': 'rate(document_processing_errors_total[5m])',
            'avg_document_size_kb': 'avg(document_size_bytes) / 1024',

            # LLM and generation metrics
            'llm_generation_time_p95': 'histogram_quantile(0.95, rate(llm_generation_duration_seconds_bucket[5m]))',
            'llm_token_count_avg': 'avg(llm_tokens_generated)',
            'llm_context_length_avg': 'avg(llm_context_length)',

            # Cache performance
            'rag_cache_hit_rate': 'rag_cache_hits_total / (rag_cache_hits_total + rag_cache_misses_total)',
            'rag_cache_size_mb': 'rag_cache_size_bytes / 1024 / 1024',

            # Quality metrics
            'answer_relevance_score': 'avg(answer_relevance_score)',
            'answer_completeness_score': 'avg(answer_completeness_score)',
            'citation_accuracy_rate': 'citations_accurate_total / citations_total',

            # Resource utilization (RAG-specific)
            'rag_memory_usage_per_query': 'avg(container_memory_working_set_bytes{container="backend"}) / rate(rag_queries_total[5m])',
            'rag_cpu_usage_per_query': 'avg(rate(container_cpu_usage_seconds_total{container="backend"}[5m])) / rate(rag_queries_total[5m])',

            # Concurrent processing
            'concurrent_rag_queries': 'sum(rag_queries_active)',
            'rag_query_queue_wait_time': 'avg(rag_query_queue_wait_seconds)',
        }

        # Workload complexity classification
        self.complexity_factors = {
            'query_length': {'low': 50, 'medium': 200, 'high': 500},  # characters
            'context_documents': {'low': 5, 'medium': 20, 'high': 50},  # number of docs
            'similarity_threshold': {'high': 0.9, 'medium': 0.7, 'low': 0.5},  # higher threshold = more selective
            'generation_tokens': {'low': 100, 'medium': 500, 'high': 1000},  # tokens generated
        }

    async def collect_rag_metrics(self) -> dict[str, float]:
        """Collect RAG-specific metrics from Prometheus"""
        metrics = {}

        for metric_name, query in self.rag_queries.items():
            try:
                result = self.prometheus.custom_query(query)
                if result and len(result) > 0:
                    if isinstance(result[0], dict) and 'value' in result[0]:
                        value = float(result[0]['value'][1])
                    else:
                        value = float(result[0])
                    metrics[metric_name] = value
                else:
                    metrics[metric_name] = 0.0
                    logger.debug(f"No data for RAG metric {metric_name}")

            except Exception as e:
                logger.warning(f"Error collecting RAG metric {metric_name}: {e}")
                metrics[metric_name] = 0.0

        return metrics

    async def analyze_query_complexity(self, metrics: dict[str, float]) -> float:
        """Analyze query complexity score (0-1)"""
        complexity_score = 0.0
        factors = []

        # Query duration factor (normalized to expected max of 10 seconds)
        query_time_factor = min(1.0, metrics.get('rag_query_duration_p95', 0) / 10.0)
        factors.append(query_time_factor * 0.3)  # 30% weight

        # Vector search complexity (more results = more complex)
        search_results_factor = min(1.0, metrics.get('vector_search_results_count', 0) / 50.0)
        factors.append(search_results_factor * 0.2)  # 20% weight

        # Context length complexity (longer context = more complex)
        context_factor = min(1.0, metrics.get('llm_context_length_avg', 0) / 4000.0)
        factors.append(context_factor * 0.2)  # 20% weight

        # Generation complexity (more tokens = more complex)
        generation_factor = min(1.0, metrics.get('llm_token_count_avg', 0) / 1000.0)
        factors.append(generation_factor * 0.15)  # 15% weight

        # Index size complexity (larger index = potentially more complex searches)
        index_factor = min(1.0, metrics.get('vector_index_size_mb', 0) / 1000.0)  # Normalize to 1GB
        factors.append(index_factor * 0.15)  # 15% weight

        complexity_score = sum(factors)
        return min(1.0, complexity_score)

    async def create_workload_profile(self, metrics: dict[str, float]) -> RAGWorkloadProfile:
        """Create RAG workload profile from metrics"""

        complexity_score = await self.analyze_query_complexity(metrics)

        # Calculate memory per query (approximate)
        query_rate = max(0.01, metrics.get('rag_query_rate', 0.01))  # Avoid division by zero
        memory_per_query = metrics.get('rag_memory_usage_per_query', 100 * 1024 * 1024) / (1024 * 1024)  # Convert to MB

        # Calculate answer quality score (combination of relevance, completeness, accuracy)
        answer_quality = (
            metrics.get('answer_relevance_score', 0.8) * 0.4 +
            metrics.get('answer_completeness_score', 0.8) * 0.3 +
            metrics.get('citation_accuracy_rate', 0.9) * 0.3
        )

        return RAGWorkloadProfile(
            query_complexity_score=complexity_score,
            average_query_time_ms=metrics.get('rag_query_duration_p50', 0) * 1000,
            p95_query_time_ms=metrics.get('rag_query_duration_p95', 0) * 1000,
            index_size_mb=metrics.get('vector_index_size_mb', 0),
            active_documents=int(metrics.get('vector_search_results_count', 0)),
            processing_queue_depth=int(metrics.get('document_processing_queue_depth', 0)),
            cache_hit_rate=metrics.get('rag_cache_hit_rate', 0),
            answer_quality_score=answer_quality,
            concurrent_queries=int(metrics.get('concurrent_rag_queries', 0)),
            memory_per_query_mb=memory_per_query
        )

class RAGPerformanceScaler:
    """RAG performance-aware auto-scaling system"""

    def __init__(self, prometheus_url: str = "http://prometheus:9090"):
        self.workload_analyzer = RAGWorkloadAnalyzer(prometheus_url)

        # Scaling thresholds optimized for RAG workloads
        self.scaling_thresholds = {
            # Performance thresholds
            'max_p95_response_time_ms': 2000,  # 2 second max for P95
            'target_p95_response_time_ms': 500,  # 500ms target for P95
            'max_query_queue_wait_ms': 100,  # Max queue wait time

            # Quality thresholds
            'min_answer_quality_score': 0.75,  # Minimum acceptable quality
            'min_cache_hit_rate': 0.6,  # Minimum cache efficiency

            # Resource thresholds
            'max_memory_per_query_mb': 200,  # Max memory per query
            'max_concurrent_queries_per_replica': 10,  # Max concurrent queries

            # Queue thresholds
            'max_processing_queue_depth': 50,  # Max documents in processing queue
            'target_processing_queue_depth': 10,  # Target queue depth
        }

        # Cost factors (simplified estimates)
        self.cost_factors = {
            'cpu_cost_per_core_hour': 0.05,
            'memory_cost_per_gb_hour': 0.01,
            'storage_cost_per_gb_hour': 0.001,
        }

        # Scaling history for trend analysis
        self.scaling_history = []

    async def calculate_rag_scaling_factors(self, profile: RAGWorkloadProfile,
                                         current_replicas: int) -> dict[str, float]:
        """Calculate scaling factors based on RAG workload characteristics"""
        factors = {}

        # Response time factor
        if profile.p95_query_time_ms > self.scaling_thresholds['max_p95_response_time_ms']:
            factors['response_time'] = 2.0  # Aggressive scale-up
        elif profile.p95_query_time_ms > self.scaling_thresholds['target_p95_response_time_ms']:
            # Linear scaling based on response time
            target = self.scaling_thresholds['target_p95_response_time_ms']
            max_time = self.scaling_thresholds['max_p95_response_time_ms']
            factors['response_time'] = 1.0 + ((profile.p95_query_time_ms - target) / (max_time - target))
        else:
            factors['response_time'] = 0.9  # Slight scale-down opportunity

        # Concurrency factor
        queries_per_replica = profile.concurrent_queries / max(1, current_replicas)
        max_queries_per_replica = self.scaling_thresholds['max_concurrent_queries_per_replica']

        if queries_per_replica > max_queries_per_replica:
            factors['concurrency'] = queries_per_replica / max_queries_per_replica
        else:
            factors['concurrency'] = 1.0

        # Memory efficiency factor
        if profile.memory_per_query_mb > self.scaling_thresholds['max_memory_per_query_mb']:
            factors['memory_efficiency'] = 1.5  # Need more replicas
        else:
            factors['memory_efficiency'] = 1.0

        # Queue depth factor
        if profile.processing_queue_depth > self.scaling_thresholds['max_processing_queue_depth']:
            queue_factor = profile.processing_queue_depth / self.scaling_thresholds['target_processing_queue_depth']
            factors['queue_depth'] = min(2.0, queue_factor)  # Cap at 2x scaling
        else:
            factors['queue_depth'] = 1.0

        # Complexity factor (more complex queries need more resources)
        if profile.query_complexity_score > 0.7:
            factors['complexity'] = 1.0 + (profile.query_complexity_score - 0.7) * 2  # Up to 1.6x
        else:
            factors['complexity'] = 1.0

        # Cache efficiency factor (poor cache hit rate needs more replicas)
        if profile.cache_hit_rate < self.scaling_thresholds['min_cache_hit_rate']:
            cache_penalty = (self.scaling_thresholds['min_cache_hit_rate'] - profile.cache_hit_rate) * 2
            factors['cache_efficiency'] = 1.0 + cache_penalty
        else:
            factors['cache_efficiency'] = 1.0

        # Quality preservation factor
        if profile.answer_quality_score < self.scaling_thresholds['min_answer_quality_score']:
            # Poor quality might indicate resource contention
            quality_penalty = (self.scaling_thresholds['min_answer_quality_score'] - profile.answer_quality_score) * 3
            factors['quality_preservation'] = 1.0 + quality_penalty
        else:
            factors['quality_preservation'] = 1.0

        return factors

    async def calculate_optimal_replicas(self, profile: RAGWorkloadProfile,
                                       current_replicas: int) -> tuple[int, float]:
        """Calculate optimal replica count and confidence score"""

        # Get scaling factors
        factors = await self.calculate_rag_scaling_factors(profile, current_replicas)

        # Calculate weighted scaling multiplier
        weights = {
            'response_time': 0.25,
            'concurrency': 0.20,
            'memory_efficiency': 0.15,
            'queue_depth': 0.15,
            'complexity': 0.10,
            'cache_efficiency': 0.10,
            'quality_preservation': 0.05
        }

        scaling_multiplier = sum(factors.get(factor, 1.0) * weight
                               for factor, weight in weights.items())

        # Apply scaling multiplier
        optimal_replicas_float = current_replicas * scaling_multiplier

        # Apply bounds and rounding
        optimal_replicas = max(2, min(20, int(np.round(optimal_replicas_float))))

        # Calculate confidence based on factor consistency
        factor_values = list(factors.values())
        factor_std = np.std(factor_values) if len(factor_values) > 1 else 0

        # Higher standard deviation = lower confidence
        confidence = max(0.3, 1.0 - (factor_std / 2.0))

        # Adjust confidence based on historical accuracy
        if len(self.scaling_history) >= 3:
            recent_accuracy = np.mean([h.get('accuracy', 0.8) for h in self.scaling_history[-3:]])
            confidence = (confidence + recent_accuracy) / 2

        return optimal_replicas, confidence

    async def estimate_performance_impact(self, profile: RAGWorkloadProfile,
                                        current_replicas: int,
                                        new_replicas: int) -> tuple[float, float]:
        """Estimate query time improvement and quality impact"""

        if new_replicas <= current_replicas:
            # Scaling down or maintaining
            replica_ratio = current_replicas / new_replicas if new_replicas > 0 else 1

            # Query time might increase due to higher load per replica
            expected_time_increase = (replica_ratio - 1) * profile.p95_query_time_ms * 0.3  # 30% impact
            expected_query_time_improvement = -expected_time_increase  # Negative = worse

            # Quality might decrease due to resource contention
            expected_quality_impact = -(replica_ratio - 1) * 0.1  # Up to -10% quality

        else:
            # Scaling up
            replica_ratio = new_replicas / current_replicas

            # Query time should improve
            load_reduction_factor = 1 / replica_ratio
            expected_query_time_improvement = profile.p95_query_time_ms * (1 - load_reduction_factor) * 0.7

            # Quality might improve due to less resource contention
            expected_quality_impact = min(0.1, (replica_ratio - 1) * 0.05)  # Up to +10% quality

        return expected_query_time_improvement, expected_quality_impact

    async def calculate_cost_impact(self, current_replicas: int, new_replicas: int,
                                  profile: RAGWorkloadProfile) -> float:
        """Calculate cost impact of scaling decision"""

        replica_change = new_replicas - current_replicas

        if replica_change == 0:
            return 0.0

        # Estimate resource usage per replica
        cpu_cores_per_replica = 1.0  # Assume 1 CPU core per replica
        memory_gb_per_replica = profile.memory_per_query_mb * 10 / 1024  # Estimate based on query memory

        # Calculate cost change per hour
        cpu_cost_change = replica_change * cpu_cores_per_replica * self.cost_factors['cpu_cost_per_core_hour']
        memory_cost_change = replica_change * memory_gb_per_replica * self.cost_factors['memory_cost_per_gb_hour']

        total_cost_change = cpu_cost_change + memory_cost_change

        return total_cost_change

    async def make_scaling_decision(self, current_replicas: int) -> RAGScalingDecision:
        """Make RAG-aware scaling decision"""

        try:
            # Collect metrics and create workload profile
            metrics = await self.workload_analyzer.collect_rag_metrics()
            profile = await self.workload_analyzer.create_workload_profile(metrics)

            # Calculate optimal replica count
            optimal_replicas, confidence = await self.calculate_optimal_replicas(profile, current_replicas)

            # Get scaling factors for explanation
            scaling_factors = await self.calculate_rag_scaling_factors(profile, current_replicas)

            # Estimate performance and quality impact
            expected_query_improvement, expected_quality_impact = await self.estimate_performance_impact(
                profile, current_replicas, optimal_replicas
            )

            # Calculate cost impact
            cost_impact = await self.calculate_cost_impact(current_replicas, optimal_replicas, profile)

            # Generate reasoning
            reasoning_parts = []

            if optimal_replicas > current_replicas:
                reasoning_parts.append(f"Scale up from {current_replicas} to {optimal_replicas} replicas")
                if profile.p95_query_time_ms > self.scaling_thresholds['target_p95_response_time_ms']:
                    reasoning_parts.append(f"P95 query time {profile.p95_query_time_ms:.0f}ms exceeds target")
                if profile.concurrent_queries / current_replicas > self.scaling_thresholds['max_concurrent_queries_per_replica']:
                    reasoning_parts.append("High concurrent query load per replica")
                if profile.processing_queue_depth > self.scaling_thresholds['target_processing_queue_depth']:
                    reasoning_parts.append(f"Processing queue depth at {profile.processing_queue_depth}")

            elif optimal_replicas < current_replicas:
                reasoning_parts.append(f"Scale down from {current_replicas} to {optimal_replicas} replicas")
                reasoning_parts.append("Current utilization allows for cost optimization")
                if profile.cache_hit_rate > 0.8:
                    reasoning_parts.append(f"High cache hit rate ({profile.cache_hit_rate:.1%}) reduces load")

            else:
                reasoning_parts.append("Maintain current replica count")
                reasoning_parts.append("Current scaling is optimal for workload")

            # Add quality and performance context
            if profile.answer_quality_score < self.scaling_thresholds['min_answer_quality_score']:
                reasoning_parts.append(f"Quality score {profile.answer_quality_score:.2f} below threshold")

            if profile.query_complexity_score > 0.7:
                reasoning_parts.append(f"High query complexity ({profile.query_complexity_score:.2f}) detected")

            reasoning = ". ".join(reasoning_parts) + "."

            decision = RAGScalingDecision(
                timestamp=datetime.now(),
                current_replicas=current_replicas,
                recommended_replicas=optimal_replicas,
                workload_profile=profile,
                scaling_factors=scaling_factors,
                confidence=confidence,
                expected_query_time_improvement_ms=expected_query_improvement,
                expected_quality_impact=expected_quality_impact,
                cost_impact_per_hour=cost_impact,
                reasoning=reasoning
            )

            # Add to history
            self.scaling_history.append({
                'timestamp': datetime.now(),
                'decision': decision,
                'accuracy': confidence  # This would be updated later based on actual results
            })

            # Keep only recent history
            if len(self.scaling_history) > 100:
                self.scaling_history = self.scaling_history[-100:]

            return decision

        except Exception as e:
            logger.error(f"Error making scaling decision: {e}")

            # Return safe default decision
            return RAGScalingDecision(
                timestamp=datetime.now(),
                current_replicas=current_replicas,
                recommended_replicas=current_replicas,  # No change on error
                workload_profile=RAGWorkloadProfile(
                    query_complexity_score=0.5,
                    average_query_time_ms=500,
                    p95_query_time_ms=1000,
                    index_size_mb=100,
                    active_documents=10,
                    processing_queue_depth=0,
                    cache_hit_rate=0.8,
                    answer_quality_score=0.8,
                    concurrent_queries=5,
                    memory_per_query_mb=50
                ),
                scaling_factors={},
                confidence=0.1,  # Low confidence due to error
                expected_query_time_improvement_ms=0,
                expected_quality_impact=0,
                cost_impact_per_hour=0,
                reasoning=f"Error occurred during scaling analysis: {str(e)}. Maintaining current scale."
            )

class RAGScalingOrchestrator:
    """Orchestrate RAG performance-aware scaling"""

    def __init__(self, prometheus_url: str = "http://prometheus:9090"):
        self.scaler = RAGPerformanceScaler(prometheus_url)
        self.prometheus = PrometheusConnect(url=prometheus_url, disable_ssl=True)

        # Kubernetes integration
        self.k8s_available = KUBERNETES_AVAILABLE
        if self.k8s_available:
            try:
                config.load_incluster_config()
            except:
                try:
                    config.load_kube_config()
                except:
                    self.k8s_available = False

            if self.k8s_available:
                self.apps_v1 = client.AppsV1Api()

    async def get_current_replicas(self) -> int:
        """Get current replica count from Kubernetes"""
        if not self.k8s_available:
            # Try to get from Prometheus
            try:
                result = self.prometheus.custom_query(
                    'count(kube_pod_info{namespace="ai-pdf-scholar", pod=~".*backend.*"})'
                )
                if result and len(result) > 0:
                    return int(float(result[0]['value'][1]))
            except:
                pass

            return 2  # Default fallback

        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name="ai-pdf-scholar-backend",
                namespace="ai-pdf-scholar"
            )
            return deployment.spec.replicas
        except:
            return 2

    async def run_scaling_cycle(self) -> RAGScalingDecision:
        """Run a single RAG scaling cycle"""
        current_replicas = await self.get_current_replicas()
        decision = await self.scaler.make_scaling_decision(current_replicas)

        logger.info(
            f"RAG Scaling Decision: {decision.current_replicas} -> {decision.recommended_replicas} "
            f"(confidence: {decision.confidence:.2f}, "
            f"expected improvement: {decision.expected_query_time_improvement_ms:.0f}ms)"
        )

        return decision

    async def run_continuous(self, interval_seconds: int = 120):
        """Run continuous RAG performance scaling"""
        logger.info("Starting RAG performance-aware scaling orchestrator...")

        while True:
            try:
                decision = await self.run_scaling_cycle()

                # Log detailed decision info
                logger.info("RAG Scaling Analysis:")
                logger.info("  Workload Profile:")
                logger.info(f"    Query Complexity: {decision.workload_profile.query_complexity_score:.2f}")
                logger.info(f"    P95 Query Time: {decision.workload_profile.p95_query_time_ms:.0f}ms")
                logger.info(f"    Cache Hit Rate: {decision.workload_profile.cache_hit_rate:.1%}")
                logger.info(f"    Quality Score: {decision.workload_profile.answer_quality_score:.2f}")
                logger.info(f"    Queue Depth: {decision.workload_profile.processing_queue_depth}")
                logger.info(f"  Decision: {decision.reasoning}")
                logger.info(f"  Cost Impact: ${decision.cost_impact_per_hour:.3f}/hour")

                await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("RAG scaling orchestrator stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in RAG scaling cycle: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

# CLI interface
async def main():
    """Main entry point for RAG performance scaler"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG Performance-Aware Scaling System")
    parser.add_argument("--prometheus-url", default="http://prometheus:9090",
                       help="Prometheus server URL")
    parser.add_argument("--mode", choices=["analyze", "decide", "continuous"],
                       default="continuous", help="Operation mode")
    parser.add_argument("--interval", type=int, default=120,
                       help="Scaling check interval in seconds")
    parser.add_argument("--output", help="Output file for decisions")

    args = parser.parse_args()

    orchestrator = RAGScalingOrchestrator(prometheus_url=args.prometheus_url)

    if args.mode == "analyze":
        logger.info("Analyzing RAG workload...")
        current_replicas = await orchestrator.get_current_replicas()
        metrics = await orchestrator.scaler.workload_analyzer.collect_rag_metrics()
        profile = await orchestrator.scaler.workload_analyzer.create_workload_profile(metrics)

        print("RAG Workload Profile:")
        print(f"  Query Complexity Score: {profile.query_complexity_score:.2f}")
        print(f"  Average Query Time: {profile.average_query_time_ms:.0f}ms")
        print(f"  P95 Query Time: {profile.p95_query_time_ms:.0f}ms")
        print(f"  Index Size: {profile.index_size_mb:.1f}MB")
        print(f"  Processing Queue: {profile.processing_queue_depth}")
        print(f"  Cache Hit Rate: {profile.cache_hit_rate:.1%}")
        print(f"  Answer Quality: {profile.answer_quality_score:.2f}")
        print(f"  Concurrent Queries: {profile.concurrent_queries}")
        print(f"  Memory per Query: {profile.memory_per_query_mb:.1f}MB")

    elif args.mode == "decide":
        logger.info("Making RAG scaling decision...")
        decision = await orchestrator.run_scaling_cycle()

        result = asdict(decision)
        print(json.dumps(result, indent=2, default=str))

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)

    elif args.mode == "continuous":
        await orchestrator.run_continuous(args.interval)

if __name__ == "__main__":
    asyncio.run(main())
