#!/usr/bin/env python3
"""
API module for multi-tenant fitness platform
"""

from .main import app
from .auth import router as auth_router
from .sources import router as sources_router
from .workouts import router as workouts_router
from .biometrics import router as biometrics_router
from .analysis import router as analysis_router
from .chat import router as chat_router
from .export import router as export_router

__all__ = [
    'app',
    'auth_router',
    'sources_router', 
    'workouts_router',
    'biometrics_router',
    'analysis_router',
    'chat_router',
    'export_router'
]
