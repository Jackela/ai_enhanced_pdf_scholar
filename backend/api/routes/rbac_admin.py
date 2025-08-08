"""
RBAC Administration API Routes
Endpoints for managing roles, permissions, and user access control.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth.dependencies import get_current_user
from backend.api.auth.models import UserModel as User
from backend.api.auth.rbac import (
    RBACService,
    SystemRoles,
    ResourceTypes,
    Actions,
    Role,
    Permission,
    get_rbac_service,
    require_role,
    require_permission
)
from backend.api.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rbac", tags=["rbac-admin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""
    user_id: int
    role_name: str
    expires_in_hours: Optional[int] = Field(None, description="Hours until role expires")
    reason: Optional[str] = Field(None, max_length=500)


class RoleCreationRequest(BaseModel):
    """Request model for creating custom roles."""
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., max_length=500)
    permissions: List[str] = Field(..., description="List of permission names")
    parent_role: Optional[str] = Field(None, description="Parent role for inheritance")


class PermissionGrantRequest(BaseModel):
    """Request model for direct permission grants."""
    user_id: int
    permission_name: str
    expires_in_hours: Optional[int] = Field(None, description="Hours until permission expires")
    reason: str = Field(..., max_length=500, description="Reason for direct grant")


class RoleResponse(BaseModel):
    """Response model for role information."""
    id: int
    name: str
    description: str
    is_system_role: bool
    priority: int
    permissions: List[str]
    user_count: int
    created_at: datetime
    parent_role: Optional[str] = None


class PermissionResponse(BaseModel):
    """Response model for permission information."""
    id: int
    name: str
    resource: str
    action: str
    description: str
    is_system_permission: bool
    role_count: int


class UserPermissionsResponse(BaseModel):
    """Response model for user permissions."""
    user_id: int
    email: str
    roles: List[str]
    direct_permissions: List[str]
    effective_permissions: List[str]
    permission_count: int


class ResourcePolicyRequest(BaseModel):
    """Request model for resource policies."""
    resource_type: str
    resource_id: str
    policy_type: str = Field(..., description="e.g., 'owner', 'department', 'project'")
    policy_value: str = Field(..., description="Policy configuration (JSON)")


class AuditLogResponse(BaseModel):
    """Response model for RBAC audit logs."""
    id: int
    timestamp: datetime
    action: str
    actor_id: int
    actor_email: str
    target_id: Optional[int]
    target_email: Optional[str]
    details: dict
    ip_address: Optional[str]


# ============================================================================
# Role Management Endpoints
# ============================================================================

@router.get("/roles", response_model=List[RoleResponse])
@require_permission(ResourceTypes.SYSTEM, Actions.READ)
async def list_roles(
    include_system: bool = Query(True, description="Include system roles"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    List all available roles.
    Requires system:read permission.
    """
    query = db.query(Role)
    
    if not include_system:
        query = query.filter(Role.is_system_role == False)
    
    roles = query.order_by(Role.priority, Role.name).all()
    
    response = []
    for role in roles:
        response.append(RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            priority=role.priority,
            permissions=[f"{p.resource}:{p.action}" for p in role.permissions],
            user_count=len(role.users),
            created_at=role.created_at,
            parent_role=role.parent_role.name if role.parent_role else None
        ))
    
    logger.info(f"User {current_user.email} listed {len(response)} roles")
    return response


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
@require_role(SystemRoles.ADMIN)
async def create_role(
    request: RoleCreationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Create a new custom role.
    Requires admin role.
    """
    try:
        role = rbac.create_custom_role(
            name=request.name,
            description=request.description,
            permissions=request.permissions,
            created_by=current_user,
            parent_role=request.parent_role
        )
        
        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            priority=role.priority,
            permissions=[f"{p.resource}:{p.action}" for p in role.permissions],
            user_count=0,
            created_at=role.created_at,
            parent_role=role.parent_role.name if role.parent_role else None
        )
    except Exception as e:
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/roles/{role_name}", status_code=status.HTTP_204_NO_CONTENT)
@require_role(SystemRoles.SUPER_ADMIN)
async def delete_role(
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a custom role.
    Cannot delete system roles.
    Requires super_admin role.
    """
    role = db.query(Role).filter_by(name=role_name).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role {role_name} not found"
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles"
        )
    
    if role.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {len(role.users)} assigned users"
        )
    
    db.delete(role)
    db.commit()
    
    logger.info(f"Role {role_name} deleted by {current_user.email}")


