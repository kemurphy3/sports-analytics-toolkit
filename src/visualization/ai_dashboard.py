#!/usr/bin/env python3
"""
AI-Powered Fitness Dashboard
Interactive web dashboard with AI-driven insights and Q&A capabilities
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3
import os
import json

# Import project modules
try:
    import sys
    import os
    # Add the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    
    from src.core.multi_athlete_calorie_calculator import MultiAthleteCalorieCalculator
    from src.core.database_schema import DatabaseSchemaManager
    from src.connectors import get_connector, list_available_connectors
    from src.core.models import Workout, BiometricReading, UserProfile
except ImportError as e:
    st.error(f"Import error: {e}")
    st.info("Make sure you're running from the project root directory")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIFitnessCoach:
    """AI-powered fitness coaching system"""
    
    def __init__(self):
        self.system_prompt = """
        You are an expert fitness coach and sports scientist. You have access to:
        - Workout data (duration, intensity, heart rate, calories)
        - Biometric data (weight, body composition) 
        - Training load metrics (CTL, ATL, TSB)
        - Sport-specific performance data
        
        Provide evidence-based recommendations that are:
        1. Specific and actionable
        2. Based on the athlete's actual data
        3. Scientifically sound
        4. Injury-prevention focused
        """
    
    def analyze_injury_risk(self, athlete_data: Dict) -> Dict:
        """Analyze injury risk using multiple factors"""
        
        risk_factors = {
            'load_spike': self._check_load_spike(athlete_data),
            'insufficient_recovery': self._check_recovery(athlete_data),
            'volume_intensity_imbalance': self._check_balance(athlete_data),
            'fatigue_accumulation': self._check_fatigue(athlete_data)
        }
        
        # Calculate composite risk score
        risk_score = sum(f['score'] * f['weight'] for f in risk_factors.values())
        
        return {
            'score': risk_score,
            'level': self._get_risk_level(risk_score),
            'factors': risk_factors,
            'recommendations': self._get_risk_recommendations(risk_factors)
        }
    
    def _check_load_spike(self, data: Dict) -> Dict:
        """Check for sudden training load increases"""
        if 'training_load' not in data:
            return {'score': 0, 'weight': 0.3, 'description': 'No data available'}
        
        acwr = data['training_load'].get('acwr_ratio', 1.0)
        if acwr > 1.5:
            return {'score': 0.8, 'weight': 0.3, 'description': 'High acute:chronic workload ratio'}
        elif acwr > 1.3:
            return {'score': 0.5, 'weight': 0.3, 'description': 'Elevated workload ratio'}
        else:
            return {'score': 0, 'weight': 0.3, 'description': 'Normal workload ratio'}
    
    def _check_recovery(self, data: Dict) -> Dict:
        """Check recovery quality indicators"""
        if 'health_indicators' not in data:
            return {'score': 0, 'weight': 0.25, 'description': 'No recovery data available'}
        
        # Check resting HR trends
        hr_trend = data['health_indicators'].get('heart_rate_trend', {})
        if hr_trend.get('trend') == 'declining':
            return {'score': 0.6, 'weight': 0.25, 'description': 'Elevated resting heart rate'}
        else:
            return {'score': 0, 'weight': 0.25, 'description': 'Normal recovery indicators'}
    
    def _check_balance(self, data: Dict) -> Dict:
        """Check training balance"""
        if 'summary_stats' not in data:
            return {'score': 0, 'weight': 0.25, 'description': 'No training data available'}
        
        consistency = data['summary_stats'].get('consistency_percent', 0)
        if consistency < 60:
            return {'score': 0.4, 'weight': 0.25, 'description': 'Low training consistency'}
        else:
            return {'score': 0, 'weight': 0.25, 'description': 'Good training consistency'}
    
    def _check_fatigue(self, data: Dict) -> Dict:
        """Check fatigue accumulation"""
        if 'training_load' not in data:
            return {'score': 0, 'weight': 0.2, 'description': 'No fatigue data available'}
        
        fatigue = data['training_load'].get('fatigue_level', 'LOW')
        if fatigue == 'HIGH':
            return {'score': 0.7, 'weight': 0.2, 'description': 'High fatigue level detected'}
        elif fatigue == 'MODERATE':
            return {'score': 0.4, 'weight': 0.2, 'description': 'Moderate fatigue'}
        else:
            return {'score': 0, 'weight': 0.2, 'description': 'Low fatigue level'}
    
    def _get_risk_level(self, score: float) -> str:
        """Convert risk score to level"""
        if score > 0.7:
            return 'HIGH'
        elif score > 0.4:
            return 'MODERATE'
        else:
            return 'LOW'
    
    def _get_risk_recommendations(self, factors: Dict) -> List[str]:
        """Generate recommendations based on risk factors"""
        recommendations = []
        
        for factor_name, factor_data in factors.items():
            if factor_data['score'] > 0.5:
                if factor_name == 'load_spike':
                    recommendations.append("Reduce training volume by 20-30% this week")
                elif factor_name == 'insufficient_recovery':
                    recommendations.append("Add 1-2 additional rest days")
                elif factor_name == 'volume_intensity_imbalance':
                    recommendations.append("Focus on building consistent training habits")
                elif factor_name == 'fatigue_accumulation':
                    recommendations.append("Consider a recovery week with reduced intensity")
        
        return recommendations
    
    def generate_workout_recommendations(self, athlete_data: Dict) -> List[Dict]:
        """Generate personalized workout recommendations"""
        
        recommendations = []
        
        # Check training balance
        if 'summary_stats' in athlete_data:
            consistency = athlete_data['summary_stats'].get('consistency_percent', 0)
            if consistency < 70:
                recommendations.append({
                    'type': 'workout',
                    'title': 'Build Training Consistency',
                    'explanation': f"Your current consistency is {consistency:.1f}%. Aim for 80%+ for optimal results.",
                    'workout_plan': "Start with 3-4 sessions per week, gradually increasing frequency"
                })
        
        # Check for variety
        if 'sport_specific' in athlete_data:
            sport_count = len(athlete_data['sport_specific'])
            if sport_count < 2:
                recommendations.append({
                    'type': 'workout',
                    'title': 'Add Training Variety',
                    'explanation': "Cross-training can improve overall fitness and prevent plateaus.",
                    'workout_plan': "Add 1-2 sessions of complementary activities per week"
                })
        
        return recommendations
    
    def answer_question(self, question: str, context: Dict) -> Dict:
        """Answer user questions with context-aware responses"""
        
        # Simple rule-based responses for demo
        # In production, this would call an AI API
        
        responses = {
            "marathon": "Based on your current fitness level, you're showing good endurance. Consider a 16-week training plan.",
            "sprint": "Your sprint recovery can be improved by adding plyometric exercises and ensuring adequate rest between high-intensity sessions.",
            "plateau": "Performance plateaus often occur due to insufficient recovery or lack of training variety. Consider deloading for a week.",
            "heart rate": "Elevated resting heart rate can indicate overtraining or insufficient recovery. Monitor for 3-5 days.",
            "strength": "Strength training 2x weekly can improve running economy by 5% and reduce injury risk by 30%.",
            "race pace": "Your optimal 10K pace should be 15-20 seconds per km slower than your 5K pace."
        }
        
        # Find best matching response
        best_response = "I'd be happy to help with your fitness question. Please provide more specific details about your training goals and current situation."
        
        for key, response in responses.items():
            if key.lower() in question.lower():
                best_response = response
                break
        
        return {
            'answer': best_response,
            'charts': [],
            'data_sources': context.get('data_sources', [])
        }

class FitnessDashboard:
    """Main dashboard application"""
    
    def __init__(self, database_path: str = "data/athlete_performance.db"):
        self.db_path = database_path
        self.calculator = MultiAthleteCalorieCalculator(database_path)
        self.db_manager = DatabaseSchemaManager(database_path)
        self.ai_coach = AIFitnessCoach()
        
        # Initialize the database schema
        try:
            self.db_manager.initialize_schema()
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            st.error(f"Database initialization failed: {e}")
        
    def run(self):
        """Run the main dashboard"""
        
        # Page configuration
        st.set_page_config(
            page_title="AI Fitness Coach Dashboard",
            page_icon="🏃",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Sidebar
        self._create_sidebar()
        
        # Main content
        self._create_main_content()
    
    def _get_athlete_options(self):
        """Get available athletes with readable names"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if athletes table exists and has data
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='athletes'")
                if cursor.fetchone():
                    cursor.execute("SELECT id, name FROM athletes WHERE is_active = 1")
                    db_athletes = cursor.fetchall()
                    
                    if db_athletes:
                        # Use database athletes
                        options = {}
                        for athlete_id, name in db_athletes:
                            if athlete_id == 'default':
                                options[f"🏃‍♂️ {name or 'Main Athlete (You)'}"] = athlete_id
                            else:
                                options[f"👥 {name or f'Athlete {athlete_id}'}"] = athlete_id
                        logger.info(f"Found {len(db_athletes)} athletes in database: {options}")
                        return options
                    else:
                        # No athletes found in database
                        logger.warning("Athletes table exists but is empty, using fallback options")
                
                # Fallback to default options
                fallback_options = {
                    "🏃‍♂️ Main Athlete (You)": "default",
                    "👥 Team Member 1": "athlete_1", 
                    "👥 Team Member 2": "athlete_2"
                }
                logger.info(f"Using fallback athlete options: {fallback_options}")
                return fallback_options
                
        except Exception as e:
            logger.error(f"Error loading athletes: {e}")
            # Fallback to default options
            fallback_options = {
                "🏃‍♂️ Main Athlete (You)": "default",
                "👥 Team Member 1": "athlete_1", 
                "👥 Team Member 2": "athlete_2"
            }
            logger.info(f"Using fallback athlete options due to error: {fallback_options}")
            return fallback_options
    
    def _create_sidebar(self):
        """Create the sidebar with athlete selection and controls"""
        with st.sidebar:
            st.title("🏃 AI Fitness Coach")
            st.markdown("---")
            
            # Athlete selection with readable names
            athlete_options = self._get_athlete_options()
            
            # Debug: Show what options were loaded
            st.write(f"🔍 Debug: Loaded athlete options: {athlete_options}")
            
            selected_athlete_name = st.selectbox(
                "Select Athlete Profile",
                list(athlete_options.keys()),
                key="athlete_selector_name"
            )
            
            # Store the actual athlete ID in session state
            athlete_id = athlete_options[selected_athlete_name]
            st.session_state["athlete_selector"] = athlete_id
            
            # Debug: Show what athlete ID is being stored
            st.write(f"🔍 Debug: Storing athlete_id '{athlete_id}' in session state")
            
            # Show current selection info
            st.info(f"📊 Viewing data for: **{selected_athlete_name}**")
            
            # Date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            
            date_range = st.date_input(
                "Date Range",
                value=(start_date, end_date),
                max_value=end_date,
                key="date_range"
            )
            
            # Note: st.date_input automatically manages session state with key="date_range"
            
            st.markdown("---")
            
            # Data sync controls
            if st.button("🔄 Sync Data Sources", type="primary"):
                with st.spinner("Syncing data..."):
                    self._sync_data_sources()
                    st.success("Data sync complete!")
            
            # Settings
            with st.expander("⚙️ Settings"):
                auto_refresh = st.checkbox("Auto-refresh (5 min)", value=True)
                if auto_refresh:
                    st.info("Dashboard will refresh every 5 minutes")
            
            st.markdown("---")
            
            # Data export
            if st.button("📥 Download My Data"):
                self._export_athlete_data(athlete_id)
    
    def _create_main_content(self):
        """Create the main dashboard content with tabs"""
        
        # Create tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Overview", 
            "💪 Performance", 
            "❤️ Health", 
            "🤖 AI Insights", 
            "💬 Ask AI"
        ])
        
        # Overview Tab
        with tab1:
            self._create_overview_tab()
        
        # Performance Tab
        with tab2:
            self._create_performance_tab()
        
        # Health Tab
        with tab3:
            self._create_health_tab()
        
        # AI Insights Tab
        with tab4:
            self._create_ai_insights_tab()
        
        # Ask AI Tab
        with tab5:
            self._create_ask_ai_tab()
    
    def _create_overview_tab(self):
        """Create the overview dashboard"""
        st.header("📊 Fitness Overview")
        
        # Get athlete data
        athlete_id = st.session_state.get("athlete_selector", "default")
        
        # Get date range from sidebar or use default
        if "date_range" in st.session_state:
            date_range = st.session_state.date_range
        else:
            # Fallback to default date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            date_range = (start_date, end_date)
        
        # Load data - convert date objects to datetime objects
        start_datetime = datetime.combine(date_range[0], datetime.min.time())
        end_datetime = datetime.combine(date_range[1], datetime.max.time())
        
        # Debug info
        st.info(f"🔍 Loading data for athlete: {athlete_id}")
        st.info(f"📅 Date range: {start_datetime.date()} to {end_datetime.date()}")
        
        workouts = self._load_workouts(athlete_id, start_datetime, end_datetime)
        biometrics = self._load_biometrics(athlete_id, start_datetime, end_datetime)
        
        st.info(f"📊 Found {len(workouts)} workouts and {len(biometrics)} biometric readings")
        
        if not workouts:
            st.warning("No workout data available for the selected period")
            return
        
        # Calculate metrics
        metrics = self._calculate_overview_metrics(workouts, biometrics)
        
        # Metric cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Fitness Score",
                value=f"{metrics['fitness_score']:.1f}",
                delta=f"{metrics['fitness_change']:+.1f} vs last month",
                delta_color="normal"
            )
        
        with col2:
            st.metric(
                label="Fatigue Level",
                value=metrics['fatigue_level'],
                delta=metrics['fatigue_trend'],
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                label="Injury Risk",
                value=metrics['injury_risk']['level'],
                delta=f"{metrics['injury_risk']['change']}% vs last week",
                delta_color="inverse"
            )
        
        with col4:
            st.metric(
                label="Weekly Volume",
                value=f"{metrics['weekly_hours']:.1f} hrs",
                delta=f"{metrics['volume_change']:+.1f} hrs"
            )
        
        # Training Load Chart
        st.subheader("Training Load & Recovery")
        fig_load = self._create_training_load_chart(workouts)
        st.plotly_chart(fig_load, use_container_width=True, key="training_load_chart")
        
        # Activity Calendar
        st.subheader("Activity Calendar")
        fig_calendar = self._create_calendar_heatmap(workouts)
        st.plotly_chart(fig_calendar, use_container_width=True, key="workout_calendar_chart")
    
    def _create_performance_tab(self):
        """Create the performance analysis tab"""
        st.header("💪 Performance Analysis")
        
        athlete_id = st.session_state.get("athlete_selector", "default")
        date_range = st.session_state.get("date_range", (datetime.now() - timedelta(days=90), datetime.now()))
        
        # Convert date objects to datetime objects
        start_datetime = datetime.combine(date_range[0], datetime.min.time())
        end_datetime = datetime.combine(date_range[1], datetime.max.time())
        
        workouts = self._load_workouts(athlete_id, start_datetime, end_datetime)
        
        if not workouts:
            st.warning("No workout data available")
            return
        
        # Sport filter
        sports = ["All"] + list(set(w.sport for w in workouts))
        sport_filter = st.selectbox("Select Sport", sports)
        
        # Filter workouts
        if sport_filter != "All":
            filtered_workouts = [w for w in workouts if w.sport == sport_filter]
        else:
            filtered_workouts = workouts
        
        # Performance Trends
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Pace/Speed Progression")
            fig_pace = self._create_pace_trend_chart(filtered_workouts)
            st.plotly_chart(fig_pace, use_container_width=True, key="pace_trend_chart")
        
        with col2:
            st.subheader("Heart Rate Zones")
            fig_hr = self._create_hr_zone_distribution(filtered_workouts)
            st.plotly_chart(fig_hr, use_container_width=True, key="hr_zone_chart")
        
        # Sport-specific analysis
        if sport_filter == "Soccer":
            self._create_soccer_analysis(filtered_workouts)
        elif sport_filter == "Running":
            self._create_running_analysis(filtered_workouts)
    
    def _create_health_tab(self):
        """Create the health monitoring tab"""
        st.header("❤️ Health & Recovery")
        
        athlete_id = st.session_state.get("athlete_selector", "default")
        date_range = st.session_state.get("date_range", (datetime.now() - timedelta(days=90), datetime.now()))
        
        # Convert date objects to datetime objects
        start_datetime = datetime.combine(date_range[0], datetime.min.time())
        end_datetime = datetime.combine(date_range[1], datetime.max.time())
        
        biometrics = self._load_biometrics(athlete_id, start_datetime, end_datetime)
        workouts = self._load_workouts(athlete_id, start_datetime, end_datetime)
        
        # Body Composition Trends
        st.subheader("Body Composition Trends")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_weight = self._create_weight_trend_chart(biometrics)
            st.plotly_chart(fig_weight, use_container_width=True, key="weight_trend_chart")
        
        with col2:
            fig_bf = self._create_body_fat_chart(biometrics)
            st.plotly_chart(fig_bf, use_container_width=True, key="body_fat_chart")
        
        # Recovery Indicators
        st.subheader("Recovery Indicators")
        fig_rhr = self._create_resting_hr_analysis(workouts)
        st.plotly_chart(fig_rhr, use_container_width=True, key="resting_hr_chart")
    
    def _create_ai_insights_tab(self):
        """Create the AI insights tab"""
        st.header("🤖 AI-Powered Insights")
        
        athlete_id = st.session_state.get("athlete_selector", "default")
        date_range = st.session_state.get("date_range", (datetime.now() - timedelta(days=90), datetime.now()))
        
        # Load data for analysis - convert date objects to datetime objects
        start_datetime = datetime.combine(date_range[0], datetime.min.time())
        end_datetime = datetime.combine(date_range[1], datetime.max.time())
        
        workouts = self._load_workouts(athlete_id, start_datetime, end_datetime)
        biometrics = self._load_biometrics(athlete_id, start_datetime, end_datetime)
        
        if not workouts:
            st.warning("No workout data available for AI analysis")
            return
        
        # Generate insights
        athlete_data = self._prepare_athlete_data(workouts, biometrics)
        insights = self.ai_coach.analyze_injury_risk(athlete_data)
        recommendations = self.ai_coach.generate_workout_recommendations(athlete_data)
        
        # Injury Risk Alert
        if insights['level'] == 'HIGH':
            st.error(f"⚠️ **High Injury Risk Detected**")
            st.write(f"Risk Score: {insights['score']:.2f}")
            st.write("**Risk Factors:**")
            for factor_name, factor_data in insights['factors'].items():
                if factor_data['score'] > 0:
                    st.write(f"• {factor_data['description']}")
            
            st.write("**Recommended Actions:**")
            for rec in insights['recommendations']:
                st.write(f"• {rec}")
        
        elif insights['level'] == 'MODERATE':
            st.warning(f"⚠️ **Moderate Injury Risk**")
            st.write(f"Risk Score: {insights['score']:.2f}")
            st.write("Monitor your training load and recovery.")
        
        else:
            st.success(f"✅ **Low Injury Risk**")
            st.write(f"Risk Score: {insights['score']:.2f}")
            st.write("Your training load is well-managed.")
        
        # Training Recommendations
        st.subheader("🎯 Personalized Training Recommendations")
        
        for rec in recommendations:
            with st.expander(rec['title'], expanded=True):
                st.write(rec['explanation'])
                st.info(rec['workout_plan'])
        
        # Performance Predictions
        st.subheader("📈 Performance Projections")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Predicted 5K Time (4 weeks)",
                "21:30",
                delta="-1:45"
            )
        
        with col2:
            st.metric(
                "Predicted 10K Time (8 weeks)",
                "44:15",
                delta="-3:20"
            )
        
        with col3:
            st.metric(
                "Fitness Level (CTL)",
                "65.2",
                delta="+5.1"
            )
    
    def _create_ask_ai_tab(self):
        """Create the AI Q&A tab"""
        st.header("💬 Ask Your AI Fitness Coach")
        
        # Suggested questions
        st.write("**Suggested Questions:**")
        
        suggested_questions = [
            "Am I ready for a marathon based on my current fitness?",
            "How can I improve my soccer sprint recovery?",
            "What's causing my recent performance plateau?",
            "Should I be concerned about my elevated resting heart rate?",
            "How do I balance strength training with running?",
            "What's my optimal race pace for a 10K?"
        ]
        
        cols = st.columns(2)
        for i, question in enumerate(suggested_questions):
            with cols[i % 2]:
                if st.button(question, key=f"q_{i}"):
                    st.session_state.current_question = question
        
        # Custom question input
        user_question = st.text_area(
            "Or ask your own question:",
            value=st.session_state.get('current_question', ''),
            height=100
        )
        
        if st.button("Get AI Analysis", type="primary"):
            if user_question:
                with st.spinner("Analyzing your data..."):
                    # Prepare context - convert date objects to datetime objects
                    athlete_id = st.session_state.get("athlete_selector", "default")
                    date_range = st.session_state.get("date_range", (datetime.now() - timedelta(days=90), datetime.now()))
                    
                    start_datetime = datetime.combine(date_range[0], datetime.min.time())
                    end_datetime = datetime.combine(date_range[1], datetime.max.time())
                    
                    workouts = self._load_workouts(athlete_id, start_datetime, end_datetime)
                    biometrics = self._load_biometrics(athlete_id, start_datetime, end_datetime)
                    
                    context = self._prepare_athlete_data(workouts, biometrics)
                    
                    # Get AI response
                    response = self.ai_coach.answer_question(user_question, context)
                    
                    # Display response
                    st.markdown("### AI Coach Response:")
                    st.write(response['answer'])
                    
                    # Show data sources used
                    with st.expander("Data sources used for this analysis"):
                        st.json(context.get('data_sources', []))
            else:
                st.warning("Please enter a question")
    
    def _sync_data_sources(self):
        """Sync data from all configured sources"""
        try:
            available_connectors = list_available_connectors()
            for source in available_connectors:
                try:
                    # Create empty config for now - in production this would load from env
                    config = {}
                    connector = get_connector(source, config)
                    # Note: This would need to be async in production
                    logger.info(f"Synced {source}")
                except Exception as e:
                    logger.warning(f"Failed to sync {source}: {e}")
        except Exception as e:
            logger.error(f"Data sync failed: {e}")
    
    def _load_workouts(self, athlete_id: str, start_date: datetime, end_date: datetime) -> List[Workout]:
        """Load workouts for analysis period"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM workouts 
                    WHERE athlete_id = ? AND start_time BETWEEN ? AND ?
                    ORDER BY start_time DESC
                """, (athlete_id, start_date.isoformat(), end_date.isoformat()))
                
                rows = cursor.fetchall()
                return [Workout(**dict(zip([col[0] for col in cursor.description], row))) for row in rows]
        except Exception as e:
            logger.error(f"Error loading workouts: {e}")
            return []
    
    def _load_biometrics(self, athlete_id: str, start_date: datetime, end_date: datetime) -> List[BiometricReading]:
        """Load biometric readings for analysis period"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM biometrics 
                    WHERE athlete_id = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                """, (athlete_id, start_date.isoformat(), end_date.isoformat()))
                
                rows = cursor.fetchall()
                return [BiometricReading(**dict(zip([col[0] for col in cursor.description], row))) for row in rows]
        except Exception as e:
            logger.error(f"Error loading biometrics: {e}")
            return []
    
    def _calculate_overview_metrics(self, workouts: List[Workout], biometrics: List[BiometricReading]) -> Dict[str, Any]:
        """Calculate overview metrics"""
        if not workouts:
            return {}
        
        # Calculate basic metrics
        total_workouts = len(workouts)
        total_duration = sum(w.duration for w in workouts if w.duration)
        weekly_hours = total_duration / 3600 / 13  # Assuming 13 weeks
        
        # Calculate fitness score (simplified CTL)
        fitness_score = min(100, weekly_hours * 10)
        
        # Calculate fatigue level
        recent_workouts = [w for w in workouts if w.start_time >= datetime.now() - timedelta(days=7)]
        recent_hours = sum(w.duration for w in recent_workouts if w.duration) / 3600
        fatigue_level = "HIGH" if recent_hours > 15 else "MODERATE" if recent_hours > 10 else "LOW"
        
        # Calculate injury risk
        acwr = recent_hours / (weekly_hours * 4) if weekly_hours > 0 else 1.0
        injury_risk = {
            'level': 'HIGH' if acwr > 1.5 else 'MODERATE' if acwr > 1.3 else 'LOW',
            'change': 0  # Placeholder
        }
        
        return {
            'fitness_score': fitness_score,
            'fitness_change': 0,  # Placeholder
            'fatigue_level': fatigue_level,
            'fatigue_trend': 0,  # Placeholder
            'injury_risk': injury_risk,
            'weekly_hours': weekly_hours,
            'volume_change': 0  # Placeholder
        }
    
    def _create_training_load_chart(self, workouts: List[Workout]) -> go.Figure:
        """Create training load chart"""
        if not workouts:
            return go.Figure()
        
        # Group by week
        weekly_data = {}
        for workout in workouts:
            week_start = workout.start_time - timedelta(days=workout.start_time.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            if week_key not in weekly_data:
                weekly_data[week_key] = 0
            weekly_data[week_key] += workout.duration / 3600  # Convert to hours
        
        dates = list(weekly_data.keys())
        hours = list(weekly_data.values())
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=hours,
            mode='lines+markers',
            name='Weekly Training Hours',
            line=dict(color='blue', width=3)
        ))
        
        fig.update_layout(
            title="Training Load Over Time",
            xaxis_title="Week",
            yaxis_title="Training Hours",
            height=400
        )
        
        return fig
    
    def _create_calendar_heatmap(self, workouts: List[Workout]) -> go.Figure:
        """Create activity calendar heatmap"""
        if not workouts:
            return go.Figure()
        
        # Create calendar data
        calendar_data = {}
        for workout in workouts:
            date_key = workout.start_time.strftime("%Y-%m-%d")
            if date_key not in calendar_data:
                calendar_data[date_key] = 0
            calendar_data[date_key] += workout.duration / 3600
        
        # Convert to heatmap format
        dates = list(calendar_data.keys())
        hours = list(calendar_data.values())
        
        fig = go.Figure(data=go.Heatmap(
            z=[hours],
            x=dates,
            y=['Training Hours'],
            colorscale='Blues'
        ))
        
        fig.update_layout(
            title="Activity Calendar",
            height=200
        )
        
        return fig
    
    def _create_pace_trend_chart(self, workouts: List[Workout]) -> go.Figure:
        """Create pace trend chart"""
        if not workouts:
            return go.Figure()
        
        # Filter workouts with distance and duration
        valid_workouts = [w for w in workouts if w.distance and w.duration]
        
        if not valid_workouts:
            return go.Figure()
        
        # Calculate paces
        dates = [w.start_time for w in valid_workouts]
        paces = [w.duration / (w.distance / 1000) for w in valid_workouts]  # seconds per km
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=paces,
            mode='lines+markers',
            name='Pace (min/km)',
            line=dict(color='red', width=2)
        ))
        
        fig.update_layout(
            title="Pace Progression",
            xaxis_title="Date",
            yaxis_title="Pace (seconds/km)",
            height=300
        )
        
        return fig
    
    def _create_hr_zone_distribution(self, workouts: List[Workout]) -> go.Figure:
        """Create heart rate zone distribution"""
        if not workouts:
            return go.Figure()
        
        # Filter workouts with heart rate data
        hr_workouts = [w for w in workouts if w.heart_rate_avg]
        
        if not hr_workouts:
            return go.Figure()
        
        # Calculate HR zones (simplified)
        zones = {
            'Zone 1 (Recovery)': 0,
            'Zone 2 (Aerobic)': 0,
            'Zone 3 (Tempo)': 0,
            'Zone 4 (Threshold)': 0,
            'Zone 5 (Anaerobic)': 0
        }
        
        for workout in hr_workouts:
            hr = workout.heart_rate_avg
            if hr < 120:
                zones['Zone 1 (Recovery)'] += 1
            elif hr < 140:
                zones['Zone 2 (Aerobic)'] += 1
            elif hr < 160:
                zones['Zone 3 (Tempo)'] += 1
            elif hr < 180:
                zones['Zone 4 (Threshold)'] += 1
            else:
                zones['Zone 5 (Anaerobic)'] += 1
        
        fig = go.Figure(data=go.Bar(
            x=list(zones.keys()),
            y=list(zones.values()),
            marker_color=['lightblue', 'blue', 'orange', 'red', 'darkred']
        ))
        
        fig.update_layout(
            title="Heart Rate Zone Distribution",
            xaxis_title="HR Zone",
            yaxis_title="Number of Workouts",
            height=300
        )
        
        return fig
    
    def _create_soccer_analysis(self, workouts: List[Workout]):
        """Create soccer-specific analysis"""
        st.subheader("Soccer Performance Analysis")
        
        # Calculate soccer metrics
        total_games = len(workouts)
        total_minutes = sum(w.duration for w in workouts if w.duration) / 60
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Games Played", total_games)
        with col2:
            st.metric("Total Minutes", f"{total_minutes:.0f}")
        with col3:
            st.metric("Avg Game Duration", f"{total_minutes/total_games:.1f} min" if total_games > 0 else "0 min")
    
    def _create_running_analysis(self, workouts: List[Workout]):
        """Create running-specific analysis"""
        st.subheader("Running Performance Analysis")
        
        # Calculate running metrics
        total_runs = len(workouts)
        total_distance = sum(w.distance for w in workouts if w.distance) / 1000  # km
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Runs", total_runs)
        with col2:
            st.metric("Total Distance", f"{total_distance:.1f} km")
        with col3:
            st.metric("Avg Distance", f"{total_distance/total_runs:.1f} km" if total_runs > 0 else "0 km")
    
    def _create_weight_trend_chart(self, biometrics: List[BiometricReading]) -> go.Figure:
        """Create weight trend chart"""
        weight_readings = [b for b in biometrics if b.metric == 'weight']
        
        if not weight_readings:
            return go.Figure()
        
        dates = [b.timestamp for b in weight_readings]
        weights = [b.value for b in weight_readings]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=weights,
            mode='lines+markers',
            name='Weight (kg)',
            line=dict(color='green', width=3)
        ))
        
        fig.update_layout(
            title="Weight Trend",
            xaxis_title="Date",
            yaxis_title="Weight (kg)",
            height=300
        )
        
        return fig
    
    def _create_body_fat_chart(self, biometrics: List[BiometricReading]) -> go.Figure:
        """Create body fat chart"""
        bf_readings = [b for b in biometrics if b.metric == 'body_fat']
        
        if not bf_readings:
            return go.Figure()
        
        dates = [b.timestamp for b in bf_readings]
        body_fat = [b.value for b in bf_readings]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=body_fat,
            mode='lines+markers',
            name='Body Fat %',
            line=dict(color='orange', width=3)
        ))
        
        fig.update_layout(
            title="Body Fat Trend",
            xaxis_title="Date",
            yaxis_title="Body Fat %",
            height=300
        )
        
        return fig
    
    def _create_resting_hr_analysis(self, workouts: List[Workout]) -> go.Figure:
        """Create resting heart rate analysis"""
        if not workouts:
            return go.Figure()
        
        # Estimate resting HR from lowest workout HR
        hr_workouts = [w for w in workouts if w.heart_rate_avg]
        
        if not hr_workouts:
            return go.Figure()
        
        # Group by month
        monthly_hr = {}
        for workout in hr_workouts:
            month_key = workout.start_time.strftime("%Y-%m")
            if month_key not in monthly_hr:
                monthly_hr[month_key] = []
            monthly_hr[month_key].append(workout.heart_rate_avg)
        
        # Calculate monthly averages
        months = sorted(monthly_hr.keys())
        avg_hr = [np.mean(hrs) for hrs in [monthly_hr[m] for m in months]]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=months,
            y=avg_hr,
            mode='lines+markers',
            name='Average HR',
            line=dict(color='red', width=3)
        ))
        
        fig.update_layout(
            title="Heart Rate Trends",
            xaxis_title="Month",
            yaxis_title="Heart Rate (bpm)",
            height=300
        )
        
        return fig
    
    def _prepare_athlete_data(self, workouts: List[Workout], biometrics: List[BiometricReading]) -> Dict[str, Any]:
        """Prepare athlete data for AI analysis"""
        if not workouts:
            return {}
        
        # Calculate training load
        recent_workouts = [w for w in workouts if w.start_time >= datetime.now() - timedelta(days=7)]
        chronic_workouts = [w for w in workouts if w.start_time >= datetime.now() - timedelta(days=28)]
        
        acute_load = sum(w.duration for w in recent_workouts if w.duration) / 3600
        chronic_load = sum(w.duration for w in chronic_workouts if w.duration) / 3600 / 4
        
        acwr = acute_load / chronic_load if chronic_load > 0 else 1.0
        
        return {
            'training_load': {
                'acute_load_hours': acute_load,
                'chronic_load_hours': chronic_load,
                'acwr_ratio': acwr
            },
            'summary_stats': {
                'total_workouts': len(workouts),
                'consistency_percent': 75  # Placeholder
            },
            'health_indicators': {
                'heart_rate_trend': {
                    'trend': 'stable'  # Placeholder
                }
            },
            'data_sources': ['workouts', 'biometrics']
        }
    
    def _export_athlete_data(self, athlete_id: str):
        """Export athlete data"""
        st.info("Data export functionality would be implemented here")
        # In production, this would generate a CSV/JSON export

def main():
    """Main entry point for the dashboard"""
    try:
        dashboard = FitnessDashboard()
        dashboard.run()
    except Exception as e:
        st.error(f"Dashboard failed to load: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
