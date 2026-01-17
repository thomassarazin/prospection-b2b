import time
import logging
from typing import Optional, Callable

class RateLimiter:
    """Rate limiter intelligent par API"""

    def __init__(self):
        self.limits = {
            "pappers": {"calls": 0, "window_start": 0, "max_per_minute": 30},
            "dropcontact": {"calls": 0, "window_start": 0, "max_per_minute": 3600},
            "default": {"calls": 0, "window_start": 0, "max_per_minute": 60}
        }

    def wait_if_needed(self, api_name: str = "default", log_fn: Optional[Callable[[str, str], None]] = None):
        """Attend si nécessaire pour respecter le rate limit"""
        
        logger = logging.getLogger("prospection_pipeline")
        now = time.time()
        limit_info = self.limits.get(api_name, self.limits["default"])

        # Reset window si > 60 secondes
        if now - limit_info["window_start"] > 60:
            limit_info["calls"] = 0
            limit_info["window_start"] = now

        # Check si rate limit atteint
        if limit_info["calls"] >= limit_info["max_per_minute"]:
            wait_time = 60 - (now - limit_info["window_start"])
            if wait_time > 0:
                logger.info(f"🚦 Rate limit {api_name}: attente {wait_time:.1f}s")
                time.sleep(wait_time)
                # Reset après attente
                limit_info["calls"] = 0
                limit_info["window_start"] = time.time()

        # Incrémenter compteur
        limit_info["calls"] += 1