# ============================================================================
# User Role Assignment Endpoints
# ============================================================================

@router.post("/assign-role", status_code=status.HTTP_200_OK)
@require_permission(ResourceTypes.USER, Actions.UPDATE)
async def assign_role_to_user(
    request: RoleAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Assign a role to a user.
    Requires user:update permission.
    """
    target_user = db.query(User).filter_by(id=request.user_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {request.user_id} not found"
        )
    
    expires_at = None
    if request.expires_in_hours:
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)
    
    try:
        success = rbac.assign_role(
            user=target_user,
            role_name=request.role_name,
            assigned_by=current_user,
            expires_at=expires_at
        )
        
        if success:
            logger.info(
                f"Role {request.role_name} assigned to user {target_user.email} "
                f"by {current_user.email}",
                extra={"reason": request.reason, "expires_at": expires_at}
            )
            return {
                "message": f"Role {request.role_name} assigned successfully",
                "user_id": request.user_id,
                "expires_at": expires_at
            }
    except Exception as e:
        logger.error(f"Failed to assign role: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/revoke-role", status_code=status.HTTP_200_OK)
@require_permission(ResourceTypes.USER, Actions.UPDATE)
async def revoke_role_from_user(
    user_id: int,
    role_name: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Revoke a role from a user.
    Requires user:update permission.
    """
    target_user = db.query(User).filter_by(id=user_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    try:
        success = rbac.revoke_role(
            user=target_user,
            role_name=role_name,
            revoked_by=current_user
        )
        
        if success:
            logger.info(
                f"Role {role_name} revoked from user {target_user.email} "
                f"by {current_user.email}",
                extra={"reason": reason}
            )
            return {
                "message": f"Role {role_name} revoked successfully",
                "user_id": user_id
            }
        else:
            return {
                "message": f"User does not have role {role_name}",
                "user_id": user_id
            }
    except Exception as e:
        logger.error(f"Failed to revoke role: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Permission Management Endpoints
# ============================================================================

@router.get("/permissions", response_model=List[PermissionResponse])
@require_permission(ResourceTypes.SYSTEM, Actions.READ)
async def list_permissions(
    resource: Optional[str] = Query(None, description="Filter by resource type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all available permissions.
    Requires system:read permission.
    """
    query = db.query(Permission)
    
    if resource:
        query = query.filter(Permission.resource == resource)
    
    permissions = query.order_by(Permission.resource, Permission.action).all()
    
    response = []
    for permission in permissions:
        response.append(PermissionResponse(
            id=permission.id,
            name=permission.name,
            resource=permission.resource,
            action=permission.action,
            description=permission.description,
            is_system_permission=permission.is_system_permission,
            role_count=len(permission.roles)
        ))
    
    return response


@router.post("/grant-permission", status_code=status.HTTP_200_OK)
@require_role(SystemRoles.ADMIN)
async def grant_direct_permission(
    request: PermissionGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Grant a direct permission to a user.
    Direct permissions bypass role assignments.
    Requires admin role.
    """
    target_user = db.query(User).filter_by(id=request.user_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {request.user_id} not found"
        )
    
    expires_at = None
    if request.expires_in_hours:
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)
    
    try:
        success = rbac.grant_permission(
            user=target_user,
            permission_name=request.permission_name,
            granted_by=current_user,
            expires_at=expires_at,
            reason=request.reason
        )
        
        if success:
            logger.info(
                f"Permission {request.permission_name} granted to user {target_user.email} "
                f"by {current_user.email}",
                extra={"reason": request.reason, "expires_at": expires_at}
            )
            return {
                "message": f"Permission {request.permission_name} granted successfully",
                "user_id": request.user_id,
                "expires_at": expires_at
            }
    except Exception as e:
        logger.error(f"Failed to grant permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# User Permissions Query Endpoints
# ============================================================================

@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
@require_permission(ResourceTypes.USER, Actions.READ)
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get all permissions for a specific user.
    Includes roles, direct grants, and effective permissions.
    Requires user:read permission.
    """
    target_user = db.query(User).filter_by(id=user_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    # Get user's roles
    roles = [role.name for role in target_user.roles]
    
    # Get direct permissions (would need to be implemented)
    direct_permissions = []  # This would query the user_permissions table
    
    # Get all effective permissions
    effective_permissions = rbac.get_user_permissions(target_user)
    
    return UserPermissionsResponse(
        user_id=target_user.id,
        email=target_user.email,
        roles=roles,
        direct_permissions=direct_permissions,
        effective_permissions=effective_permissions,
        permission_count=len(effective_permissions)
    )


@router.get("/my-permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get current user's permissions.
    """
    roles = [role.name for role in current_user.roles]
    direct_permissions = []  # This would query the user_permissions table
    effective_permissions = rbac.get_user_permissions(current_user)
    
    return UserPermissionsResponse(
        user_id=current_user.id,
        email=current_user.email,
        roles=roles,
        direct_permissions=direct_permissions,
        effective_permissions=effective_permissions,
        permission_count=len(effective_permissions)
    )


@router.post("/check-permission", response_model=dict)
async def check_permission(
    resource: str,
    action: str,
    resource_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Check if current user has a specific permission.
    """
    result = rbac.check_permission(
        user=current_user,
        resource=resource,
        action=action,
        resource_id=resource_id
    )
    
    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "context": result.context,
        "cached": result.cached
    }


# ============================================================================
# Resource Policy Endpoints
# ============================================================================

@router.post("/resource-policies", status_code=status.HTTP_201_CREATED)
@require_permission(ResourceTypes.SYSTEM, Actions.UPDATE)
async def create_resource_policy(
    request: ResourcePolicyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a resource-level access policy.
    Requires system:update permission.
    """
    from backend.api.auth.rbac import ResourcePolicy
    
    policy = ResourcePolicy(
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        policy_type=request.policy_type,
        policy_value=request.policy_value,
        created_by=current_user.id
    )
    
    db.add(policy)
    db.commit()
    
    logger.info(
        f"Resource policy created for {request.resource_type}:{request.resource_id} "
        f"by {current_user.email}"
    )
    
    return {
        "message": "Resource policy created successfully",
        "policy_id": policy.id
    }


# ============================================================================
# Audit Log Endpoints
# ============================================================================

@router.get("/audit-logs", response_model=List[AuditLogResponse])
@require_permission(ResourceTypes.AUDIT, Actions.READ)
async def get_rbac_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    actor_id: Optional[int] = Query(None),
    target_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get RBAC audit logs.
    Requires audit:read permission.
    """
    # This would query an audit log table
    # For now, return empty list as placeholder
    logger.info(f"User {current_user.email} accessed RBAC audit logs")
    return []


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=dict)
@require_permission(ResourceTypes.SYSTEM, Actions.READ)
async def get_rbac_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get RBAC system statistics.
    Requires system:read permission.
    """
    total_users = db.query(User).count()
    total_roles = db.query(Role).count()
    total_permissions = db.query(Permission).count()
    
    # Get role distribution
    role_distribution = {}
    roles = db.query(Role).all()
    for role in roles:
        role_distribution[role.name] = len(role.users)
    
    return {
        "total_users": total_users,
        "total_roles": total_roles,
        "total_permissions": total_permissions,
        "system_roles": db.query(Role).filter_by(is_system_role=True).count(),
        "custom_roles": db.query(Role).filter_by(is_system_role=False).count(),
        "role_distribution": role_distribution,
        "timestamp": datetime.utcnow()
    }


if __name__ == "__main__":
    pass