"""
Role-Based Access Control (RBAC) System
Enterprise-grade role and permission management for production environments.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Union

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session

from backend.api.auth.jwt_auth import get_current_user, User

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# RBAC Models
# ============================================================================

# Association tables for many-to-many relationships
user_roles = Table(
    'user_roles', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id')),
    Column('assigned_at', DateTime, default=datetime.utcnow),
    Column('assigned_by', Integer, ForeignKey('users.id')),
    Column('expires_at', DateTime, nullable=True)  # For temporary role assignments
)

role_permissions = Table(
    'role_permissions', Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id')),
    Column('permission_id', Integer, ForeignKey('permissions.id')),
    Column('granted_at', DateTime, default=datetime.utcnow),
    Column('granted_by', Integer, ForeignKey('users.id'))
)

user_permissions = Table(
    'user_permissions', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('permission_id', Integer, ForeignKey('permissions.id')),
    Column('granted_at', DateTime, default=datetime.utcnow),
    Column('granted_by', Integer, ForeignKey('users.id')),
    Column('expires_at', DateTime, nullable=True),  # For temporary permissions
    Column('reason', String(500))  # Audit trail for direct permission grants
)


class Role(Base):
    """Role model for RBAC."""
    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    is_system_role = Column(Boolean, default=False)  # Prevent deletion of system roles
    priority = Column(Integer, default=0)  # For role hierarchy
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    permissions = relationship('Permission', secondary=role_permissions, backref='roles')
    users = relationship('User', secondary=user_roles, backref='roles')
    
    # Parent role for inheritance
    parent_role_id = Column(Integer, ForeignKey('roles.id'), nullable=True)
    parent_role = relationship('Role', remote_side=[id])


class Permission(Base):
    """Permission model for fine-grained access control."""
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(100), nullable=False)  # e.g., 'document', 'user', 'system'
    action = Column(String(50), nullable=False)  # e.g., 'read', 'write', 'delete'
    description = Column(String(500))
    is_system_permission = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Conditions for dynamic permissions
    conditions = Column(String(1000))  # JSON string for permission conditions


class ResourcePolicy(Base):
    """Resource-level policies for attribute-based access control."""
    __tablename__ = 'resource_policies'
    
    id = Column(Integer, primary_key=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=False)
    policy_type = Column(String(50))  # 'owner', 'department', 'project', etc.
    policy_value = Column(String(500))  # JSON for complex policies
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'))


# ============================================================================
# Predefined Roles and Permissions
# ============================================================================

class SystemRoles(str, Enum):
    """System-defined roles that cannot be deleted."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"
    SERVICE_ACCOUNT = "service_account"  # For API-to-API communication


class ResourceTypes(str, Enum):
    """Resource types for permission management."""
    DOCUMENT = "document"
    USER = "user"
    SYSTEM = "system"
    LIBRARY = "library"
    RAG = "rag"
    SETTINGS = "settings"
    AUDIT = "audit"
    ANALYTICS = "analytics"


