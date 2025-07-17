"""
MCB Rate Limiter Module
Redis-based rate limiting for secure and scalable request throttling.
Replaces the insecure in-memory rate limiting system.
"""
import redis
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Redis-based rate limiter for MCB application.
    Provides secure, scalable rate limiting that persists across application restarts.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize the rate limiter with Redis connection.
        
        Args:
            redis_url: Redis connection URL
        """
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis.ping()
            logger.info("Successfully connected to Redis for rate limiting")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory dict for development (not recommended for production)
            self.redis = None
            self._memory_store = {}
            logger.warning("Using in-memory fallback for rate limiting (not recommended for production)")
    
    def check_daily_limit(self, username: str, game_count: int, daily_limit: int = 200) -> tuple[bool, dict]:
        """
        Check if user is within daily game analysis limit.
        
        Args:
            username: Username to check
            game_count: Number of games being requested
            daily_limit: Maximum games allowed per day
            
        Returns:
            Tuple of (is_allowed, usage_info)
        """
        key = f"daily_usage:{username}:{datetime.now().strftime('%Y-%m-%d')}"
        
        try:
            if self.redis:
                current_usage = int(self.redis.get(key) or 0)
            else:
                # Fallback to memory store
                current_usage = self._memory_store.get(key, 0)
            
            if current_usage + game_count > daily_limit:
                return False, {
                    'daily_limit': daily_limit,
                    'used_today': current_usage,
                    'remaining': max(0, daily_limit - current_usage)
                }
            
            # Update usage with expiration
            new_usage = current_usage + game_count
            if self.redis:
                self.redis.setex(key, timedelta(days=1), new_usage)
            else:
                self._memory_store[key] = new_usage
            
            return True, {
                'daily_limit': daily_limit,
                'used_today': new_usage,
                'remaining': daily_limit - new_usage
            }
            
        except Exception as e:
            logger.error(f"Error checking daily limit for {username}: {e}")
            # On error, allow the request but log the issue
            return True, {
                'daily_limit': daily_limit,
                'used_today': 0,
                'remaining': daily_limit,
                'error': 'Rate limiting temporarily unavailable'
            }
    
    def check_minute_limit(self, username: str, requests_per_minute: int = 5) -> bool:
        """
        Check if user is within per-minute request limit.
        
        Args:
            username: Username to check
            requests_per_minute: Maximum requests allowed per minute
            
        Returns:
            True if request is allowed, False if rate limited
        """
        key = f"minute_limit:{username}:{int(time.time() // 60)}"
        
        try:
            if self.redis:
                current_requests = int(self.redis.get(key) or 0)
            else:
                # Fallback to memory store
                current_requests = self._memory_store.get(key, 0)
            
            if current_requests >= requests_per_minute:
                return False
            
            # Increment request count with 60-second expiration
            new_requests = current_requests + 1
            if self.redis:
                self.redis.setex(key, 60, new_requests)
            else:
                self._memory_store[key] = new_requests
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking minute limit for {username}: {e}")
            # On error, allow the request but log the issue
            return True
    
    def get_usage_stats(self, username: str) -> Dict[str, Any]:
        """
        Get current usage statistics for a user.
        
        Args:
            username: Username to check
            
        Returns:
            Dictionary with usage statistics
        """
        daily_key = f"daily_usage:{username}:{datetime.now().strftime('%Y-%m-%d')}"
        minute_key = f"minute_limit:{username}:{int(time.time() // 60)}"
        
        try:
            if self.redis:
                daily_usage = int(self.redis.get(daily_key) or 0)
                minute_usage = int(self.redis.get(minute_key) or 0)
            else:
                daily_usage = self._memory_store.get(daily_key, 0)
                minute_usage = self._memory_store.get(minute_key, 0)
            
            return {
                'daily_usage': daily_usage,
                'daily_remaining': max(0, 200 - daily_usage),
                'minute_usage': minute_usage,
                'minute_remaining': max(0, 5 - minute_usage)
            }
            
        except Exception as e:
            logger.error(f"Error getting usage stats for {username}: {e}")
            return {
                'daily_usage': 0,
                'daily_remaining': 200,
                'minute_usage': 0,
                'minute_remaining': 5,
                'error': 'Stats temporarily unavailable'
            }
    
    def reset_user_limits(self, username: str) -> bool:
        """
        Reset all limits for a user (admin function).
        
        Args:
            username: Username to reset
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.redis:
                # Get all keys for this user
                daily_key = f"daily_usage:{username}:*"
                minute_key = f"minute_limit:{username}:*"
                
                daily_keys = self.redis.keys(daily_key)
                minute_keys = self.redis.keys(minute_key)
                
                all_keys = daily_keys + minute_keys
                if all_keys:
                    self.redis.delete(*all_keys)
            else:
                # Remove from memory store
                keys_to_remove = [k for k in self._memory_store.keys() if username in k]
                for key in keys_to_remove:
                    del self._memory_store[key]
            
            logger.info(f"Reset rate limits for user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting limits for {username}: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the rate limiting system.
        
        Returns:
            Dictionary with health status
        """
        try:
            if self.redis:
                self.redis.ping()
                return {
                    'status': 'healthy',
                    'backend': 'redis',
                    'connection': 'active'
                }
            else:
                return {
                    'status': 'degraded',
                    'backend': 'memory',
                    'connection': 'fallback',
                    'warning': 'Using in-memory fallback - not recommended for production'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'backend': 'redis',
                'connection': 'failed',
                'error': str(e)
            }