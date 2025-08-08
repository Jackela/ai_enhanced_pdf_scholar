"""
Authentication and Authorization Exception Classes
Handles errors related to user authentication, authorization, and sessions.
"""

from typing import Any, Optional
from .base import PDFScholarError


class AuthenticationError(PDFScholarError):
    """Base class for authentication-related errors."""
    
    def __init__(
        self, 
        message: str, 
        username: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize authentication error.
        
        Args:
            message: Error message
            username: Username involved (if applicable)
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if username:
            context['username'] = username
        
        super().__init__(message, context=context, **kwargs)
        self.username = username
    
    def _get_default_user_message(self) -> str:
        return "Authentication failed. Please check your credentials."


class AuthorizationError(PDFScholarError):
    """Raised when user lacks required permissions."""
    
    def __init__(
        self, 
        message: str, 
        user_id: Optional[int] = None,
        required_permission: Optional[str] = None,
        resource: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize authorization error.
        
        Args:
            message: Error message
            user_id: User ID attempting access
            required_permission: Permission that was required
            resource: Resource being accessed
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if user_id:
            context['user_id'] = user_id
        if required_permission:
            context['required_permission'] = required_permission
        if resource:
            context['resource'] = resource
        
        super().__init__(message, context=context, **kwargs)
        self.user_id = user_id
        self.required_permission = required_permission
        self.resource = resource
    
    def _get_default_user_message(self) -> str:
        return "You don't have permission to access this resource."


class TokenError(AuthenticationError):
    """Raised when token validation or processing fails."""
    
    def __init__(
        self, 
        message: str, 
        token_type: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize token error.
        
        Args:
            message: Error message
            token_type: Type of token (access, refresh, etc.)
            reason: Specific reason for token error
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if token_type:
            context['token_type'] = token_type
        if reason:
            context['reason'] = reason
        
        super().__init__(message, context=context, **kwargs)
        self.token_type = token_type
        self.reason = reason
    
    def _get_default_user_message(self) -> str:
        if self.reason == "expired":
            return "Your session has expired. Please log in again."
        elif self.reason == "invalid":
            return "Invalid authentication token. Please log in again."
        return "Authentication token error. Please log in again."


class AccountError(PDFScholarError):
    """Raised when account-related operations fail."""
    
    def __init__(
        self, 
        message: str, 
        username: Optional[str] = None,
        account_status: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize account error.
        
        Args:
            message: Error message
            username: Username of the account
            account_status: Current account status
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if username:
            context['username'] = username
        if account_status:
            context['account_status'] = account_status
        
        super().__init__(message, context=context, **kwargs)
        self.username = username
        self.account_status = account_status
    
    def _get_default_user_message(self) -> str:
        if self.account_status == "locked":
            return "Your account has been locked. Please contact support."
        elif self.account_status == "suspended":
            return "Your account has been suspended. Please contact support."
        elif self.account_status == "unverified":
            return "Please verify your email address before continuing."
        return "Account operation failed. Please contact support."


class PasswordError(AuthenticationError):
    """Raised when password-related operations fail."""
    
    def __init__(
        self, 
        message: str, 
        username: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize password error.
        
        Args:
            message: Error message
            username: Username involved
            reason: Specific reason for password error
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if reason:
            context['reason'] = reason
        
        super().__init__(message, username=username, context=context, **kwargs)
        self.reason = reason
    
    def _get_default_user_message(self) -> str:
        if self.reason == "weak":
            return "Password does not meet security requirements."
        elif self.reason == "incorrect":
            return "Incorrect password provided."
        elif self.reason == "expired":
            return "Your password has expired. Please reset it."
        return "Password operation failed."


class SessionError(AuthenticationError):
    """Raised when session management fails."""
    
    def __init__(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize session error.
        
        Args:
            message: Error message
            session_id: Session identifier
            reason: Specific reason for session error
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop('context', {})
        if session_id:
            context['session_id'] = session_id
        if reason:
            context['reason'] = reason
        
        super().__init__(message, context=context, **kwargs)
        self.session_id = session_id
        self.reason = reason
    
    def _get_default_user_message(self) -> str:
        if self.reason == "expired":
            return "Your session has expired. Please log in again."
        elif self.reason == "invalid":
            return "Invalid session. Please log in again."
        return "Session error occurred. Please log in again."