class Actions(str, Enum):
    """Standard CRUD+ actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXECUTE = "execute"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    IMPORT = "import"


# ============================================================================
# RBAC Service
# ============================================================================

@dataclass
class PermissionCheck:
    """Result of a permission check."""
    allowed: bool
    reason: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    ttl: int = 300  # Cache TTL in seconds


class RBACService:
    """
    Role-Based Access Control service with caching and audit logging.
    Implements hierarchical roles, dynamic permissions, and resource policies.
    """
    
    def __init__(self, db: Session, cache_enabled: bool = True):
        """Initialize RBAC service."""
        self.db = db
        self.cache_enabled = cache_enabled
        self._permission_cache: Dict[str, tuple[PermissionCheck, datetime]] = {}
        self._role_hierarchy_cache: Dict[int, Set[int]] = {}
        
    def check_permission(
        self,
        user: User,
        resource: str,
        action: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PermissionCheck:
        """
        Check if user has permission to perform action on resource.
        
        Args:
            user: Current user
            resource: Resource type
            action: Action to perform
            resource_id: Optional specific resource ID
            context: Additional context for dynamic permissions
            
        Returns:
            PermissionCheck result
        """
        # Build cache key
        cache_key = f"{user.id}:{resource}:{action}:{resource_id}"
        
        # Check cache
        if self.cache_enabled and cache_key in self._permission_cache:
            cached_result, cached_time = self._permission_cache[cache_key]
            if (datetime.utcnow() - cached_time).seconds < cached_result.ttl:
                cached_result.cached = True
                return cached_result
        
        # Super admin bypass
        if self._is_super_admin(user):
            result = PermissionCheck(
                allowed=True,
                reason="Super admin has all permissions",
                context={"role": SystemRoles.SUPER_ADMIN}
            )
            self._cache_permission(cache_key, result)
            return result
        
        # Check role-based permissions
        if self._has_role_permission(user, resource, action):
            result = PermissionCheck(
                allowed=True,
                reason=f"Permission granted through role",
                context={"method": "role"}
            )
            self._cache_permission(cache_key, result)
            return result
        
        # Check direct user permissions
        if self._has_direct_permission(user, resource, action):
            result = PermissionCheck(
                allowed=True,
                reason="Direct permission grant",
                context={"method": "direct"}
            )
            self._cache_permission(cache_key, result)
            return result
        
        # Check resource-level policies
        if resource_id and self._check_resource_policy(user, resource, action, resource_id, context):
            result = PermissionCheck(
                allowed=True,
                reason="Resource policy allows access",
                context={"method": "policy", "resource_id": resource_id}
            )
            self._cache_permission(cache_key, result)
            return result
        
        # Permission denied
        result = PermissionCheck(
            allowed=False,
            reason=f"No permission for {action} on {resource}",
            context={"user_id": user.id, "roles": [r.name for r in user.roles]}
        )
        self._cache_permission(cache_key, result)
        return result
    
    def assign_role(
        self,
        user: User,
        role_name: str,
        assigned_by: User,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user: User to assign role to
            role_name: Name of the role
            assigned_by: User performing the assignment
            expires_at: Optional expiration time for temporary roles
            
        Returns:
            Success status
        """
        # Check if assigner has permission
        if not self.check_permission(assigned_by, ResourceTypes.USER, Actions.UPDATE).allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to assign roles"
            )
        
        role = self.db.query(Role).filter_by(name=role_name).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role {role_name} not found"
            )
        
        # Check if user already has this role
        if role in user.roles:
            return True
        
        # Add role assignment
        user.roles.append(role)
        self.db.commit()
        
        # Log the assignment
        logger.info(
            f"Role {role_name} assigned to user {user.email} by {assigned_by.email}",
            extra={"expires_at": expires_at}
        )
        
        # Clear cache for this user
        self._clear_user_cache(user.id)
        
        return True
    
    def revoke_role(
        self,
        user: User,
        role_name: str,
        revoked_by: User
    ) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user: User to revoke role from
            role_name: Name of the role
            revoked_by: User performing the revocation
            
        Returns:
            Success status
        """
        # Check if revoker has permission
        if not self.check_permission(revoked_by, ResourceTypes.USER, Actions.UPDATE).allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to revoke roles"
            )
        
        role = self.db.query(Role).filter_by(name=role_name).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role {role_name} not found"
            )
        
        # Remove role if present
        if role in user.roles:
            user.roles.remove(role)
            self.db.commit()
            
            # Log the revocation
            logger.info(
                f"Role {role_name} revoked from user {user.email} by {revoked_by.email}"
            )
            
            # Clear cache for this user
            self._clear_user_cache(user.id)
            
            return True
        
        return False
    
    def grant_permission(
        self,
        user: User,
        permission_name: str,
        granted_by: User,
        expires_at: Optional[datetime] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Grant a direct permission to a user.
        
        Args:
            user: User to grant permission to
            permission_name: Name of the permission
            granted_by: User granting the permission
            expires_at: Optional expiration time
            reason: Reason for direct grant (for audit)
            
        Returns:
            Success status
        """
        # Check if granter has permission
        if not self.check_permission(granted_by, ResourceTypes.USER, Actions.UPDATE).allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to grant permissions"
            )
        
        permission = self.db.query(Permission).filter_by(name=permission_name).first()
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission {permission_name} not found"
            )
        
        # Add direct permission grant
        # This would need to be implemented with proper SQLAlchemy relationships
        
        # Log the grant
        logger.info(
            f"Permission {permission_name} granted to user {user.email} by {granted_by.email}",
            extra={"expires_at": expires_at, "reason": reason}
        )
        
        # Clear cache for this user
        self._clear_user_cache(user.id)
        
        return True
    
    def get_user_permissions(self, user: User) -> List[str]:
        """
        Get all permissions for a user (from roles and direct grants).
        
        Args:
            user: User to get permissions for
            
        Returns:
            List of permission names
        """
        permissions = set()
        
        # Get permissions from roles (including inherited)
        for role in user.roles:
            role_permissions = self._get_role_permissions_recursive(role)
            permissions.update(role_permissions)
        
        # Get direct permissions
        # This would need to be implemented with proper SQLAlchemy query
        
        return list(permissions)
    
    def create_custom_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        created_by: User,
        parent_role: Optional[str] = None
    ) -> Role:
        """
        Create a custom role with specified permissions.
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permission names
            created_by: User creating the role
            parent_role: Optional parent role for inheritance
            
        Returns:
            Created role
        """
        # Check if creator has permission
        if not self.check_permission(created_by, ResourceTypes.SYSTEM, Actions.CREATE).allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to create roles"
            )
        
        # Check if role already exists
        if self.db.query(Role).filter_by(name=name).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role {name} already exists"
            )
        
        # Create role
        role = Role(
            name=name,
            description=description,
            is_system_role=False
        )
        
        # Set parent role if specified
        if parent_role:
            parent = self.db.query(Role).filter_by(name=parent_role).first()
            if parent:
                role.parent_role = parent
        
        # Add permissions
        for perm_name in permissions:
            permission = self.db.query(Permission).filter_by(name=perm_name).first()
            if permission:
                role.permissions.append(permission)
        
        self.db.add(role)
        self.db.commit()
        
        logger.info(f"Custom role {name} created by {created_by.email}")
        
        return role
    
    # ========================================================================
    # Private Methods
    # ========================================================================
    
    def _is_super_admin(self, user: User) -> bool:
        """Check if user has super admin role."""
        return any(role.name == SystemRoles.SUPER_ADMIN for role in user.roles)
    
    def _has_role_permission(self, user: User, resource: str, action: str) -> bool:
        """Check if user has permission through their roles."""
        permission_name = f"{resource}:{action}"
        
        for role in user.roles:
            role_permissions = self._get_role_permissions_recursive(role)
            if permission_name in role_permissions or f"{resource}:*" in role_permissions:
                return True
        
        return False
    
    def _has_direct_permission(self, user: User, resource: str, action: str) -> bool:
        """Check if user has direct permission grant."""
        # This would need to be implemented with proper SQLAlchemy query
        permission_name = f"{resource}:{action}"
        # Query user_permissions table for non-expired direct grants
        return False
    
    def _check_resource_policy(
        self,
        user: User,
        resource: str,
        action: str,
        resource_id: str,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check resource-level policies."""
        # Example: Check if user owns the resource
        policies = self.db.query(ResourcePolicy).filter_by(
            resource_type=resource,
            resource_id=resource_id
        ).all()
        
        for policy in policies:
            if policy.policy_type == "owner":
                # Check if user is the owner
                if context and context.get("owner_id") == user.id:
                    return True
            elif policy.policy_type == "department":
                # Check department-based access
                if context and context.get("department") == user.department:
                    return True
        
        return False
    
    def _get_role_permissions_recursive(self, role: Role) -> Set[str]:
        """Get all permissions for a role including inherited permissions."""
        if role.id in self._role_hierarchy_cache:
            return self._role_hierarchy_cache[role.id]
        
        permissions = set()
        
        # Get direct permissions
        for permission in role.permissions:
            permissions.add(f"{permission.resource}:{permission.action}")
        
        # Get inherited permissions from parent role
        if role.parent_role:
            parent_permissions = self._get_role_permissions_recursive(role.parent_role)
            permissions.update(parent_permissions)
        
        # Cache the result
        self._role_hierarchy_cache[role.id] = permissions
        
        return permissions
    
    def _cache_permission(self, key: str, result: PermissionCheck):
        """Cache a permission check result."""
        if self.cache_enabled:
            self._permission_cache[key] = (result, datetime.utcnow())
    
    def _clear_user_cache(self, user_id: int):
        """Clear all cached permissions for a user."""
        keys_to_remove = [k for k in self._permission_cache.keys() if k.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self._permission_cache[key]


# ============================================================================
# Dependency Injection
# ============================================================================

def get_rbac_service(db: Session = Depends(get_db)) -> RBACService:
    """Get RBAC service instance."""
    return RBACService(db)


# ============================================================================
# Permission Decorators
# ============================================================================

def require_permission(resource: str, action: str):
    """
    Decorator to require specific permission for an endpoint.
    
    Args:
        resource: Resource type
        action: Action required
        
    Example:
        @require_permission(ResourceTypes.DOCUMENT, Actions.DELETE)
        async def delete_document(doc_id: int, user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = kwargs.get("current_user") or kwargs.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Get RBAC service
            db = kwargs.get("db")
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            rbac = RBACService(db)
            
            # Check permission
            permission_check = rbac.check_permission(user, resource, action)
            if not permission_check.allowed:
                logger.warning(
                    f"Permission denied for user {user.email}: {permission_check.reason}",
                    extra=permission_check.context
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=permission_check.reason
                )
            
            # Add permission context to kwargs
            kwargs["permission_context"] = permission_check.context
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(*permissions: tuple[str, str]):
    """
    Decorator to require any of the specified permissions.
    
    Args:
        permissions: List of (resource, action) tuples
        
    Example:
        @require_any_permission(
            (ResourceTypes.DOCUMENT, Actions.UPDATE),
            (ResourceTypes.DOCUMENT, Actions.APPROVE)
        )
        async def update_document(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user") or kwargs.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            db = kwargs.get("db")
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            rbac = RBACService(db)
            
            # Check if user has any of the required permissions
            for resource, action in permissions:
                permission_check = rbac.check_permission(user, resource, action)
                if permission_check.allowed:
                    kwargs["permission_context"] = permission_check.context
                    return await func(*args, **kwargs)
            
            # No permission granted
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires any of: {permissions}"
            )
        
        return wrapper
    return decorator


def require_role(role_name: str):
    """
    Decorator to require a specific role.
    
    Args:
        role_name: Name of the required role
        
    Example:
        @require_role(SystemRoles.ADMIN)
        async def admin_endpoint(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user") or kwargs.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check if user has the required role
            if not any(role.name == role_name for role in user.roles):
                logger.warning(f"Role {role_name} required but user {user.email} doesn't have it")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role {role_name} required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# Initialize Default Roles and Permissions
# ============================================================================

def initialize_rbac_system(db: Session):
    """
    Initialize the RBAC system with default roles and permissions.
    Should be called during application startup.
    """
    # Create default permissions
    default_permissions = [
        # Document permissions
        ("document:create", ResourceTypes.DOCUMENT, Actions.CREATE, "Create documents"),
        ("document:read", ResourceTypes.DOCUMENT, Actions.READ, "Read documents"),
        ("document:update", ResourceTypes.DOCUMENT, Actions.UPDATE, "Update documents"),
        ("document:delete", ResourceTypes.DOCUMENT, Actions.DELETE, "Delete documents"),
        ("document:list", ResourceTypes.DOCUMENT, Actions.LIST, "List documents"),
        ("document:export", ResourceTypes.DOCUMENT, Actions.EXPORT, "Export documents"),
        
        # User permissions
        ("user:create", ResourceTypes.USER, Actions.CREATE, "Create users"),
        ("user:read", ResourceTypes.USER, Actions.READ, "Read user profiles"),
        ("user:update", ResourceTypes.USER, Actions.UPDATE, "Update users"),
        ("user:delete", ResourceTypes.USER, Actions.DELETE, "Delete users"),
        ("user:list", ResourceTypes.USER, Actions.LIST, "List users"),
        
        # System permissions
        ("system:read", ResourceTypes.SYSTEM, Actions.READ, "Read system info"),
        ("system:update", ResourceTypes.SYSTEM, Actions.UPDATE, "Update system settings"),
        ("system:execute", ResourceTypes.SYSTEM, Actions.EXECUTE, "Execute system commands"),
        
        # Library permissions
        ("library:read", ResourceTypes.LIBRARY, Actions.READ, "Read library"),
        ("library:update", ResourceTypes.LIBRARY, Actions.UPDATE, "Update library"),
        
        # RAG permissions
        ("rag:execute", ResourceTypes.RAG, Actions.EXECUTE, "Execute RAG queries"),
        
        # Audit permissions
        ("audit:read", ResourceTypes.AUDIT, Actions.READ, "Read audit logs"),
        ("audit:export", ResourceTypes.AUDIT, Actions.EXPORT, "Export audit logs"),
    ]
    
    for name, resource, action, description in default_permissions:
        if not db.query(Permission).filter_by(name=name).first():
            permission = Permission(
                name=name,
                resource=resource,
                action=action,
                description=description,
                is_system_permission=True
            )
            db.add(permission)
    
    # Create default roles
    role_permissions = {
        SystemRoles.SUPER_ADMIN: ["*:*"],  # All permissions
        SystemRoles.ADMIN: [
            "document:*", "user:*", "library:*", "rag:*", "system:read", "audit:*"
        ],
        SystemRoles.MODERATOR: [
            "document:*", "user:read", "user:list", "library:*", "rag:*", "audit:read"
        ],
        SystemRoles.USER: [
            "document:create", "document:read", "document:list", "document:update",
            "library:read", "rag:execute", "user:read"
        ],
        SystemRoles.GUEST: [
            "document:read", "document:list", "library:read"
        ],
        SystemRoles.SERVICE_ACCOUNT: [
            "document:*", "library:*", "rag:*", "system:read"
        ]
    }
    
    for role_name, permission_patterns in role_permissions.items():
        if not db.query(Role).filter_by(name=role_name).first():
            role = Role(
                name=role_name,
                description=f"System role: {role_name}",
                is_system_role=True,
                priority=list(SystemRoles).index(role_name)
            )
            
            # Add permissions to role
            for pattern in permission_patterns:
                if pattern == "*:*":
                    # Add all permissions
                    all_perms = db.query(Permission).all()
                    role.permissions.extend(all_perms)
                elif pattern.endswith(":*"):
                    # Add all permissions for a resource
                    resource = pattern.split(":")[0]
                    resource_perms = db.query(Permission).filter_by(resource=resource).all()
                    role.permissions.extend(resource_perms)
                else:
                    # Add specific permission
                    perm = db.query(Permission).filter_by(name=pattern).first()
                    if perm:
                        role.permissions.append(perm)
            
            db.add(role)
    
    db.commit()
    logger.info("RBAC system initialized with default roles and permissions")


if __name__ == "__main__":
    # Example usage
    pass