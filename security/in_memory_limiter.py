"""
In-Memory Rate Limiter (Fallback)
A simple, non-persistent rate limiter for development or environments without Redis.
"""
import time
from collections import defaultdict

class InMemoryRateLimiter:
    def __init__(self):
        # {username: {'daily_count': count, 'daily_timestamp': timestamp}}
        self.daily_usage = defaultdict(lambda: {'count': 0, 'timestamp': 0})
        # {username: [timestamp1, timestamp2, ...]}
        self.minute_requests = defaultdict(list)
        print("Using in-memory fallback for rate limiting (not recommended for production)")

    def check_daily_limit(self, username: str, game_count: int, limit: int):
        """Checks if the user is within their daily game analysis limit."""
        now = time.time()
        user_data = self.daily_usage[username]

        # Reset daily count if a day has passed
        if now - user_data['timestamp'] > 86400:
            user_data['count'] = 0
            user_data['timestamp'] = now

        remaining = limit - user_data['count']
        if game_count > remaining:
            return False, {'limit': limit, 'remaining': remaining, 'reset_in_seconds': 86400 - (now - user_data['timestamp'])}

        # Increment count if check passes
        user_data['count'] += game_count
        return True, {'limit': limit, 'remaining': limit - user_data['count'], 'reset_in_seconds': 86400 - (now - user_data['timestamp'])}

    def check_minute_limit(self, username: str, limit: int = 5, period: int = 60):
        """Checks if the user is making too many requests per minute."""
        now = time.time()
        requests = self.minute_requests[username]

        # Remove timestamps older than the period
        requests = [t for t in requests if now - t < period]
        self.minute_requests[username] = requests

        if len(requests) >= limit:
            return False

        self.minute_requests[username].append(now)
        return True

    def health_check(self):
        """Health check for the in-memory limiter."""
        return {'status': 'ok', 'type': 'in-memory'}