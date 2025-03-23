from flask import request, abort
import time
from collections import defaultdict
import re

class RequestTracker:
    def __init__(self):
        self.requests = defaultdict(list)
        self.sequential_access = defaultdict(list)
        self.time_pattern_access = defaultdict(list)
    
    def cleanup_old_requests(self, threshold_time):
        current_time = time.time()
        for ip in list(self.requests.keys()):
            self.requests[ip] = [t for t in self.requests[ip] if current_time - t < threshold_time]
            if not self.requests[ip]:
                del self.requests[ip]

class SecurityMiddleware:
    def __init__(self, app, bot_detection, rate_limits):
        self.app = app
        self.bot_detection = bot_detection
        self.rate_limits = rate_limits
        self.request_tracker = RequestTracker()
        
        # Register middleware
        app.before_request(self.check_request)
    
    def is_bot(self):
        user_agent = request.headers.get('User-Agent', '').lower()
        return any(pattern in user_agent for pattern in self.bot_detection['user_agent_patterns'])
    
    def check_rate_limits(self, ip):
        current_time = time.time()
        self.request_tracker.cleanup_old_requests(3600)  # Cleanup entries older than 1 hour
        
        # Add current request
        self.request_tracker.requests[ip].append(current_time)
        
        # Check endpoint-specific limits
        endpoint = request.endpoint
        if endpoint in self.rate_limits['endpoints']:
            recent_requests = len([t for t in self.request_tracker.requests[ip] 
                                if current_time - t < 60])
            if recent_requests > self.rate_limits['endpoints'][endpoint]['requests_per_minute']:
                return False
        
        # Check global limits
        minute_requests = len([t for t in self.request_tracker.requests[ip] 
                             if current_time - t < 60])
        hour_requests = len([t for t in self.request_tracker.requests[ip] 
                           if current_time - t < 3600])
        
        return (minute_requests <= self.rate_limits['global']['requests_per_minute'] and 
                hour_requests <= self.rate_limits['global']['requests_per_hour'])
    
    def check_suspicious_patterns(self, ip):
        if not self.bot_detection['request_patterns']['suspicious_patterns']['sequential_access']:
            return False
            
        current_path = request.path
        id_match = re.search(r'/\d+', current_path)
        if id_match:
            current_id = int(id_match.group()[1:])
            self.request_tracker.sequential_access[ip].append(current_id)
            
            # Check last 5 requests for sequential pattern
            recent_ids = self.request_tracker.sequential_access[ip][-5:]
            if len(recent_ids) >= 3:
                is_sequential = all(recent_ids[i] + 1 == recent_ids[i + 1] 
                                  for i in range(len(recent_ids) - 1))
                if is_sequential:
                    return True
        
        return False
    
    def check_request(self):
        ip = request.remote_addr
        
        # Check if it's a bot
        if self.bot_detection['enabled'] and self.is_bot():
            abort(403, "Bot access denied")
        
        # Check rate limits
        if not self.check_rate_limits(ip):
            abort(429, "Rate limit exceeded")
        
        # Check suspicious patterns
        if self.check_suspicious_patterns(ip):
            abort(403, "Suspicious access pattern detected")
        
        return None
