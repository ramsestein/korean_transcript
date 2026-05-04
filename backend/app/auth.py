"""Multi-user token-based authentication for the meeting interpreter.

Users are defined via environment variables ending in _USER:
  USER1_USER=password1
  USER2_USER=password2

Security features:
- Tokens expire after 24 hours
- Rate limiting per IP (5 attempts per 5 minutes)
- Global circuit breaker: blocks login if too many failures from different IPs
  (protects against VPN/Tor distributed brute force attacks)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

# Token expiration time (24 hours in seconds)
TOKEN_EXPIRY_SECONDS = 24 * 60 * 60

# Rate limiting per IP: {ip: (attempts, first_attempt_timestamp)}
_login_attempts: dict[str, tuple[int, float]] = {}
RATE_LIMIT_WINDOW = 300  # 5 minutes
MAX_LOGIN_ATTEMPTS = 5

# Global circuit breaker for distributed attacks
# If we see too many failures from different IPs in a short window, block all logins
_global_failures: list[float] = []  # timestamps of failed attempts
GLOBAL_FAILURE_WINDOW = 60  # 1 minute window
MAX_GLOBAL_FAILURES = 20  # Max 20 failures from different IPs in 1 minute
GLOBAL_LOCKOUT_DURATION = 600  # 10 minutes lockout if threshold exceeded
_global_lockout_until: float = 0  # timestamp when lockout ends


@dataclass
class TokenInfo:
    username: str
    created_at: float


# In-memory token storage: {token: TokenInfo}
_valid_tokens: dict[str, TokenInfo] = {}
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


def _cleanup_expired_tokens() -> None:
    """Remove expired tokens from storage."""
    now = time.time()
    expired = [
        token for token, info in _valid_tokens.items()
        if now - info.created_at > TOKEN_EXPIRY_SECONDS
    ]
    for token in expired:
        del _valid_tokens[token]


def create_token(username: str) -> str:
    """Create a new random token associated with a username."""
    _cleanup_expired_tokens()
    
    token = secrets.token_urlsafe(32)
    _valid_tokens[token] = TokenInfo(
        username=username,
        created_at=time.time()
    )
    return token


def verify_token(token: str | None) -> tuple[bool, str]:
    """Check if a token is valid and not expired. Returns (is_valid, username)."""
    if not token:
        return False, ""
    
    _cleanup_expired_tokens()
    
    info = _valid_tokens.get(token)
    if not info:
        return False, ""
    
    # Check expiration
    if time.time() - info.created_at > TOKEN_EXPIRY_SECONDS:
        del _valid_tokens[token]
        return False, ""
    
    return True, info.username


def revoke_token(token: str) -> None:
    """Remove a token (logout)."""
    _valid_tokens.pop(token, None)


def get_token_username(token: str) -> str | None:
    """Get username associated with token."""
    info = _valid_tokens.get(token)
    return info.username if info else None


def check_global_circuit_breaker() -> tuple[bool, str]:
    """Check if global circuit breaker has triggered.
    
    Protects against distributed brute force attacks using multiple IPs/VPNs/Tor.
    
    Returns (allowed, reason). If not allowed, reason contains lockout time remaining.
    """
    global _global_lockout_until
    
    now = time.time()
    
    # Check if currently in lockout
    if now < _global_lockout_until:
        remaining = int(_global_lockout_until - now)
        return False, f"Login temporarily disabled due to suspicious activity. Try again in {remaining} seconds."
    
    # Clean up old failures outside window
    cutoff = now - GLOBAL_FAILURE_WINDOW
    _global_failures[:] = [ts for ts in _global_failures if ts > cutoff]
    
    # Check if too many failures
    if len(_global_failures) >= MAX_GLOBAL_FAILURES:
        # Trigger lockout
        _global_lockout_until = now + GLOBAL_LOCKOUT_DURATION
        _global_failures.clear()
        
        # Log security event
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            "SECURITY ALERT: Global login lockout triggered! "
            f"{MAX_GLOBAL_FAILURES} failed attempts in {GLOBAL_FAILURE_WINDOW}s. "
            f"Login blocked for {GLOBAL_LOCKOUT_DURATION}s."
        )
        
        return False, f"Security alert detected. Login disabled for {GLOBAL_LOCKOUT_DURATION // 60} minutes."
    
    return True, ""


def record_failed_attempt() -> None:
    """Record a failed login attempt for global tracking."""
    _global_failures.append(time.time())


def check_rate_limit(client_ip: str) -> bool:
    """Check if client IP is rate limited.
    
    Returns True if allowed, False if rate limited.
    """
    now = time.time()
    attempts, first_attempt = _login_attempts.get(client_ip, (0, now))
    
    # Reset window if expired
    if now - first_attempt > RATE_LIMIT_WINDOW:
        _login_attempts[client_ip] = (1, now)
        return True
    
    # Check limit
    if attempts >= MAX_LOGIN_ATTEMPTS:
        return False
    
    _login_attempts[client_ip] = (attempts + 1, first_attempt)
    return True


def log_failed_login(username: str, client_ip: str) -> None:
    """Log failed login attempt for monitoring and record for circuit breaker."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Failed login attempt: username='%s' from ip='%s'", username, client_ip)
    
    # Record for global circuit breaker (distributed attack detection)
    record_failed_attempt()


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


def authenticate_user(username: str, password: str, client_ip: str) -> tuple[str | None, str]:
    """Verify username/password and return a new token if valid.
    
    Username is case-insensitive.
    
    Returns (token, error_message). Token is None if auth failed.
    """
    # Check global circuit breaker first (distributed attack protection)
    allowed, reason = check_global_circuit_breaker()
    if not allowed:
        return None, reason
    
    # Check per-IP rate limiting
    if not check_rate_limit(client_ip):
        return None, "Too many login attempts. Please try again in 5 minutes."
    
    users = get_users_from_env()
    username_lower = username.lower()
    
    if username_lower not in users:
        log_failed_login(username, client_ip)
        return None, "Invalid username or password"
    
    expected_password = users[username_lower]
    
    # Compare hashed passwords
    input_hash = hash_password(password)
    expected_hash = hash_password(expected_password)
    
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(input_hash, expected_hash):
        log_failed_login(username, client_ip)
        return None, "Invalid username or password"
    
    # Create token
    token = create_token(username_lower)
    return token, ""


def list_usernames() -> list[str]:
    """Return list of configured usernames (for debugging)."""
    return list(get_users_from_env().keys())
