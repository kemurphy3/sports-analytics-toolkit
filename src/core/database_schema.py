#!/usr/bin/env python3
"""
Database schema management for multi-tenant fitness platform
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

logger = logging.getLogger(__name__)

class DatabaseSchemaManager:
    """Manages database schema creation and migrations"""
    
    def __init__(self, database_path: str = "data/athlete_performance.db"):
        self.database_path = database_path
        self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
    
    def initialize_schema(self):
        """Initialize the complete database schema"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Create new multi-tenant tables
                self._create_users_table(conn)
                self._create_athletes_table(conn)
                self._create_sources_table(conn)
                self._create_sync_jobs_table(conn)
                
                # Create existing tables with tenant support
                self._create_workouts_table(conn)
                self._create_biometrics_table(conn)
                self._create_athlete_profiles_table(conn)
                self._create_calorie_calibration_table(conn)
                self._create_weather_cache_table(conn)
                self._create_elevation_cache_table(conn)
                
                # Create indexes for performance
                self._create_indexes(conn)
                
                # Insert default tenant and user
                self._insert_default_data(conn)
                
                logger.info("Database schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    def _create_users_table(self, conn: sqlite3.Connection):
        """Create users table for authentication"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mfa_secret TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")
    
    def _create_athletes_table(self, conn: sqlite3.Connection):
        """Create athletes table linked to users"""
        conn.execute("""
                    CREATE TABLE IF NOT EXISTS athletes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                profile_data TEXT, -- JSON string
                settings TEXT, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_athletes_user ON athletes(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_athletes_active ON athletes(is_active)")
    
    def _create_sources_table(self, conn: sqlite3.Connection):
        """Create data sources table for OAuth connections"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                provider TEXT NOT NULL, -- 'strava', 'garmin', etc.
                oauth_tokens_encrypted TEXT NOT NULL, -- Encrypted OAuth tokens
                refresh_token_encrypted TEXT,
                expires_at TIMESTAMP,
                last_sync TIMESTAMP,
                status TEXT DEFAULT 'active', -- 'active', 'error', 'needs_reauth'
                sync_frequency_minutes INTEGER DEFAULT 1440, -- 24 hours
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_details TEXT, -- JSON string with error info
                rate_limit_remaining INTEGER,
                rate_limit_reset TIMESTAMP,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_athlete ON sources(athlete_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_provider ON sources(provider)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_last_sync ON sources(last_sync)")
    
    def _create_sync_jobs_table(self, conn: sqlite3.Connection):
        """Create sync jobs table for tracking background operations"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_jobs (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'running', 'completed', 'failed'
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_details TEXT, -- JSON string
                records_processed INTEGER DEFAULT 0,
                records_created INTEGER DEFAULT 0,
                records_updated INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_source ON sync_jobs(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_created ON sync_jobs(created_at)")
    
    def _create_workouts_table(self, conn: sqlite3.Connection):
        """Create workouts table with tenant isolation"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                workout_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                sport TEXT NOT NULL,
                sport_category TEXT,
                distance REAL,
                duration INTEGER,
                calories INTEGER,
                heart_rate_avg REAL,
                heart_rate_max REAL,
                elevation_gain REAL,
                average_speed REAL,
                max_speed REAL,
                average_cadence REAL,
                external_ids TEXT, -- JSON array of external IDs
                location_data TEXT, -- JSON string
                data_source TEXT NOT NULL,
                raw_data TEXT, -- JSON string
                data_quality_score REAL DEFAULT 1.0,
                ml_features_extracted BOOLEAN DEFAULT FALSE,
                plugin_data TEXT, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_athlete ON workouts(athlete_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_source ON workouts(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_start_time ON workouts(start_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_sport ON workouts(sport)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_external_ids ON workouts(external_ids)")
    
    def _create_biometrics_table(self, conn: sqlite3.Connection):
        """Create biometrics table with tenant isolation"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS biometrics (
                reading_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                metric TEXT NOT NULL, -- 'weight', 'body_fat', 'hrv', 'sleep'
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                original_unit TEXT, -- Store original unit for reference
                confidence REAL DEFAULT 1.0,
                data_source TEXT NOT NULL,
                device_id TEXT,
                raw_data TEXT, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
                    )
                """)
                
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_athlete ON biometrics(athlete_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_source ON biometrics(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_timestamp ON biometrics(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_metric ON biometrics(metric)")
    
    def _create_athlete_profiles_table(self, conn: sqlite3.Connection):
        """Create athlete profiles table for personalized calculations"""
        conn.execute("""
                    CREATE TABLE IF NOT EXISTS athlete_profiles (
                id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                age INTEGER,
                gender TEXT CHECK(gender IN ('male', 'female', 'other')),
                weight_kg REAL,
                        height_cm REAL,
                        vo2max REAL,
                        resting_hr INTEGER,
                        max_hr INTEGER,
                activity_level TEXT CHECK(activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
                    )
                """)
                
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_athlete ON athlete_profiles(athlete_id)")
    
    def _create_calorie_calibration_table(self, conn: sqlite3.Connection):
        """Create calorie calibration table for per-athlete adjustments"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calorie_calibration (
                id TEXT PRIMARY KEY,
                        athlete_id TEXT NOT NULL,
                        sport_category TEXT NOT NULL,
                        calibration_factor REAL DEFAULT 1.0,
                        sample_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
                    )
                """)
                
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calibration_athlete ON calorie_calibration(athlete_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calibration_sport ON calorie_calibration(sport_category)")
    
    def _create_weather_cache_table(self, conn: sqlite3.Connection):
        """Create weather cache table for location-based data"""
        conn.execute("""
                    CREATE TABLE IF NOT EXISTS weather_cache (
                id TEXT PRIMARY KEY,
                location_hash TEXT NOT NULL, -- Hash of lat/lng
                date DATE NOT NULL,
                weather_data TEXT NOT NULL, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
                    )
                """)
                
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_cache(location_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_cache(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_expires ON weather_cache(expires_at)")
    
    def _create_elevation_cache_table(self, conn: sqlite3.Connection):
        """Create elevation cache table for GPS data"""
        conn.execute("""
                    CREATE TABLE IF NOT EXISTS elevation_cache (
                id TEXT PRIMARY KEY,
                location_hash TEXT NOT NULL, -- Hash of lat/lng
                elevation REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_elevation_location ON elevation_cache(location_hash)")
    
    def _create_indexes(self, conn: sqlite3.Connection):
        """Create additional performance indexes"""
        # Composite indexes for common queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_athlete_date ON workouts(athlete_id, start_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_athlete_sport ON workouts(athlete_id, sport)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_athlete_metric ON biometrics(athlete_id, metric)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_athlete_provider ON sources(athlete_id, provider)")
    
    def _insert_default_data(self, conn: sqlite3.Connection):
        """Insert default tenant and user for development"""
        try:
            # Insert default tenant (using 'default' as tenant_id)
            conn.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, tenant_id, created_at)
                VALUES ('default_user', 'admin@example.com', 'default_hash', 'default', CURRENT_TIMESTAMP)
            """)
            
            # Insert default athlete
            conn.execute("""
                INSERT OR IGNORE INTO athletes (id, user_id, name, created_at)
                VALUES ('default_athlete', 'default_user', 'Default Athlete', CURRENT_TIMESTAMP)
            """)
            
            # Insert default profile
            conn.execute("""
                INSERT OR IGNORE INTO athlete_profiles (id, athlete_id, age, gender, weight_kg, height_cm, activity_level, created_at)
                VALUES ('default_profile', 'default_athlete', 30, 'male', 75.0, 180.0, 'moderate', CURRENT_TIMESTAMP)
            """)
            
            conn.commit()
            logger.info("Default data inserted successfully")
                
        except Exception as e:
            logger.warning(f"Failed to insert default data: {e}")
    
    def migrate_to_multi_tenant(self):
        """Migrate existing single-tenant data to multi-tenant structure"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Check if migration is needed
                cursor = conn.execute("PRAGMA table_info(workouts)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'athlete_id' not in columns:
                    logger.info("Adding athlete_id column to workouts table")
                    conn.execute("ALTER TABLE workouts ADD COLUMN athlete_id TEXT DEFAULT 'default_athlete'")
                    
                    # Update existing workouts to use default athlete
                    conn.execute("UPDATE workouts SET athlete_id = 'default_athlete' WHERE athlete_id IS NULL")
                    
                    # Create index on athlete_id
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_athlete_id ON workouts(athlete_id)")
                
                # Check biometrics table
                cursor = conn.execute("PRAGMA table_info(biometrics)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'athlete_id' not in columns:
                    logger.info("Adding athlete_id column to biometrics table")
                    conn.execute("ALTER TABLE biometrics ADD COLUMN athlete_id TEXT DEFAULT 'default_athlete'")
                    
                    # Update existing biometrics to use default athlete
                    conn.execute("UPDATE biometrics SET athlete_id = 'default_athlete' WHERE athlete_id IS NULL")
                    
                    # Create index on athlete_id
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_biometrics_athlete_id ON biometrics(athlete_id)")
                
                # Check if source_id columns exist
                if 'source_id' not in columns:
                    logger.info("Adding source_id column to workouts table")
                    conn.execute("ALTER TABLE workouts ADD COLUMN source_id TEXT DEFAULT 'default_source'")
                
                cursor = conn.execute("PRAGMA table_info(biometrics)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'source_id' not in columns:
                    logger.info("Adding source_id column to biometrics table")
                    conn.execute("ALTER TABLE biometrics ADD COLUMN source_id TEXT DEFAULT 'default_source'")
                
                # Create default source if it doesn't exist
                conn.execute("""
                    INSERT OR IGNORE INTO sources (id, athlete_id, provider, oauth_tokens_encrypted, status, created_at)
                    VALUES ('default_source', 'default_athlete', 'strava', 'default_encrypted', 'active', CURRENT_TIMESTAMP)
                """)
                
                conn.commit()
                logger.info("Migration to multi-tenant completed successfully")
                
        except Exception as e:
            logger.error(f"Failed to migrate to multi-tenant: {e}")
            raise
    
    def get_schema_version(self) -> str:
        """Get current database schema version"""
        try:
            with sqlite3.connect(self.database_path) as conn:
                # Create schema_version table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor = conn.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    # Insert initial version
                    conn.execute("INSERT INTO schema_version (version) VALUES ('1.0.0')")
                    conn.commit()
                    return "1.0.0"
                    
        except Exception as e:
            logger.error(f"Failed to get schema version: {e}")
            return "unknown"
    
    def upgrade_schema(self, target_version: str):
        """Upgrade schema to target version"""
        current_version = self.get_schema_version()
        logger.info(f"Upgrading schema from {current_version} to {target_version}")
        
        # Add upgrade logic here as needed
        # For now, just update the version
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (target_version,))
                conn.commit()
                logger.info(f"Schema upgraded to {target_version}")
        except Exception as e:
            logger.error(f"Failed to upgrade schema: {e}")
            raise
