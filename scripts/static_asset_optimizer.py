#!/usr/bin/env python3
"""
Static Asset Optimizer
Intelligent optimization for images, CSS, and JavaScript assets.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import aiofiles
from PIL import Image

# Asset optimization libraries
try:
    import cssmin
    import jsmin
    from htmlmin import minify as html_minify
except ImportError:
    cssmin = None
    jsmin = None
    html_minify = None

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Classes
# ============================================================================

@dataclass
class OptimizationConfig:
    """Configuration for asset optimization."""
    # Image optimization
    enable_image_optimization: bool = True
    image_quality: int = 85  # JPEG quality (0-100)
    image_formats: list[str] = field(default_factory=lambda: ["webp", "avif", "original"])
    max_image_width: int = 1920
    max_image_height: int = 1080

    # CSS optimization
    enable_css_minification: bool = True
    enable_css_combining: bool = True

    # JavaScript optimization
    enable_js_minification: bool = True
    enable_js_combining: bool = True

    # HTML optimization
    enable_html_minification: bool = True

    # Caching and versioning
    enable_asset_versioning: bool = True
    enable_cache_busting: bool = True

    # Output settings
    output_directory: str = "optimized"
    preserve_originals: bool = True

    # Performance settings
    max_concurrent_operations: int = 4
    optimization_timeout_seconds: int = 30

    # CDN settings
    cdn_base_url: str | None = None
    enable_cdn_upload: bool = False


@dataclass
class AssetInfo:
    """Information about an asset file."""
    file_path: Path
    original_size: int
    optimized_size: int = 0
    mime_type: str = ""
    optimization_ratio: float = 0.0
    processing_time_ms: float = 0.0

    # Versions and formats
    versions: dict[str, Path] = field(default_factory=dict)
    hash_original: str = ""
    hash_optimized: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_optimized: datetime | None = None
    optimization_count: int = 0

    def calculate_optimization_ratio(self):
        """Calculate optimization ratio."""
        if self.original_size > 0:
            self.optimization_ratio = (
                (self.original_size - self.optimized_size) / self.original_size * 100
            )

    def get_best_version(self) -> tuple[str, Path]:
        """Get the best optimized version."""
        if not self.versions:
            return "original", self.file_path

        # Prefer modern formats
        format_priority = ["avif", "webp", "original"]

        for format_name in format_priority:
            if format_name in self.versions:
                return format_name, self.versions[format_name]

        # Fallback to first available version
        format_name = next(iter(self.versions))
        return format_name, self.versions[format_name]


@dataclass
class OptimizationStatistics:
    """Statistics for optimization operations."""
    total_files: int = 0
    optimized_files: int = 0
    failed_files: int = 0

    # Size statistics
    original_total_size: int = 0
    optimized_total_size: int = 0
    bytes_saved: int = 0

    # Performance statistics
    total_processing_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0

    # File type statistics
    files_by_type: dict[str, int] = field(default_factory=dict)
    optimization_by_type: dict[str, dict[str, Any]] = field(default_factory=dict)

    def calculate_totals(self):
        """Calculate total statistics."""
        if self.original_total_size > 0:
            self.bytes_saved = self.original_total_size - self.optimized_total_size

        if self.optimized_files > 0:
            self.avg_processing_time_ms = self.total_processing_time_ms / self.optimized_files

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        self.calculate_totals()

        return {
            "files": {
                "total": self.total_files,
                "optimized": self.optimized_files,
                "failed": self.failed_files,
                "success_rate": (self.optimized_files / self.total_files * 100) if self.total_files > 0 else 0
            },
            "size_reduction": {
                "original_mb": round(self.original_total_size / (1024 * 1024), 2),
                "optimized_mb": round(self.optimized_total_size / (1024 * 1024), 2),
                "saved_mb": round(self.bytes_saved / (1024 * 1024), 2),
                "reduction_percent": round((self.bytes_saved / self.original_total_size * 100) if self.original_total_size > 0 else 0, 2)
            },
            "performance": {
                "total_time_seconds": round(self.total_processing_time_ms / 1000, 2),
                "avg_time_ms": round(self.avg_processing_time_ms, 2)
            },
            "by_type": self.files_by_type
        }


# ============================================================================
# Asset Optimizers
# ============================================================================

class ImageOptimizer:
    """Optimizer for image assets."""

    def __init__(self, config: OptimizationConfig):
        """Initialize image optimizer."""
        self.config = config

        # Supported formats
        self.input_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        self.output_formats = {
            'webp': 'WEBP',
            'avif': 'AVIF',
            'jpeg': 'JPEG',
            'png': 'PNG'
        }

    async def optimize_image(self, input_path: Path, output_dir: Path) -> AssetInfo:
        """Optimize a single image."""
        start_time = time.time()

        try:
            # Get original file info
            original_size = input_path.stat().st_size
            mime_type = mimetypes.guess_type(str(input_path))[0] or 'application/octet-stream'

            asset_info = AssetInfo(
                file_path=input_path,
                original_size=original_size,
                mime_type=mime_type,
                hash_original=await self._calculate_file_hash(input_path)
            )

            # Open and process image
            with Image.open(input_path) as img:
                # Convert RGBA to RGB for JPEG
                if img.mode == 'RGBA' and 'jpeg' in self.config.image_formats:
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    img = background

                # Resize if needed
                if (img.width > self.config.max_image_width or
                    img.height > self.config.max_image_height):

                    img.thumbnail(
                        (self.config.max_image_width, self.config.max_image_height),
                        Image.Resampling.LANCZOS
                    )

                # Generate optimized versions
                total_optimized_size = 0

                for format_name in self.config.image_formats:
                    if format_name == 'original':
                        continue

                    output_path = self._get_output_path(input_path, output_dir, format_name)

                    try:
                        # Save in specified format
                        if format_name == 'webp':
                            img.save(
                                output_path,
                                'WEBP',
                                quality=self.config.image_quality,
                                optimize=True
                            )
                        elif format_name == 'avif':
                            img.save(
                                output_path,
                                'AVIF',
                                quality=self.config.image_quality,
                                optimize=True
                            )
                        elif format_name == 'jpeg':
                            img.save(
                                output_path,
                                'JPEG',
                                quality=self.config.image_quality,
                                optimize=True,
                                progressive=True
                            )
                        elif format_name == 'png':
                            img.save(
                                output_path,
                                'PNG',
                                optimize=True
                            )

                        # Record version
                        if output_path.exists():
                            version_size = output_path.stat().st_size
                            asset_info.versions[format_name] = output_path
                            total_optimized_size += version_size

                    except Exception as e:
                        logger.error(f"Error saving {format_name} version of {input_path}: {e}")

                # Always include original if requested
                if 'original' in self.config.image_formats:
                    original_output = self._get_output_path(input_path, output_dir, 'original')

                    # Copy original if preserving structure
                    if not original_output.exists():
                        import shutil
                        shutil.copy2(input_path, original_output)

                    asset_info.versions['original'] = original_output
                    total_optimized_size += original_size

                # Use smallest version for size calculation
                if asset_info.versions:
                    smallest_size = min(
                        path.stat().st_size for path in asset_info.versions.values()
                    )
                    asset_info.optimized_size = smallest_size
                else:
                    asset_info.optimized_size = original_size

                asset_info.calculate_optimization_ratio()
                asset_info.processing_time_ms = (time.time() - start_time) * 1000
                asset_info.last_optimized = datetime.utcnow()
                asset_info.optimization_count += 1

                return asset_info

        except Exception as e:
            logger.error(f"Error optimizing image {input_path}: {e}")
            asset_info = AssetInfo(
                file_path=input_path,
                original_size=input_path.stat().st_size,
                optimized_size=input_path.stat().st_size,
                processing_time_ms=(time.time() - start_time) * 1000
            )
            return asset_info

    def _get_output_path(self, input_path: Path, output_dir: Path, format_name: str) -> Path:
        """Get output path for optimized image."""
        if format_name == 'original':
            suffix = input_path.suffix
        else:
            suffix = f'.{format_name}'

        filename = f"{input_path.stem}{suffix}"
        return output_dir / input_path.parent.relative_to(input_path.parent.parent) / filename

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception:
            return ""


class CSSOptimizer:
    """Optimizer for CSS assets."""

    def __init__(self, config: OptimizationConfig):
        """Initialize CSS optimizer."""
        self.config = config

    async def optimize_css(self, input_path: Path, output_dir: Path) -> AssetInfo:
        """Optimize a CSS file."""
        start_time = time.time()

        try:
            # Read CSS content
            async with aiofiles.open(input_path, encoding='utf-8') as f:
                css_content = await f.read()

            original_size = len(css_content.encode('utf-8'))

            # Minify CSS if library is available
            if cssmin and self.config.enable_css_minification:
                optimized_content = cssmin.cssmin(css_content)
            else:
                # Basic optimization without external library
                optimized_content = self._basic_css_optimization(css_content)

            optimized_size = len(optimized_content.encode('utf-8'))

            # Write optimized CSS
            output_path = self._get_css_output_path(input_path, output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(optimized_content)

            # Create asset info
            asset_info = AssetInfo(
                file_path=input_path,
                original_size=original_size,
                optimized_size=optimized_size,
                mime_type='text/css',
                processing_time_ms=(time.time() - start_time) * 1000
            )

            asset_info.versions['minified'] = output_path
            asset_info.calculate_optimization_ratio()
            asset_info.last_optimized = datetime.utcnow()
            asset_info.optimization_count += 1

            return asset_info

        except Exception as e:
            logger.error(f"Error optimizing CSS {input_path}: {e}")
            return AssetInfo(
                file_path=input_path,
                original_size=input_path.stat().st_size,
                optimized_size=input_path.stat().st_size,
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def _basic_css_optimization(self, css_content: str) -> str:
        """Basic CSS optimization without external libraries."""
        # Remove comments
        import re
        css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)

        # Remove unnecessary whitespace
        css_content = re.sub(r'\s+', ' ', css_content)
        css_content = re.sub(r';\s*}', '}', css_content)
        css_content = re.sub(r'{\s*', '{', css_content)
        css_content = re.sub(r'}\s*', '}', css_content)
        css_content = re.sub(r';\s*', ';', css_content)

        return css_content.strip()

    def _get_css_output_path(self, input_path: Path, output_dir: Path) -> Path:
        """Get output path for optimized CSS."""
        filename = f"{input_path.stem}.min{input_path.suffix}"
        return output_dir / input_path.parent.relative_to(input_path.parent.parent) / filename


class JavaScriptOptimizer:
    """Optimizer for JavaScript assets."""

    def __init__(self, config: OptimizationConfig):
        """Initialize JavaScript optimizer."""
        self.config = config

    async def optimize_js(self, input_path: Path, output_dir: Path) -> AssetInfo:
        """Optimize a JavaScript file."""
        start_time = time.time()

        try:
            # Read JavaScript content
            async with aiofiles.open(input_path, encoding='utf-8') as f:
                js_content = await f.read()

            original_size = len(js_content.encode('utf-8'))

            # Minify JavaScript if library is available
            if jsmin and self.config.enable_js_minification:
                optimized_content = jsmin.jsmin(js_content)
            else:
                # Basic optimization without external library
                optimized_content = self._basic_js_optimization(js_content)

            optimized_size = len(optimized_content.encode('utf-8'))

            # Write optimized JavaScript
            output_path = self._get_js_output_path(input_path, output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(optimized_content)

            # Create asset info
            asset_info = AssetInfo(
                file_path=input_path,
                original_size=original_size,
                optimized_size=optimized_size,
                mime_type='text/javascript',
                processing_time_ms=(time.time() - start_time) * 1000
            )

            asset_info.versions['minified'] = output_path
            asset_info.calculate_optimization_ratio()
            asset_info.last_optimized = datetime.utcnow()
            asset_info.optimization_count += 1

            return asset_info

        except Exception as e:
            logger.error(f"Error optimizing JavaScript {input_path}: {e}")
            return AssetInfo(
                file_path=input_path,
                original_size=input_path.stat().st_size,
                optimized_size=input_path.stat().st_size,
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def _basic_js_optimization(self, js_content: str) -> str:
        """Basic JavaScript optimization without external libraries."""
        # Remove single-line comments (but preserve URLs and regexes)
        import re
        js_content = re.sub(r'//[^\r\n]*', '', js_content)

        # Remove multi-line comments
        js_content = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)

        # Remove unnecessary whitespace
        js_content = re.sub(r'\s+', ' ', js_content)
        js_content = re.sub(r'{\s*', '{', js_content)
        js_content = re.sub(r'}\s*', '}', js_content)
        js_content = re.sub(r';\s*', ';', js_content)

        return js_content.strip()

    def _get_js_output_path(self, input_path: Path, output_dir: Path) -> Path:
        """Get output path for optimized JavaScript."""
        filename = f"{input_path.stem}.min{input_path.suffix}"
        return output_dir / input_path.parent.relative_to(input_path.parent.parent) / filename


# ============================================================================
# Static Asset Optimizer
# ============================================================================

class StaticAssetOptimizer:
    """
    Comprehensive static asset optimizer for images, CSS, and JavaScript.
    """

    def __init__(self, config: OptimizationConfig):
        """Initialize static asset optimizer."""
        self.config = config

        # Initialize specific optimizers
        self.image_optimizer = ImageOptimizer(config)
        self.css_optimizer = CSSOptimizer(config)
        self.js_optimizer = JavaScriptOptimizer(config)

        # Statistics
        self.stats = OptimizationStatistics()

        # Asset tracking
        self.optimized_assets: dict[str, AssetInfo] = {}

        # Semaphore for concurrent operations
        self._semaphore = asyncio.Semaphore(config.max_concurrent_operations)

        logger.info("Static Asset Optimizer initialized")

    async def optimize_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path] | None = None
    ) -> OptimizationStatistics:
        """Optimize all assets in a directory."""
        input_path = Path(input_dir)
        output_path = Path(output_dir) if output_dir else input_path / self.config.output_directory

        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_path}")

        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting asset optimization: {input_path} -> {output_path}")

        # Find all assets
        assets_to_optimize = await self._find_assets(input_path)

        # Reset statistics
        self.stats = OptimizationStatistics()
        self.stats.total_files = len(assets_to_optimize)

        # Process assets concurrently
        tasks = []
        for asset_path in assets_to_optimize:
            task = asyncio.create_task(
                self._optimize_single_asset(asset_path, input_path, output_path)
            )
            tasks.append(task)

        # Wait for all optimizations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Optimization error: {result}")
                self.stats.failed_files += 1
            elif isinstance(result, AssetInfo):
                self.stats.optimized_files += 1
                self.stats.original_total_size += result.original_size
                self.stats.optimized_total_size += result.optimized_size
                self.stats.total_processing_time_ms += result.processing_time_ms

                # Track by file type
                file_ext = result.file_path.suffix.lower()
                self.stats.files_by_type[file_ext] = self.stats.files_by_type.get(file_ext, 0) + 1

        self.stats.calculate_totals()

        # Generate optimization manifest
        await self._generate_manifest(output_path)

        logger.info(f"Asset optimization completed: {self.stats.optimized_files}/{self.stats.total_files} files")

        return self.stats

    async def _find_assets(self, input_dir: Path) -> list[Path]:
        """Find all assets to optimize."""
        assets = []

        # Supported file extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        css_extensions = {'.css'}
        js_extensions = {'.js'}

        all_extensions = image_extensions | css_extensions | js_extensions

        # Walk through directory
        for file_path in input_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in all_extensions:
                assets.append(file_path)

        return assets

    async def _optimize_single_asset(
        self,
        asset_path: Path,
        input_dir: Path,
        output_dir: Path
    ) -> AssetInfo | None:
        """Optimize a single asset."""
        async with self._semaphore:
            try:
                file_ext = asset_path.suffix.lower()

                # Determine optimizer based on file type
                if file_ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}:
                    if self.config.enable_image_optimization:
                        asset_info = await self.image_optimizer.optimize_image(asset_path, output_dir)
                    else:
                        return None

                elif file_ext == '.css':
                    if self.config.enable_css_minification:
                        asset_info = await self.css_optimizer.optimize_css(asset_path, output_dir)
                    else:
                        return None

                elif file_ext == '.js':
                    if self.config.enable_js_minification:
                        asset_info = await self.js_optimizer.optimize_js(asset_path, output_dir)
                    else:
                        return None

                else:
                    return None

                # Store asset info
                self.optimized_assets[str(asset_path)] = asset_info

                logger.debug(
                    f"Optimized {asset_path.name}: "
                    f"{asset_info.original_size} -> {asset_info.optimized_size} bytes "
                    f"({asset_info.optimization_ratio:.1f}% reduction)"
                )

                return asset_info

            except Exception as e:
                logger.error(f"Error optimizing {asset_path}: {e}")
                return None

    async def _generate_manifest(self, output_dir: Path):
        """Generate optimization manifest."""
        manifest = {
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": self.stats.get_summary(),
            "assets": {}
        }

        # Add asset information
        for asset_path_str, asset_info in self.optimized_assets.items():
            asset_path = Path(asset_path_str)

            # Get relative path for manifest
            try:
                relative_path = str(asset_path.relative_to(output_dir.parent))
            except ValueError:
                relative_path = str(asset_path)

            manifest["assets"][relative_path] = {
                "original_size": asset_info.original_size,
                "optimized_size": asset_info.optimized_size,
                "optimization_ratio": round(asset_info.optimization_ratio, 2),
                "processing_time_ms": round(asset_info.processing_time_ms, 2),
                "versions": {
                    format_name: str(path)
                    for format_name, path in asset_info.versions.items()
                },
                "hash_original": asset_info.hash_original,
                "last_optimized": asset_info.last_optimized.isoformat() if asset_info.last_optimized else None
            }

        # Write manifest
        manifest_path = output_dir / "optimization_manifest.json"
        async with aiofiles.open(manifest_path, 'w') as f:
            await f.write(json.dumps(manifest, indent=2))

        logger.info(f"Generated optimization manifest: {manifest_path}")

    # ========================================================================
    # Asset Versioning and Cache Busting
    # ========================================================================

    async def generate_versioned_assets(self, output_dir: Path) -> dict[str, str]:
        """Generate versioned asset URLs for cache busting."""
        if not self.config.enable_asset_versioning:
            return {}

        versioned_urls = {}

        for asset_path_str, asset_info in self.optimized_assets.items():
            asset_path = Path(asset_path_str)

            # Get best optimized version
            format_name, optimized_path = asset_info.get_best_version()

            # Generate version hash
            try:
                async with aiofiles.open(optimized_path, 'rb') as f:
                    content = await f.read()
                    version_hash = hashlib.sha256(content).hexdigest()[:8]
            except Exception:
                version_hash = str(int(time.time()))

            # Create versioned URL
            if self.config.cdn_base_url:
                base_url = self.config.cdn_base_url.rstrip('/')
            else:
                base_url = ""

            relative_path = str(optimized_path.relative_to(output_dir))

            if self.config.enable_cache_busting:
                versioned_url = f"{base_url}/{relative_path}?v={version_hash}"
            else:
                # Add version to filename
                path_parts = relative_path.split('.')
                if len(path_parts) > 1:
                    versioned_filename = f"{'.'.join(path_parts[:-1])}.{version_hash}.{path_parts[-1]}"
                else:
                    versioned_filename = f"{relative_path}.{version_hash}"

                versioned_url = f"{base_url}/{versioned_filename}"

            # Use original path as key
            original_relative = str(asset_path.relative_to(output_dir.parent))
            versioned_urls[original_relative] = versioned_url

        # Write versioned URLs manifest
        versioned_manifest_path = output_dir / "versioned_assets.json"
        async with aiofiles.open(versioned_manifest_path, 'w') as f:
            await f.write(json.dumps(versioned_urls, indent=2))

        logger.info(f"Generated {len(versioned_urls)} versioned asset URLs")
        return versioned_urls

    # ========================================================================
    # CDN Upload Integration
    # ========================================================================

    async def upload_to_cdn(self, output_dir: Path) -> bool:
        """Upload optimized assets to CDN."""
        if not self.config.enable_cdn_upload or not self.config.cdn_base_url:
            return False

        try:
            upload_count = 0

            # Upload all optimized assets
            for asset_info in self.optimized_assets.values():
                for format_name, asset_path in asset_info.versions.items():
                    success = await self._upload_single_asset(asset_path, output_dir)
                    if success:
                        upload_count += 1

            logger.info(f"Uploaded {upload_count} assets to CDN")
            return upload_count > 0

        except Exception as e:
            logger.error(f"Error uploading to CDN: {e}")
            return False

    async def _upload_single_asset(self, asset_path: Path, output_dir: Path) -> bool:
        """Upload a single asset to CDN."""
        try:
            # This would integrate with actual CDN service (CloudFront, Cloudflare, etc.)
            # For now, just log the upload
            relative_path = str(asset_path.relative_to(output_dir))
            cdn_url = f"{self.config.cdn_base_url.rstrip('/')}/{relative_path}"

            logger.debug(f"Would upload {asset_path} to {cdn_url}")

            # Simulate upload delay
            await asyncio.sleep(0.1)

            return True

        except Exception as e:
            logger.error(f"Error uploading {asset_path}: {e}")
            return False

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_optimization_report(self) -> dict[str, Any]:
        """Get detailed optimization report."""
        return {
            "summary": self.stats.get_summary(),
            "assets": [
                {
                    "path": str(asset_info.file_path),
                    "original_size": asset_info.original_size,
                    "optimized_size": asset_info.optimized_size,
                    "optimization_ratio": round(asset_info.optimization_ratio, 2),
                    "processing_time_ms": round(asset_info.processing_time_ms, 2),
                    "formats_generated": list(asset_info.versions.keys())
                }
                for asset_info in self.optimized_assets.values()
            ]
        }


# ============================================================================
# Command Line Interface
# ============================================================================

async def main():
    """Main function for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Static Asset Optimizer")
    parser.add_argument("input_dir", help="Input directory containing assets")
    parser.add_argument("--output-dir", help="Output directory for optimized assets")
    parser.add_argument("--image-quality", type=int, default=85, help="Image quality (0-100)")
    parser.add_argument("--max-image-width", type=int, default=1920, help="Maximum image width")
    parser.add_argument("--max-image-height", type=int, default=1080, help="Maximum image height")
    parser.add_argument("--disable-css", action="store_true", help="Disable CSS optimization")
    parser.add_argument("--disable-js", action="store_true", help="Disable JavaScript optimization")
    parser.add_argument("--disable-images", action="store_true", help="Disable image optimization")
    parser.add_argument("--concurrent", type=int, default=4, help="Maximum concurrent operations")
    parser.add_argument("--cdn-url", help="CDN base URL for assets")
    parser.add_argument("--upload-cdn", action="store_true", help="Upload to CDN after optimization")
    parser.add_argument("--report", help="Generate optimization report (output file)")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Create configuration
        config = OptimizationConfig(
            enable_image_optimization=not args.disable_images,
            enable_css_minification=not args.disable_css,
            enable_js_minification=not args.disable_js,
            image_quality=args.image_quality,
            max_image_width=args.max_image_width,
            max_image_height=args.max_image_height,
            max_concurrent_operations=args.concurrent,
            cdn_base_url=args.cdn_url,
            enable_cdn_upload=args.upload_cdn
        )

        # Create optimizer
        optimizer = StaticAssetOptimizer(config)

        # Run optimization
        print(f"Optimizing assets in {args.input_dir}...")
        stats = await optimizer.optimize_directory(args.input_dir, args.output_dir)

        # Print results
        summary = stats.get_summary()
        print("\nOptimization Complete!")
        print(f"Files processed: {summary['files']['total']}")
        print(f"Files optimized: {summary['files']['optimized']}")
        print(f"Success rate: {summary['files']['success_rate']:.1f}%")
        print(f"Size reduction: {summary['size_reduction']['saved_mb']:.2f}MB ({summary['size_reduction']['reduction_percent']:.1f}%)")
        print(f"Processing time: {summary['performance']['total_time_seconds']:.1f}s")

        # Generate versioned assets
        if args.output_dir:
            output_path = Path(args.output_dir)
        else:
            output_path = Path(args.input_dir) / config.output_directory

        versioned_urls = await optimizer.generate_versioned_assets(output_path)
        print(f"Generated {len(versioned_urls)} versioned asset URLs")

        # Upload to CDN if requested
        if args.upload_cdn:
            success = await optimizer.upload_to_cdn(output_path)
            print(f"CDN upload: {'Success' if success else 'Failed'}")

        # Generate report if requested
        if args.report:
            report = optimizer.get_optimization_report()
            with open(args.report, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Optimization report saved to {args.report}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
