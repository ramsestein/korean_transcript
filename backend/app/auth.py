"""Simple token-based authentication for the meeting interpreter."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

# Simple in-memory token storage (resets on restart; for VPS this is fine)
# Format: {token: {"created": datetime, "expires": datetime}}
_valid_tokens: set[str] = set()
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a pepper (from env)."""
    settings = get_settings()
    # Use a simple pepper from env or default
    pepper = getattr(settings, 'auth_pepper', 'default-pepper-change-me')
    return hashlib.sha256(f"{password}{pepper}".encode()).hexdigest()


def create_token() -> str:
    """Create a new random token."""
    token = secrets.token_urlsafe(32)
    _valid_tokens.add(token)
    return token


def verify_token(token: str | None) -> bool:
    """Check if a token is valid."""
    if not token:
        return False
    return token in _valid_tokens


def revoke_token(token: str) -> None:
    """Remove a token (logout)."""
    _valid_tokens.discard(token)


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]
) -> str:
    """Dependency to require authentication. Returns the token if valid."""
    settings = get_settings()
    
    # If auth is disabled, allow all
    if not getattr(settings, 'auth_enabled', False):
        return "disabled"
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    if not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token


def authenticate_user(password: str) -> str | None:
    """Verify password and return a new token if valid."""
    settings = get_settings()
    admin_password = getattr(settings, 'admin_password', None)
    
    if not admin_password:
        return None
    
    # Compare hashed passwords
    input_hash = hash_password(password)
    expected_hash = hash_password(admin_password)
    
    # Use constant-time comparison to prevent timing attacks
    if hmac.compare_digest(input_hash, expected_hash):
        return create_token()
    
    return None
