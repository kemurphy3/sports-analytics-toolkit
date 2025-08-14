#!/usr/bin/env python3
"""
Command Line Interface for Athlete Performance Predictor
Provides commands for authentication, synchronization, analysis, and export
"""

import click
import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json
import uuid

from .core.data_ingestion import DataIngestionOrchestrator
from .core.multi_athlete_calorie_calculator import MultiAthleteCalorieCalculator
from .core.database_schema import DatabaseSchemaManager
from .connectors import get_connector, list_available_connectors
from .core.models import Workout, BiometricReading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', default='.env', help='Configuration file path')
def cli(verbose, config):
    """Athlete Performance Predictor - Multi-Source Fitness Data Platform"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load environment variables
    if os.path.exists(config):
        from dotenv import load_dotenv
        load_dotenv(config)
        logger.info(f"Loaded configuration from {config}")
    else:
        logger.warning(f"Configuration file {config} not found")

@cli.group()
def auth():
    """Manage authentication for data sources"""
    pass

@cli.group()
def db():
    """Database management commands"""
    pass

@db.command()
def migrate():
    """Force migrate database to new schema"""
    click.echo("🔄 Force migrating database schema...")
    
    try:
        orchestrator = DataIngestionOrchestrator()
        orchestrator._force_migrate_database()
        click.echo("✅ Database migration completed successfully")
        click.echo("💡 You may need to re-sync your data sources")
    except Exception as e:
        click.echo(f"❌ Database migration failed: {e}")
        click.echo("💡 Check the logs for more details")

@auth.command()
@click.argument('source')
def authenticate(source):
    """Authenticate with a specific data source"""
    click.echo(f"🔐 Authenticating with {source}...")
    
    try:
        # Check if source is available
        available_connectors = list_available_connectors()
        if source not in available_connectors:
            click.echo(f"❌ Unknown data source: {source}")
            click.echo(f"Available sources: {', '.join(available_connectors)}")
            return
        
        click.echo(f"📋 {source} connector available")
        
        # Check if credentials are configured
        if source == "strava":
            # For Strava, we need at minimum: CLIENT_ID, CLIENT_SECRET, and either ACCESS_TOKEN or REFRESH_TOKEN
            client_id = os.getenv("STRAVA_CLIENT_ID")
            client_secret = os.getenv("STRAVA_CLIENT_SECRET")
            access_token = os.getenv("STRAVA_ACCESS_TOKEN")
            refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
            
            if not client_id or not client_secret:
                click.echo("❌ Missing required Strava API credentials:")
                click.echo("   - STRAVA_CLIENT_ID (from Strava API settings)")
                click.echo("   - STRAVA_CLIENT_SECRET (from Strava API settings)")
                click.echo("\n💡 These are permanent credentials you set up once in Strava")
                return
            
            if not access_token and not refresh_token:
                click.echo("❌ Missing Strava authentication tokens:")
                click.echo("   - STRAVA_ACCESS_TOKEN (initial token from OAuth)")
                click.echo("   - STRAVA_REFRESH_TOKEN (long-lived token for auto-refresh)")
                click.echo("\n💡 You need to complete OAuth flow to get these tokens")
                click.echo("   The system will automatically refresh expired access tokens")
                return
        
        elif source == "vesync":
            # For VeSync, we need username and password
            username = os.getenv("VESYNC_USERNAME")
            password = os.getenv("VESYNC_PASSWORD")
            
            if not username or not password:
                click.echo("❌ Missing required VeSync credentials:")
                click.echo("   - VESYNC_USERNAME (your VeSync account email)")
                click.echo("   - VESYNC_PASSWORD (your VeSync account password)")
                click.echo("\n💡 These are your VeSync app login credentials")
                return
        
        click.echo("✅ Credentials configured")
        click.echo("�� Testing connection...")
        
        # Test connection and register if successful
        if asyncio.run(test_connection(source)):
            # Register the connector with the orchestrator for ongoing use
            register_connector_after_auth(source)
        
    except Exception as e:
        click.echo(f"❌ Authentication failed: {e}")

@auth.command()
def list():
    """List all available data sources"""
    click.echo("📱 Available Data Sources:")
    click.echo("=" * 50)
    
    try:
        orchestrator = DataIngestionOrchestrator()
        available_connectors = orchestrator.get_available_connectors()
        
        if available_connectors:
            for source_name in available_connectors:
                click.echo(f"🔗 {source_name}")
                click.echo(f"   Status: Available")
                click.echo()
        else:
            click.echo("No connectors available")
            
    except Exception as e:
        click.echo(f"❌ Error listing connectors: {e}")
        click.echo("No connectors available")

def register_connector_after_auth(source: str):
    """Register a connector with the orchestrator after successful authentication"""
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Get connector config
        config = {}
        if source == "strava":
            config = {
                "access_token": os.getenv("STRAVA_ACCESS_TOKEN"),
                "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET")
            }
        elif source == "vesync":
            config = {
                "username": os.getenv("VESYNC_USERNAME"),
                "password": os.getenv("VESYNC_PASSWORD"),
                "timezone": os.getenv("VESYNC_TIMEZONE", "America/Denver")
            }
        
        # Register the connector
        orchestrator.register_connector(source, config)
        click.echo(f"✅ {source} connector registered and ready for data synchronization")
        
        # Clean up
        orchestrator.cleanup()
        
    except Exception as e:
        click.echo(f"⚠️ Warning: Failed to register {source} connector: {e}")
        click.echo("You may need to re-authenticate before syncing data")

async def test_connection(source: str):
    """Test connection to a data source"""
    try:
        # Create connector instance
        config = {}
        
        # Get required config fields based on source
        if source == "strava":
            config = {
                "access_token": os.getenv("STRAVA_ACCESS_TOKEN"),
                "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
                "client_id": os.getenv("STRAVA_CLIENT_ID"),
                "client_secret": os.getenv("STRAVA_CLIENT_SECRET")
            }
        elif source == "vesync":
            config = {
                "username": os.getenv("VESYNC_USERNAME"),
                "password": os.getenv("VESYNC_PASSWORD"),
                "timezone": os.getenv("VESYNC_TIMEZONE", "America/Denver")
            }
        
        connector = get_connector(source, config)
        
        # Test connection
        if await connector.authenticate():
            click.echo("✅ Connection successful!")
            click.echo(f"🔗 {source} connector is now ready to use")
            return True
        else:
            click.echo("❌ Connection failed")
            return False
            
    except Exception as e:
        click.echo(f"❌ Connection test failed: {e}")
        return False

@cli.group()
def sync():
    """Synchronize data from configured sources"""
    pass

@sync.command()
@click.option('--days', '-d', default=30, help='Number of days to sync')
@click.option('--sources', '-s', help='Comma-separated list of sources to sync')
@click.option('--force', '-f', is_flag=True, help='Force sync even if recently synced')
def synchronize(days, sources, force):
    """Synchronize data from all configured sources"""
    click.echo(f"🔄 Starting synchronization for last {days} days...")
    
    # Parse sources
    source_list = None
    if sources:
        source_list = [s.strip() for s in sources.split(',')]
        click.echo(f"📱 Syncing sources: {', '.join(source_list)}")
    
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Register available connectors
        register_available_connectors(orchestrator)
        
        if not orchestrator.connectors:
            click.echo("❌ No connectors configured")
            click.echo("Use 'auth authenticate <source>' to configure sources")
            return
        
        # Run sync
        result = asyncio.run(orchestrator.sync_all_sources(days, source_list))
        
        if 'error' in result:
            click.echo(f"❌ Sync failed: {result['error']}")
            return
        
        # Display results
        click.echo("✅ Synchronization completed!")
        click.echo(f"📊 Sources synced: {result['sources_synced']}")
        click.echo(f"✅ Successful: {result['successful_syncs']}")
        click.echo(f"❌ Failed: {result['failed_syncs']}")
        click.echo(f"🏃 Workouts: {result['total_workouts']}")
        click.echo(f"📈 Biometrics: {result['total_biometrics']}")
        
        # Show deduplication stats
        if 'workout_deduplication' in result:
            dedup = result['workout_deduplication']
            click.echo(f"🔄 Workout deduplication: {dedup['duplicates_removed']} duplicates removed ({dedup['reduction_percent']:.1f}% reduction)")
        
        if 'biometric_deduplication' in result:
            dedup = result['biometric_deduplication']
            click.echo(f"🔄 Biometric deduplication: {dedup['duplicates_removed']} duplicates removed ({dedup['reduction_percent']:.1f}% reduction)")
        
        # Show source results
        for source, source_result in result['source_results'].items():
            if source_result['success']:
                click.echo(f"✅ {source}: {len(source_result['workouts'])} workouts, {len(source_result['biometrics'])} biometrics")
            else:
                click.echo(f"❌ {source}: {source_result.get('error', 'Unknown error')}")
        
        orchestrator.cleanup()
        
    except Exception as e:
        click.echo(f"❌ Synchronization failed: {e}")
        logger.error(f"Sync failed: {e}")

def register_available_connectors(orchestrator: DataIngestionOrchestrator):
    """Register all available connectors with the orchestrator"""
    available_connectors = list_available_connectors()
    
    if not available_connectors:
        click.echo("ℹ️ No connectors available yet")
        click.echo("Connectors will be implemented for: Strava, Garmin, Fitbit, WHOOP, Oura, Withings")
        return
    
    click.echo(f"📱 Available connectors: {', '.join(available_connectors)}")
    
    # Register connectors with the orchestrator
    for source in available_connectors:
        try:
            config = {}
            if source == "strava":
                config = {
                    "access_token": os.getenv("STRAVA_ACCESS_TOKEN"),
                    "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
                    "client_id": os.getenv("STRAVA_CLIENT_ID"),
                    "client_secret": os.getenv("STRAVA_CLIENT_SECRET")
                }
            elif source == "vesync":
                config = {
                    "username": os.getenv("VESYNC_USERNAME"),
                    "password": os.getenv("VESYNC_PASSWORD"),
                    "timezone": os.getenv("VESYNC_TIMEZONE", "America/Denver")
                }
            
            # For Strava, we need at minimum CLIENT_ID and CLIENT_SECRET
            if source == "strava":
                if config.get("client_id") and config.get("client_secret"):
                    orchestrator.register_connector(source, config)
                    click.echo(f"✅ Registered {source} connector")
                else:
                    click.echo(f"⚠️ {source} connector not configured (missing CLIENT_ID or CLIENT_SECRET)")
            elif source == "vesync":
                if config.get("username") and config.get("password"):
                    orchestrator.register_connector(source, config)
                    click.echo(f"✅ Registered {source} connector")
                else:
                    click.echo(f"⚠️ {source} connector not configured (missing username or password)")
            else:
                if any(config.values()):  # For other connectors
                    orchestrator.register_connector(source, config)
                    click.echo(f"✅ Registered {source} connector")
                else:
                    click.echo(f"⚠️ {source} connector not configured (missing credentials)")
                
        except Exception as e:
            click.echo(f"❌ Failed to register {source} connector: {e}")

@cli.group()
def analyze():
    """Analyze synchronized fitness data"""
    pass

@analyze.command()
@click.option('--days', '-d', default=30, help='Number of days to analyze')
@click.option('--plugin', '-p', help='Analysis plugin to use (e.g., ball_sports)')
def run(days, plugin):
    """Run fitness analysis on synchronized data"""
    click.echo(f"🔬 Running fitness analysis for last {days} days...")
    
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Get data
        end_date = datetime.today()
        start_date = end_date - timedelta(days=days)
        
        workouts = orchestrator.get_workouts(start_date, end_date)
        biometrics = orchestrator.get_biometrics(start_date, end_date)
        
        if not workouts and not biometrics:
            click.echo("❌ No data available for analysis")
            click.echo("Run 'sync' first to collect data")
            return
        
        click.echo(f"📊 Analyzing {len(workouts)} workouts and {len(biometrics)} biometric readings")
        
        # Get summaries
        workout_summary = orchestrator.get_workout_summary(start_date, end_date)
        biometric_summary = orchestrator.get_biometric_summary(start_date, end_date)
        
        # Display workout summary
        click.echo("\n🏃 Workout Summary:")
        click.echo(f"   Total: {workout_summary.total_workouts}")
        click.echo(f"   Duration: {workout_summary.total_duration // 3600}h {(workout_summary.total_duration % 3600) // 60}m")
        click.echo(f"   Distance: {workout_summary.total_distance / 1000:.1f} km")
        click.echo(f"   Calories: {workout_summary.total_calories:,}")
        
        # Sport breakdown
        if workout_summary.sport_breakdown:
            click.echo("\n   Sport Breakdown:")
            for sport, count in sorted(workout_summary.sport_breakdown.items(), key=lambda x: x[1], reverse=True):
                click.echo(f"     {sport}: {count}")
        
        # Source breakdown
        if workout_summary.source_breakdown:
            click.echo("\n   Source Breakdown:")
            for source, count in sorted(workout_summary.source_breakdown.items(), key=lambda x: x[1], reverse=True):
                click.echo(f"     {source}: {count}")
        
        # Display biometric summary
        click.echo("\n📈 Biometric Summary:")
        click.echo(f"   Total Readings: {biometric_summary.total_readings}")
        
        if biometric_summary.metrics_by_type:
            click.echo("\n   Metrics by Type:")
            for metric, count in sorted(biometric_summary.metrics_by_type.items(), key=lambda x: x[1], reverse=True):
                click.echo(f"     {metric}: {count}")
        
        # Plugin analysis
        if plugin:
            click.echo(f"\n🔌 Running {plugin} plugin analysis...")
            run_plugin_analysis(plugin, workouts, biometrics)
        
        orchestrator.cleanup()
        click.echo("\n✅ Analysis completed!")
        
    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        logger.error(f"Analysis failed: {e}")

def run_plugin_analysis(plugin: str, workouts: List[Workout], biometrics: List[BiometricReading]):
    """Run analysis using a specific plugin"""
    try:
        if plugin == "ball_sports":
            # Ball sports analysis
            ball_sport_workouts = [w for w in workouts if w.sport_category == "ball_sport"]
            if ball_sport_workouts:
                click.echo(f"   🏀 Found {len(ball_sport_workouts)} ball sport workouts")
                
                # GPS analysis for ball sports
                gps_workouts = [w for w in ball_sport_workouts if w.has_gps]
                if gps_workouts:
                    click.echo(f"   📍 {len(gps_workouts)} workouts have GPS data")
                    
                    # Calculate field coverage, sprint detection, etc.
                    total_distance = sum(w.distance or 0 for w in gps_workouts)
                    avg_duration = sum(w.duration for w in gps_workouts) / len(gps_workouts)
                    
                    click.echo(f"   📏 Total distance: {total_distance / 1000:.1f} km")
                    click.echo(f"   ⏱️ Average duration: {avg_duration // 60}m {avg_duration % 60}s")
                else:
                    click.echo("   📍 No GPS data available for ball sport analysis")
            else:
                click.echo("   🏀 No ball sport workouts found")
        else:
            click.echo(f"   ℹ️ Plugin '{plugin}' not implemented yet")
            
    except Exception as e:
        click.echo(f"   ❌ Plugin analysis failed: {e}")

@cli.group()
def export():
    """Export synchronized data"""
    pass

@export.command()
@click.option('--format', '-f', type=click.Choice(['parquet', 'csv']), default='parquet', help='Export format')
@click.option('--output', '-o', help='Output file path')
@click.option('--days', '-d', default=30, help='Number of days to export')
def data(format, output, days):
    """Export synchronized data in specified format"""
    click.echo(f"📤 Exporting data for last {days} days in {format.upper()} format...")
    
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Export data
        output_path = orchestrator.export_data(format, output)
        
        click.echo(f"✅ Data exported successfully!")
        click.echo(f"📁 Output: {output_path}")
        
        # Show file sizes
        if output_path:
            from pathlib import Path
            base_path = Path(output_path)
            for file_path in base_path.parent.glob(f"{base_path.name}*"):
                if file_path.exists():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    click.echo(f"   {file_path.name}: {size_mb:.1f} MB")
        
        orchestrator.cleanup()
        
    except Exception as e:
        click.echo(f"❌ Export failed: {e}")
        logger.error(f"Export failed: {e}")

@cli.command()
def status():
    """Show synchronization status for all sources"""
    click.echo("📊 Synchronization Status:")
    click.echo("=" * 50)
    
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Get configured sources
        configured_sources = orchestrator.get_configured_sources()
        
        if not configured_sources:
            click.echo("ℹ️ No sources configured yet")
            click.echo("Use 'auth authenticate <source>' to configure sources")
            return
        
        click.echo("📱 Configured Data Sources:")
        for source in configured_sources:
            click.echo(f"   🔗 {source}")
        
        click.echo()
        
        # Get sync status for configured sources
        sync_status = orchestrator.get_sync_status()
        
        for source, status in sync_status.items():
            click.echo(f"📱 {source}:")
            
            if status['status'] == 'active':
                click.echo(f"   ✅ Status: {status['status']}")
            elif status['status'] == 'error':
                click.echo(f"   ❌ Status: {status['status']}")
            else:
                click.echo(f"   ⏳ Status: {status['status']}")
            
            if status['last_sync']:
                click.echo(f"   🕒 Last Sync: {status['last_sync']}")
            
            if status['sync_count']:
                click.echo(f"   🔄 Sync Count: {status['sync_count']}")
            
            if status['error_message']:
                click.echo(f"   ⚠️ Error: {status['error_message']}")
            
            click.echo()
        
        # Show data summary
        workout_summary = orchestrator.get_workout_summary()
        biometric_summary = orchestrator.get_biometric_summary()
        
        click.echo("📈 Data Summary:")
        click.echo(f"   🏃 Workouts: {workout_summary.total_workouts}")
        click.echo(f"   📊 Biometrics: {biometric_summary.total_readings}")
        
        orchestrator.cleanup()
        
    except Exception as e:
        click.echo(f"❌ Status check failed: {e}")
        logger.error(f"Status check failed: {e}")

@cli.command()
def migrate():
    """Migrate existing CSV data to new database schema"""
    click.echo("🔄 Migrating existing CSV data to new database schema...")
    
    try:
        # Initialize orchestrator
        orchestrator = DataIngestionOrchestrator()
        
        # Check for existing CSV files
        csv_files = []
        data_dir = os.path.join(os.path.dirname(__file__), "data") # Adjust path to project root
        if os.path.exists(data_dir):
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        
        if not csv_files:
            click.echo("ℹ️ No CSV files found to migrate")
            return
        
        click.echo(f"📁 Found {len(csv_files)} CSV files to migrate")
        
        for csv_file in csv_files:
            click.echo(f"   📄 Migrating {csv_file}...")
            
            try:
                # This would implement CSV migration logic
                # For now, just show what would be migrated
                click.echo(f"      ℹ️ Would migrate {csv_file} to database")
                
            except Exception as e:
                click.echo(f"      ❌ Failed to migrate {csv_file}: {e}")
        
        click.echo("\n✅ Migration preview completed")
        click.echo("ℹ️ Full migration will be implemented in future versions")
        
        orchestrator.cleanup()
        
    except Exception as e:
        click.echo(f"❌ Migration failed: {e}")
        logger.error(f"Migration failed: {e}")

@cli.command()
def version():
    """Show version information"""
    click.echo("🏃‍♂️ Athlete Performance Predictor")
    click.echo("Multi-Source Fitness Data Platform")
    click.echo("Version: 2.0.0")
    click.echo("Enhanced with multi-source data ingestion")

@cli.command()
@click.argument('name')
@click.option('--email', help='Athlete email address')
@click.option('--age', type=int, help='Athlete age in years')
@click.option('--gender', type=click.Choice(['male', 'female']), help='Athlete gender')
@click.option('--weight-kg', type=float, help='Athlete weight in kilograms')
def add_athlete(name: str, email: Optional[str] = None, 
                age: Optional[int] = None, gender: Optional[str] = None,
                weight_kg: Optional[float] = None):
    """Add a new athlete to the system"""
    try:
        # Initialize database schema
        db_manager = DatabaseSchemaManager('data/athlete_performance.db')
        db_manager.initialize_schema()
        
        # Create athlete using calculator
        calculator = MultiAthleteCalorieCalculator('data/athlete_performance.db')
        athlete_id = calculator.create_athlete(name, email)
        
        # Update profile if additional data provided
        if any([age, gender, weight_kg]):
            profile_updates = {}
            if age:
                profile_updates['age'] = age
            if gender:
                profile_updates['gender'] = gender
            if weight_kg:
                profile_updates['weight_kg'] = weight_kg
            
            db_manager.update_athlete_profile(athlete_id, profile_updates)
        
        click.echo(f"✅ Created athlete: {name} (ID: {athlete_id})")
        
    except Exception as e:
        click.echo(f"❌ Failed to create athlete: {e}")

@cli.command()
@click.argument('athlete_id')
@click.argument('start_date')
@click.argument('end_date')
def calculate_calories(athlete_id: str, start_date: str, end_date: str):
    """Calculate calories for an athlete's workouts"""
    try:
        calculator = MultiAthleteCalorieCalculator('data/athlete_performance.db')
        
        # Get workouts for athlete
        workouts = calculator.get_athlete_workouts(athlete_id, start_date, end_date)
        
        if not workouts:
            click.echo(f"❌ No workouts found for athlete {athlete_id} between {start_date} and {end_date}")
            return
        
        results = []
        total_calories = 0
        
        click.echo(f"🏃‍♂️ Calculating calories for {len(workouts)} workouts...")
        click.echo("=" * 60)
        
        for workout in workouts:
            result = calculator.calculate_for_athlete(workout, athlete_id)
            results.append({
                'date': workout.start_time.strftime('%Y-%m-%d'),
                'sport': workout.sport,
                'duration': f"{workout.duration // 60}m",
                'calories': result.calories,
                'method': result.method,
                'confidence': result.confidence
            })
            total_calories += result.calories
        
        # Display results
        for result in results:
            click.echo(f"{result['date']} | {result['sport']:15} | {result['duration']:5} | "
                      f"{result['calories']:4} cal | {result['method']:20} | {result['confidence']:.2f}")
        
        click.echo("=" * 60)
        click.echo(f"📊 Total Calories: {total_calories:,} kcal")
        click.echo(f"📈 Average Confidence: {sum(r['confidence'] for r in results) / len(results):.2f}")
        
    except Exception as e:
        click.echo(f"❌ Failed to calculate calories: {e}")

