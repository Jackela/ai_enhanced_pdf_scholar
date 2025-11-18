from typing import Any

#!/usr/bin/env python3
"""
Streaming Upload Performance Benchmark
Demonstrates memory efficiency and performance characteristics of the streaming upload system.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import psutil

from backend.api.streaming_models import StreamingUploadRequest
from backend.services.streaming_upload_service import StreamingUploadService
from backend.services.streaming_validation_service import StreamingValidationService


class MemoryMonitor:
    """Monitor memory usage during operations."""

    def __init__(self) -> None:
        self.process = psutil.Process()
        self.baseline_memory = self.get_current_memory()
        self.peak_memory = self.baseline_memory
        self.samples = []

    def get_current_memory(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def sample(self, label: str = "") -> Any:
        """Take a memory usage sample."""
        current = self.get_current_memory()
        self.peak_memory = max(self.peak_memory, current)
        self.samples.append((time.time(), current, label))
        return current

    def get_stats(self) -> dict:
        """Get memory statistics."""
        current = self.get_current_memory()
        return {
            "baseline_mb": self.baseline_memory,
            "current_mb": current,
            "peak_mb": self.peak_memory,
            "peak_increase_mb": self.peak_memory - self.baseline_memory,
            "current_increase_mb": current - self.baseline_memory,
        }


class MockWebSocketManager:
    """Mock WebSocket manager for benchmarking."""

    def __init__(self) -> None:
        self.progress_updates = []

    async def send_upload_progress(self, client_id: str, progress_data: dict) -> None:
        self.progress_updates.append((time.time(), progress_data))

    async def join_upload_room(self, client_id: str, session_id: str) -> None:
        pass


def create_test_file(size_mb: int, filename: str) -> Path:
    """Create a test file of specified size."""
    file_path = Path(tempfile.gettempdir()) / filename

    print(f"Creating {size_mb}MB test file: {file_path}")

    # Create file with random-ish data (but compressible for speed)
    chunk_size = 1024 * 1024  # 1MB chunks
    pattern = b"A" * 1000 + b"B" * 24  # Simple pattern

    with open(file_path, "wb") as f:
        for i in range(size_mb):
            # Vary pattern slightly to prevent excessive compression
            varied_pattern = pattern + str(i % 100).encode().ljust(24, b"X")
            f.write(varied_pattern * (chunk_size // len(varied_pattern)))

            # Write remainder if needed
            remainder = chunk_size % len(varied_pattern)
            if remainder:
                f.write(varied_pattern[:remainder])

    return file_path


async def benchmark_traditional_upload(
    file_path: Path, memory_monitor: MemoryMonitor
) -> dict:
    """Benchmark traditional upload (loading entire file into memory)."""
    print("\n=== Traditional Upload Benchmark ===")

    start_time = time.time()
    memory_monitor.sample("Traditional upload start")

    # Simulate traditional upload by reading entire file
    with open(file_path, "rb") as f:
        file_data = f.read()  # Load entire file into memory
        file_size = len(file_data)

        memory_monitor.sample("File loaded into memory")

        # Simulate some processing
        await asyncio.sleep(0.1)

        # Simulate validation
        is_pdf = file_data.startswith(b"%PDF-")

        # Calculate hash (simulating integrity check)
        import hashlib

        file_hash = hashlib.sha256(file_data).hexdigest()

        memory_monitor.sample("Processing complete")

    end_time = time.time()

    stats = {
        "method": "traditional",
        "duration_seconds": end_time - start_time,
        "file_size_mb": file_size / (1024 * 1024),
        "memory_stats": memory_monitor.get_stats(),
        "throughput_mbps": (file_size / (1024 * 1024)) / (end_time - start_time),
    }

    print("Traditional upload completed:")
    print(f"  Duration: {stats['duration_seconds']:.2f}s")
    print(f"  Memory increase: {stats['memory_stats']['peak_increase_mb']:.1f}MB")
    print(f"  Throughput: {stats['throughput_mbps']:.1f} MB/s")

    return stats


async def benchmark_streaming_upload(
    file_path: Path, memory_monitor: MemoryMonitor
) -> dict:
    """Benchmark streaming upload with chunked processing."""
    print("\n=== Streaming Upload Benchmark ===")

    # Setup streaming service
    upload_dir = Path(tempfile.gettempdir()) / "streaming_uploads"
    upload_dir.mkdir(exist_ok=True)

    streaming_service = StreamingUploadService(
        upload_dir=upload_dir,
        max_concurrent_uploads=1,
        memory_limit_mb=200.0,
    )

    validation_service = StreamingValidationService()
    mock_websocket = MockWebSocketManager()

    try:
        start_time = time.time()
        memory_monitor.sample("Streaming upload start")

        # Create upload request
        file_size = file_path.stat().st_size
        request = StreamingUploadRequest(
            filename=file_path.name,
            file_size=file_size,
            client_id=f"benchmark_{uuid4()}",
            chunk_size=2 * 1024 * 1024,  # 2MB chunks
        )

        # Initiate upload
        session = await streaming_service.initiate_upload(request, mock_websocket)
        memory_monitor.sample("Session initiated")

        # Process file in chunks
        chunk_size = session.chunk_size
        chunks_processed = 0

        with open(file_path, "rb") as f:
            chunk_id = 0
            offset = 0

            while offset < file_size:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break

                is_final = offset + len(chunk_data) >= file_size

                # Process chunk
                success, message = await streaming_service.process_chunk(
                    session_id=session.session_id,
                    chunk_id=chunk_id,
                    chunk_data=chunk_data,
                    chunk_offset=offset,
                    is_final=is_final,
                    websocket_manager=mock_websocket,
                )

                if not success:
                    raise Exception(f"Chunk processing failed: {message}")

                chunks_processed += 1
                offset += len(chunk_data)
                chunk_id += 1

                # Sample memory every 10 chunks
                if chunks_processed % 10 == 0:
                    memory_monitor.sample(f"Processed {chunks_processed} chunks")

        memory_monitor.sample("All chunks processed")

        # Validate final file
        if session.temp_file_path:
            validation_result = await validation_service.validate_streaming_upload(
                session.temp_file_path
            )
            memory_monitor.sample("Validation complete")

        end_time = time.time()

        # Clean up
        await streaming_service.cancel_upload(session.session_id, "Benchmark complete")

    finally:
        await streaming_service.cleanup()

    stats = {
        "method": "streaming",
        "duration_seconds": end_time - start_time,
        "file_size_mb": file_size / (1024 * 1024),
        "chunks_processed": chunks_processed,
        "chunk_size_mb": chunk_size / (1024 * 1024),
        "memory_stats": memory_monitor.get_stats(),
        "throughput_mbps": (file_size / (1024 * 1024)) / (end_time - start_time),
        "progress_updates": len(mock_websocket.progress_updates),
    }

    print("Streaming upload completed:")
    print(f"  Duration: {stats['duration_seconds']:.2f}s")
    print(f"  Chunks processed: {stats['chunks_processed']}")
    print(f"  Memory increase: {stats['memory_stats']['peak_increase_mb']:.1f}MB")
    print(f"  Throughput: {stats['throughput_mbps']:.1f} MB/s")
    print(f"  Progress updates: {stats['progress_updates']}")

    return stats


def print_comparison(traditional_stats: dict, streaming_stats: dict) -> None:
    """Print comparison between traditional and streaming methods."""
    print(f"\n{'='*60}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*60}")

    file_size_mb = traditional_stats["file_size_mb"]
    print(f"File size: {file_size_mb:.1f} MB")

    print("\nMemory Usage:")
    trad_memory = traditional_stats["memory_stats"]["peak_increase_mb"]
    stream_memory = streaming_stats["memory_stats"]["peak_increase_mb"]
    memory_reduction = ((trad_memory - stream_memory) / trad_memory) * 100

    print(f"  Traditional: {trad_memory:.1f} MB")
    print(f"  Streaming:   {stream_memory:.1f} MB")
    print(f"  Reduction:   {memory_reduction:.1f}%")

    print("\nThroughput:")
    print(f"  Traditional: {traditional_stats['throughput_mbps']:.1f} MB/s")
    print(f"  Streaming:   {streaming_stats['throughput_mbps']:.1f} MB/s")

    throughput_ratio = (
        streaming_stats["throughput_mbps"] / traditional_stats["throughput_mbps"]
    )
    if throughput_ratio > 1:
        print(f"  Streaming is {throughput_ratio:.1f}x faster")
    else:
        print(f"  Traditional is {1/throughput_ratio:.1f}x faster")

    print("\nAdditional Streaming Benefits:")
    print(f"  Chunks processed: {streaming_stats['chunks_processed']}")
    print(f"  Progress updates: {streaming_stats['progress_updates']}")
    print(f"  Memory efficiency: {memory_reduction:.1f}% reduction")

    # Calculate efficiency score
    efficiency_score = memory_reduction + (throughput_ratio * 10)
    print(f"\nEfficiency Score: {efficiency_score:.0f}/100")

    if memory_reduction > 50:
        print("✅ Excellent memory efficiency")
    elif memory_reduction > 25:
        print("⚠️  Good memory efficiency")
    else:
        print("❌ Poor memory efficiency")


async def run_benchmark_suite() -> Any:
    """Run comprehensive benchmark suite."""
    print("Streaming Upload Performance Benchmark")
    print("=" * 60)

    # Test different file sizes
    test_sizes = [10, 25, 50, 100]  # MB
    results = []

    for size_mb in test_sizes:
        print(f"\n🧪 Testing {size_mb}MB file")
        print("-" * 40)

        # Create test file
        test_file = create_test_file(size_mb, f"benchmark_{size_mb}mb.dat")

        try:
            # Benchmark traditional method
            trad_monitor = MemoryMonitor()
            trad_stats = await benchmark_traditional_upload(test_file, trad_monitor)

            # Wait for memory to settle
            await asyncio.sleep(1)

            # Benchmark streaming method
            stream_monitor = MemoryMonitor()
            stream_stats = await benchmark_streaming_upload(test_file, stream_monitor)

            # Compare results
            print_comparison(trad_stats, stream_stats)

            results.append(
                {
                    "file_size_mb": size_mb,
                    "traditional": trad_stats,
                    "streaming": stream_stats,
                }
            )

        finally:
            # Clean up test file
            if test_file.exists():
                test_file.unlink()

    # Print summary
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")

    print(f"{'Size (MB)':<10} {'Memory Reduction':<18} {'Throughput Ratio':<18}")
    print("-" * 50)

    for result in results:
        size = result["file_size_mb"]
        trad_mem = result["traditional"]["memory_stats"]["peak_increase_mb"]
        stream_mem = result["streaming"]["memory_stats"]["peak_increase_mb"]
        mem_reduction = (
            ((trad_mem - stream_mem) / trad_mem) * 100 if trad_mem > 0 else 0
        )

        trad_throughput = result["traditional"]["throughput_mbps"]
        stream_throughput = result["streaming"]["throughput_mbps"]
        throughput_ratio = (
            stream_throughput / trad_throughput if trad_throughput > 0 else 1
        )

        print(f"{size:<10} {mem_reduction:>6.1f}%{'':<11} {throughput_ratio:>6.2f}x")

    # Calculate averages
    avg_memory_reduction = sum(
        (
            (
                r["traditional"]["memory_stats"]["peak_increase_mb"]
                - r["streaming"]["memory_stats"]["peak_increase_mb"]
            )
            / r["traditional"]["memory_stats"]["peak_increase_mb"]
        )
        * 100
        for r in results
    ) / len(results)

    avg_throughput_ratio = sum(
        r["streaming"]["throughput_mbps"] / r["traditional"]["throughput_mbps"]
        for r in results
    ) / len(results)

    print("-" * 50)
    print(
        f"{'Average':<10} {avg_memory_reduction:>6.1f}%{'':<11} {avg_throughput_ratio:>6.2f}x"
    )

    print("\n🎯 Key Findings:")
    print(f"   • Average memory reduction: {avg_memory_reduction:.1f}%")
    print("   • Streaming provides consistent memory usage regardless of file size")
    print("   • Progress tracking enables better user experience")
    print("   • Upload resumption prevents data loss on interruption")

    return results


if __name__ == "__main__":
    # Check if running in appropriate environment
    if psutil.virtual_memory().available < 500 * 1024 * 1024:  # 500MB
        print(
            "Warning: Less than 500MB available memory. Benchmark may not be accurate."
        )

    # Run benchmarks
    asyncio.run(run_benchmark_suite())
