#!/usr/bin/env python3
"""
API Documentation Synchronization Script

This script automatically synchronizes API documentation with the actual codebase,
ensuring that documentation stays current with code changes.

Usage:
    python scripts/api_docs_sync.py --check         # Check for inconsistencies
    python scripts/api_docs_sync.py --update        # Update documentation
    python scripts/api_docs_sync.py --validate      # Validate API endpoints
"""

import argparse
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
import yaml
from fastapi.openapi.utils import get_openapi


class APIDocumentationSync:
    """Synchronizes API documentation with actual implementation."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.api_base_url = "http://localhost:8000"
        self.docs_dir = self.project_root / "docs" / "api"
        self.backend_dir = self.project_root / "backend"

        # Documentation files to sync
        self.doc_files = {
            "api_reference": self.docs_dir / "complete-api-reference.md",
            "openapi_spec": self.docs_dir / "openapi.json",
            "sdk_docs": self.docs_dir / "sdk-documentation.md",
            "changelog": self.docs_dir / "api-changelog.md"
        }

        # Tracked changes
        self.changes = {
            "new_endpoints": [],
            "modified_endpoints": [],
            "deprecated_endpoints": [],
            "schema_changes": [],
            "breaking_changes": []
        }

        print(f"🔄 API Documentation Sync initialized")
        print(f"   Project: {self.project_root}")
        print(f"   API Base: {self.api_base_url}")
        print(f"   Docs Dir: {self.docs_dir}")

    def extract_api_endpoints(self) -> Dict[str, Any]:
        """Extract API endpoints from FastAPI application code."""
        endpoints = {}

        # Find all route files
        route_files = list((self.backend_dir / "api" / "routes").glob("*.py"))
        main_file = self.backend_dir / "api" / "main.py"
        if main_file.exists():
            route_files.append(main_file)

        for route_file in route_files:
            try:
                with open(route_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)

                    file_endpoints = self._parse_fastapi_routes(tree, route_file, content)
                    endpoints.update(file_endpoints)

            except Exception as e:
                print(f"⚠️  Error parsing {route_file}: {e}")

        return endpoints

    def _parse_fastapi_routes(self, tree: ast.AST, file_path: Path, content: str) -> Dict[str, Any]:
        """Parse FastAPI route definitions from AST."""
        endpoints = {}
        lines = content.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Look for FastAPI decorators
                for decorator in node.decorator_list:
                    endpoint_info = self._extract_endpoint_info(decorator, node, lines)
                    if endpoint_info:
                        endpoint_key = f"{endpoint_info['method']}:{endpoint_info['path']}"
                        endpoint_info.update({
                            'file': str(file_path.relative_to(self.project_root)),
                            'line_number': node.lineno,
                            'function_name': node.name,
                            'docstring': ast.get_docstring(node),
                            'parameters': self._extract_function_parameters(node),
                            'return_annotation': self._get_annotation_string(node.returns)
                        })
                        endpoints[endpoint_key] = endpoint_info

        return endpoints

    def _extract_endpoint_info(self, decorator: ast.AST, func_node: ast.FunctionDef, lines: List[str]) -> Optional[Dict[str, Any]]:
        """Extract endpoint information from FastAPI decorators."""
        if not isinstance(decorator, ast.Call):
            return None

        # Check for common FastAPI HTTP methods
        http_methods = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']

        method = None
        path = None

        # Handle router.get(), app.post(), etc.
        if isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr in http_methods:
                method = decorator.func.attr.upper()
        # Handle direct @get, @post decorators
        elif isinstance(decorator.func, ast.Name):
            if decorator.func.id in http_methods:
                method = decorator.func.id.upper()

        if not method:
            return None

        # Extract path from first argument
        if decorator.args and isinstance(decorator.args[0], ast.Str):
            path = decorator.args[0].s
        elif decorator.args and isinstance(decorator.args[0], ast.Constant):
            path = decorator.args[0].value

        if not path:
            return None

        # Extract additional metadata from decorator keywords
        metadata = {}
        for keyword in decorator.keywords:
            if keyword.arg == 'response_model':
                metadata['response_model'] = self._get_annotation_string(keyword.value)
            elif keyword.arg == 'status_code':
                if isinstance(keyword.value, ast.Constant):
                    metadata['status_code'] = keyword.value.value
            elif keyword.arg == 'tags':
                metadata['tags'] = self._extract_list_values(keyword.value)
            elif keyword.arg == 'summary':
                if isinstance(keyword.value, ast.Constant):
                    metadata['summary'] = keyword.value.value
            elif keyword.arg == 'description':
                if isinstance(keyword.value, ast.Constant):
                    metadata['description'] = keyword.value.value

        return {
            'method': method,
            'path': path,
            'metadata': metadata
        }

    def _extract_function_parameters(self, func_node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """Extract function parameter information."""
        parameters = []

        for arg in func_node.args.args:
            param_info = {
                'name': arg.arg,
                'annotation': self._get_annotation_string(arg.annotation),
                'default': None
            }
            parameters.append(param_info)

        # Handle defaults
        defaults = func_node.args.defaults
        if defaults:
            # Defaults apply to the last N parameters
            offset = len(parameters) - len(defaults)
            for i, default in enumerate(defaults):
                param_index = offset + i
                if param_index < len(parameters):
                    parameters[param_index]['default'] = self._get_default_value(default)

        return parameters

    def _get_annotation_string(self, annotation: Optional[ast.AST]) -> Optional[str]:
        """Convert AST annotation to string representation."""
        if not annotation:
            return None

        try:
            if isinstance(annotation, ast.Name):
                return annotation.id
            elif isinstance(annotation, ast.Constant):
                return str(annotation.value)
            elif isinstance(annotation, ast.Attribute):
                return f"{self._get_annotation_string(annotation.value)}.{annotation.attr}"
            elif isinstance(annotation, ast.Subscript):
                value = self._get_annotation_string(annotation.value)
                slice_val = self._get_annotation_string(annotation.slice)
                return f"{value}[{slice_val}]"
            else:
                return ast.unparse(annotation) if hasattr(ast, 'unparse') else str(annotation)
        except:
            return str(type(annotation).__name__)

    def _get_default_value(self, default: ast.AST) -> Any:
        """Extract default value from AST node."""
        if isinstance(default, ast.Constant):
            return default.value
        elif isinstance(default, ast.Name):
            return default.id
        elif isinstance(default, ast.Attribute):
            return f"{self._get_default_value(default.value)}.{default.attr}"
        else:
            return str(default)

    def _extract_list_values(self, node: ast.AST) -> List[Any]:
        """Extract values from a list AST node."""
        if isinstance(node, ast.List):
            return [self._get_default_value(item) for item in node.elts]
        return []

    def fetch_live_openapi_spec(self) -> Optional[Dict[str, Any]]:
        """Fetch OpenAPI specification from running server."""
        try:
            response = requests.get(f"{self.api_base_url}/api/openapi.json", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Failed to fetch OpenAPI spec: HTTP {response.status_code}")
                return None
        except requests.RequestException as e:
            print(f"⚠️  Cannot connect to API server: {e}")
            return None

    def compare_endpoints(self, code_endpoints: Dict[str, Any], live_spec: Optional[Dict[str, Any]]) -> None:
        """Compare endpoints from code analysis with live API specification."""
        if not live_spec:
            print("⚠️  Skipping live API comparison (server not available)")
            return

        # Extract endpoints from OpenAPI spec
        live_endpoints = {}
        if 'paths' in live_spec:
            for path, methods in live_spec['paths'].items():
                for method, spec in methods.items():
                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                        endpoint_key = f"{method.upper()}:{path}"
                        live_endpoints[endpoint_key] = {
                            'method': method.upper(),
                            'path': path,
                            'spec': spec
                        }

        # Find differences
        code_keys = set(code_endpoints.keys())
        live_keys = set(live_endpoints.keys())

        # New endpoints (in code but not in live spec)
        new_endpoints = code_keys - live_keys
        for endpoint_key in new_endpoints:
            self.changes['new_endpoints'].append({
                'endpoint': endpoint_key,
                'details': code_endpoints[endpoint_key]
            })

        # Deprecated endpoints (in live spec but not in code)
        deprecated_endpoints = live_keys - code_keys
        for endpoint_key in deprecated_endpoints:
            self.changes['deprecated_endpoints'].append({
                'endpoint': endpoint_key,
                'details': live_endpoints[endpoint_key]
            })

        # Modified endpoints (in both, but potentially different)
        common_endpoints = code_keys & live_keys
        for endpoint_key in common_endpoints:
            code_endpoint = code_endpoints[endpoint_key]
            live_endpoint = live_endpoints[endpoint_key]

            # Compare basic properties
            if self._endpoints_differ(code_endpoint, live_endpoint):
                self.changes['modified_endpoints'].append({
                    'endpoint': endpoint_key,
                    'code_version': code_endpoint,
                    'live_version': live_endpoint
                })

    def _endpoints_differ(self, code_endpoint: Dict[str, Any], live_endpoint: Dict[str, Any]) -> bool:
        """Check if code and live endpoints differ significantly."""
        # This is a simplified comparison - you might want to make it more sophisticated
        code_summary = code_endpoint.get('metadata', {}).get('summary', '')
        live_summary = live_endpoint.get('spec', {}).get('summary', '')

        code_description = code_endpoint.get('docstring', '')
        live_description = live_endpoint.get('spec', {}).get('description', '')

        return code_summary != live_summary or code_description != live_description

    def update_api_reference_doc(self, endpoints: Dict[str, Any]) -> None:
        """Update the API reference documentation file."""
        doc_file = self.doc_files['api_reference']

        if not doc_file.exists():
            print(f"⚠️  API reference file not found: {doc_file}")
            return

        # Read current documentation
        with open(doc_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Generate new endpoints section
        endpoints_md = self._generate_endpoints_markdown(endpoints)

        # Update the endpoints section
        # Look for a specific marker in the documentation
        start_marker = "<!-- AUTO-GENERATED ENDPOINTS START -->"
        end_marker = "<!-- AUTO-GENERATED ENDPOINTS END -->"

        if start_marker in content and end_marker in content:
            before = content.split(start_marker)[0]
            after = content.split(end_marker)[1]

            new_content = f"{before}{start_marker}\n{endpoints_md}\n{end_marker}{after}"

            # Write updated documentation
            with open(doc_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            print(f"✅ Updated API reference documentation: {doc_file.name}")
        else:
            print(f"⚠️  Auto-update markers not found in {doc_file.name}")

    def _generate_endpoints_markdown(self, endpoints: Dict[str, Any]) -> str:
        """Generate Markdown documentation for endpoints."""
        md_content = []
        md_content.append("## Auto-Generated API Endpoints\n")
        md_content.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        # Group endpoints by path prefix
        grouped_endpoints = {}
        for endpoint_key, endpoint in endpoints.items():
            path = endpoint['path']
            prefix = path.split('/')[1] if path.startswith('/') and len(path.split('/')) > 1 else 'root'

            if prefix not in grouped_endpoints:
                grouped_endpoints[prefix] = []
            grouped_endpoints[prefix].append((endpoint_key, endpoint))

        # Generate documentation for each group
        for prefix, group_endpoints in sorted(grouped_endpoints.items()):
            md_content.append(f"### {prefix.title()} Endpoints\n")

            for endpoint_key, endpoint in sorted(group_endpoints):
                method = endpoint['method']
                path = endpoint['path']
                summary = endpoint.get('metadata', {}).get('summary', '')
                docstring = endpoint.get('docstring', '')

                md_content.append(f"#### `{method} {path}`\n")
                if summary:
                    md_content.append(f"{summary}\n")
                if docstring:
                    md_content.append(f"{docstring}\n")

                # Parameters
                if endpoint.get('parameters'):
                    md_content.append("**Parameters:**")
                    for param in endpoint['parameters']:
                        param_type = param.get('annotation', 'Any')
                        default = param.get('default')
                        default_str = f" = {default}" if default is not None else ""
                        md_content.append(f"- `{param['name']}: {param_type}{default_str}`")
                    md_content.append("")

                # Response model
                response_model = endpoint.get('metadata', {}).get('response_model')
                if response_model:
                    md_content.append(f"**Response Model:** `{response_model}`\n")

                # File location
                md_content.append(f"**Source:** `{endpoint['file']}:{endpoint['line_number']}`\n")
                md_content.append("---\n")

        return "\n".join(md_content)

    def save_openapi_spec(self, spec: Dict[str, Any]) -> None:
        """Save OpenAPI specification to file."""
        spec_file = self.doc_files['openapi_spec']

        try:
            with open(spec_file, 'w', encoding='utf-8') as f:
                json.dump(spec, f, indent=2, sort_keys=True)

            print(f"✅ Saved OpenAPI specification: {spec_file.name}")
        except Exception as e:
            print(f"❌ Failed to save OpenAPI spec: {e}")

    def generate_changelog_entry(self) -> str:
        """Generate changelog entry based on detected changes."""
        if not any(self.changes.values()):
            return ""

        timestamp = datetime.now().strftime("%Y-%m-%d")
        changelog_entry = [f"## {timestamp}\n"]

        if self.changes['new_endpoints']:
            changelog_entry.append("### New Endpoints")
            for change in self.changes['new_endpoints']:
                endpoint = change['endpoint']
                changelog_entry.append(f"- `{endpoint}` - New endpoint added")
            changelog_entry.append("")

        if self.changes['deprecated_endpoints']:
            changelog_entry.append("### Deprecated Endpoints")
            for change in self.changes['deprecated_endpoints']:
                endpoint = change['endpoint']
                changelog_entry.append(f"- `{endpoint}` - Endpoint deprecated")
            changelog_entry.append("")

        if self.changes['modified_endpoints']:
            changelog_entry.append("### Modified Endpoints")
            for change in self.changes['modified_endpoints']:
                endpoint = change['endpoint']
                changelog_entry.append(f"- `{endpoint}` - Endpoint modified")
            changelog_entry.append("")

        return "\n".join(changelog_entry)

    def update_changelog(self, new_entry: str) -> None:
        """Update the API changelog file."""
        if not new_entry.strip():
            print("ℹ️  No changes detected - changelog not updated")
            return

        changelog_file = self.doc_files['changelog']

        # Read existing changelog or create new one
        existing_content = ""
        if changelog_file.exists():
            with open(changelog_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()

        # Prepend new entry
        header = "# API Changelog\n\nThis file tracks changes to the AI Enhanced PDF Scholar API.\n\n"
        new_content = header + new_entry + "\n" + existing_content

        # Write updated changelog
        with open(changelog_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ Updated API changelog: {changelog_file.name}")

    def check_inconsistencies(self) -> List[str]:
        """Check for inconsistencies between code and documentation."""
        issues = []

        # Check if documentation files exist
        for doc_name, doc_path in self.doc_files.items():
            if not doc_path.exists():
                issues.append(f"Missing documentation file: {doc_path}")

        # Extract endpoints from code
        code_endpoints = self.extract_api_endpoints()

        # Check against live API
        live_spec = self.fetch_live_openapi_spec()
        if live_spec:
            self.compare_endpoints(code_endpoints, live_spec)

            # Report issues from comparison
            if self.changes['new_endpoints']:
                issues.append(f"Found {len(self.changes['new_endpoints'])} new endpoints not in live API")

            if self.changes['deprecated_endpoints']:
                issues.append(f"Found {len(self.changes['deprecated_endpoints'])} deprecated endpoints")

            if self.changes['modified_endpoints']:
                issues.append(f"Found {len(self.changes['modified_endpoints'])} modified endpoints")

        return issues

    def sync_documentation(self) -> None:
        """Perform complete documentation synchronization."""
        print("🔄 Starting API documentation synchronization...")

        # Extract endpoints from code
        print("📋 Extracting API endpoints from code...")
        code_endpoints = self.extract_api_endpoints()
        print(f"   Found {len(code_endpoints)} endpoints in code")

        # Fetch live API specification
        print("🌐 Fetching live API specification...")
        live_spec = self.fetch_live_openapi_spec()
        if live_spec:
            print("   Successfully fetched live API spec")
            self.save_openapi_spec(live_spec)

        # Compare and detect changes
        print("🔍 Comparing code and live API...")
        self.compare_endpoints(code_endpoints, live_spec)

        # Update documentation
        print("📝 Updating documentation files...")
        self.update_api_reference_doc(code_endpoints)

        # Generate changelog entry
        changelog_entry = self.generate_changelog_entry()
        if changelog_entry:
            self.update_changelog(changelog_entry)

        # Summary
        print("\n📊 Synchronization Summary:")
        print(f"   • Endpoints in code: {len(code_endpoints)}")
        if live_spec:
            live_endpoint_count = sum(len(methods) for methods in live_spec.get('paths', {}).values())
            print(f"   • Endpoints in live API: {live_endpoint_count}")
        print(f"   • New endpoints: {len(self.changes['new_endpoints'])}")
        print(f"   • Modified endpoints: {len(self.changes['modified_endpoints'])}")
        print(f"   • Deprecated endpoints: {len(self.changes['deprecated_endpoints'])}")

        print("✅ API documentation synchronization completed!")

    def validate_endpoints(self) -> bool:
        """Validate that all documented endpoints are accessible."""
        print("🔍 Validating API endpoints...")

        issues = []

        # Extract endpoints from documentation
        code_endpoints = self.extract_api_endpoints()

        # Test each endpoint
        for endpoint_key, endpoint in code_endpoints.items():
            method = endpoint['method']
            path = endpoint['path']

            try:
                # For GET requests, try to access them
                if method == 'GET':
                    url = f"{self.api_base_url}{path}"
                    response = requests.head(url, timeout=5)
                    if response.status_code >= 500:
                        issues.append(f"Endpoint {endpoint_key} returned server error: {response.status_code}")

            except requests.RequestException as e:
                issues.append(f"Endpoint {endpoint_key} is not accessible: {e}")

        if issues:
            print("❌ Validation issues found:")
            for issue in issues:
                print(f"   • {issue}")
            return False
        else:
            print(f"✅ All {len(code_endpoints)} endpoints validated successfully!")
            return True


def main():
    """Main entry point for API documentation synchronization."""
    parser = argparse.ArgumentParser(description="API Documentation Synchronization")
    parser.add_argument("--check", action="store_true", help="Check for inconsistencies")
    parser.add_argument("--update", action="store_true", help="Update documentation")
    parser.add_argument("--validate", action="store_true", help="Validate API endpoints")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    args = parser.parse_args()

    # Initialize synchronizer
    project_root = Path(args.project_root).resolve()
    sync_tool = APIDocumentationSync(project_root)

    try:
        if args.check:
            issues = sync_tool.check_inconsistencies()
            if issues:
                print("❌ Inconsistencies found:")
                for issue in issues:
                    print(f"   • {issue}")
                sys.exit(1)
            else:
                print("✅ No inconsistencies found!")

        elif args.validate:
            valid = sync_tool.validate_endpoints()
            sys.exit(0 if valid else 1)

        elif args.update:
            sync_tool.sync_documentation()

        else:
            # Default: run full sync
            sync_tool.sync_documentation()

    except KeyboardInterrupt:
        print("\n⚠️  Synchronization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Synchronization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()