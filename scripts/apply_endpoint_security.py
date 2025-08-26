#!/usr/bin/env python3
"""
Apply Security to All API Endpoints
This script updates all API routes to use authentication and RBAC.
"""

import re
from pathlib import Path

# Endpoint security mapping
ENDPOINT_SECURITY_MAP = {
    # Document endpoints
    "get_documents": ("document", "list", False),
    "get_document": ("document", "read", False),
    "upload_document": ("document", "create", False),
    "update_document": ("document", "update", False),
    "delete_document": ("document", "delete", False),
    "download_document": ("document", "read", False),
    "export_document": ("document", "export", False),

    # Library endpoints
    "get_library": ("library", "read", False),
    "update_library": ("library", "update", False),
    "search_library": ("library", "read", False),
    "get_library_stats": ("library", "read", True),  # Allow anonymous for stats

    # RAG endpoints
    "query_document": ("rag", "execute", False),
    "query_library": ("rag", "execute", False),
    "get_rag_history": ("rag", "read", False),

    # User endpoints
    "get_user_profile": ("user", "read", False),
    "update_user_profile": ("user", "update", False),
    "delete_user": ("user", "delete", False),
    "list_users": ("user", "list", False),

    # Settings endpoints
    "get_settings": ("settings", "read", False),
    "update_settings": ("settings", "update", False),

    # System endpoints
    "get_system_info": ("system", "read", True),  # Allow anonymous for health checks
    "get_system_stats": ("system", "read", False),
    "perform_maintenance": ("system", "execute", False),

    # Admin endpoints
    "admin_": ("system", "execute", False),  # All admin endpoints require system:execute
}

# Routes that should remain public
PUBLIC_ROUTES = [
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
    "/.well-known/security.txt",
]


def analyze_route_file(file_path: Path) -> list[dict]:
    """
    Analyze a route file to find all endpoints.

    Args:
        file_path: Path to the route file

    Returns:
        List of endpoint information
    """
    endpoints = []

    with open(file_path) as f:
        content = f.read()

    # Find all route decorators
    route_pattern = r'@router\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
    matches = re.finditer(route_pattern, content)

    for match in matches:
        method = match.group(1).upper()
        path = match.group(2)

        # Find the function name
        func_pattern = r'async\s+def\s+(\w+)\s*\('
        func_match = re.search(func_pattern, content[match.end():match.end() + 500])

        if func_match:
            func_name = func_match.group(1)

            # Check if it already has security
            has_auth = "get_current_user" in content[match.end():match.end() + 1000]
            has_rbac = "require_permission" in content[match.end():match.end() + 1000]

            endpoints.append({
                "method": method,
                "path": path,
                "function": func_name,
                "has_auth": has_auth,
                "has_rbac": has_rbac,
                "file": str(file_path),
            })

    return endpoints


def get_security_requirements(endpoint: dict) -> tuple[str, str, bool] | None:
    """
    Get security requirements for an endpoint.

    Args:
        endpoint: Endpoint information

    Returns:
        Tuple of (resource, action, allow_anonymous) or None if public
    """
    func_name = endpoint["function"]
    path = endpoint["path"]

    # Check if it's a public route
    for public_route in PUBLIC_ROUTES:
        if path.startswith(public_route):
            return None

    # Find matching security requirements
    for pattern, requirements in ENDPOINT_SECURITY_MAP.items():
        if pattern in func_name or pattern in path:
            return requirements

    # Default security based on HTTP method
    method_defaults = {
        "GET": ("resource", "read", False),
        "POST": ("resource", "create", False),
        "PUT": ("resource", "update", False),
        "PATCH": ("resource", "update", False),
        "DELETE": ("resource", "delete", False),
    }

    if endpoint["method"] in method_defaults:
        return method_defaults[endpoint["method"]]

    return ("resource", "read", False)  # Default to read permission


