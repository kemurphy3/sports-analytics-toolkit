#!/usr/bin/env python3
"""
Authentication API router for multi-tenant fitness platform
"""

import os
import logging
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import EmailStr

from ..auth import AuthManager, OAuthManager
from ..auth.models import (
    UserCreate, UserLogin, TokenResponse, UserUpdate,
    PasswordResetRequest, PasswordResetConfirm,
    MagicLinkRequest, MagicLinkVerify
)

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

# Initialize managers
auth_manager = AuthManager()
oauth_manager = OAuthManager()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    try:
        token = credentials.credentials
        user = auth_manager.get_current_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """Register a new user account"""
    try:
        # Create user
        user = auth_manager.create_user(user_data)
        
        # Create default athlete profile
        # TODO: Implement athlete creation
        
        return {
            "message": "User registered successfully",
            "user_id": user.id,
            "email": user.email,
            "status": "pending_verification"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"User registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )

@router.post("/login", response_model=TokenResponse)
async def login_user(user_login: UserLogin):
    """Authenticate user and return access tokens"""
    try:
        token_response = auth_manager.login_user(user_login)
        if not token_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        return token_response
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )

@router.post("/refresh", response_model=dict)
async def refresh_access_token(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        new_access_token = auth_manager.refresh_access_token(refresh_token)
        if not new_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed. Please try again."
        )

@router.post("/logout")
async def logout_user(current_user = Depends(get_current_user)):
    """Logout user and revoke refresh tokens"""
    try:
        # Revoke all user sessions
        auth_manager.revoke_all_user_sessions(current_user.id)
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed. Please try again."
        )

@router.post("/password-reset/request")
async def request_password_reset(reset_request: PasswordResetRequest):
    """Request password reset via email"""
    try:
        # TODO: Implement email sending with reset token
        # For now, just return success message
        
        return {
            "message": "If an account with this email exists, a password reset link has been sent."
        }
        
    except Exception as e:
        logger.error(f"Password reset request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed. Please try again."
        )

@router.post("/password-reset/confirm")
async def confirm_password_reset(reset_confirm: PasswordResetConfirm):
    """Confirm password reset with token"""
    try:
        # TODO: Implement password reset confirmation
        # For now, just return success message
        
        return {"message": "Password reset successfully"}
        
    except Exception as e:
        logger.error(f"Password reset confirmation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset confirmation failed. Please try again."
        )

@router.post("/magic-link/request")
async def request_magic_link(magic_request: MagicLinkRequest):
    """Request magic link login via email"""
    try:
        # TODO: Implement email sending with magic link
        # For now, just return success message
        
        return {
            "message": "If an account with this email exists, a magic link has been sent."
        }
        
    except Exception as e:
        logger.error(f"Magic link request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Magic link request failed. Please try again."
        )

@router.post("/magic-link/verify")
async def verify_magic_link(magic_verify: MagicLinkVerify):
    """Verify magic link and return access tokens"""
    try:
        # TODO: Implement magic link verification
        # For now, just return error
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Magic link verification not yet implemented"
        )
        
    except Exception as e:
        logger.error(f"Magic link verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Magic link verification failed. Please try again."
        )

@router.get("/oauth/{provider}/authorize")
async def initiate_oauth_flow(
    provider: str,
    redirect_uri: str,
    current_user = Depends(get_current_user)
):
    """Initiate OAuth flow for a provider"""
    try:
        # Validate provider
        if provider not in oauth_manager.get_available_providers():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth provider: {provider}"
            )
        
        # Initiate OAuth flow
        auth_url = oauth_manager.initiate_oauth_flow(
            current_user.id, provider, redirect_uri
        )
        
        if not auth_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate OAuth flow"
            )
        
        return {"authorization_url": auth_url}
        
    except Exception as e:
        logger.error(f"OAuth initiation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth initiation failed. Please try again."
        )

@router.get("/oauth/{provider}/callback")
async def complete_oauth_flow(
    provider: str,
    state: str,
    code: str
):
    """Complete OAuth flow with authorization code"""
    try:
        # Complete OAuth flow
        result = oauth_manager.complete_oauth_flow(state, code, provider)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state"
            )
        
        return {
            "message": f"Successfully connected {provider}",
            "provider": provider,
            "status": "connected"
        }
        
    except Exception as e:
        logger.error(f"OAuth completion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth completion failed. Please try again."
        )

@router.get("/profile", response_model=dict)
async def get_user_profile(current_user = Depends(get_current_user)):
    """Get current user profile"""
    try:
        return {
            "id": current_user.id,
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "role": current_user.role.value,
            "status": current_user.status.value,
            "created_at": current_user.created_at.isoformat(),
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None
        }
        
    except Exception as e:
        logger.error(f"Profile retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile retrieval failed. Please try again."
        )

@router.put("/profile", response_model=dict)
async def update_user_profile(
    user_update: UserUpdate,
    current_user = Depends(get_current_user)
):
    """Update current user profile"""
    try:
        updated_user = auth_manager.update_user(current_user.id, user_update)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Profile update failed"
            )
        
        return {
            "message": "Profile updated successfully",
            "user_id": updated_user.id
        }
        
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed. Please try again."
        )

@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(current_user = Depends(get_current_user)):
    """Delete current user account and all associated data"""
    try:
        # TODO: Implement GDPR-compliant data deletion
        # For now, just return success
        
        return {"message": "Account deletion not yet implemented"}
        
    except Exception as e:
        logger.error(f"Account deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed. Please try again."
        )
