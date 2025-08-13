"""
Advanced Test Categorization and Dependency Analysis System

Provides intelligent test categorization, dependency mapping, and execution
optimization for parallel test execution.
"""

import ast
import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
import importlib.util


class TestCategory(Enum):
    """Test categories for execution optimization."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "end_to_end"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATABASE = "database"
    CONCURRENT = "concurrent"
    SLOW = "slow"


class IsolationLevel(Enum):
    """Database isolation levels for parallel execution."""
    SHARED = "shared"              # Share database with table cleanup
    PER_WORKER = "per_worker"      # One database per pytest worker
    PER_TEST = "per_test"          # New database for each test
    PER_CLASS = "per_class"        # One database per test class


class ResourceRequirement(Enum):
    """Resource requirements for test execution."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TestDependency:
    """Represents a dependency between tests or test components."""
    
    dependency_type: str  # "database", "file", "service", "network", "state"
    source: str          # Test or component name
    target: str          # Dependency target
    description: str     # Human-readable description
    blocking: bool = False  # Whether this dependency blocks parallel execution
    

@dataclass
class TestCharacteristics:
    """Comprehensive test characteristics for execution optimization."""
    
    test_name: str
    test_path: str
    category: TestCategory
    isolation_level: IsolationLevel
    
    # Resource requirements
    memory_requirement: ResourceRequirement = ResourceRequirement.LOW
    cpu_requirement: ResourceRequirement = ResourceRequirement.LOW
    io_requirement: ResourceRequirement = ResourceRequirement.LOW
    
    # Execution characteristics
    estimated_duration_ms: int = 100
    database_operations: int = 0
    file_operations: int = 0
    network_calls: int = 0
    concurrent_operations: int = 0
    
    # Parallel execution safety
    parallel_safe: bool = True
    requires_isolation: bool = False
    can_share_database: bool = True
    thread_safe: bool = True
    
    # Dependencies
    dependencies: List[TestDependency] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)  # Tests that conflict
    
    # Markers and metadata
    pytest_markers: Set[str] = field(default_factory=set)
    custom_attributes: Dict[str, Any] = field(default_factory=dict)