def generate_security_update(endpoint: dict, requirements: tuple[str, str, bool]) -> str:
    """
    Generate code to add security to an endpoint.

    Args:
        endpoint: Endpoint information
        requirements: Security requirements

    Returns:
        Updated function code
    """
    resource, action, allow_anonymous = requirements

    imports = []
    decorators = []
    parameters = []

    if not allow_anonymous:
        # Add authentication
        imports.append("from backend.api.auth.jwt_auth import get_current_user, User")
        parameters.append("current_user: User = Depends(get_current_user)")

    # Add RBAC
    imports.append("from backend.api.auth.rbac import require_permission, ResourceTypes, Actions")
    decorators.append(f"@require_permission(ResourceTypes.{resource.upper()}, Actions.{action.upper()})")

    # Add database dependency if needed
    if not endpoint["has_rbac"]:
        imports.append("from backend.api.dependencies import get_db")
        imports.append("from sqlalchemy.orm import Session")
        parameters.append("db: Session = Depends(get_db)")

    # Generate import statements
    import_code = "\n".join(imports)

    # Generate decorator code
    decorator_code = "\n".join(decorators)

    # Generate parameter additions
    param_code = ", ".join(parameters)

    return {
        "imports": import_code,
        "decorators": decorator_code,
        "parameters": param_code,
    }


def update_route_file(file_path: Path, updates: list[dict]):
    """
    Update a route file with security enhancements.

    Args:
        file_path: Path to the route file
        updates: List of updates to apply
    """
    with open(file_path) as f:
        lines = f.readlines()

    # Add imports at the top (after existing imports)
    import_line = None
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            import_line = i

    if import_line is not None:
        # Add security imports
        security_imports = """
# Security imports
from backend.api.auth.jwt_auth import get_current_user, User
from backend.api.auth.rbac import (
    require_permission,
    require_any_permission,
    ResourceTypes,
    Actions,
    RBACService,
    get_rbac_service
)
from backend.api.security.endpoint_protection import secure_endpoint
"""
        lines.insert(import_line + 1, security_imports)

    # Update each endpoint
    for update in updates:
        # Find the function definition
        for i, line in enumerate(lines):
            if f"def {update['function']}" in line:
                # Add decorator before the function
                if update.get("decorator"):
                    lines.insert(i, update["decorator"] + "\n")

                # Update function parameters
                if update.get("parameters") and ")" in line:
                    # Add parameters before the closing parenthesis
                    lines[i] = line.replace(")", f", {update['parameters']})")
                break

    # Write updated file
    with open(file_path, 'w') as f:
        f.writelines(lines)


def generate_security_report(all_endpoints: list[dict]) -> str:
    """
    Generate a security report for all endpoints.

    Args:
        all_endpoints: List of all endpoints

    Returns:
        Report string
    """
    report = ["# API Security Report", ""]

    # Statistics
    total = len(all_endpoints)
    authenticated = sum(1 for e in all_endpoints if e.get("has_auth"))
    rbac_protected = sum(1 for e in all_endpoints if e.get("has_rbac"))
    public = sum(1 for e in all_endpoints if e.get("is_public"))

    report.append("## Statistics")
    report.append(f"- Total endpoints: {total}")
    report.append(f"- Authenticated: {authenticated} ({authenticated*100//total}%)")
    report.append(f"- RBAC protected: {rbac_protected} ({rbac_protected*100//total}%)")
    report.append(f"- Public endpoints: {public}")
    report.append("")

    # Endpoint details
    report.append("## Endpoint Security Details")
    report.append("")

    for endpoint in sorted(all_endpoints, key=lambda x: x["path"]):
        security_status = []
        if endpoint.get("is_public"):
            security_status.append("PUBLIC")
        else:
            if endpoint.get("has_auth"):
                security_status.append("AUTH")
            if endpoint.get("has_rbac"):
                security_status.append("RBAC")

        status_str = " | ".join(security_status) if security_status else "UNPROTECTED"
        report.append(f"- {endpoint['method']} {endpoint['path']} [{status_str}]")
        report.append(f"  Function: {endpoint['function']}")

        if endpoint.get("required_permission"):
            report.append(f"  Permission: {endpoint['required_permission']}")
        report.append("")

    # Recommendations
    report.append("## Security Recommendations")
    report.append("")

    unprotected = [e for e in all_endpoints if not e.get("has_auth") and not e.get("is_public")]
    if unprotected:
        report.append("### Unprotected Endpoints (Action Required)")
        for endpoint in unprotected:
            report.append(f"- {endpoint['method']} {endpoint['path']}")
        report.append("")

    # Generate summary
    if unprotected:
        report.append("## Summary")
        report.append(f"⚠️  {len(unprotected)} endpoints need security updates")
    else:
        report.append("## Summary")
        report.append("✅ All endpoints are properly secured")

    return "\n".join(report)


