#!/usr/bin/env python3
"""
Authentication models for multi-tenant fitness platform
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    """User roles in the system"""
    USER = "user"
    ATHLETE = "athlete"
    COACH = "coach"
    ADMIN = "admin"

class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

class UserCreate(BaseModel):
    """Model for user registration"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    first_name: str = Field(..., min_length=1, max_length=50, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User last name")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (auto-generated if not provided)")
    role: UserRole = Field(UserRole.USER, description="User role")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "securepassword123",
                "first_name": "John",
                "last_name": "Doe",
                "role": "user"
            }
        }

class UserLogin(BaseModel):
    """Model for user login"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(False, description="Remember user session")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "securepassword123",
                "remember_me": False
            }
        }

class UserUpdate(BaseModel):
    """Model for user profile updates"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Smith"
            }
        }

class User(BaseModel):
    """User model"""
    id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    tenant_id: str = Field(..., description="Tenant identifier")
    role: UserRole = Field(..., description="User role")
    status: UserStatus = Field(..., description="User account status")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    mfa_enabled: bool = Field(False, description="Whether MFA is enabled")
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "user_123",
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "tenant_id": "tenant_456",
                "role": "user",
                "status": "active",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "mfa_enabled": False
            }
        }

class TokenResponse(BaseModel):
    """Model for authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: User = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "user_123",
                    "email": "john.doe@example.com",
                    "first_name": "John",
                    "last_name": "Doe"
                }
            }
        }

class RefreshTokenRequest(BaseModel):
    """Model for token refresh request"""
    refresh_token: str = Field(..., description="JWT refresh token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }

class PasswordResetRequest(BaseModel):
    """Model for password reset request"""
    email: EmailStr = Field(..., description="User email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com"
            }
        }

class PasswordResetConfirm(BaseModel):
    """Model for password reset confirmation"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "reset_token_123",
                "new_password": "newsecurepassword123"
            }
        }

class MagicLinkRequest(BaseModel):
    """Model for magic link request"""
    email: EmailStr = Field(..., description="User email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com"
            }
        }

class MagicLinkVerify(BaseModel):
    """Model for magic link verification"""
    token: str = Field(..., description="Magic link token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "magic_token_123"
            }
        }

class MFAEnableRequest(BaseModel):
    """Model for enabling MFA"""
    password: str = Field(..., description="Current password for verification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "password": "currentpassword123"
            }
        }

class MFAVerifyRequest(BaseModel):
    """Model for MFA verification"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit MFA code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "123456"
            }
        }

class SessionInfo(BaseModel):
    """Model for session information"""
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    created_at: datetime = Field(..., description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    ip_address: Optional[str] = Field(None, description="IP address of session")
    user_agent: Optional[str] = Field(None, description="User agent string")
    is_active: bool = Field(..., description="Whether session is active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "user_id": "user_456",
                "tenant_id": "tenant_789",
                "created_at": "2024-01-01T00:00:00Z",
                "expires_at": "2024-01-01T23:59:59Z",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "is_active": True
            }
        }
