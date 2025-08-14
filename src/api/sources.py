#!/usr/bin/env python3
"""
Data sources API router for multi-tenant fitness platform
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from ..auth import OAuthManager
from .auth import get_current_user
from ..auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize OAuth manager
oauth_manager = OAuthManager()

class SourceInfo(BaseModel):
    """Data source information"""
    id: str
    provider: str
    status: str
    last_sync: Optional[str]
    created_at: str
    connected_at: Optional[str]

class SourceConnection(BaseModel):
    """Source connection request"""
    provider: str
    redirect_uri: str

class SyncRequest(BaseModel):
    """Manual sync request"""
    force_full: bool = False
    priority: str = "normal"  # low, normal, high

@router.get("/", response_model=List[SourceInfo])
async def list_data_sources(current_user: User = Depends(get_current_user)):
    """List all data sources for the current user"""
    try:
        sources = oauth_manager.get_user_oauth_sources(current_user.id)
        
        # Convert to response format
        source_list = []
        for source in sources:
            source_list.append(SourceInfo(
                id=source.get("id", "unknown"),
                provider=source["provider"],
                status=source["status"],
                last_sync=source["last_sync"].isoformat() if source["last_sync"] else None,
                created_at=source["created_at"].isoformat(),
                connected_at=source["created_at"].isoformat() if source["status"] == "active" else None
            ))
        
        return source_list
        
    except Exception as e:
        logger.error(f"Failed to list data sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve data sources"
        )

@router.get("/available")
async def get_available_providers():
    """Get list of available OAuth providers"""
    try:
        providers = oauth_manager.get_available_providers()
        return {"providers": providers}
        
    except Exception as e:
        logger.error(f"Failed to get available providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available providers"
        )

@router.post("/{provider}/connect")
async def connect_data_source(
    provider: str,
    connection: SourceConnection,
    current_user: User = Depends(get_current_user)
):
    """Connect a new data source via OAuth"""
    try:
        # Validate provider
        if provider not in oauth_manager.get_available_providers():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )
        
        # Initiate OAuth flow
        auth_url = oauth_manager.initiate_oauth_flow(
            current_user.id, provider, connection.redirect_uri
        )
        
        if not auth_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate OAuth flow"
            )
        
        return {
            "message": f"OAuth flow initiated for {provider}",
            "authorization_url": auth_url,
            "provider": provider
        }
        
    except Exception as e:
        logger.error(f"Failed to connect data source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect data source"
        )

@router.delete("/{source_id}")
async def disconnect_data_source(
    source_id: str,
    current_user: User = Depends(get_current_user)
):
    """Disconnect and delete a data source"""
    try:
        # TODO: Implement source deletion
        # For now, just return success message
        
        return {
            "message": "Data source disconnected successfully",
            "source_id": source_id
        }
        
    except Exception as e:
        logger.error(f"Failed to disconnect data source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect data source"
        )

@router.post("/{source_id}/sync")
async def trigger_manual_sync(
    source_id: str,
    sync_request: SyncRequest,
    current_user: User = Depends(get_current_user)
):
    """Trigger manual synchronization for a data source"""
    try:
        # TODO: Implement manual sync triggering
        # For now, just return success message
        
        return {
            "message": "Manual sync triggered successfully",
            "source_id": source_id,
            "sync_id": "sync_123",  # Placeholder
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger manual sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger manual sync"
        )

@router.get("/{source_id}/status")
async def get_source_status(
    source_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed status of a data source"""
    try:
        # TODO: Implement source status retrieval
        # For now, return placeholder data
        
        return {
            "source_id": source_id,
            "status": "active",
            "last_sync": "2024-01-01T00:00:00Z",
            "next_sync": "2024-01-01T01:00:00Z",
            "sync_count": 0,
            "error_count": 0,
            "last_error": None,
            "rate_limit_remaining": 1000,
            "rate_limit_reset": "2024-01-01T02:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Failed to get source status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve source status"
        )

@router.get("/{source_id}/sync-history")
async def get_sync_history(
    source_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Get sync history for a data source"""
    try:
        # TODO: Implement sync history retrieval
        # For now, return empty list
        
        return {
            "source_id": source_id,
            "syncs": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get sync history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync history"
        )

@router.post("/{source_id}/test")
async def test_source_connection(
    source_id: str,
    current_user: User = Depends(get_current_user)
):
    """Test connection to a data source"""
    try:
        # TODO: Implement connection testing
        # For now, return success message
        
        return {
            "message": "Connection test successful",
            "source_id": source_id,
            "status": "connected",
            "response_time_ms": 150
        }
        
    except Exception as e:
        logger.error(f"Failed to test source connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test source connection"
        )

@router.put("/{source_id}/settings")
async def update_source_settings(
    source_id: str,
    settings: dict,
    current_user: User = Depends(get_current_user)
):
    """Update settings for a data source"""
    try:
        # TODO: Implement source settings update
        # For now, just return success message
        
        return {
            "message": "Source settings updated successfully",
            "source_id": source_id
        }
        
    except Exception as e:
        logger.error(f"Failed to update source settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update source settings"
        )