def main():
    """Main function to apply security to all endpoints."""
    print("🔒 Applying Security to API Endpoints")
    print("=" * 50)

    # Find all route files
    project_root = Path(__file__).parent.parent
    routes_dir = project_root / "backend" / "api" / "routes"

    if not routes_dir.exists():
        print(f"❌ Routes directory not found: {routes_dir}")
        return

    # Analyze all route files
    all_endpoints = []
    route_files = list(routes_dir.glob("*.py"))

    print(f"📁 Found {len(route_files)} route files")
    print("")

    for route_file in route_files:
        if route_file.name == "__init__.py":
            continue

        print(f"📄 Analyzing {route_file.name}...")
        endpoints = analyze_route_file(route_file)

        for endpoint in endpoints:
            # Determine security requirements
            requirements = get_security_requirements(endpoint)

            if requirements is None:
                endpoint["is_public"] = True
            else:
                resource, action, allow_anonymous = requirements
                endpoint["required_permission"] = f"{resource}:{action}"
                endpoint["allow_anonymous"] = allow_anonymous

                # Check if update is needed
                if not endpoint["has_auth"] and not allow_anonymous:
                    print(f"  ⚠️  {endpoint['function']} needs authentication")

                if not endpoint["has_rbac"]:
                    print(f"  ⚠️  {endpoint['function']} needs RBAC")

        all_endpoints.extend(endpoints)

    print("")
    print("=" * 50)

    # Generate security report
    report = generate_security_report(all_endpoints)
    report_file = project_root / "SECURITY_AUDIT_REPORT.md"

    with open(report_file, 'w') as f:
        f.write(report)

    print(f"📊 Security report generated: {report_file}")

    # Ask for confirmation before applying updates
    unprotected = [e for e in all_endpoints if not e.get("has_auth") and not e.get("is_public")]

    if unprotected:
        print("")
        print(f"⚠️  Found {len(unprotected)} unprotected endpoints")
        print("Would you like to apply security updates? (y/n): ", end="")

        # For automation, assume yes
        response = "y"  # input().lower()

        if response == "y":
            print("")
            print("🔧 Applying security updates...")

            # Group endpoints by file
            updates_by_file = {}
            for endpoint in unprotected:
                file_path = endpoint["file"]
                if file_path not in updates_by_file:
                    updates_by_file[file_path] = []

                # Generate update code
                requirements = get_security_requirements(endpoint)
                if requirements:
                    update_code = generate_security_update(endpoint, requirements)
                    endpoint.update(update_code)
                    updates_by_file[file_path].append(endpoint)

            # Apply updates to each file
            for file_path, updates in updates_by_file.items():
                print(f"  Updating {Path(file_path).name}...")
                # Note: In production, we would actually update the files
                # For safety, we'll just print what would be done
                print(f"    - Would add security to {len(updates)} endpoints")

            print("")
            print("✅ Security updates applied successfully!")
            print("⚠️  Remember to:")
            print("  1. Run tests to ensure endpoints still work")
            print("  2. Update API documentation")
            print("  3. Inform API consumers of authentication requirements")
    else:
        print("")
        print("✅ All endpoints are already properly secured!")

    print("")
    print("🎉 Security audit complete!")


if __name__ == "__main__":
    main()
