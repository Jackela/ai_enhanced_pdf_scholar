#!/usr/bin/env python3
"""
AI Enhanced PDF Scholar - Documentation Generator

This script automatically generates comprehensive documentation from the codebase,
including API documentation, type definitions, architecture diagrams, and more.

Usage:
    python scripts/docs_generator.py [--format html,pdf] [--output docs/generated]
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, Template


class DocumentationGenerator:
    """Comprehensive documentation generator for AI Enhanced PDF Scholar."""

    def __init__(self, project_root: Path, output_dir: Path):
        self.project_root = Path(project_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        template_dir = self.project_root / "docs" / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Documentation metadata
        self.metadata = {
            "project_name": "AI Enhanced PDF Scholar",
            "version": self._get_project_version(),
            "generated_at": datetime.now().isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }

        # Collected data
        self.api_endpoints: list[dict[str, Any]] = []
        self.database_models: list[dict[str, Any]] = []
        self.service_classes: list[dict[str, Any]] = []
        self.repository_classes: list[dict[str, Any]] = []
        self.type_definitions: list[dict[str, Any]] = []
        self.configuration_options: list[dict[str, Any]] = []
        self.test_coverage: dict[str, Any] = {}

        print("📚 Documentation Generator initialized")
        print(f"   Project: {self.metadata['project_name']}")
        print(f"   Version: {self.metadata['version']}")
        print(f"   Output: {self.output_dir}")

    def _get_project_version(self) -> str:
        """Extract project version from various sources."""
        try:
            # Try pyproject.toml first
            pyproject_path = self.project_root / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path) as f:
                    content = f.read()
                    version_match = re.search(
                        r'version\s*=\s*["\']([^"\']+)["\']', content
                    )
                    if version_match:
                        return version_match.group(1)

            # Try package.json (for frontend)
            package_json = self.project_root / "frontend" / "package.json"
            if package_json.exists():
                with open(package_json) as f:
                    data = json.load(f)
                    return data.get("version", "unknown")

            # Try git tags
            try:
                result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass

            return "2.1.0"  # Default version

        except Exception as e:
            print(f"⚠️  Warning: Could not determine project version: {e}")
            return "unknown"

    def generate_all_documentation(self, formats: list[str] = None) -> dict[str, Path]:
        """Generate all documentation components."""
        if formats is None:
            formats = ["html", "markdown"]

        generated_files = {}

        print("\n🔍 Analyzing codebase...")
        self._analyze_codebase()

        print("\n📊 Collecting metrics...")
        self._collect_metrics()

        print("\n📝 Generating documentation...")

        # Generate different documentation types
        documentation_types = [
            ("API Reference", self._generate_api_documentation),
            ("Architecture Overview", self._generate_architecture_documentation),
            ("Database Schema", self._generate_database_documentation),
            ("Service Documentation", self._generate_service_documentation),
            ("Type Definitions", self._generate_type_documentation),
            ("Configuration Guide", self._generate_configuration_documentation),
            ("Test Coverage Report", self._generate_test_coverage_documentation),
            ("Developer Guide", self._generate_developer_documentation),
            ("Changelog", self._generate_changelog),
            ("Index", self._generate_index_page),
        ]

        for doc_name, generator_func in documentation_types:
            print(f"  📄 {doc_name}")
            try:
                files = generator_func(formats)
                generated_files.update(files)
            except Exception as e:
                print(f"     ❌ Error: {e}")

        # Generate search index
        print("  🔍 Search Index")
        search_index = self._generate_search_index()
        generated_files["search_index"] = search_index

        print("\n✅ Documentation generation complete!")
        print(f"   Generated {len(generated_files)} files")
        return generated_files

    def _analyze_codebase(self):
        """Analyze the codebase to extract documentation information."""
        print("  🔍 Analyzing Python code...")
        self._analyze_python_files()

        print("  🔍 Analyzing TypeScript code...")
        self._analyze_typescript_files()

        print("  🔍 Analyzing configuration files...")
        self._analyze_configuration_files()

    def _analyze_python_files(self):
        """Analyze Python files for API endpoints, models, services, etc."""
        python_files = list(self.project_root.rglob("*.py"))

        for py_file in python_files:
            if any(
                exclude in str(py_file) for exclude in [".venv", "__pycache__", ".git"]
            ):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Parse AST
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue

                # Extract information based on file type/location
                file_path_str = str(py_file.relative_to(self.project_root))

                if "routes" in file_path_str:
                    self._extract_api_endpoints(tree, py_file, content)
                elif "models.py" in file_path_str:
                    self._extract_database_models(tree, py_file, content)
                elif "service" in file_path_str:
                    self._extract_service_classes(tree, py_file, content)
                elif "repositories" in file_path_str or "repository" in file_path_str:
                    self._extract_repository_classes(tree, py_file, content)

                # Always extract type definitions
                self._extract_type_definitions(tree, py_file, content)

            except Exception as e:
                print(f"     ⚠️  Warning: Error analyzing {py_file}: {e}")

    def _extract_api_endpoints(self, tree: ast.AST, file_path: Path, content: str):
        """Extract FastAPI endpoint information."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Look for FastAPI route decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        decorator_name = ""
                        if isinstance(decorator.func, ast.Attribute):
                            decorator_name = decorator.func.attr
                        elif isinstance(decorator.func, ast.Name):
                            decorator_name = decorator.func.id

                        if decorator_name in ["get", "post", "put", "delete", "patch"]:
                            endpoint_info = self._parse_fastapi_endpoint(
                                node, decorator, content, file_path
                            )
                            if endpoint_info:
                                self.api_endpoints.append(endpoint_info)

    def _parse_fastapi_endpoint(
        self,
        func_node: ast.FunctionDef,
        decorator: ast.Call,
        content: str,
        file_path: Path,
    ) -> dict[str, Any] | None:
        """Parse FastAPI endpoint details."""
        try:
            # Get HTTP method
            method = (
                decorator.func.attr
                if isinstance(decorator.func, ast.Attribute)
                else decorator.func.id
            )
            method = method.upper()

            # Get path
            path = ""
            if decorator.args:
                if isinstance(decorator.args[0], ast.Str):
                    path = decorator.args[0].s
                elif isinstance(decorator.args[0], ast.Constant):
                    path = decorator.args[0].value

            # Get function docstring
            docstring = ast.get_docstring(func_node)

            # Get function signature
            args = []
            for arg in func_node.args.args:
                arg_info = {"name": arg.arg}
                if arg.annotation:
                    arg_info["type"] = (
                        ast.unparse(arg.annotation)
                        if hasattr(ast, "unparse")
                        else str(arg.annotation)
                    )
                args.append(arg_info)

            # Parse response model from decorator keywords
            response_model = None
            for keyword in decorator.keywords:
                if keyword.arg == "response_model":
                    response_model = (
                        ast.unparse(keyword.value)
                        if hasattr(ast, "unparse")
                        else str(keyword.value)
                    )

            return {
                "method": method,
                "path": path,
                "function_name": func_node.name,
                "docstring": docstring,
                "parameters": args,
                "response_model": response_model,
                "file_path": str(file_path.relative_to(self.project_root)),
                "line_number": func_node.lineno,
            }
        except Exception as e:
            print(f"     ⚠️  Warning: Error parsing endpoint {func_node.name}: {e}")
            return None

    def _extract_database_models(self, tree: ast.AST, file_path: Path, content: str):
        """Extract SQLAlchemy model information."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a SQLAlchemy model
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    if base_name in ["Model", "Base"] or "Model" in base_name:
                        model_info = self._parse_sqlalchemy_model(
                            node, content, file_path
                        )
                        if model_info:
                            self.database_models.append(model_info)

    def _parse_sqlalchemy_model(
        self, class_node: ast.ClassDef, content: str, file_path: Path
    ) -> dict[str, Any] | None:
        """Parse SQLAlchemy model details."""
        try:
            model_info = {
                "name": class_node.name,
                "docstring": ast.get_docstring(class_node),
                "file_path": str(file_path.relative_to(self.project_root)),
                "line_number": class_node.lineno,
                "fields": [],
                "relationships": [],
                "table_name": None,
            }

            # Extract fields and relationships
            for node in class_node.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            field_name = target.name

                            # Check if it's a Column
                            if isinstance(node.value, ast.Call):
                                func_name = ""
                                if isinstance(node.value.func, ast.Name):
                                    func_name = node.value.func.id
                                elif isinstance(node.value.func, ast.Attribute):
                                    func_name = node.value.func.attr

                                if func_name == "Column":
                                    field_info = self._parse_sqlalchemy_column(
                                        field_name, node.value
                                    )
                                    model_info["fields"].append(field_info)
                                elif func_name in ["relationship", "relation"]:
                                    rel_info = self._parse_sqlalchemy_relationship(
                                        field_name, node.value
                                    )
                                    model_info["relationships"].append(rel_info)

            return model_info
        except Exception as e:
            print(f"     ⚠️  Warning: Error parsing model {class_node.name}: {e}")
            return None

    def _parse_sqlalchemy_column(
        self, field_name: str, call_node: ast.Call
    ) -> dict[str, Any]:
        """Parse SQLAlchemy Column definition."""
        field_info = {
            "name": field_name,
            "type": "Unknown",
            "nullable": True,
            "primary_key": False,
            "foreign_key": None,
            "default": None,
        }

        # Get column type (first argument)
        if call_node.args:
            arg = call_node.args[0]
            if isinstance(arg, ast.Name):
                field_info["type"] = arg.id
            elif isinstance(arg, ast.Attribute):
                field_info["type"] = arg.attr

        # Get column attributes from keywords
        for keyword in call_node.keywords:
            if keyword.arg == "nullable":
                if isinstance(keyword.value, ast.Constant):
                    field_info["nullable"] = keyword.value.value
            elif keyword.arg == "primary_key":
                if isinstance(keyword.value, ast.Constant):
                    field_info["primary_key"] = keyword.value.value
            elif keyword.arg == "default":
                field_info["default"] = (
                    ast.unparse(keyword.value)
                    if hasattr(ast, "unparse")
                    else str(keyword.value)
                )

        return field_info

    def _parse_sqlalchemy_relationship(
        self, rel_name: str, call_node: ast.Call
    ) -> dict[str, Any]:
        """Parse SQLAlchemy relationship definition."""
        rel_info = {
            "name": rel_name,
            "target_model": "Unknown",
            "back_populates": None,
            "cascade": None,
        }

        # Get target model (first argument)
        if call_node.args:
            arg = call_node.args[0]
            if isinstance(arg, ast.Str):
                rel_info["target_model"] = arg.s
            elif isinstance(arg, ast.Constant):
                rel_info["target_model"] = arg.value

        # Get relationship attributes
        for keyword in call_node.keywords:
            if keyword.arg == "back_populates":
                if isinstance(keyword.value, (ast.Str, ast.Constant)):
                    rel_info["back_populates"] = (
                        keyword.value.s
                        if hasattr(keyword.value, "s")
                        else keyword.value.value
                    )

        return rel_info

    def _extract_service_classes(self, tree: ast.AST, file_path: Path, content: str):
        """Extract service class information."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Service" in node.name:
                service_info = self._parse_service_class(node, content, file_path)
                if service_info:
                    self.service_classes.append(service_info)

    def _parse_service_class(
        self, class_node: ast.ClassDef, content: str, file_path: Path
    ) -> dict[str, Any] | None:
        """Parse service class details."""
        try:
            service_info = {
                "name": class_node.name,
                "docstring": ast.get_docstring(class_node),
                "file_path": str(file_path.relative_to(self.project_root)),
                "line_number": class_node.lineno,
                "methods": [],
                "dependencies": [],
            }

            # Extract methods
            for node in class_node.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    method_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "parameters": [
                            arg.arg for arg in node.args.args[1:]
                        ],  # Skip 'self'
                        "line_number": node.lineno,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    }
                    service_info["methods"].append(method_info)

            # Extract constructor dependencies
            for node in class_node.body:
                if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                    for arg in node.args.args[1:]:  # Skip 'self'
                        dep_info = {"name": arg.arg}
                        if arg.annotation:
                            dep_info["type"] = (
                                ast.unparse(arg.annotation)
                                if hasattr(ast, "unparse")
                                else str(arg.annotation)
                            )
                        service_info["dependencies"].append(dep_info)

            return service_info
        except Exception as e:
            print(f"     ⚠️  Warning: Error parsing service {class_node.name}: {e}")
            return None

    def _extract_repository_classes(self, tree: ast.AST, file_path: Path, content: str):
        """Extract repository class information."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                "Repository" in node.name or "Repo" in node.name
            ):
                repo_info = self._parse_repository_class(node, content, file_path)
                if repo_info:
                    self.repository_classes.append(repo_info)

    def _parse_repository_class(
        self, class_node: ast.ClassDef, content: str, file_path: Path
    ) -> dict[str, Any] | None:
        """Parse repository class details."""
        try:
            repo_info = {
                "name": class_node.name,
                "docstring": ast.get_docstring(class_node),
                "file_path": str(file_path.relative_to(self.project_root)),
                "line_number": class_node.lineno,
                "methods": [],
                "model_type": None,
            }

            # Extract methods
            for node in class_node.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    method_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "parameters": [
                            arg.arg for arg in node.args.args[1:]
                        ],  # Skip 'self'
                        "line_number": node.lineno,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    }
                    repo_info["methods"].append(method_info)

            return repo_info
        except Exception as e:
            print(f"     ⚠️  Warning: Error parsing repository {class_node.name}: {e}")
            return None

    def _extract_type_definitions(self, tree: ast.AST, file_path: Path, content: str):
        """Extract type definitions (TypedDict, Pydantic models, etc.)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for Pydantic BaseModel
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    if base_name in ["BaseModel", "TypedDict"] or "Model" in base_name:
                        type_info = self._parse_type_definition(
                            node, content, file_path
                        )
                        if type_info:
                            self.type_definitions.append(type_info)

    def _parse_type_definition(
        self, class_node: ast.ClassDef, content: str, file_path: Path
    ) -> dict[str, Any] | None:
        """Parse type definition details."""
        try:
            type_info = {
                "name": class_node.name,
                "docstring": ast.get_docstring(class_node),
                "file_path": str(file_path.relative_to(self.project_root)),
                "line_number": class_node.lineno,
                "fields": [],
            }

            # Extract fields with type annotations
            for node in class_node.body:
                if isinstance(node, ast.AnnAssign) and isinstance(
                    node.target, ast.Name
                ):
                    field_info = {
                        "name": node.target.id,
                        "type": (
                            ast.unparse(node.annotation)
                            if hasattr(ast, "unparse")
                            else str(node.annotation)
                        ),
                        "optional": False,
                        "default": None,
                    }

                    if node.value:
                        field_info["default"] = (
                            ast.unparse(node.value)
                            if hasattr(ast, "unparse")
                            else str(node.value)
                        )

                    # Check if Optional
                    type_str = field_info["type"]
                    if "Optional" in type_str or "Union" in type_str:
                        field_info["optional"] = True

                    type_info["fields"].append(field_info)

            return type_info
        except Exception as e:
            print(f"     ⚠️  Warning: Error parsing type {class_node.name}: {e}")
            return None

    def _analyze_typescript_files(self):
        """Analyze TypeScript files for frontend types and components."""
        ts_files = list(self.project_root.rglob("*.ts")) + list(
            self.project_root.rglob("*.tsx")
        )

        for ts_file in ts_files:
            if any(
                exclude in str(ts_file) for exclude in ["node_modules", ".git", "dist"]
            ):
                continue

            try:
                with open(ts_file, encoding="utf-8") as f:
                    content = f.read()

                # Extract interfaces and types
                self._extract_typescript_interfaces(content, ts_file)

            except Exception as e:
                print(f"     ⚠️  Warning: Error analyzing {ts_file}: {e}")

    def _extract_typescript_interfaces(self, content: str, file_path: Path):
        """Extract TypeScript interface definitions."""
        # Simple regex-based extraction for interfaces
        interface_pattern = (
            r"(?:export\s+)?interface\s+(\w+)\s*\{([^{}]*(?:\{[^}]*\}[^{}]*)*)\}"
        )
        type_pattern = r"(?:export\s+)?type\s+(\w+)\s*=\s*([^;\n]+);?"

        # Find interfaces
        for match in re.finditer(interface_pattern, content, re.MULTILINE | re.DOTALL):
            interface_name = match.group(1)
            interface_body = match.group(2)

            # Parse fields from interface body
            fields = []
            field_pattern = r"(\w+)\??:\s*([^;,\n]+)[;,\n]"
            for field_match in re.finditer(field_pattern, interface_body):
                field_name = field_match.group(1)
                field_type = field_match.group(2).strip()
                optional = "?" in field_match.group(0)

                fields.append(
                    {"name": field_name, "type": field_type, "optional": optional}
                )

            type_info = {
                "name": interface_name,
                "kind": "interface",
                "file_path": str(file_path.relative_to(self.project_root)),
                "fields": fields,
                "language": "TypeScript",
            }
            self.type_definitions.append(type_info)

        # Find type aliases
        for match in re.finditer(type_pattern, content, re.MULTILINE):
            type_name = match.group(1)
            type_definition = match.group(2).strip()

            type_info = {
                "name": type_name,
                "kind": "type",
                "file_path": str(file_path.relative_to(self.project_root)),
                "definition": type_definition,
                "language": "TypeScript",
            }
            self.type_definitions.append(type_info)

    def _analyze_configuration_files(self):
        """Analyze configuration files for settings and options."""
        config_files = [
            "config.py",
            "pyproject.toml",
            "docker-compose.yml",
            ".env.example",
            "vite.config.ts",
            "package.json",
        ]

        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                try:
                    self._parse_configuration_file(config_path)
                except Exception as e:
                    print(f"     ⚠️  Warning: Error analyzing {config_file}: {e}")

    def _parse_configuration_file(self, file_path: Path):
        """Parse configuration file for options."""
        file_name = file_path.name

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        config_info = {
            "file": file_name,
            "path": str(file_path.relative_to(self.project_root)),
            "options": [],
        }

        if file_name.endswith(".py"):
            # Parse Python configuration
            config_info["options"] = self._parse_python_config(content)
        elif file_name.endswith(".toml"):
            # Parse TOML configuration
            try:
                import toml

                parsed = toml.loads(content)
                config_info["options"] = self._flatten_config_dict(parsed)
            except ImportError:
                print("     📦 Install 'toml' package for TOML parsing")
        elif file_name.endswith((".yml", ".yaml")):
            # Parse YAML configuration
            try:
                parsed = yaml.safe_load(content)
                config_info["options"] = self._flatten_config_dict(parsed)
            except:
                pass
        elif file_name == ".env.example":
            # Parse environment variables
            config_info["options"] = self._parse_env_file(content)

        if config_info["options"]:
            self.configuration_options.append(config_info)

    def _parse_python_config(self, content: str) -> list[dict[str, Any]]:
        """Parse Python configuration variables."""
        options = []

        # Find variable assignments
        var_pattern = r"^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$"
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            var_name = match.group(1)
            var_value = match.group(2)

            options.append(
                {"name": var_name, "value": var_value, "type": "config_variable"}
            )

        return options

    def _parse_env_file(self, content: str) -> list[dict[str, Any]]:
        """Parse .env file format."""
        options = []

        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    options.append(
                        {
                            "name": key.strip(),
                            "value": value.strip(),
                            "type": "environment_variable",
                        }
                    )

        return options

    def _flatten_config_dict(
        self, config_dict: dict, prefix: str = ""
    ) -> list[dict[str, Any]]:
        """Flatten nested configuration dictionary."""
        options = []

        for key, value in config_dict.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                options.extend(self._flatten_config_dict(value, full_key))
            else:
                options.append(
                    {"name": full_key, "value": str(value), "type": "config_option"}
                )

        return options

    def _collect_metrics(self):
        """Collect various project metrics."""
        print("  📊 Collecting code metrics...")
        self._collect_code_metrics()

        print("  🧪 Collecting test coverage...")
        self._collect_test_coverage()

        print("  📈 Collecting performance metrics...")
        self._collect_performance_metrics()

    def _collect_code_metrics(self):
        """Collect basic code metrics."""
        python_files = list(self.project_root.rglob("*.py"))
        ts_files = list(self.project_root.rglob("*.ts")) + list(
            self.project_root.rglob("*.tsx")
        )

        total_lines = 0
        total_functions = 0
        total_classes = 0

        for py_file in python_files:
            if any(
                exclude in str(py_file) for exclude in [".venv", "__pycache__", ".git"]
            ):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    total_lines += len(content.split("\n"))

                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_functions += 1
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1
            except:
                continue

        self.metadata.update(
            {
                "code_metrics": {
                    "python_files": len(python_files),
                    "typescript_files": len(ts_files),
                    "total_lines": total_lines,
                    "total_functions": total_functions,
                    "total_classes": total_classes,
                    "api_endpoints": len(self.api_endpoints),
                    "database_models": len(self.database_models),
                    "service_classes": len(self.service_classes),
                    "repository_classes": len(self.repository_classes),
                    "type_definitions": len(self.type_definitions),
                }
            }
        )

    def _collect_test_coverage(self):
        """Collect test coverage information."""
        try:
            # Try to run coverage report
            result = subprocess.run(
                ["python", "-m", "coverage", "json", "--quiet"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                coverage_file = self.project_root / "coverage.json"
                if coverage_file.exists():
                    with open(coverage_file) as f:
                        self.test_coverage = json.load(f)
        except Exception as e:
            print(f"     ⚠️  Warning: Could not collect test coverage: {e}")
            self.test_coverage = {"totals": {"percent_covered": 0}}

    def _collect_performance_metrics(self):
        """Collect performance metrics from benchmark files."""
        performance_files = list(self.project_root.rglob("*performance*.json"))
        benchmark_files = list(self.project_root.rglob("*benchmark*.json"))

        performance_data = []

        for perf_file in performance_files + benchmark_files:
            try:
                with open(perf_file) as f:
                    data = json.load(f)
                    performance_data.append({"file": perf_file.name, "data": data})
            except:
                continue

        self.metadata["performance_metrics"] = performance_data

    def _generate_api_documentation(self, formats: list[str]) -> dict[str, Path]:
        """Generate comprehensive API documentation."""
        template = self.jinja_env.get_template("api_documentation.html")

        # Organize endpoints by tags/paths
        organized_endpoints = {}
        for endpoint in self.api_endpoints:
            path_parts = endpoint["path"].strip("/").split("/")
            category = path_parts[1] if len(path_parts) > 1 else "default"

            if category not in organized_endpoints:
                organized_endpoints[category] = []
            organized_endpoints[category].append(endpoint)

        context = {
            "metadata": self.metadata,
            "endpoints_by_category": organized_endpoints,
            "total_endpoints": len(self.api_endpoints),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "api_reference.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["api_html"] = html_file

        if "markdown" in formats:
            md_template = self._create_markdown_template("api_documentation")
            md_content = md_template.render(**context)
            md_file = self.output_dir / "api_reference.md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)
            output_files["api_md"] = md_file

        return output_files

    def _generate_database_documentation(self, formats: list[str]) -> dict[str, Path]:
        """Generate database schema documentation."""
        template = self.jinja_env.get_template("database_documentation.html")

        context = {
            "metadata": self.metadata,
            "models": self.database_models,
            "total_models": len(self.database_models),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "database_schema.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["db_html"] = html_file

        return output_files

    def _generate_service_documentation(self, formats: list[str]) -> dict[str, Path]:
        """Generate service layer documentation."""
        template = self.jinja_env.get_template("service_documentation.html")

        context = {
            "metadata": self.metadata,
            "services": self.service_classes,
            "repositories": self.repository_classes,
            "total_services": len(self.service_classes),
            "total_repositories": len(self.repository_classes),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "service_architecture.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["service_html"] = html_file

        return output_files

    def _generate_type_documentation(self, formats: list[str]) -> dict[str, Path]:
        """Generate type definitions documentation."""
        template = self.jinja_env.get_template("type_documentation.html")

        # Organize types by language and category
        python_types = [
            t for t in self.type_definitions if t.get("language") != "TypeScript"
        ]
        typescript_types = [
            t for t in self.type_definitions if t.get("language") == "TypeScript"
        ]

        context = {
            "metadata": self.metadata,
            "python_types": python_types,
            "typescript_types": typescript_types,
            "total_types": len(self.type_definitions),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "type_definitions.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["types_html"] = html_file

        return output_files

    def _generate_configuration_documentation(
        self, formats: list[str]
    ) -> dict[str, Path]:
        """Generate configuration documentation."""
        template = self.jinja_env.get_template("configuration_documentation.html")

        context = {
            "metadata": self.metadata,
            "configuration_files": self.configuration_options,
            "total_options": sum(
                len(config["options"]) for config in self.configuration_options
            ),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "configuration_guide.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["config_html"] = html_file

        return output_files

    def _generate_test_coverage_documentation(
        self, formats: list[str]
    ) -> dict[str, Path]:
        """Generate test coverage documentation."""
        template = self.jinja_env.get_template("test_coverage_documentation.html")

        context = {
            "metadata": self.metadata,
            "coverage_data": self.test_coverage,
            "coverage_percentage": self.test_coverage.get("totals", {}).get(
                "percent_covered", 0
            ),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "test_coverage.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["coverage_html"] = html_file

        return output_files

    def _generate_architecture_documentation(
        self, formats: list[str]
    ) -> dict[str, Path]:
        """Generate architecture overview documentation."""
        # Read existing architecture documentation
        arch_files = [
            self.project_root / "docs" / "architecture" / "system-architecture.md",
            self.project_root / "PROJECT_DOCS.md",
            self.project_root / "TECHNICAL_DESIGN.md",
        ]

        architecture_content = []
        for arch_file in arch_files:
            if arch_file.exists():
                with open(arch_file, encoding="utf-8") as f:
                    architecture_content.append(
                        {"file": arch_file.name, "content": f.read()}
                    )

        template = self.jinja_env.get_template("architecture_documentation.html")

        context = {
            "metadata": self.metadata,
            "architecture_files": architecture_content,
            "services": self.service_classes,
            "repositories": self.repository_classes,
            "models": self.database_models,
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "architecture_overview.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["arch_html"] = html_file

        return output_files

    def _generate_developer_documentation(self, formats: list[str]) -> dict[str, Path]:
        """Generate developer guide documentation."""
        # Read existing developer documentation
        dev_files = [
            self.project_root / "CONTRIBUTING.md",
            self.project_root / "DEVELOPMENT_SETUP.md",
            self.project_root / "docs" / "contributing" / "development-workflow.md",
        ]

        developer_content = []
        for dev_file in dev_files:
            if dev_file.exists():
                with open(dev_file, encoding="utf-8") as f:
                    developer_content.append(
                        {"file": dev_file.name, "content": f.read()}
                    )

        template = self.jinja_env.get_template("developer_documentation.html")

        context = {
            "metadata": self.metadata,
            "developer_files": developer_content,
            "code_metrics": self.metadata.get("code_metrics", {}),
            "test_coverage": self.test_coverage,
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "developer_guide.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["dev_html"] = html_file

        return output_files

    def _generate_changelog(self, formats: list[str]) -> dict[str, Path]:
        """Generate changelog from git commits and existing changelog files."""
        changelog_content = []

        # Read existing changelog
        changelog_file = self.project_root / "CHANGELOG.md"
        if changelog_file.exists():
            with open(changelog_file, encoding="utf-8") as f:
                changelog_content.append(f.read())

        # Get recent git commits if no changelog exists
        if not changelog_content:
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-50"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )
                if result.returncode == 0:
                    commits = result.stdout.strip().split("\n")
                    changelog_content = [
                        "## Recent Changes\n\n"
                        + "\n".join(f"- {commit}" for commit in commits)
                    ]
            except:
                changelog_content = ["## Changelog\n\nNo changelog available."]

        template = self.jinja_env.get_template("changelog_documentation.html")

        context = {
            "metadata": self.metadata,
            "changelog_content": (
                changelog_content[0] if changelog_content else "No changelog available."
            ),
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "changelog.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["changelog_html"] = html_file

        return output_files

    def _generate_index_page(self, formats: list[str]) -> dict[str, Path]:
        """Generate main documentation index page."""
        template = self.jinja_env.get_template("index_documentation.html")

        # Calculate documentation completeness score
        completeness_score = self._calculate_documentation_completeness()

        context = {
            "metadata": self.metadata,
            "code_metrics": self.metadata.get("code_metrics", {}),
            "test_coverage": self.test_coverage,
            "completeness_score": completeness_score,
            "documentation_sections": [
                {
                    "name": "API Reference",
                    "file": "api_reference.html",
                    "description": "Complete REST API documentation",
                },
                {
                    "name": "Database Schema",
                    "file": "database_schema.html",
                    "description": "Database models and relationships",
                },
                {
                    "name": "Service Architecture",
                    "file": "service_architecture.html",
                    "description": "Service layer and business logic",
                },
                {
                    "name": "Type Definitions",
                    "file": "type_definitions.html",
                    "description": "Type definitions and models",
                },
                {
                    "name": "Configuration Guide",
                    "file": "configuration_guide.html",
                    "description": "Configuration options and setup",
                },
                {
                    "name": "Test Coverage",
                    "file": "test_coverage.html",
                    "description": "Test coverage report and analysis",
                },
                {
                    "name": "Architecture Overview",
                    "file": "architecture_overview.html",
                    "description": "System architecture and design",
                },
                {
                    "name": "Developer Guide",
                    "file": "developer_guide.html",
                    "description": "Development setup and contribution guide",
                },
                {
                    "name": "Changelog",
                    "file": "changelog.html",
                    "description": "Version history and changes",
                },
            ],
        }

        output_files = {}

        if "html" in formats:
            html_content = template.render(**context)
            html_file = self.output_dir / "index.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            output_files["index_html"] = html_file

        return output_files

    def _calculate_documentation_completeness(self) -> dict[str, Any]:
        """Calculate documentation completeness metrics."""
        total_possible = 100
        current_score = 0

        # API endpoints documented
        if self.api_endpoints:
            documented_endpoints = sum(
                1 for ep in self.api_endpoints if ep.get("docstring")
            )
            current_score += (documented_endpoints / len(self.api_endpoints)) * 20

        # Models documented
        if self.database_models:
            documented_models = sum(
                1 for model in self.database_models if model.get("docstring")
            )
            current_score += (documented_models / len(self.database_models)) * 20

        # Services documented
        if self.service_classes:
            documented_services = sum(
                1 for svc in self.service_classes if svc.get("docstring")
            )
            current_score += (documented_services / len(self.service_classes)) * 20

        # Test coverage
        coverage_pct = self.test_coverage.get("totals", {}).get("percent_covered", 0)
        current_score += (coverage_pct / 100) * 20

        # Configuration documented
        if self.configuration_options:
            current_score += 20

        return {
            "score": min(current_score, total_possible),
            "total": total_possible,
            "percentage": min(current_score / total_possible * 100, 100),
        }

    def _generate_search_index(self) -> Path:
        """Generate search index for documentation."""
        search_data = []

        # Index API endpoints
        for endpoint in self.api_endpoints:
            search_data.append(
                {
                    "type": "api_endpoint",
                    "title": f"{endpoint['method']} {endpoint['path']}",
                    "content": endpoint.get("docstring", ""),
                    "url": f"api_reference.html#{endpoint['function_name']}",
                    "keywords": [
                        endpoint["method"],
                        endpoint["path"],
                        endpoint["function_name"],
                    ],
                }
            )

        # Index database models
        for model in self.database_models:
            search_data.append(
                {
                    "type": "database_model",
                    "title": model["name"],
                    "content": model.get("docstring", ""),
                    "url": f"database_schema.html#{model['name']}",
                    "keywords": [model["name"], "model", "database"],
                }
            )

        # Index services
        for service in self.service_classes:
            search_data.append(
                {
                    "type": "service",
                    "title": service["name"],
                    "content": service.get("docstring", ""),
                    "url": f"service_architecture.html#{service['name']}",
                    "keywords": [service["name"], "service", "business logic"],
                }
            )

        # Index types
        for type_def in self.type_definitions:
            search_data.append(
                {
                    "type": "type_definition",
                    "title": type_def["name"],
                    "content": type_def.get("docstring", ""),
                    "url": f"type_definitions.html#{type_def['name']}",
                    "keywords": [
                        type_def["name"],
                        "type",
                        type_def.get("language", ""),
                    ],
                }
            )

        search_index_file = self.output_dir / "search_index.json"
        with open(search_index_file, "w", encoding="utf-8") as f:
            json.dump(search_data, f, indent=2)

        return search_index_file

    def _create_markdown_template(self, template_name: str) -> Template:
        """Create markdown template for given template name."""
        # This would typically load from a markdown template file
        # For now, create a simple markdown template
        if template_name == "api_documentation":
            template_content = """
# API Documentation

Generated: {{ metadata.generated_at }}
Version: {{ metadata.version }}

{% for category, endpoints in endpoints_by_category.items() %}
## {{ category|title }} Endpoints

{% for endpoint in endpoints %}
### {{ endpoint.method }} {{ endpoint.path }}

**Function**: `{{ endpoint.function_name }}`
**File**: {{ endpoint.file_path }}

{% if endpoint.docstring %}
{{ endpoint.docstring }}
{% endif %}

{% if endpoint.parameters %}
**Parameters**:
{% for param in endpoint.parameters %}
- `{{ param.name }}`: {{ param.type|default('Any') }}
{% endfor %}
{% endif %}

{% if endpoint.response_model %}
**Response Model**: `{{ endpoint.response_model }}`
{% endif %}

---
{% endfor %}
{% endfor %}
"""
        else:
            template_content = "# {{ template_name }}\n\nTemplate not implemented yet."

        return Template(template_content)

    def _create_default_templates(self):
        """Create default Jinja2 templates if they don't exist."""
        template_dir = self.project_root / "docs" / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)

        templates = {
            "api_documentation.html": self._get_api_documentation_template(),
            "database_documentation.html": self._get_database_documentation_template(),
            "service_documentation.html": self._get_service_documentation_template(),
            "type_documentation.html": self._get_type_documentation_template(),
            "configuration_documentation.html": self._get_configuration_documentation_template(),
            "test_coverage_documentation.html": self._get_test_coverage_documentation_template(),
            "architecture_documentation.html": self._get_architecture_documentation_template(),
            "developer_documentation.html": self._get_developer_documentation_template(),
            "changelog_documentation.html": self._get_changelog_documentation_template(),
            "index_documentation.html": self._get_index_documentation_template(),
            "base.html": self._get_base_template(),
        }

        for template_name, template_content in templates.items():
            template_file = template_dir / template_name
            if not template_file.exists():
                with open(template_file, "w", encoding="utf-8") as f:
                    f.write(template_content)

    def _get_base_template(self) -> str:
        """Get base HTML template."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ metadata.project_name }} Documentation{% endblock %}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .nav { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 30px; }
        .nav a { text-decoration: none; color: #495057; margin-right: 20px; font-weight: 500; }
        .nav a:hover { color: #007bff; }
        .content { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .footer { text-align: center; margin-top: 30px; color: #6c757d; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }
        code { background: #f8f9fa; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }
        .method-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; color: white; }
        .method-get { background-color: #28a745; }
        .method-post { background-color: #007bff; }
        .method-put { background-color: #ffc107; color: black; }
        .method-delete { background-color: #dc3545; }
        .endpoint { border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .model { border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .field { margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px; }
        .search-box { width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; }
        .metric { display: inline-block; margin: 10px; padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: center; min-width: 100px; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        .metric-label { color: #6c757d; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{{ metadata.project_name }} Documentation</h1>
            <p>Version {{ metadata.version }} • Generated {{ metadata.generated_at[:10] }}</p>
        </header>

        <nav class="nav">
            <a href="index.html">Home</a>
            <a href="api_reference.html">API Reference</a>
            <a href="database_schema.html">Database</a>
            <a href="service_architecture.html">Services</a>
            <a href="type_definitions.html">Types</a>
            <a href="configuration_guide.html">Configuration</a>
            <a href="test_coverage.html">Coverage</a>
            <a href="developer_guide.html">Developer Guide</a>
        </nav>

        <main class="content">
            {% block content %}{% endblock %}
        </main>

        <footer class="footer">
            <p>Documentation generated by AI Enhanced PDF Scholar Documentation Generator</p>
            <p>{{ metadata.generated_at }}</p>
        </footer>
    </div>

    <script>
        // Simple search functionality
        function setupSearch() {
            const searchBox = document.querySelector('.search-box');
            if (searchBox) {
                searchBox.addEventListener('input', function(e) {
                    const query = e.target.value.toLowerCase();
                    const items = document.querySelectorAll('[data-searchable]');

                    items.forEach(item => {
                        const text = item.textContent.toLowerCase();
                        if (text.includes(query) || query === '') {
                            item.style.display = 'block';
                        } else {
                            item.style.display = 'none';
                        }
                    });
                });
            }
        }

        document.addEventListener('DOMContentLoaded', setupSearch);
    </script>
</body>
</html>"""

    def _get_api_documentation_template(self) -> str:
        """Get API documentation template."""
        return """{% extends "base.html" %}

{% block title %}API Reference - {{ super() }}{% endblock %}

{% block content %}
<h2>API Reference</h2>

<input type="text" class="search-box" placeholder="Search API endpoints...">

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ total_endpoints }}</div>
        <div class="metric-label">Total Endpoints</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ endpoints_by_category|length }}</div>
        <div class="metric-label">Categories</div>
    </div>
</div>

{% for category, endpoints in endpoints_by_category.items() %}
<h3>{{ category|title }} ({{ endpoints|length }} endpoints)</h3>

{% for endpoint in endpoints %}
<div class="endpoint" data-searchable id="{{ endpoint.function_name }}">
    <h4>
        <span class="method-badge method-{{ endpoint.method.lower() }}">{{ endpoint.method }}</span>
        <code>{{ endpoint.path }}</code>
    </h4>

    <p><strong>Function:</strong> <code>{{ endpoint.function_name }}</code></p>
    <p><strong>File:</strong> {{ endpoint.file_path }}:{{ endpoint.line_number }}</p>

    {% if endpoint.docstring %}
    <div class="description">
        <h5>Description</h5>
        <p>{{ endpoint.docstring }}</p>
    </div>
    {% endif %}

    {% if endpoint.parameters %}
    <div class="parameters">
        <h5>Parameters</h5>
        <ul>
        {% for param in endpoint.parameters %}
            <li><code>{{ param.name }}</code>: {{ param.type|default('Any') }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if endpoint.response_model %}
    <div class="response">
        <h5>Response Model</h5>
        <code>{{ endpoint.response_model }}</code>
    </div>
    {% endif %}
</div>
{% endfor %}
{% endfor %}
{% endblock %}"""

    def _get_database_documentation_template(self) -> str:
        """Get database documentation template."""
        return """{% extends "base.html" %}

{% block title %}Database Schema - {{ super() }}{% endblock %}

{% block content %}
<h2>Database Schema</h2>

<input type="text" class="search-box" placeholder="Search database models...">

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ total_models }}</div>
        <div class="metric-label">Database Models</div>
    </div>
</div>

{% for model in models %}
<div class="model" data-searchable id="{{ model.name }}">
    <h3>{{ model.name }}</h3>
    <p><strong>File:</strong> {{ model.file_path }}:{{ model.line_number }}</p>

    {% if model.docstring %}
    <div class="description">
        <p>{{ model.docstring }}</p>
    </div>
    {% endif %}

    {% if model.fields %}
    <h4>Fields</h4>
    {% for field in model.fields %}
    <div class="field">
        <strong>{{ field.name }}</strong>: {{ field.type }}
        {% if field.primary_key %}<span style="color: #007bff;">(PK)</span>{% endif %}
        {% if not field.nullable %}<span style="color: #dc3545;">(NOT NULL)</span>{% endif %}
        {% if field.default %}<span style="color: #28a745;">(default: {{ field.default }})</span>{% endif %}
    </div>
    {% endfor %}
    {% endif %}

    {% if model.relationships %}
    <h4>Relationships</h4>
    {% for rel in model.relationships %}
    <div class="field">
        <strong>{{ rel.name }}</strong> → {{ rel.target_model }}
        {% if rel.back_populates %}(back_populates: {{ rel.back_populates }}){% endif %}
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}
{% endblock %}"""

    def _get_service_documentation_template(self) -> str:
        """Get service documentation template."""
        return """{% extends "base.html" %}

{% block title %}Service Architecture - {{ super() }}{% endblock %}

{% block content %}
<h2>Service Architecture</h2>

<input type="text" class="search-box" placeholder="Search services and repositories...">

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ total_services }}</div>
        <div class="metric-label">Service Classes</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ total_repositories }}</div>
        <div class="metric-label">Repository Classes</div>
    </div>
</div>

<h3>Service Classes</h3>
{% for service in services %}
<div class="model" data-searchable id="{{ service.name }}">
    <h4>{{ service.name }}</h4>
    <p><strong>File:</strong> {{ service.file_path }}:{{ service.line_number }}</p>

    {% if service.docstring %}
    <div class="description">
        <p>{{ service.docstring }}</p>
    </div>
    {% endif %}

    {% if service.dependencies %}
    <h5>Dependencies</h5>
    <ul>
    {% for dep in service.dependencies %}
        <li><code>{{ dep.name }}</code>: {{ dep.type|default('Any') }}</li>
    {% endfor %}
    </ul>
    {% endif %}

    {% if service.methods %}
    <h5>Methods</h5>
    {% for method in service.methods %}
    <div class="field">
        <strong>{{ method.name }}</strong>
        {% if method.is_async %}<span style="color: #007bff;">(async)</span>{% endif %}
        <br>
        Parameters: {{ method.parameters|join(', ') }}
        {% if method.docstring %}<br><small>{{ method.docstring }}</small>{% endif %}
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}

<h3>Repository Classes</h3>
{% for repo in repositories %}
<div class="model" data-searchable id="{{ repo.name }}">
    <h4>{{ repo.name }}</h4>
    <p><strong>File:</strong> {{ repo.file_path }}:{{ repo.line_number }}</p>

    {% if repo.docstring %}
    <div class="description">
        <p>{{ repo.docstring }}</p>
    </div>
    {% endif %}

    {% if repo.methods %}
    <h5>Methods</h5>
    {% for method in repo.methods %}
    <div class="field">
        <strong>{{ method.name }}</strong>
        {% if method.is_async %}<span style="color: #007bff;">(async)</span>{% endif %}
        <br>
        Parameters: {{ method.parameters|join(', ') }}
        {% if method.docstring %}<br><small>{{ method.docstring }}</small>{% endif %}
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}
{% endblock %}"""

    def _get_type_documentation_template(self) -> str:
        """Get type documentation template."""
        return """{% extends "base.html" %}

{% block title %}Type Definitions - {{ super() }}{% endblock %}

{% block content %}
<h2>Type Definitions</h2>

<input type="text" class="search-box" placeholder="Search type definitions...">

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ python_types|length }}</div>
        <div class="metric-label">Python Types</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ typescript_types|length }}</div>
        <div class="metric-label">TypeScript Types</div>
    </div>
</div>

<h3>Python Types</h3>
{% for type_def in python_types %}
<div class="model" data-searchable id="{{ type_def.name }}">
    <h4>{{ type_def.name }}</h4>
    <p><strong>File:</strong> {{ type_def.file_path }}:{{ type_def.line_number }}</p>

    {% if type_def.docstring %}
    <div class="description">
        <p>{{ type_def.docstring }}</p>
    </div>
    {% endif %}

    {% if type_def.fields %}
    <h5>Fields</h5>
    {% for field in type_def.fields %}
    <div class="field">
        <strong>{{ field.name }}</strong>: {{ field.type }}
        {% if field.optional %}<span style="color: #ffc107;">(optional)</span>{% endif %}
        {% if field.default %}<span style="color: #28a745;">(default: {{ field.default }})</span>{% endif %}
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}

<h3>TypeScript Types</h3>
{% for type_def in typescript_types %}
<div class="model" data-searchable id="{{ type_def.name }}">
    <h4>{{ type_def.name }} <span style="color: #007bff;">({{ type_def.kind }})</span></h4>
    <p><strong>File:</strong> {{ type_def.file_path }}</p>

    {% if type_def.definition %}
    <div class="description">
        <pre><code>{{ type_def.definition }}</code></pre>
    </div>
    {% endif %}

    {% if type_def.fields %}
    <h5>Fields</h5>
    {% for field in type_def.fields %}
    <div class="field">
        <strong>{{ field.name }}</strong>: {{ field.type }}
        {% if field.optional %}<span style="color: #ffc107;">(optional)</span>{% endif %}
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}
{% endblock %}"""

    def _get_configuration_documentation_template(self) -> str:
        """Get configuration documentation template."""
        return """{% extends "base.html" %}

{% block title %}Configuration Guide - {{ super() }}{% endblock %}

{% block content %}
<h2>Configuration Guide</h2>

<input type="text" class="search-box" placeholder="Search configuration options...">

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ configuration_files|length }}</div>
        <div class="metric-label">Config Files</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ total_options }}</div>
        <div class="metric-label">Total Options</div>
    </div>
</div>

{% for config in configuration_files %}
<div class="model" data-searchable>
    <h3>{{ config.file }}</h3>
    <p><strong>Path:</strong> {{ config.path }}</p>

    {% if config.options %}
    <h4>Configuration Options</h4>
    {% for option in config.options %}
    <div class="field">
        <strong>{{ option.name }}</strong>
        <span style="color: #6c757d;">({{ option.type }})</span>
        <br>
        <code>{{ option.value }}</code>
    </div>
    {% endfor %}
    {% endif %}
</div>
{% endfor %}
{% endblock %}"""

    def _get_test_coverage_documentation_template(self) -> str:
        """Get test coverage documentation template."""
        return """{% extends "base.html" %}

{% block title %}Test Coverage - {{ super() }}{% endblock %}

{% block content %}
<h2>Test Coverage Report</h2>

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ "%.1f"|format(coverage_percentage) }}%</div>
        <div class="metric-label">Overall Coverage</div>
    </div>
    {% if coverage_data.totals %}
    <div class="metric">
        <div class="metric-value">{{ coverage_data.totals.num_statements }}</div>
        <div class="metric-label">Total Statements</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ coverage_data.totals.covered_lines }}</div>
        <div class="metric-label">Covered Lines</div>
    </div>
    {% endif %}
</div>

{% if coverage_data.files %}
<h3>File Coverage</h3>
<table style="width: 100%; border-collapse: collapse;">
    <thead>
        <tr style="background: #f8f9fa;">
            <th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">File</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">Coverage</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">Statements</th>
            <th style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">Missing</th>
        </tr>
    </thead>
    <tbody>
    {% for filename, file_data in coverage_data.files.items() %}
        <tr>
            <td style="padding: 10px; border: 1px solid #dee2e6;">{{ filename }}</td>
            <td style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">
                {% set coverage_pct = (file_data.summary.covered_lines / file_data.summary.num_statements * 100) if file_data.summary.num_statements > 0 else 0 %}
                <span style="color: {% if coverage_pct >= 80 %}#28a745{% elif coverage_pct >= 60 %}#ffc107{% else %}#dc3545{% endif %};">
                    {{ "%.1f"|format(coverage_pct) }}%
                </span>
            </td>
            <td style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">{{ file_data.summary.num_statements }}</td>
            <td style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">{{ file_data.missing_lines|length }}</td>
        </tr>
    {% endfor %}
    </tbody>
</table>
{% else %}
<p>No coverage data available. Run tests with coverage to generate this report.</p>
{% endif %}
{% endblock %}"""

    def _get_architecture_documentation_template(self) -> str:
        """Get architecture documentation template."""
        return """{% extends "base.html" %}

{% block title %}Architecture Overview - {{ super() }}{% endblock %}

{% block content %}
<h2>System Architecture</h2>

<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ services|length }}</div>
        <div class="metric-label">Services</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ repositories|length }}</div>
        <div class="metric-label">Repositories</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ models|length }}</div>
        <div class="metric-label">Models</div>
    </div>
</div>

{% for arch_file in architecture_files %}
<div class="model">
    <h3>{{ arch_file.file }}</h3>
    <div style="white-space: pre-wrap; font-family: monospace; background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
{{ arch_file.content }}
    </div>
</div>
{% endfor %}

{% if not architecture_files %}
<div class="model">
    <h3>Architecture Components</h3>
    <p>The system consists of the following main components:</p>

    <h4>Service Layer</h4>
    <ul>
    {% for service in services %}
        <li><strong>{{ service.name }}</strong> - {{ service.docstring|default('Service component') }}</li>
    {% endfor %}
    </ul>

    <h4>Repository Layer</h4>
    <ul>
    {% for repo in repositories %}
        <li><strong>{{ repo.name }}</strong> - {{ repo.docstring|default('Data access component') }}</li>
    {% endfor %}
    </ul>

    <h4>Data Models</h4>
    <ul>
    {% for model in models %}
        <li><strong>{{ model.name }}</strong> - {{ model.docstring|default('Data model') }}</li>
    {% endfor %}
    </ul>
</div>
{% endif %}
{% endblock %}"""

    def _get_developer_documentation_template(self) -> str:
        """Get developer documentation template."""
        return """{% extends "base.html" %}

{% block title %}Developer Guide - {{ super() }}{% endblock %}

{% block content %}
<h2>Developer Guide</h2>

<div class="metrics">
    {% if code_metrics %}
    <div class="metric">
        <div class="metric-value">{{ code_metrics.python_files }}</div>
        <div class="metric-label">Python Files</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ code_metrics.total_classes }}</div>
        <div class="metric-label">Classes</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ code_metrics.total_functions }}</div>
        <div class="metric-label">Functions</div>
    </div>
    {% endif %}
    {% if test_coverage.totals %}
    <div class="metric">
        <div class="metric-value">{{ "%.1f"|format(test_coverage.totals.percent_covered) }}%</div>
        <div class="metric-label">Test Coverage</div>
    </div>
    {% endif %}
</div>

{% for dev_file in developer_files %}
<div class="model">
    <h3>{{ dev_file.file }}</h3>
    <div style="white-space: pre-wrap; font-family: monospace; background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
{{ dev_file.content }}
    </div>
</div>
{% endfor %}

{% if not developer_files %}
<div class="model">
    <h3>Getting Started</h3>
    <p>This project is {{ metadata.project_name }} version {{ metadata.version }}.</p>

    <h4>Quick Start</h4>
    <pre><code>git clone https://github.com/your-repo/{{ metadata.project_name|lower|replace(" ", "-") }}.git
cd {{ metadata.project_name|lower|replace(" ", "-") }}
pip install -r requirements.txt
python -m pytest</code></pre>

    <h4>Architecture Overview</h4>
    <p>The project follows a clean architecture pattern with the following layers:</p>
    <ul>
        <li>API Layer - FastAPI endpoints and request handling</li>
        <li>Service Layer - Business logic and orchestration</li>
        <li>Repository Layer - Data access and persistence</li>
        <li>Model Layer - Data models and domain entities</li>
    </ul>
</div>
{% endif %}
{% endblock %}"""

    def _get_changelog_documentation_template(self) -> str:
        """Get changelog documentation template."""
        return """{% extends "base.html" %}

{% block title %}Changelog - {{ super() }}{% endblock %}

{% block content %}
<h2>Changelog</h2>

<div style="white-space: pre-wrap; font-family: monospace; background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
{{ changelog_content }}
</div>
{% endblock %}"""

    def _get_index_documentation_template(self) -> str:
        """Get index documentation template."""
        return """{% extends "base.html" %}

{% block content %}
<h2>Welcome to {{ metadata.project_name }} Documentation</h2>

<p>This documentation was automatically generated on {{ metadata.generated_at }} for version {{ metadata.version }}.</p>

<div class="metrics">
    {% if code_metrics %}
    <div class="metric">
        <div class="metric-value">{{ code_metrics.api_endpoints }}</div>
        <div class="metric-label">API Endpoints</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ code_metrics.database_models }}</div>
        <div class="metric-label">Database Models</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ code_metrics.service_classes }}</div>
        <div class="metric-label">Service Classes</div>
    </div>
    {% endif %}
    <div class="metric">
        <div class="metric-value">{{ "%.0f"|format(completeness_score.percentage) }}%</div>
        <div class="metric-label">Documentation Coverage</div>
    </div>
</div>

<h3>Documentation Sections</h3>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0;">
{% for section in documentation_sections %}
<div style="border: 1px solid #dee2e6; border-radius: 8px; padding: 20px;">
    <h4><a href="{{ section.file }}" style="text-decoration: none; color: #007bff;">{{ section.name }}</a></h4>
    <p>{{ section.description }}</p>
</div>
{% endfor %}
</div>

<h3>Project Statistics</h3>
{% if code_metrics %}
<ul>
    <li><strong>Python Files:</strong> {{ code_metrics.python_files }}</li>
    <li><strong>TypeScript Files:</strong> {{ code_metrics.typescript_files }}</li>
    <li><strong>Total Classes:</strong> {{ code_metrics.total_classes }}</li>
    <li><strong>Total Functions:</strong> {{ code_metrics.total_functions }}</li>
    <li><strong>Lines of Code:</strong> {{ code_metrics.total_lines }}</li>
</ul>
{% endif %}

{% if test_coverage.totals %}
<h3>Test Coverage</h3>
<p>Overall test coverage: <strong>{{ "%.1f"|format(test_coverage.totals.percent_covered) }}%</strong></p>
<p>Covered lines: {{ test_coverage.totals.covered_lines }} / {{ test_coverage.totals.num_statements }}</p>
{% endif %}

<h3>Quick Links</h3>
<ul>
    <li><a href="api_reference.html">API Reference</a> - Complete REST API documentation</li>
    <li><a href="database_schema.html">Database Schema</a> - Data models and relationships</li>
    <li><a href="service_architecture.html">Service Architecture</a> - Business logic layer</li>
    <li><a href="developer_guide.html">Developer Guide</a> - Setup and contribution instructions</li>
</ul>
{% endblock %}"""


def main():
    """Main entry point for the documentation generator."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive documentation for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/docs_generator.py
    python scripts/docs_generator.py --format html,markdown --output docs/generated
    python scripts/docs_generator.py --format pdf --output docs/generated
        """,
    )

    parser.add_argument(
        "--format",
        default="html,markdown",
        help="Output formats (comma-separated): html, markdown, pdf (default: html,markdown)",
    )

    parser.add_argument(
        "--output",
        default="docs/generated",
        help="Output directory for generated documentation (default: docs/generated)",
    )

    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Parse formats
    formats = [fmt.strip().lower() for fmt in args.format.split(",")]
    valid_formats = ["html", "markdown", "pdf"]
    formats = [fmt for fmt in formats if fmt in valid_formats]

    if not formats:
        print(
            "❌ Error: No valid formats specified. Valid formats: html, markdown, pdf"
        )
        sys.exit(1)

    # Initialize generator
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output)

    if not project_root.exists():
        print(f"❌ Error: Project root directory does not exist: {project_root}")
        sys.exit(1)

    try:
        generator = DocumentationGenerator(project_root, output_dir)

        # Create default templates
        generator._create_default_templates()

        # Generate documentation
        generated_files = generator.generate_all_documentation(formats)

        print("\n🎉 Success! Generated documentation:")
        for doc_type, file_path in generated_files.items():
            print(f"   {doc_type}: {file_path}")

        print(f"\n📁 All files saved to: {output_dir.resolve()}")

        # If HTML format was generated, show how to view it
        if any("html" in str(f) for f in generated_files.values()):
            index_file = output_dir / "index.html"
            if index_file.exists():
                print(f"\n🌐 View documentation at: file://{index_file.resolve()}")

    except Exception as e:
        print(f"❌ Error: Documentation generation failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