class TestAnalyzer:
    """Analyzes test code to extract characteristics and dependencies."""
    
    def __init__(self):
        self.database_patterns = [
            r'db\.',
            r'database',
            r'connection',
            r'execute\(',
            r'fetch_',
            r'transaction',
            r'commit',
            r'rollback'
        ]
        
        self.file_patterns = [
            r'open\(',
            r'Path\(',
            r'\.read\(',
            r'\.write\(',
            r'tempfile',
            r'\.exists\(',
            r'\.unlink\('
        ]
        
        self.network_patterns = [
            r'requests\.',
            r'urllib',
            r'httpx',
            r'aiohttp',
            r'socket',
            r'http',
            r'api'
        ]
        
        self.concurrent_patterns = [
            r'threading',
            r'asyncio',
            r'concurrent',
            r'multiprocessing',
            r'Thread\(',
            r'Pool\(',
            r'async def',
            r'await '
        ]
    
    def analyze_test_file(self, file_path: Path) -> List[TestCharacteristics]:
        """Analyze a test file and extract characteristics for all tests."""
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Extract test functions and classes
            test_characteristics = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    characteristics = self._analyze_test_function(node, file_path, content)
                    test_characteristics.append(characteristics)
                elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                    class_chars = self._analyze_test_class(node, file_path, content)
                    test_characteristics.extend(class_chars)
            
            return test_characteristics
            
        except Exception as e:
            print(f"Warning: Failed to analyze test file {file_path}: {e}")
            return []
    
    def _analyze_test_function(
        self, 
        node: ast.FunctionDef, 
        file_path: Path, 
        content: str
    ) -> TestCharacteristics:
        """Analyze a single test function."""
        
        test_name = node.name
        full_name = f"{file_path.stem}::{test_name}"
        
        # Extract function content
        func_content = ast.get_source_segment(content, node) or ""
        
        # Basic categorization
        category = self._categorize_test(test_name, func_content, file_path)
        isolation_level = self._determine_isolation_level(func_content, category)
        
        # Analyze resource requirements
        memory_req = self._analyze_memory_requirements(func_content)
        cpu_req = self._analyze_cpu_requirements(func_content)
        io_req = self._analyze_io_requirements(func_content)
        
        # Count operations
        db_ops = self._count_pattern_matches(func_content, self.database_patterns)
        file_ops = self._count_pattern_matches(func_content, self.file_patterns)
        network_ops = self._count_pattern_matches(func_content, self.network_patterns)
        concurrent_ops = self._count_pattern_matches(func_content, self.concurrent_patterns)
        
        # Estimate duration
        duration = self._estimate_duration(func_content, category, db_ops, file_ops)
        
        # Analyze parallel safety
        parallel_safe = self._is_parallel_safe(func_content, category)
        requires_isolation = self._requires_isolation(func_content, category)
        can_share_db = self._can_share_database(func_content, category)
        thread_safe = self._is_thread_safe(func_content)
        
        # Extract pytest markers
        markers = self._extract_pytest_markers(node, func_content)
        
        # Analyze dependencies
        dependencies = self._analyze_dependencies(func_content, test_name)
        
        return TestCharacteristics(
            test_name=full_name,
            test_path=str(file_path),
            category=category,
            isolation_level=isolation_level,
            memory_requirement=memory_req,
            cpu_requirement=cpu_req,
            io_requirement=io_req,
            estimated_duration_ms=duration,
            database_operations=db_ops,
            file_operations=file_ops,
            network_calls=network_ops,
            concurrent_operations=concurrent_ops,
            parallel_safe=parallel_safe,
            requires_isolation=requires_isolation,
            can_share_database=can_share_db,
            thread_safe=thread_safe,
            dependencies=dependencies,
            pytest_markers=markers
        )
    
    def _analyze_test_class(
        self, 
        node: ast.ClassDef, 
        file_path: Path, 
        content: str
    ) -> List[TestCharacteristics]:
        """Analyze all test methods in a test class."""
        characteristics = []
        
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                char = self._analyze_test_function(item, file_path, content)
                # Update test name to include class
                char.test_name = f"{file_path.stem}::{node.name}::{item.name}"
                characteristics.append(char)
        
        return characteristics
    
    def _categorize_test(self, test_name: str, content: str, file_path: Path) -> TestCategory:
        """Categorize test based on name, content, and file path."""
        
        # File path based categorization
        path_str = str(file_path).lower()
        if 'integration' in path_str:
            return TestCategory.INTEGRATION
        elif 'e2e' in path_str or 'end_to_end' in path_str:
            return TestCategory.E2E
        elif 'performance' in path_str or 'benchmark' in path_str:
            return TestCategory.PERFORMANCE
        elif 'security' in path_str:
            return TestCategory.SECURITY
        
        # Content based categorization
        content_lower = content.lower()
        name_lower = test_name.lower()
        
        # Check for integration patterns
        integration_patterns = [
            'integration', 'end_to_end', 'e2e', 'workflow', 'complete',
            'full', 'system', 'api.*test', 'service.*integration'
        ]
        if any(re.search(pattern, content_lower) or re.search(pattern, name_lower) 
               for pattern in integration_patterns):
            return TestCategory.INTEGRATION
        
        # Check for performance patterns
        performance_patterns = [
            'performance', 'benchmark', 'speed', 'timing', 'duration',
            'throughput', 'latency', 'memory_usage', 'cpu_usage'
        ]
        if any(re.search(pattern, content_lower) or re.search(pattern, name_lower)
               for pattern in performance_patterns):
            return TestCategory.PERFORMANCE
        
        # Check for database patterns
        if self._count_pattern_matches(content, self.database_patterns) > 3:
            return TestCategory.DATABASE
        
        # Check for concurrent patterns
        if self._count_pattern_matches(content, self.concurrent_patterns) > 0:
            return TestCategory.CONCURRENT
        
        # Check for slow test indicators
        slow_patterns = ['sleep', 'time.sleep', 'slow', 'wait', 'timeout']
        if any(pattern in content_lower for pattern in slow_patterns):
            return TestCategory.SLOW
        
        # Default to unit test
        return TestCategory.UNIT
    
    def _determine_isolation_level(self, content: str, category: TestCategory) -> IsolationLevel:
        """Determine required isolation level based on content analysis."""
        
        # Force per-test isolation for certain patterns
        isolation_patterns = [
            'isolated', 'isolation', 'clean_state', 'fresh_db',
            'reset_database', 'migrate', 'schema'
        ]
        if any(pattern in content.lower() for pattern in isolation_patterns):
            return IsolationLevel.PER_TEST
        
        # Category-based isolation
        if category in [TestCategory.INTEGRATION, TestCategory.E2E]:
            return IsolationLevel.PER_WORKER
        elif category == TestCategory.PERFORMANCE:
            return IsolationLevel.PER_TEST  # Performance tests need clean state
        elif category == TestCategory.DATABASE:
            return IsolationLevel.PER_WORKER
        
        # Check for transaction patterns
        transaction_patterns = ['transaction', 'commit', 'rollback', 'begin']
        if any(pattern in content.lower() for pattern in transaction_patterns):
            return IsolationLevel.PER_WORKER
        
        return IsolationLevel.SHARED
    
    def _count_pattern_matches(self, content: str, patterns: List[str]) -> int:
        """Count pattern matches in content."""
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))
        return count
    
    def _analyze_memory_requirements(self, content: str) -> ResourceRequirement:
        """Analyze memory requirements based on content."""
        high_memory_patterns = [
            'large_document', 'big_file', 'memory_intensive',
            'load_all', 'cache_all', 'bulk_', 'massive'
        ]
        
        if any(pattern in content.lower() for pattern in high_memory_patterns):
            return ResourceRequirement.HIGH
        
        medium_memory_patterns = [
            'document', 'file_processing', 'embedding', 'vector',
            'index', 'search', 'rag'
        ]
        
        if any(pattern in content.lower() for pattern in medium_memory_patterns):
            return ResourceRequirement.MEDIUM
        
        return ResourceRequirement.LOW
    
    def _analyze_cpu_requirements(self, content: str) -> ResourceRequirement:
        """Analyze CPU requirements based on content."""
        high_cpu_patterns = [
            'cpu_intensive', 'computation', 'algorithm', 'processing',
            'parallel', 'multiprocessing', 'heavy', 'complex'
        ]
        
        if any(pattern in content.lower() for pattern in high_cpu_patterns):
            return ResourceRequirement.HIGH
        
        medium_cpu_patterns = [
            'loop', 'iteration', 'calculation', 'analysis', 'search',
            'parsing', 'encoding', 'decoding'
        ]
        
        if any(pattern in content.lower() for pattern in medium_cpu_patterns):
            return ResourceRequirement.MEDIUM
        
        return ResourceRequirement.LOW
    
    def _analyze_io_requirements(self, content: str) -> ResourceRequirement:
        """Analyze I/O requirements based on content."""
        high_io_patterns = [
            'file_upload', 'download', 'streaming', 'large_file',
            'bulk_import', 'export', 'io_intensive'
        ]
        
        if any(pattern in content.lower() for pattern in high_io_patterns):
            return ResourceRequirement.HIGH
        
        file_ops = self._count_pattern_matches(content, self.file_patterns)
        db_ops = self._count_pattern_matches(content, self.database_patterns)
        
        if file_ops > 5 or db_ops > 10:
            return ResourceRequirement.MEDIUM
        elif file_ops > 0 or db_ops > 0:
            return ResourceRequirement.LOW
        
        return ResourceRequirement.LOW
    
    def _estimate_duration(
        self, 
        content: str, 
        category: TestCategory,
        db_ops: int,
        file_ops: int
    ) -> int:
        """Estimate test duration in milliseconds."""
        
        base_duration = 100  # Base 100ms
        
        # Category multipliers
        category_multipliers = {
            TestCategory.UNIT: 1.0,
            TestCategory.INTEGRATION: 3.0,
            TestCategory.E2E: 10.0,
            TestCategory.PERFORMANCE: 20.0,
            TestCategory.DATABASE: 2.0,
            TestCategory.CONCURRENT: 5.0,
            TestCategory.SLOW: 50.0,
            TestCategory.SECURITY: 5.0
        }
        
        duration = base_duration * category_multipliers.get(category, 1.0)
        
        # Add duration for operations
        duration += db_ops * 10  # 10ms per DB operation
        duration += file_ops * 5  # 5ms per file operation
        
        # Check for explicit duration indicators
        if 'sleep' in content.lower():
            sleep_matches = re.findall(r'sleep\((\d+(?:\.\d+)?)\)', content, re.IGNORECASE)
            for match in sleep_matches:
                duration += float(match) * 1000  # Convert seconds to ms
        
        return int(duration)
    
    def _is_parallel_safe(self, content: str, category: TestCategory) -> bool:
        """Determine if test is safe for parallel execution."""
        
        # Unsafe patterns
        unsafe_patterns = [
            'global ', 'singleton', 'shared_state', 'race_condition',
            'not_thread_safe', 'sequential_only', 'exclusive_access'
        ]
        
        if any(pattern in content.lower() for pattern in unsafe_patterns):
            return False
        
        # Category-based safety
        if category in [TestCategory.E2E, TestCategory.SECURITY]:
            return False  # Often require exclusive access
        
        return True
    
    def _requires_isolation(self, content: str, category: TestCategory) -> bool:
        """Determine if test requires database isolation."""
        
        isolation_patterns = [
            'requires_isolation', 'clean_database', 'fresh_state',
            'isolation', 'exclusive', 'schema_change', 'migration'
        ]
        
        if any(pattern in content.lower() for pattern in isolation_patterns):
            return True
        
        # Category-based isolation
        return category in [TestCategory.INTEGRATION, TestCategory.E2E, TestCategory.PERFORMANCE]
    
    def _can_share_database(self, content: str, category: TestCategory) -> bool:
        """Determine if test can share database with others."""
        
        exclusive_patterns = [
            'exclusive_database', 'schema_change', 'migration',
            'drop_table', 'create_table', 'alter_table'
        ]
        
        if any(pattern in content.lower() for pattern in exclusive_patterns):
            return False
        
        return category not in [TestCategory.E2E, TestCategory.PERFORMANCE]
    
    def _is_thread_safe(self, content: str) -> bool:
        """Determine if test is thread-safe."""
        
        unsafe_patterns = [
            'not_thread_safe', 'global ', 'shared_resource',
            'race_condition', 'thread_unsafe'
        ]
        
        return not any(pattern in content.lower() for pattern in unsafe_patterns)
    
    def _extract_pytest_markers(self, node: ast.FunctionDef, content: str) -> Set[str]:
        """Extract pytest markers from test function."""
        markers = set()
        
        # Extract from decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if hasattr(decorator.value, 'id') and decorator.value.id == 'pytest':
                    markers.add(decorator.attr)
            elif isinstance(decorator, ast.Call):
                if (isinstance(decorator.func, ast.Attribute) and
                    hasattr(decorator.func.value, 'id') and 
                    decorator.func.value.id == 'pytest'):
                    markers.add(decorator.func.attr)
        
        # Extract from content patterns
        marker_patterns = [
            r'@pytest\.mark\.(\w+)',
            r'pytestmark\s*=.*pytest\.mark\.(\w+)'
        ]
        
        for pattern in marker_patterns:
            matches = re.findall(pattern, content)
            markers.update(matches)
        
        return markers
    
    def _analyze_dependencies(self, content: str, test_name: str) -> List[TestDependency]:
        """Analyze test dependencies."""
        dependencies = []
        
        # Database dependencies
        if self._count_pattern_matches(content, self.database_patterns) > 0:
            dependencies.append(TestDependency(
                dependency_type="database",
                source=test_name,
                target="database_connection",
                description="Requires database access",
                blocking=True
            ))
        
        # File dependencies
        if self._count_pattern_matches(content, self.file_patterns) > 0:
            dependencies.append(TestDependency(
                dependency_type="file",
                source=test_name,
                target="file_system",
                description="Requires file system access",
                blocking=False
            ))
        
        # Network dependencies
        if self._count_pattern_matches(content, self.network_patterns) > 0:
            dependencies.append(TestDependency(
                dependency_type="network",
                source=test_name,
                target="network_access",
                description="Requires network access",
                blocking=True
            ))
        
        return dependencies


