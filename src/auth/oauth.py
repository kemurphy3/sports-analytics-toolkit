#!/usr/bin/env python3
"""
OAuth manager for multi-tenant fitness platform
"""

import os
import uuid
import hashlib
import secrets
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
from urllib.parse import urlencode, parse_qs, urlparse
import requests

logger = logging.getLogger(__name__)

class OAuthProvider:
    """Base class for OAuth providers"""
    
    def __init__(self, name: str, client_id: str, client_secret: str, 
                 auth_url: str, token_url: str, scope: str = ""):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.scope = scope
    
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth authorization URL"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state,
            'scope': self.scope
        }
        
        # Add PKCE for enhanced security
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge_method = 'S256'
        
        params.update({
            'code_challenge': code_challenge.hex(),
            'code_challenge_method': code_challenge_method
        })
        
        return f"{self.auth_url}?{urlencode(params)}", code_verifier
    
    def exchange_code_for_tokens(self, code: str, redirect_uri: str, 
                                code_verifier: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access tokens"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code_verifier': code_verifier
            }
            
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            return None
    
    def refresh_tokens(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
            
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to refresh tokens: {e}")
            return None

class StravaOAuthProvider(OAuthProvider):
    """Strava OAuth provider implementation"""
    
    def __init__(self):
        super().__init__(
            name="strava",
            client_id=os.getenv("STRAVA_CLIENT_ID", ""),
            client_secret=os.getenv("STRAVA_CLIENT_SECRET", ""),
            auth_url="https://www.strava.com/oauth/authorize",
            token_url="https://www.strava.com/oauth/token",
            scope="read,activity:read_all,profile:read_all"
        )

class GarminOAuthProvider(OAuthProvider):
    """Garmin OAuth provider implementation"""
    
    def __init__(self):
        super().__init__(
            name="garmin",
            client_id=os.getenv("GARMIN_CLIENT_ID", ""),
            client_secret=os.getenv("GARMIN_CLIENT_SECRET", ""),
            auth_url="https://connect.garmin.com/oauthConfirm",
            token_url="https://connect.garmin.com/oauth/token",
            scope=""
        )

class OAuthManager:
    """Manages OAuth flows and token storage"""
    
    def __init__(self, database_path: str = "data/athlete_performance.db"):
        self.database_path = database_path
        
        # Initialize encryption key
        self.encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY")
        if not self.encryption_key:
            # Generate a new key if none exists
            self.encryption_key = Fernet.generate_key()
            logger.warning("Generated new OAuth encryption key. Set OAUTH_ENCRYPTION_KEY env var for production.")
        
        self.cipher = Fernet(self.encryption_key)
        
        # Initialize OAuth providers
        self.providers = {
            "strava": StravaOAuthProvider(),
            "garmin": GarminOAuthProvider()
        }
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize OAuth database tables"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Create OAuth states table for CSRF protection
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS oauth_states (
                        id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        code_verifier TEXT NOT NULL,
                        redirect_uri TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_state ON oauth_states(state)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_user ON oauth_states(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON oauth_states(expires_at)")
                
                conn.commit()
                logger.info("OAuth database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize OAuth database: {e}")
            raise
    
    def _encrypt_tokens(self, tokens: Dict[str, Any]) -> str:
        """Encrypt OAuth tokens for secure storage"""
        try:
            token_json = json.dumps(tokens)
            encrypted_data = self.cipher.encrypt(token_json.encode())
            return encrypted_data.hex()
        except Exception as e:
            logger.error(f"Failed to encrypt tokens: {e}")
            raise
    
    def _decrypt_tokens(self, encrypted_tokens: str) -> Optional[Dict[str, Any]]:
        """Decrypt OAuth tokens from storage"""
        try:
            encrypted_data = bytes.fromhex(encrypted_tokens)
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt tokens: {e}")
            return None
    
    def get_provider(self, provider_name: str) -> Optional[OAuthProvider]:
        """Get OAuth provider by name"""
        return self.providers.get(provider_name)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available OAuth providers"""
        return list(self.providers.keys())
    
    def initiate_oauth_flow(self, user_id: str, provider_name: str, 
                           redirect_uri: str) -> Optional[str]:
        """Initiate OAuth flow for a user"""
        try:
            provider = self.get_provider(provider_name)
            if not provider:
                raise ValueError(f"Unknown OAuth provider: {provider_name}")
            
            # Generate state for CSRF protection
            state = secrets.token_urlsafe(32)
            
            # Generate authorization URL
            auth_url, code_verifier = provider.get_authorization_url(redirect_uri, state)
            
            # Store OAuth state
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    INSERT INTO oauth_states (
                        id, state, user_id, provider, code_verifier, 
                        redirect_uri, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), state, user_id, provider_name,
                    code_verifier, redirect_uri,
                    datetime.now() + timedelta(minutes=10)  # 10 minute expiry
                ))
                conn.commit()
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Failed to initiate OAuth flow: {e}")
            return None
    
    def complete_oauth_flow(self, state: str, code: str, 
                           provider_name: str) -> Optional[Dict[str, Any]]:
        """Complete OAuth flow and store tokens"""
        try:
            # Verify OAuth state
            oauth_state = self._verify_oauth_state(state, provider_name)
            if not oauth_state:
                raise ValueError("Invalid or expired OAuth state")
            
            # Get provider
            provider = self.get_provider(provider_name)
            if not provider:
                raise ValueError(f"Unknown OAuth provider: {provider_name}")
            
            # Exchange code for tokens
            tokens = provider.exchange_code_for_tokens(
                code, oauth_state['redirect_uri'], oauth_state['code_verifier']
            )
            
            if not tokens:
                raise ValueError("Failed to exchange code for tokens")
            
            # Store tokens in sources table
            self._store_oauth_tokens(
                oauth_state['user_id'], provider_name, tokens
            )
            
            # Mark OAuth state as used
            self._mark_oauth_state_used(state)
            
            return {
                "user_id": oauth_state['user_id'],
                "provider": provider_name,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to complete OAuth flow: {e}")
            return None
    
    def _verify_oauth_state(self, state: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Verify OAuth state and return state data"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT user_id, provider, code_verifier, redirect_uri, 
                           expires_at, used
                    FROM oauth_states 
                    WHERE state = ? AND provider = ?
                """, (state, provider_name))
                
                row = cursor.fetchone()
                if row:
                    user_id, provider, code_verifier, redirect_uri, expires_at, used = row
                    
                    # Check if state is used or expired
                    if used or datetime.now() > datetime.fromisoformat(expires_at):
                        return None
                    
                    return {
                        "user_id": user_id,
                        "provider": provider,
                        "code_verifier": code_verifier,
                        "redirect_uri": redirect_uri
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to verify OAuth state: {e}")
            return None
    
    def _mark_oauth_state_used(self, state: str):
        """Mark OAuth state as used"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE oauth_states 
                    SET used = TRUE
                    WHERE state = ?
                """, (state,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark OAuth state as used: {e}")
    
    def _store_oauth_tokens(self, user_id: str, provider: str, tokens: Dict[str, Any]):
        """Store OAuth tokens in sources table"""
        try:
            # Encrypt tokens
            encrypted_tokens = self._encrypt_tokens(tokens)
            
            # Get athlete ID for user
            athlete_id = self._get_athlete_id_for_user(user_id)
            if not athlete_id:
                raise ValueError(f"No athlete found for user: {user_id}")
            
            with sqlite3.connect(self.database_path) as conn:
                # Check if source already exists
                cursor = conn.execute("""
                    SELECT id FROM sources 
                    WHERE athlete_id = ? AND provider = ?
                """, (athlete_id, provider))
                
                existing_source = cursor.fetchone()
                
                if existing_source:
                    # Update existing source
                    conn.execute("""
                        UPDATE sources 
                        SET oauth_tokens_encrypted = ?, 
                            refresh_token_encrypted = ?,
                            expires_at = ?,
                            last_sync = NULL,
                            status = 'active',
                            updated_at = ?
                        WHERE athlete_id = ? AND provider = ?
                    """, (
                        encrypted_tokens,
                        tokens.get('refresh_token', ''),
                        datetime.fromtimestamp(tokens.get('expires_at', 0)) if tokens.get('expires_at') else None,
                        datetime.now(),
                        athlete_id, provider
                    ))
                else:
                    # Create new source
                    conn.execute("""
                        INSERT INTO sources (
                            id, athlete_id, provider, oauth_tokens_encrypted,
                            refresh_token_encrypted, expires_at, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), athlete_id, provider, encrypted_tokens,
                        tokens.get('refresh_token', ''),
                        datetime.fromtimestamp(tokens.get('expires_at', 0)) if tokens.get('expires_at') else None,
                        'active', datetime.now(), datetime.now()
                    ))
                
                conn.commit()
                logger.info(f"Stored OAuth tokens for {provider} for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to store OAuth tokens: {e}")
            raise
    
    def _get_athlete_id_for_user(self, user_id: str) -> Optional[str]:
        """Get athlete ID for a user"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT id FROM athletes 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Failed to get athlete ID for user: {e}")
            return None
    
    def get_oauth_tokens(self, athlete_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Get OAuth tokens for an athlete and provider"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT oauth_tokens_encrypted, refresh_token_encrypted, expires_at
                    FROM sources 
                    WHERE athlete_id = ? AND provider = ?
                """, (athlete_id, provider))
                
                row = cursor.fetchone()
                if row:
                    encrypted_tokens, refresh_token, expires_at = row
                    
                    # Decrypt tokens
                    tokens = self._decrypt_tokens(encrypted_tokens)
                    if tokens:
                        tokens['refresh_token'] = refresh_token
                        tokens['expires_at'] = expires_at
                        return tokens
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get OAuth tokens: {e}")
            return None
    
    def refresh_oauth_tokens(self, athlete_id: str, provider: str) -> bool:
        """Refresh OAuth tokens for an athlete and provider"""
        try:
            # Get current tokens
            tokens = self.get_oauth_tokens(athlete_id, provider)
            if not tokens or not tokens.get('refresh_token'):
                return False
            
            # Get provider
            oauth_provider = self.get_provider(provider)
            if not oauth_provider:
                return False
            
            # Refresh tokens
            new_tokens = oauth_provider.refresh_tokens(tokens['refresh_token'])
            if not new_tokens:
                return False
            
            # Store new tokens
            self._store_oauth_tokens(athlete_id, provider, new_tokens)
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh OAuth tokens: {e}")
            return False
    
    def revoke_oauth_access(self, athlete_id: str, provider: str) -> bool:
        """Revoke OAuth access for an athlete and provider"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    UPDATE sources 
                    SET status = 'revoked', updated_at = ?
                    WHERE athlete_id = ? AND provider = ?
                """, (datetime.now(), athlete_id, provider))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke OAuth access: {e}")
            return False
    
    def cleanup_expired_oauth_states(self):
        """Clean up expired OAuth states"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("""
                    DELETE FROM oauth_states 
                    WHERE expires_at < ?
                """, (datetime.now(),))
                conn.commit()
                logger.info("Cleaned up expired OAuth states")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired OAuth states: {e}")
    
    def get_user_oauth_sources(self, user_id: str) -> List[Dict[str, Any]]:
        """Get OAuth sources for a user"""
        try:
            athlete_id = self._get_athlete_id_for_user(user_id)
            if not athlete_id:
                return []
            
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute("""
                    SELECT provider, status, last_sync, created_at
                    FROM sources 
                    WHERE athlete_id = ?
                    ORDER BY created_at DESC
                """, (athlete_id,))
                
                sources = []
                for row in cursor.fetchall():
                    sources.append({
                        "provider": row[0],
                        "status": row[1],
                        "last_sync": datetime.fromisoformat(row[2]) if row[2] else None,
                        "created_at": datetime.fromisoformat(row[3])
                    })
                
                return sources
                
        except Exception as e:
            logger.error(f"Failed to get user OAuth sources: {e}")
            return []
    
    def check_token_expiry(self, athlete_id: str, provider: str) -> bool:
        """Check if OAuth tokens are expired and need refresh"""
        try:
            tokens = self.get_oauth_tokens(athlete_id, provider)
            if not tokens or not tokens.get('expires_at'):
                return True
            
            # Check if token expires within 1 hour
            expiry_time = tokens['expires_at']
            if isinstance(expiry_time, str):
                expiry_time = datetime.fromisoformat(expiry_time)
            
            return datetime.now() + timedelta(hours=1) > expiry_time
            
        except Exception as e:
            logger.error(f"Failed to check token expiry: {e}")
            return True
