import bcrypt
import jwt
from datetime import datetime, timedelta
import re
import json
import os
from functools import wraps
from flask import jsonify, request

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

class SecurityManager:
    def __init__(self):
        self.failed_attempts = {}
        self.blocked_ips = {}
        self.activity_log = []
        self.load_security_config()

    def load_security_config(self):
        config_file = os.path.join(os.path.dirname(__file__), "system_config.json")
        with open(config_file, 'r') as f:
            config = json.load(f)
            self.security_config = config.get('security', {})

    def validate_password_strength(self, password):
        """Check password against security policy."""
        policy = self.security_config.get('password_policy', {})
        
        if len(password) < policy.get('min_length', 8):
            return False, "Password too short"
        
        if policy.get('require_uppercase') and not any(c.isupper() for c in password):
            return False, "Password must contain uppercase letters"
            
        if policy.get('require_numbers') and not any(c.isdigit() for c in password):
            return False, "Password must contain numbers"
            
        if policy.get('require_special') and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain special characters"
            
        return True, "Password meets requirements"

    def check_rate_limit(self, ip_address):
        """Check if IP is within rate limits."""
        if ip_address in self.blocked_ips:
            if datetime.now() < self.blocked_ips[ip_address]:
                return False, "IP temporarily blocked"
            else:
                del self.blocked_ips[ip_address]
                
        attempts = self.failed_attempts.get(ip_address, [])
        current_time = datetime.now()
        
        # Remove attempts older than 15 minutes
        attempts = [time for time in attempts if (current_time - time).seconds < 900]
        self.failed_attempts[ip_address] = attempts
        
        if len(attempts) >= self.security_config.get('max_login_attempts', 5):
            self.blocked_ips[ip_address] = current_time + timedelta(minutes=15)
            return False, "Too many failed attempts"
            
        return True, "Within rate limit"

    def log_failed_attempt(self, ip_address):
        """Log failed login attempt."""
        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = []
        self.failed_attempts[ip_address].append(datetime.now())

    def generate_token(self, user_data):
        """Generate JWT token with refresh capability."""
        exp = datetime.utcnow() + timedelta(minutes=self.security_config.get('session_timeout_minutes', 60))
        refresh_exp = datetime.utcnow() + timedelta(days=7)
        
        token = jwt.encode({
            **user_data,
            'exp': exp,
            'iat': datetime.utcnow()
        }, SECRET_KEY, algorithm='HS256')
        
        refresh_token = jwt.encode({
            'user_id': user_data.get('user_id'),
            'exp': refresh_exp,
            'iat': datetime.utcnow(),
            'refresh': True
        }, SECRET_KEY, algorithm='HS256')
        
        return token, refresh_token

    def verify_token(self, token):
        """Verify JWT token."""
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return True, data
        except jwt.ExpiredSignatureError:
            return False, "Token expired"
        except jwt.InvalidTokenError:
            return False, "Invalid token"

    def log_activity(self, user_id, action, details=None):
        """Log admin activity for audit."""
        activity = {
            'user_id': user_id,
            'action': action,
            'timestamp': datetime.utcnow().isoformat(),
            'ip_address': request.remote_addr,
            'details': details
        }
        self.activity_log.append(activity)
        self._save_activity_log()

    def _save_activity_log(self):
        """Save activity log to file."""
        log_file = os.path.join(os.path.dirname(__file__), "admin_activity.json")
        with open(log_file, 'w') as f:
            json.dump(self.activity_log, f, indent=2)

# Initialize security manager
security_manager = SecurityManager()

def require_admin(f):
    """Decorator for admin-only routes with enhanced security."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
            
        token = token.replace('Bearer ', '')
        valid, data = security_manager.verify_token(token)
        
        if not valid:
            return jsonify({'error': data}), 401
            
        if data.get('role') != 'admin':
            security_manager.log_activity(
                data.get('user_id'),
                'unauthorized_access_attempt',
                {'endpoint': request.endpoint}
            )
            return jsonify({'error': 'Admin access required'}), 403
            
        # Log admin activity
        security_manager.log_activity(
            data.get('user_id'),
            'api_access',
            {'endpoint': request.endpoint, 'method': request.method}
        )
        return f(*args, **kwargs)
    return decorated

def sanitize_input(data):
    """Sanitize input data to prevent injection attacks."""
    if isinstance(data, str):
        # Remove potential script tags
        data = re.sub(r'<script[^>]*>.*?</script>', '', data, flags=re.DOTALL)
        # Remove other potentially dangerous HTML tags
        data = re.sub(r'<[^>]*>', '', data)
        # Escape special characters
        data = data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return data
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(x) for x in data]
    return data

def validate_ip_address(ip):
    """Validate IP address format."""
    pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return bool(re.match(pattern, ip))