class TestExecutionPlanner:
    """Plans optimal test execution based on characteristics and dependencies."""
    
    def __init__(self):
        self.analyzer = TestAnalyzer()
        self.test_characteristics: Dict[str, TestCharacteristics] = {}
    
    def analyze_test_directory(self, test_dir: Path) -> Dict[str, TestCharacteristics]:
        """Analyze all test files in directory."""
        characteristics = {}
        
        for test_file in test_dir.rglob("test_*.py"):
            file_characteristics = self.analyzer.analyze_test_file(test_file)
            for char in file_characteristics:
                characteristics[char.test_name] = char
        
        self.test_characteristics = characteristics
        return characteristics
    
    def create_execution_plan(
        self, 
        test_characteristics: Dict[str, TestCharacteristics],
        max_workers: int = 8,
        memory_limit_mb: int = 2048
    ) -> Dict[str, Any]:
        """Create optimal execution plan for parallel testing."""
        
        # Categorize tests by isolation requirements
        isolation_groups = {
            IsolationLevel.SHARED: [],
            IsolationLevel.PER_WORKER: [],
            IsolationLevel.PER_TEST: [],
            IsolationLevel.PER_CLASS: []
        }
        
        for test_name, char in test_characteristics.items():
            isolation_groups[char.isolation_level].append((test_name, char))
        
        # Calculate resource requirements
        total_memory_estimate = sum(
            self._estimate_memory_usage(char) 
            for char in test_characteristics.values()
        )
        
        # Determine optimal worker allocation
        worker_allocation = self._allocate_workers(
            isolation_groups, max_workers, memory_limit_mb
        )
        
        # Create execution phases
        execution_phases = self._create_execution_phases(isolation_groups)
        
        return {
            "execution_plan": {
                "total_tests": len(test_characteristics),
                "max_workers": max_workers,
                "memory_limit_mb": memory_limit_mb,
                "estimated_memory_mb": total_memory_estimate,
                "worker_allocation": worker_allocation,
                "execution_phases": execution_phases
            },
            "isolation_groups": {
                level.value: [(name, char.estimated_duration_ms) 
                             for name, char in tests]
                for level, tests in isolation_groups.items()
            },
            "performance_predictions": self._predict_performance(
                isolation_groups, worker_allocation
            )
        }
    
    def _estimate_memory_usage(self, char: TestCharacteristics) -> float:
        """Estimate memory usage in MB for a test."""
        base_memory = 10  # Base 10MB per test
        
        multipliers = {
            ResourceRequirement.LOW: 1.0,
            ResourceRequirement.MEDIUM: 2.0,
            ResourceRequirement.HIGH: 5.0,
            ResourceRequirement.CRITICAL: 10.0
        }
        
        return base_memory * multipliers[char.memory_requirement]
    
    def _allocate_workers(
        self,
        isolation_groups: Dict[IsolationLevel, List[Tuple[str, TestCharacteristics]]],
        max_workers: int,
        memory_limit_mb: int
    ) -> Dict[str, Any]:
        """Allocate workers optimally across isolation groups."""
        
        # Calculate test counts and complexity
        group_stats = {}
        for level, tests in isolation_groups.items():
            if not tests:
                continue
                
            total_duration = sum(char.estimated_duration_ms for _, char in tests)
            total_memory = sum(self._estimate_memory_usage(char) for _, char in tests)
            
            group_stats[level.value] = {
                "test_count": len(tests),
                "total_duration_ms": total_duration,
                "total_memory_mb": total_memory,
                "avg_duration_ms": total_duration / len(tests) if tests else 0
            }
        
        # Allocate workers based on workload
        total_duration = sum(stats["total_duration_ms"] for stats in group_stats.values())
        worker_allocation = {}
        
        remaining_workers = max_workers
        for level_name, stats in group_stats.items():
            if remaining_workers <= 0:
                break
                
            # Allocate based on duration proportion
            duration_ratio = stats["total_duration_ms"] / total_duration if total_duration > 0 else 0
            allocated_workers = max(1, int(remaining_workers * duration_ratio))
            allocated_workers = min(allocated_workers, stats["test_count"])
            
            worker_allocation[level_name] = {
                "workers": allocated_workers,
                "tests_per_worker": stats["test_count"] / allocated_workers if allocated_workers > 0 else 0,
                "estimated_duration_per_worker": stats["total_duration_ms"] / allocated_workers if allocated_workers > 0 else 0
            }
            
            remaining_workers -= allocated_workers
        
        return worker_allocation
    
    def _create_execution_phases(
        self,
        isolation_groups: Dict[IsolationLevel, List[Tuple[str, TestCharacteristics]]]
    ) -> List[Dict[str, Any]]:
        """Create execution phases for optimal parallel execution."""
        
        phases = []
        
        # Phase 1: Shared database tests (fastest, can run in parallel)
        if isolation_groups[IsolationLevel.SHARED]:
            phases.append({
                "phase": 1,
                "name": "Shared Database Tests",
                "isolation_level": "shared",
                "tests": [name for name, _ in isolation_groups[IsolationLevel.SHARED]],
                "parallel_execution": True,
                "estimated_duration_ms": max(
                    char.estimated_duration_ms 
                    for _, char in isolation_groups[IsolationLevel.SHARED]
                ) if isolation_groups[IsolationLevel.SHARED] else 0
            })
        
        # Phase 2: Per-worker database tests
        if isolation_groups[IsolationLevel.PER_WORKER]:
            phases.append({
                "phase": 2,
                "name": "Worker Isolated Tests",
                "isolation_level": "per_worker",
                "tests": [name for name, _ in isolation_groups[IsolationLevel.PER_WORKER]],
                "parallel_execution": True,
                "estimated_duration_ms": sum(
                    char.estimated_duration_ms 
                    for _, char in isolation_groups[IsolationLevel.PER_WORKER]
                ) // 4  # Assuming 4 workers on average
            })
        
        # Phase 3: Per-test isolation (slower, but still parallel)
        if isolation_groups[IsolationLevel.PER_TEST]:
            phases.append({
                "phase": 3,
                "name": "Test Isolated Tests",
                "isolation_level": "per_test",
                "tests": [name for name, _ in isolation_groups[IsolationLevel.PER_TEST]],
                "parallel_execution": True,
                "estimated_duration_ms": sum(
                    char.estimated_duration_ms 
                    for _, char in isolation_groups[IsolationLevel.PER_TEST]
                ) // 2  # Assuming 2 workers due to higher overhead
            })
        
        # Phase 4: Per-class isolation
        if isolation_groups[IsolationLevel.PER_CLASS]:
            phases.append({
                "phase": 4,
                "name": "Class Isolated Tests",
                "isolation_level": "per_class", 
                "tests": [name for name, _ in isolation_groups[IsolationLevel.PER_CLASS]],
                "parallel_execution": True,
                "estimated_duration_ms": sum(
                    char.estimated_duration_ms 
                    for _, char in isolation_groups[IsolationLevel.PER_CLASS]
                )
            })
        
        return phases
    
    def _predict_performance(
        self,
        isolation_groups: Dict[IsolationLevel, List[Tuple[str, TestCharacteristics]]],
        worker_allocation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict parallel execution performance."""
        
        # Sequential execution time
        sequential_duration = sum(
            char.estimated_duration_ms
            for group in isolation_groups.values()
            for _, char in group
        )
        
        # Parallel execution time (estimated)
        parallel_duration = 0
        for level, tests in isolation_groups.items():
            if not tests:
                continue
                
            level_name = level.value
            if level_name in worker_allocation:
                workers = worker_allocation[level_name]["workers"]
                total_duration = sum(char.estimated_duration_ms for _, char in tests)
                phase_duration = total_duration / workers if workers > 0 else total_duration
                parallel_duration = max(parallel_duration, phase_duration)
        
        speedup = sequential_duration / parallel_duration if parallel_duration > 0 else 1
        efficiency = speedup / len(worker_allocation) if worker_allocation else 1
        
        return {
            "sequential_duration_ms": sequential_duration,
            "parallel_duration_ms": parallel_duration,
            "estimated_speedup": speedup,
            "parallel_efficiency": efficiency,
            "time_savings_percent": ((sequential_duration - parallel_duration) / sequential_duration * 100) if sequential_duration > 0 else 0
        }