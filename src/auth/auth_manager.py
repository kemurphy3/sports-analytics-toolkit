#!/usr/bin/env python3
"""
Authentication manager for multi-tenant fitness platform
"""

import os
import uuid
import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from .models import (
    User, UserCreate, UserLogin, TokenResponse, UserUpdate,
    UserRole, UserStatus, RefreshTokenRequest
)

logger = logging.getLogger(__name__)

class AuthManager:
    """Manages user authentication and authorization"""
    
    def __init__(self, database_path: str = "data/athlete_performance.db"):
        self.database_path = database_path
        self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        
        # JWT configuration
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize authentication database tables"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Create users table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        status TEXT NOT NULL DEFAULT 'pending_verification',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        failed_login_attempts INTEGER DEFAULT 0,
                        locked_until TIMESTAMP,
                        mfa_secret TEXT,
                        mfa_enabled BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # Create refresh tokens table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS refresh_tokens (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        token_hash TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_revoked BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Create password reset tokens table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        token_hash TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        used BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Create magic link tokens table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS magic_link_tokens (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        token_hash TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        used BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)")
                
                conn.commit()
                logger.info("Authentication database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize authentication database: {e}")
            raise
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using Argon2"""
        return self.pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def _generate_tenant_id(self) -> str:
        """Generate a unique tenant ID"""
        return f"tenant_{uuid.uuid4().hex[:8]}"
    
    def _generate_user_id(self) -> str:
        """Generate a unique user ID"""
        return f"user_{uuid.uuid4().hex[:8]}"
    
    def _hash_token(self, token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user account"""
        try:
            # Check if user already exists
            if self.get_user_by_email(user_data.email):
                raise ValueError("User with this email already exists")
            
            # Generate IDs
            user_id = self._generate_user_id()
            tenant_id = user_data.tenant_id or self._generate_tenant_id()
            
            # Hash password
            password_hash = self._hash_password(user_data.password)
            
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    INSERT INTO users (
                        id, email, password_hash, first_name, last_name,
                        tenant_id, role, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, user_data.email, password_hash, user_data.first_name,
                    user_data.last_name, tenant_id, user_data.role.value,
                    UserStatus.PENDING_VERIFICATION.value, datetime.now(), datetime.now()
                ))
                
                conn.commit()
                
                # Return created user
                return self.get_user_by_id(user_id)
                
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT id, email, first_name, last_name, tenant_id, role, status,
                           is_active, created_at, updated_at, last_login, mfa_enabled
                    FROM users WHERE email = ?
                """, (email,))
                
                row = cursor.fetchone()
                if row:
                    return User(
                        id=row[0],
                        email=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        tenant_id=row[4],
                        role=UserRole(row[5]),
                        status=UserStatus(row[6]),
                        is_active=bool(row[7]),
                        created_at=datetime.fromisoformat(row[8]),
                        updated_at=datetime.fromisoformat(row[9]),
                        last_login=datetime.fromisoformat(row[10]) if row[10] else None,
                        mfa_enabled=bool(row[11])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT id, email, first_name, last_name, tenant_id, role, status,
                           is_active, created_at, updated_at, last_login, mfa_enabled
                    FROM users WHERE id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return User(
                        id=row[0],
                        email=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        tenant_id=row[4],
                        role=UserRole(row[5]),
                        status=UserStatus(row[6]),
                        is_active=bool(row[7]),
                        created_at=datetime.fromisoformat(row[8]),
                        updated_at=datetime.fromisoformat(row[9]),
                        last_login=datetime.fromisoformat(row[10]) if row[10] else None,
                        mfa_enabled=bool(row[11])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                return None
            
            # Check if account is locked
            if self._is_account_locked(user.id):
                raise ValueError("Account is temporarily locked due to failed login attempts")
            
            # Check if account is active
            if not user.is_active or user.status != UserStatus.ACTIVE:
                return None
            
            # Get stored password hash
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,))
                row = cursor.fetchone()
                if not row:
                    return None
                
                stored_hash = row[0]
                
                # Verify password
                if self._verify_password(password, stored_hash):
                    # Reset failed login attempts
                    self._reset_failed_login_attempts(user.id)
                    # Update last login
                    self._update_last_login(user.id)
                    return user
                else:
                    # Increment failed login attempts
                    self._increment_failed_login_attempts(user.id)
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to authenticate user: {e}")
            return None
    
    def _is_account_locked(self, user_id: str) -> bool:
        """Check if user account is locked"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT locked_until FROM users WHERE id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row and row[0]:
                    locked_until = datetime.fromisoformat(row[0])
                    if datetime.now() < locked_until:
                        return True
                    else:
                        # Clear lock if expired
                        conn.execute("UPDATE users SET locked_until = NULL WHERE id = ?", (user_id,))
                        conn.commit()
                        return False
                return False
                
        except Exception as e:
            logger.error(f"Failed to check account lock: {e}")
            return False
    
    def _increment_failed_login_attempts(self, user_id: str):
        """Increment failed login attempts and lock account if needed"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Get current failed attempts
                cursor = conn.execute("""
                    SELECT failed_login_attempts FROM users WHERE id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    failed_attempts = row[0] + 1
                    
                    # Lock account after 5 failed attempts for 15 minutes
                    if failed_attempts >= 5:
                        locked_until = datetime.now() + timedelta(minutes=15)
                        conn.execute("""
                            UPDATE users 
                            SET failed_login_attempts = ?, locked_until = ?
                            WHERE id = ?
                        """, (failed_attempts, locked_until, user_id))
                    else:
                        conn.execute("""
                            UPDATE users 
                            SET failed_login_attempts = ?
                            WHERE id = ?
                        """, (failed_attempts, user_id))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to increment failed login attempts: {e}")
    
    def _reset_failed_login_attempts(self, user_id: str):
        """Reset failed login attempts"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE users 
                    SET failed_login_attempts = 0, locked_until = NULL
                    WHERE id = ?
                """, (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to reset failed login attempts: {e}")
    
    def _update_last_login(self, user_id: str):
        """Update user's last login timestamp"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE users 
                    SET last_login = ?, updated_at = ?
                    WHERE id = ?
                """, (datetime.now(), datetime.now(), user_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update last login: {e}")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create and store refresh token"""
        try:
            # Generate token
            token = secrets.token_urlsafe(32)
            token_hash = self._hash_token(token)
            
            # Set expiration
            expires_at = datetime.now() + timedelta(days=self.refresh_token_expire_days)
            
            # Store in database
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (str(uuid.uuid4()), user_id, token_hash, expires_at))
                conn.commit()
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise
    
    def verify_refresh_token(self, refresh_token: str) -> Optional[str]:
        """Verify refresh token and return user ID"""
        try:
            token_hash = self._hash_token(refresh_token)
            
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT user_id, expires_at, is_revoked
                    FROM refresh_tokens 
                    WHERE token_hash = ?
                """, (token_hash,))
                
                row = cursor.fetchone()
                if row:
                    user_id, expires_at, is_revoked = row
                    
                    # Check if token is revoked or expired
                    if is_revoked or datetime.now() > datetime.fromisoformat(expires_at):
                        return None
                    
                    return user_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to verify refresh token: {e}")
            return None
    
    def revoke_refresh_token(self, refresh_token: str):
        """Revoke a refresh token"""
        try:
            token_hash = self._hash_token(refresh_token)
            
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE refresh_tokens 
                    SET is_revoked = TRUE
                    WHERE token_hash = ?
                """, (token_hash,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {e}")
    
    def login_user(self, user_login: UserLogin) -> Optional[TokenResponse]:
        """Authenticate user and return tokens"""
        try:
            # Authenticate user
            user = self.authenticate_user(user_login.email, user_login.password)
            if not user:
                return None
            
            # Create tokens
            access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
            access_token = self.create_access_token(
                data={"sub": user.id, "email": user.email, "tenant_id": user.tenant_id},
                expires_delta=access_token_expires
            )
            
            refresh_token = self.create_refresh_token(user.id)
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=self.access_token_expire_minutes * 60,
                user=user
            )
            
        except Exception as e:
            logger.error(f"Failed to login user: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            user_id = self.verify_refresh_token(refresh_token)
            if not user_id:
                return None
            
            # Get user
            user = self.get_user_by_id(user_id)
            if not user:
                return None
            
            # Create new access token
            access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
            access_token = self.create_access_token(
                data={"sub": user.id, "email": user.email, "tenant_id": user.tenant_id},
                expires_delta=access_token_expires
            )
            
            return access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None
    
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT access token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"Failed to verify access token: {e}")
            return None
    
    def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from access token"""
        try:
            payload = self.verify_access_token(token)
            if not payload:
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            return self.get_user_by_id(user_id)
            
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            return None
    
    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """Update user profile"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Build dynamic UPDATE query
                fields = []
                values = []
                
                for field, value in user_update.dict(exclude_unset=True).items():
                    if value is not None:
                        fields.append(f"{field} = ?")
                        values.append(value)
                
                if fields:
                    fields.append("updated_at = ?")
                    values.append(datetime.now())
                    values.append(user_id)
                    
                    query = f"""
                        UPDATE users 
                        SET {', '.join(fields)}
                        WHERE id = ?
                    """
                    
                    conn.execute(query, values)
                    conn.commit()
                    
                    return self.get_user_by_id(user_id)
                
                return self.get_user_by_id(user_id)
                
        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            return None
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user account"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Revoke all refresh tokens
                conn.execute("""
                    UPDATE refresh_tokens 
                    SET is_revoked = TRUE
                    WHERE user_id = ?
                """, (user_id,))
                
                # Delete user
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False
    
    def cleanup_expired_tokens(self):
        """Clean up expired tokens from database"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Clean up expired refresh tokens
                conn.execute("""
                    DELETE FROM refresh_tokens 
                    WHERE expires_at < ?
                """, (datetime.now(),))
                
                # Clean up expired password reset tokens
                conn.execute("""
                    DELETE FROM password_reset_tokens 
                    WHERE expires_at < ?
                """, (datetime.now(),))
                
                # Clean up expired magic link tokens
                conn.execute("""
                    DELETE FROM magic_link_tokens 
                    WHERE expires_at < ?
                """, (datetime.now(),))
                
                conn.commit()
                logger.info("Cleaned up expired tokens")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
    
    def get_user_sessions(self, user_id: str) -> list:
        """Get active user sessions"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT id, user_id, expires_at, created_at, is_revoked
                    FROM refresh_tokens 
                    WHERE user_id = ? AND is_revoked = FALSE AND expires_at > ?
                    ORDER BY created_at DESC
                """, (user_id, datetime.now()))
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        "session_id": row[0],
                        "user_id": row[1],
                        "expires_at": datetime.fromisoformat(row[2]),
                        "created_at": datetime.fromisoformat(row[3]),
                        "is_active": not bool(row[4])
                    })
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    def revoke_user_session(self, session_id: str) -> bool:
        """Revoke a specific user session"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE refresh_tokens 
                    SET is_revoked = TRUE
                    WHERE id = ?
                """, (session_id,))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke user session: {e}")
            return False
    
    def revoke_all_user_sessions(self, user_id: str) -> bool:
        """Revoke all sessions for a user"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE refresh_tokens 
                    SET is_revoked = TRUE
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke all user sessions: {e}")
            return False
