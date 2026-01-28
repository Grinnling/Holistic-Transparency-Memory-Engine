# auth_system.py - Authentication architecture (implement now, use later)
"""
Multi-tier authentication system for memory chat
- Local-only mode (development)
- API key mode (remote access)  
- Full OAuth mode (production)
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
import hashlib
import jwt
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import os

class AuthMode(Enum):
    DISABLED = "disabled"      # No auth (localhost only)
    API_KEY = "api_key"       # Simple API keys
    JWT_BEARER = "jwt_bearer" # JWT tokens
    OAUTH = "oauth"           # Full OAuth2 (future)

class Permission(Enum):
    # Basic permissions
    READ_CHAT = "read:chat"
    WRITE_CHAT = "write:chat" 
    READ_MEMORY = "read:memory"
    WRITE_MEMORY = "write:memory"
    READ_ERRORS = "read:errors"
    CLEAR_ERRORS = "clear:errors"
    
    # Service management
    VIEW_SERVICES = "view:services"
    CONTROL_SERVICES = "control:services"
    VIEW_METRICS = "view:metrics"
    
    # System administration  
    ADMIN_SYSTEM = "admin:system"
    MANAGE_USERS = "manage:users"
    VIEW_LOGS = "view:logs"
    
    # Future features
    SHARE_CONVERSATIONS = "share:conversations"
    COLLABORATE_REALTIME = "collaborate:realtime"
    MANAGE_SCRATCHPADS = "manage:scratchpads"

@dataclass
class User:
    id: str
    username: str
    email: Optional[str] = None
    permissions: List[Permission] = None
    created_at: datetime = None
    last_active: datetime = None
    is_active: bool = True
    metadata: Dict[str, Any] = None

@dataclass  
class APIKey:
    key_id: str
    key_hash: str  # Never store raw keys
    name: str
    permissions: List[Permission]
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: datetime = None
    is_active: bool = True

class AuthSystem:
    def __init__(self, mode: AuthMode = AuthMode.DISABLED):
        self.mode = mode
        self.secret_key = os.getenv("AUTH_SECRET_KEY", secrets.token_urlsafe(32))
        self.api_keys: Dict[str, APIKey] = {}
        self.users: Dict[str, User] = {}
        
        # INTEGRATION: Use existing security framework
        self.mok_signing = self._init_mok_integration()
        self.auditd_logger = self._init_auditd_logging()
        self.biometric_monitor = self._init_biometric_monitor()
        
        # Default user for local development
        if mode == AuthMode.DISABLED:
            self.default_user = User(
                id="local_user",
                username="developer", 
                permissions=list(Permission),  # All permissions
                created_at=datetime.now()
            )
    
    def _init_mok_integration(self):
        """Initialize MOK (Machine Owner Key) signing for API tokens"""
        # Reuse existing MOK infrastructure for API key signing
        try:
            from secure_model_manager import SecureModelManager
            return SecureModelManager().get_mok_signer()
        except ImportError:
            return None
    
    def _init_auditd_logging(self):
        """Initialize auditd integration for auth events"""
        # Reuse existing auditd logging system
        try:
            import subprocess
            # Check if auditd is available
            subprocess.run(['which', 'auditctl'], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _init_biometric_monitor(self):
        """Initialize biometric duress detection"""
        # Integrate with existing biometric system
        try:
            # Check if biometric monitor service is available
            return os.path.exists('/sys/class/biometric_monitor')
        except:
            return False
    
    def audit_log_auth_event(self, event_type: str, user_id: str, details: dict):
        """Log authentication events using existing auditd infrastructure"""
        if not self.auditd_logger:
            return
            
        # Use existing audit logging format
        audit_message = f"type=AUTH_EVENT user={user_id} action={event_type} details={json.dumps(details)}"
        try:
            subprocess.run(['auditctl', '-m', audit_message], check=True)
        except subprocess.CalledProcessError:
            pass  # Fail silently if auditd unavailable
    
    def generate_api_key(self, name: str, owner_id: str, permissions: List[Permission], 
                        expires_in_days: Optional[int] = None) -> tuple[str, APIKey]:
        """Generate new API key and return (raw_key, api_key_object)"""
        raw_key = f"mk_{secrets.token_urlsafe(32)}"  # mk_ prefix for "memory key"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        api_key = APIKey(
            key_id=secrets.token_urlsafe(8),
            key_hash=key_hash,
            name=name,
            permissions=permissions,
            owner_id=owner_id,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        
        self.api_keys[key_hash] = api_key
        return raw_key, api_key
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate API key and return APIKey object if valid"""
        if not raw_key or not raw_key.startswith("mk_"):
            return None
            
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = self.api_keys.get(key_hash)
        
        if not api_key or not api_key.is_active:
            return None
            
        # Check expiration
        if api_key.expires_at and datetime.now() > api_key.expires_at:
            return None
            
        # Update last used
        api_key.last_used = datetime.now()
        return api_key
    
    def create_jwt_token(self, user: User, expires_in_hours: int = 24) -> str:
        """Create JWT token for user"""
        payload = {
            "sub": user.id,
            "username": user.username,
            "permissions": [p.value for p in user.permissions or []],
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return User if valid"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            user_id = payload.get("sub")
            
            # In real implementation, would fetch from database
            user = self.users.get(user_id)
            if user and user.is_active:
                user.last_active = datetime.now()
                return user
                
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        return None
    
    def has_permission(self, user_or_key: Union[User, APIKey], permission: Permission) -> bool:
        """Check if user/key has specific permission"""
        if isinstance(user_or_key, User):
            return permission in (user_or_key.permissions or [])
        elif isinstance(user_or_key, APIKey):
            return permission in user_or_key.permissions
        return False
    
    def get_current_user(self, request_context: Any) -> User:
        """Get current user from request context (FastAPI dependency)"""
        if self.mode == AuthMode.DISABLED:
            return self.default_user
            
        # Implementation depends on auth mode
        # This would be expanded based on chosen auth method
        raise NotImplementedError(f"Auth mode {self.mode} not implemented")

# FastAPI Dependencies
auth_system = AuthSystem(mode=AuthMode.DISABLED)  # Start disabled

security_bearer = HTTPBearer(auto_error=False)
security_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_current_user(
    bearer: HTTPAuthorizationCredentials = Security(security_bearer),
    api_key: str = Security(security_api_key)
) -> User:
    """FastAPI dependency to get current user"""
    
    if auth_system.mode == AuthMode.DISABLED:
        return auth_system.default_user
    
    # Try API key first
    if api_key:
        validated_key = auth_system.validate_api_key(api_key)
        if validated_key:
            # Convert APIKey to User-like object for permissions
            return User(
                id=validated_key.owner_id,
                username=f"api_key_{validated_key.name}",
                permissions=validated_key.permissions
            )
    
    # Try JWT Bearer token
    if bearer and bearer.credentials:
        user = auth_system.validate_jwt_token(bearer.credentials)
        if user:
            return user
    
    raise HTTPException(status_code=401, detail="Authentication required")

def require_permission(permission: Permission):
    """Decorator to require specific permission"""
    def dependency(user: User = Depends(get_current_user)):
        if not auth_system.has_permission(user, permission):
            raise HTTPException(
                status_code=403, 
                detail=f"Permission required: {permission.value}"
            )
        return user
    return dependency

# Example usage in FastAPI routes:
"""
@app.post("/chat")
async def chat_endpoint(
    message: ChatMessage,
    user: User = Depends(require_permission(Permission.WRITE_CHAT))
):
    # User is authenticated and has write:chat permission
    pass

@app.get("/admin/logs")  
async def get_logs(
    user: User = Depends(require_permission(Permission.VIEW_LOGS))
):
    # Only users with view:logs permission can access
    pass

@app.post("/services/restart")
async def restart_service(
    service: str,
    user: User = Depends(require_permission(Permission.CONTROL_SERVICES))
):
    # Only users with control:services permission
    pass
"""

# CLI commands for managing auth (implement later)
def setup_auth_cli():
    """CLI commands for managing authentication"""
    import click
    
    @click.group()
    def auth():
        """Authentication management commands"""
        pass
    
    @auth.command()
    @click.option('--name', required=True, help='API key name')
    @click.option('--permissions', multiple=True, help='Permissions to grant')
    @click.option('--expires', type=int, help='Expiration in days')
    def create_key(name: str, permissions: List[str], expires: Optional[int]):
        """Create new API key"""
        # Implementation here
        pass
    
    @auth.command() 
    def list_keys():
        """List all API keys"""
        # Implementation here
        pass
    
    return auth

if __name__ == "__main__":
    # Test the auth system
    auth = AuthSystem(AuthMode.API_KEY)
    
    # Create test API key
    raw_key, api_key = auth.generate_api_key(
        name="test_key",
        owner_id="test_user", 
        permissions=[Permission.READ_CHAT, Permission.WRITE_CHAT]
    )
    
    print(f"Generated API key: {raw_key}")
    print(f"Key ID: {api_key.key_id}")
    
    # Validate it
    validated = auth.validate_api_key(raw_key)
    print(f"Validation successful: {validated is not None}")
