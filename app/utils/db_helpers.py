"""Database helper utilities for improved performance and cleaner code.

This module provides:
- Context managers for database sessions
- Cached system settings with TTL
- Bulk operation helpers
- Query optimization utilities
"""

from contextlib import contextmanager
from functools import lru_cache
import time
from typing import Optional, Any, List, Dict
from app.db import SessionLocal
from app.models import SystemSetting


# Cache for system settings with TTL
_settings_cache: Dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 300  # 5 minutes


@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Ensures proper cleanup and error handling.
    
    Usage:
        with get_db_session() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_cached_setting(key: str, default: Any = None, use_cache: bool = True) -> Any:
    """
    Get a system setting with caching to reduce database queries.
    
    Args:
        key: Setting key to retrieve
        default: Default value if setting doesn't exist
        use_cache: Whether to use cache (set False to force DB read)
    
    Returns:
        Setting value or default
    """
    if use_cache:
        # Check cache
        if key in _settings_cache:
            value, timestamp = _settings_cache[key]
            if time.time() - timestamp < _CACHE_TTL:
                return value
    
    # Cache miss or expired, fetch from DB
    with get_db_session() as db:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        value = setting.value if setting else default
        
        # Update cache
        _settings_cache[key] = (value, time.time())
        
        return value


def get_cached_int_setting(key: str, default: int = 0, use_cache: bool = True) -> int:
    """Get an integer system setting with caching."""
    value = get_cached_setting(key, default, use_cache)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_cached_bool_setting(key: str, default: bool = False, use_cache: bool = True) -> bool:
    """Get a boolean system setting with caching."""
    value = get_cached_setting(key, str(default).lower(), use_cache)
    return str(value).lower() in ('true', '1', 'yes', 'on')


def invalidate_setting_cache(key: Optional[str] = None):
    """
    Invalidate cached settings.
    
    Args:
        key: Specific key to invalidate, or None to clear all cache
    """
    global _settings_cache
    if key:
        _settings_cache.pop(key, None)
    else:
        _settings_cache.clear()


def bulk_update_settings(settings: Dict[str, Any]):
    """
    Update multiple system settings in a single transaction.
    
    Args:
        settings: Dictionary of {key: value} pairs to update
    """
    with get_db_session() as db:
        for key, value in settings.items():
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not setting:
                setting = SystemSetting(key=key, value=str(value))
                db.add(setting)
            else:
                setting.value = str(value)
            
            # Invalidate cache for this key
            invalidate_setting_cache(key)
        
        db.commit()


def execute_with_retry(func, max_retries: int = 3, delay: float = 0.1):
    """
    Execute a database function with retry logic for handling locked database.
    
    Args:
        func: Function to execute (should accept db session as first arg)
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries fail
    """
    import sqlite3
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            with get_db_session() as db:
                return func(db)
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                continue
            raise
        except Exception:
            raise
    
    raise last_exception


# Lazy import optimization - only import when needed
_influx_client = None
_requests_session = None


def get_influx_client():
    """Lazy load InfluxDB client to reduce startup time."""
    global _influx_client
    if _influx_client is None:
        from influxdb_client import InfluxDBClient
        import os
        
        url = os.environ.get('INFLUX_URL', '')
        token = os.environ.get('INFLUX_TOKEN', '')
        org = os.environ.get('INFLUX_ORG', '')
        
        if url and token and org:
            _influx_client = InfluxDBClient(url=url, token=token, org=org)
    
    return _influx_client


def get_requests_session():
    """
    Get a shared requests session for connection pooling.
    Reusing sessions improves performance significantly.
    """
    global _requests_session
    if _requests_session is None:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        _requests_session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        _requests_session.mount("http://", adapter)
        _requests_session.mount("https://", adapter)
    
    return _requests_session
