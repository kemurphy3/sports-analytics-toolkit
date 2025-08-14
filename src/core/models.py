#!/usr/bin/env python3
"""
Minimal Data Models for Multi-Source Fitness Data Platform
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum

class Workout(BaseModel):
    """Workout data model - now supports multi-athlete"""
    workout_id: str = Field(..., description="Unique workout identifier")
    athlete_id: str = Field(..., description="Unique athlete identifier")
    source_id: Optional[str] = Field(None, description="Source identifier")
    start_time: datetime = Field(..., description="Workout start time")
    end_time: Optional[datetime] = Field(None, description="Workout end time")
    duration: int = Field(..., description="Duration in seconds")
    sport: str = Field(..., description="Sport/activity type")
    sport_category: Optional[str] = Field(None, description="Sport category")
    distance: Optional[float] = Field(None, description="Distance in meters")
    calories: Optional[int] = Field(None, description="Calories burned")
    heart_rate_avg: Optional[float] = Field(None, description="Average heart rate")
    heart_rate_max: Optional[float] = Field(None, description="Maximum heart rate")
    elevation_gain: Optional[float] = Field(None, description="Elevation gain in meters")
    power_avg: Optional[float] = Field(None, description="Average power in watts")
    cadence_avg: Optional[float] = Field(None, description="Average cadence")
    training_load: Optional[float] = Field(None, description="Training load score")
    perceived_exertion: Optional[int] = Field(None, description="Perceived exertion (1-10)")
    has_gps: bool = Field(False, description="Whether workout has GPS data")
    route_hash: Optional[str] = Field(None, description="Route hash for deduplication")
    gps_data: Optional[str] = Field(None, description="GPS data as JSON string")
    source: str = Field(..., description="Data source (strava, vesync, etc.)")
    external_ids: str = Field(default="{}", description="External IDs as JSON string")
    raw_data: Optional[str] = Field(None, description="Raw data from source as JSON string")
    data_quality_score: float = Field(0.8, description="Data quality score (0-1)")
    ml_features_extracted: bool = Field(False, description="Whether ML features extracted")
    plugin_data: str = Field(default="{}", description="Plugin-specific data as JSON string")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")

class BiometricReading(BaseModel):
    """Biometric reading model - now supports multi-athlete"""
    reading_id: str = Field(..., description="Unique reading identifier")
    athlete_id: str = Field(..., description="Unique athlete identifier")
    source_id: str = Field(..., description="Source identifier")
    timestamp: datetime = Field(..., description="Reading timestamp")
    metric: str = Field(..., description="Metric type (weight, body_fat, etc.)")
    value: float = Field(..., description="Metric value")
    unit: str = Field(..., description="Unit of measurement")
    original_unit: Optional[str] = Field(None, description="Original unit before conversion")
    confidence: Optional[float] = Field(1.0, description="Confidence in the reading")
    data_source: str = Field(..., description="Data source")
    device_id: Optional[str] = Field(None, description="Device identifier")
    raw_data: Optional[str] = Field(None, description="Raw data from source as JSON string")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")

class SyncStatus(BaseModel):
    """Status of data synchronization for each source"""
    
    data_source: str = Field(..., description="Data source name")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    status: str = Field("pending", description="Current sync status")
    error_message: Optional[str] = Field(None, description="Last error message if any")
    sync_count: int = Field(0, description="Number of successful syncs")
    last_error: Optional[datetime] = Field(None, description="Last error occurrence")

class DataSource(BaseModel):
    """Configuration for a data source"""
    
    name: str = Field(..., description="Source name")
    enabled: bool = Field(True, description="Whether source is enabled")
    priority: int = Field(0, description="Priority for deduplication (lower = higher priority)")
    sync_interval_hours: int = Field(24, description="Sync interval in hours")
    last_sync: Optional[datetime] = Field(None, description="Last sync time")
    auth_token: Optional[str] = Field(None, description="Encrypted authentication token")
    refresh_token: Optional[str] = Field(None, description="Encrypted refresh token")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")

class WorkoutSummary(BaseModel):
    """Summary statistics for workouts"""
    
    total_workouts: int = Field(0, description="Total number of workouts")
    total_duration: int = Field(0, description="Total duration in seconds")
    total_distance: float = Field(0.0, description="Total distance in meters")
    total_calories: int = Field(0, description="Total calories burned")
    sport_breakdown: Dict[str, int] = Field(default_factory=dict, description="Workouts by sport")
    category_breakdown: Dict[str, int] = Field(default_factory=dict, description="Workouts by category")
    source_breakdown: Dict[str, int] = Field(default_factory=dict, description="Workouts by source")
    weekly_workouts: Dict[str, int] = Field(default_factory=dict, description="Workouts by week")
    monthly_workouts: Dict[str, int] = Field(default_factory=dict, description="Workouts by month")

class BiometricSummary(BaseModel):
    """Summary statistics for biometric readings"""
    
    total_readings: int = Field(0, description="Total number of readings")
    metrics_by_type: Dict[str, int] = Field(default_factory=dict, description="Readings by metric type")
    sources_by_type: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Sources by metric type")
    daily_averages: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Daily averages by metric")
    weekly_trends: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Weekly trends by metric")

class Athlete(BaseModel):
    """Core athlete profile for multi-athlete support"""
    athlete_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Athlete name")
    email: Optional[str] = Field(None, description="Contact email")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = Field(True, description="Whether athlete is active")

class UserProfile(BaseModel):
    """User profile for personalized calorie calculations - now linked to athlete"""
    athlete_id: str = Field(..., description="Links to athlete record")
    age: int = Field(..., ge=13, le=100, description="User age in years")
    gender: Literal['male', 'female'] = Field(..., description="User gender")
    weight_kg: float = Field(..., gt=30, lt=300, description="Weight in kilograms")
    height_cm: Optional[float] = Field(None, gt=100, lt=250, description="Height in centimeters")
    vo2max: Optional[float] = Field(None, gt=20, lt=80, description="VO2 max in ml/kg/min")
    resting_hr: Optional[int] = Field(None, gt=40, lt=100, description="Resting heart rate")
    max_hr: Optional[int] = Field(None, gt=150, lt=220, description="Maximum heart rate")
    activity_level: Literal['sedentary', 'light', 'moderate', 'active', 'very_active'] = Field(
        'moderate', description="Activity level"
    )
    
    @property
    def calculated_max_hr(self) -> int:
        """Calculate max HR using age-based formula if not provided"""
        if self.max_hr:
            return self.max_hr
        # Standard age-based formula: 220 - age
        return 220 - self.age
    
    @property
    def bmr(self) -> float:
        """Basal Metabolic Rate using Mifflin-St Jeor equation"""
        if self.gender == 'male':
            return (10 * self.weight_kg) + (6.25 * (self.height_cm or 175)) - (5 * self.age) + 5
        else:
            return (10 * self.weight_kg) + (6.25 * (self.height_cm or 162)) - (5 * self.age) - 161
    
    @property
    def tdee(self) -> float:
        """Total Daily Energy Expenditure"""
        activity_multipliers = {
            'sedentary': 1.2,
            'light': 1.375,
            'moderate': 1.55,
            'active': 1.725,
            'very_active': 1.9
        }
        return self.bmr * activity_multipliers.get(self.activity_level, 1.55)
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user_001",
                "age": 30,
                "gender": "male",
                "weight_kg": 75.0,
                "height_cm": 180.0,
                "vo2max": 45.0,
                "resting_hr": 58,
                "max_hr": 190,
                "activity_level": "active"
            }
        }

class CalorieCalculationResult(BaseModel):
    """Result of calorie calculation with confidence and method details"""
    calories: int = Field(..., description="Calculated calories")
    method: str = Field(..., description="Calculation method used")
    confidence: float = Field(..., description="Confidence level (0-1)")
    factors: Dict[str, Any] = Field(default_factory=dict, description="Factors used in calculation")
    quality_score: float = Field(..., description="Overall quality score")
    
    class Config:
        schema_extra = {
            "example": {
                "calories": 450,
                "method": "heart_rate_keytel",
                "confidence": 0.85,
                "factors": {"hr_avg": 150, "duration_min": 45, "weight_kg": 75},
                "quality_score": 0.9
            }
        }

class AthleteDataSource(BaseModel):
    """Athlete's connection to a data source"""
    athlete_id: str = Field(..., description="Athlete identifier")
    source_name: str = Field(..., description="Data source name")
    auth_token: Optional[str] = Field(None, description="Authentication token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    expires_at: Optional[datetime] = Field(None, description="Token expiration")
    last_sync: Optional[datetime] = Field(None, description="Last synchronization")
    active: bool = Field(True, description="Whether connection is active")

class AthleteCalorieCalibration(BaseModel):
    """Per-athlete calorie calibration factors"""
    athlete_id: str = Field(..., description="Athlete identifier")
    sport_category: str = Field(..., description="Sport category")
    calibration_factor: float = Field(1.0, description="Calibration multiplier")
    sample_count: int = Field(0, description="Number of samples used")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