@cli.command()
def list_athletes():
    """List all athletes in the system"""
    try:
        import sqlite3
        
        with sqlite3.connect('data/athlete_performance.db') as conn:
            cursor = conn.execute("""
                SELECT a.athlete_id, a.name, a.email, a.created_at, a.active,
                       p.age, p.gender, p.weight_kg, p.activity_level
                FROM athletes a
                LEFT JOIN athlete_profiles p ON a.athlete_id = p.athlete_id
                ORDER BY a.created_at DESC
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                click.echo("❌ No athletes found in the system")
                return
            
            click.echo("👥 ATHLETES IN SYSTEM")
            click.echo("=" * 80)
            click.echo(f"{'ID':<36} {'Name':<20} {'Age':<4} {'Gender':<6} {'Weight':<7} {'Activity':<10} {'Created':<10}")
            click.echo("-" * 80)
            
            for row in rows:
                athlete_id, name, email, created_at, active, age, gender, weight, activity = row
                created_date = datetime.fromisoformat(created_at).strftime('%Y-%m-%d') if created_at else 'N/A'
                age_str = str(age) if age else 'N/A'
                gender_str = gender if gender else 'N/A'
                weight_str = f"{weight:.1f}kg" if weight else 'N/A'
                activity_str = activity if activity else 'N/A'
                
                status = "✅" if active else "❌"
                
                click.echo(f"{athlete_id:<36} {name:<20} {age_str:<4} {gender_str:<6} "
                          f"{weight_str:<7} {activity_str:<10} {created_date:<10} {status}")
            
            click.echo(f"\n📊 Total Athletes: {len(rows)}")
            
    except Exception as e:
        click.echo(f"❌ Failed to list athletes: {e}")

@cli.command()
@click.argument('athlete_id')
@click.option('--age', type=int, help='Athlete age in years')
@click.option('--gender', type=click.Choice(['male', 'female']), help='Athlete gender')
@click.option('--weight-kg', type=float, help='Athlete weight in kilograms')
@click.option('--height-cm', type=float, help='Athlete height in centimeters')
@click.option('--vo2max', type=float, help='Athlete VO2 max in ml/kg/min')
@click.option('--resting-hr', type=int, help='Athlete resting heart rate')
@click.option('--max-hr', type=int, help='Athlete maximum heart rate')
@click.option('--activity-level', type=click.Choice(['sedentary', 'light', 'moderate', 'active', 'very_active']), help='Athlete activity level')
def update_profile(athlete_id: str, age: Optional[int] = None, gender: Optional[str] = None,
                  weight_kg: Optional[float] = None, height_cm: Optional[float] = None,
                  vo2max: Optional[float] = None, resting_hr: Optional[int] = None,
                  max_hr: Optional[int] = None, activity_level: Optional[str] = None):
    """Update an athlete's profile"""
    try:
        db_manager = DatabaseSchemaManager('data/athlete_performance.db')
        
        # Build profile updates
        profile_updates = {}
        if age is not None:
            profile_updates['age'] = age
        if gender is not None:
            profile_updates['gender'] = gender
        if weight_kg is not None:
            profile_updates['weight_kg'] = weight_kg
        if height_cm is not None:
            profile_updates['height_cm'] = height_cm
        if vo2max is not None:
            profile_updates['vo2max'] = vo2max
        if resting_hr is not None:
            profile_updates['resting_hr'] = resting_hr
        if max_hr is not None:
            profile_updates['max_hr'] = max_hr
        if activity_level is not None:
            profile_updates['activity_level'] = activity_level
        
        if not profile_updates:
            click.echo("❌ No profile updates specified")
            return
        
        # Update profile
        db_manager.update_athlete_profile(athlete_id, profile_updates)
        click.echo(f"✅ Updated profile for athlete {athlete_id}")
        
        # Show updated profile
        updated_profile = db_manager.get_athlete_profile(athlete_id)
        if updated_profile:
            click.echo("\n📋 Updated Profile:")
            for key, value in updated_profile.items():
                if key != 'athlete_id':
                    click.echo(f"  {key}: {value}")
        
    except Exception as e:
        click.echo(f"❌ Failed to update profile: {e}")

if __name__ == "__main__":
    cli()
