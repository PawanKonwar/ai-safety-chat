"""
Authentication utilities for AI Safety Chat
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, User
import secrets

# JWT settings
SECRET_KEY = "your-secret-key-change-in-production"  # In production, use env variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(
    session_token: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from token or create anonymous user"""
    
    # Try to get token from Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    elif session_token:
        token = session_token
    
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    return user
    
    # If no valid token, return anonymous user
    anonymous_user = db.query(User).filter(User.username == "anonymous").first()
    if not anonymous_user:
        # Create anonymous user if it doesn't exist
        anonymous_user = User(
            username="anonymous",
            email=None,
            role="user"
        )
        db.add(anonymous_user)
        db.commit()
        db.refresh(anonymous_user)
    
    return anonymous_user


def get_or_create_anonymous_session(db: Session) -> str:
    """Get or create an anonymous session ID"""
    # For simplicity, we'll use a session ID based on timestamp
    # In production, you'd want to store this in a session table
    return f"anon_{secrets.token_hex(16)}"
