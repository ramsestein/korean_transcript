"""Multi-user token-based authentication for the meeting interpreter.

Users are defined via environment variables ending in _USER:
  USER1_USER=password1
  USER2_USER=password2
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

# Simple in-memory token storage: {token: username}
_valid_tokens: dict[str, str] = {}
_bearer_scheme = HTTPBearer(auto_error=False)


def get_users_from_env() -> dict[str, str]:
    """Extract users from environment variables ending in _USER.
    
    Returns dict: {lowercase_username: password}
    Example: USER1_USER=pass123 -> {'user1': 'pass123'}
    """
    users = {}
    for key, value in os.environ.items():
        if key.upper().endswith('_USER') and not key.upper().startswith('AUTH'):
            # Extract username from VARNAME_USER
            username = key.upper().replace('_USER', '').lower()
            if username:  # Ignore empty usernames
                users[username] = value
    return users


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a pepper (from env)."""
    settings = get_settings()
    pepper = getattr(settings, 'auth_pepper', 'default-pepper-change-me')
    return hashlib.sha256(f"{password}{pepper}".encode()).hexdigest()


def create_token(username: str) -> str:
    """Create a new random token associated with a username."""
    token = secrets.token_urlsafe(32)
    _valid_tokens[token] = username
    return token


def verify_token(token: str | None) -> tuple[bool, str]:
    """Check if a token is valid. Returns (is_valid, username)."""
    if not token:
        return False, ""
    if token in _valid_tokens:
        return True, _valid_tokens[token]
    return False, ""


def revoke_token(token: str) -> None:
    """Remove a token (logout)."""
    _valid_tokens.pop(token, None)


def get_token_username(token: str) -> str | None:
    """Get username associated with token."""
    return _valid_tokens.get(token)


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
    is_valid, username = verify_token(token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token


def authenticate_user(username: str, password: str) -> str | None:
    """Verify username/password and return a new token if valid.
    
    Username is case-insensitive.
    """
    users = get_users_from_env()
    username_lower = username.lower()
    
    if username_lower not in users:
        return None
    
    expected_password = users[username_lower]
    
    # Compare hashed passwords
    input_hash = hash_password(password)
    expected_hash = hash_password(expected_password)
    
    # Use constant-time comparison to prevent timing attacks
    if hmac.compare_digest(input_hash, expected_hash):
        return create_token(username_lower)
    
    return None


def list_usernames() -> list[str]:
    """Return list of configured usernames (for debugging)."""
    return list(get_users_from_env().keys())
