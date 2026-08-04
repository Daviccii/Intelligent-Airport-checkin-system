import csv
import re
from flask import Flask, request, jsonify, send_from_directory, redirect, send_file, Response, stream_with_context
from flask_cors import CORS
from security_utils import security_manager, sanitize_input, validate_passport, require_admin
import bcrypt
from flight_manager import FlightManager
from activity_tracker import log_activity, get_activities, get_bookings_log, get_checkins_log, get_payments_log, save_activities
import json
import os
from dotenv import load_dotenv
import threading
from PIL import Image, ImageChops, ImageStat, ImageDraw, ImageFont
import io
import random
from datetime import datetime, timedelta, timezone
import smtplib
from email.message import EmailMessage
import urllib.parse
import qrcode
import secrets
import time
import logging
from mpesa_integration import mpesa_integration, sms_integration, email_integration
from validation_utils import ValidationUtils, ValidationError, validate_form_data
from dynamic_booking_api import register_dynamic_booking_endpoints

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to initialize RQ queue for background jobs (optional)
RQ_QUEUE = None
try:
    import redis
    from rq import Queue
    redis_port_str = os.getenv('REDIS_PORT', '6379')
    try:
        redis_port = int(redis_port_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid REDIS_PORT value: {redis_port_str}, using default 6379")
        redis_port = 6379
    redis_conn = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=redis_port, db=0)
    RQ_QUEUE = Queue(connection=redis_conn)
except Exception:
    # RQ/Redis not available; will fall back to threading
    pass

# Basic file/directory configuration (safe defaults)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))
# Portal-specific directories
PASSENGER_DIR = os.path.join(FRONTEND_DIR, 'passenger')
ADMIN_DIR = os.path.join(FRONTEND_DIR, 'admin')
STAFF_DIR = os.path.join(FRONTEND_DIR, 'staff')
MEMBER_DIR = os.path.join(FRONTEND_DIR, 'member')
EVENTS_FILE = os.path.join(BASE_DIR, 'events.json')
PASSENGER_FILE = os.path.join(BASE_DIR, 'passengers.json')
SESSIONS_FILE = os.path.join(BASE_DIR, 'sessions.json')
ACCESS_CODES_FILE = os.path.join(BASE_DIR, 'access_codes.json')
ADMIN_USERS_FILE = os.path.join(BASE_DIR, 'admin_users.json')
MEMBER_USERS_FILE = os.path.join(BASE_DIR, 'member_users.json')
HOLDS_FILE = os.path.join(BASE_DIR, 'holds.json')
OPENAPI_FILE = os.path.join(BASE_DIR, 'openapi.json')
BOOKINGS_FILE = os.path.join(BASE_DIR, 'bookings.json')
FLIGHTS_FILE = os.path.join(BASE_DIR, 'flights.json')
ANNOUNCEMENTS_FILE = os.path.join(BASE_DIR, 'announcements.json')
FACE_DIR = os.path.join(BASE_DIR, 'face_store')
SETTINGS_FILE = os.path.join(BASE_DIR, 'system_config.json')
STAFF_FILE = os.path.join(BASE_DIR, 'staff.json')
STAFF_ALLOWED_PERMISSIONS = [
    'view_passengers',
    'view_flights',
    'view_dashboard',
    'edit_passengers'
]

# Each portal gets its OWN session cookie name. Previously every portal
# (passenger/admin/staff/member) set a cookie named plain 'session' on
# path '/', so logging into any one portal in a browser silently
# overwrote the session cookie for every other portal open in that same
# browser -- e.g. logging into /staff after /admin would clobber the
# admin session, making admin/staff pages randomly "stop working"
# depending on login order.
SESSION_COOKIE_NAMES = {
    'admin': 'admin_session',
    'staff': 'staff_session',
    'member': 'member_session',
    'passenger': 'passenger_session',
}
try:
    os.makedirs(FRONTEND_DIR, exist_ok=True)
except Exception:
    pass
try:
    os.makedirs(FACE_DIR, exist_ok=True)
except Exception:
    pass

# In tests we prefer a clean in-memory `passengers` list. When running
# the server directly (as __main__), we'll load persisted data from
# `passengers.json` just before starting the app.
passengers = []
fm = FlightManager()

# Flask app instance
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
# Enable CORS for API routes to support local file-served frontend during development
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Register dynamic booking endpoints
register_dynamic_booking_endpoints(app)

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _load_json_file(filepath, default=None):
    """Load JSON from file, return default if not found or invalid."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}

def _save_json_file(filepath, data):
    """Save JSON to file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f'Error saving to {filepath}: {e}')
        return False

def _load_passengers():
    """Load persisted passengers from passengers.json."""
    data = _load_json_file(PASSENGER_FILE, [])
    return data if isinstance(data, list) else []

# Restore any previously-persisted passengers so `/api/passengers`, check-in,
# and seat-assignment flows see real data after a restart instead of starting
# from an empty list (the in-memory `passengers` list above was never being
# reloaded from disk, so every restart silently dropped all existing
# passengers and the next save overwrote passengers.json with only whatever
# had been created since that restart).
passengers = _load_passengers()

def _normalize_phone(phone):
    if not phone:
        return ''
    normalized = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if normalized.startswith('00'):
        normalized = '+' + normalized[2:]
    return normalized

def _smtp_send_message(msg):
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT') or 0)
    if not smtp_host or not smtp_port:
        raise RuntimeError('SMTP is not configured')
    use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
    starttls = os.getenv('SMTP_STARTTLS', 'false').lower() in ('1', 'true', 'yes')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')

    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.ehlo()
        if starttls:
            server.starttls()
            server.ehlo()

    try:
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass

def _send_sms_via_gateway(phone, message):
    gateway = os.getenv('SMS_GATEWAY_DOMAIN')
    if not gateway:
        raise RuntimeError('SMS gateway domain not configured')
    to_addr = f"{phone}@{gateway}"
    msg = EmailMessage()
    msg['Subject'] = os.getenv('SMS_SUBJECT', 'SMS Notification')
    msg['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER') or 'no-reply@example.com'
    msg['To'] = to_addr
    msg.set_content(message)
    _smtp_send_message(msg)
    return True

def _send_sms_via_twilio(phone, message):
    import base64
    import urllib.request
    import urllib.parse

    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_FROM_NUMBER')
    if not (account_sid and auth_token and from_number):
        raise RuntimeError('Twilio configuration missing')

    data = urllib.parse.urlencode({
        'From': from_number,
        'To': phone,
        'Body': message
    }).encode('utf-8')
    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    req = urllib.request.Request(url, data=data, method='POST')
    basic = base64.b64encode(f'{account_sid}:{auth_token}'.encode('utf-8')).decode('ascii')
    req.add_header('Authorization', f'Basic {basic}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f'Twilio SMS failed with status {resp.status}')
    return True

def _send_sms_message(phone, message):
    phone = _normalize_phone(phone)
    if not phone:
        raise RuntimeError('Invalid phone number')
    if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
        return _send_sms_via_twilio(phone, message)
    if os.getenv('SMS_GATEWAY_DOMAIN'):
        return _send_sms_via_gateway(phone, message)
    raise RuntimeError('No SMS provider configured')

def send_booking_confirmation_sms(passenger, booking_ref, flight_details):
    """Send booking confirmation SMS to the passenger."""
    phone = passenger.get('phone') or passenger.get('mpesa_phone')
    if not phone:
        log_event({
            'type': 'booking_sms_skipped',
            'passport': passenger.get('passport'),
            'booking_ref': booking_ref,
            'reason': 'no_phone_available',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        return False

    phone = _normalize_phone(phone)
    if not phone:
        log_event({
            'type': 'booking_sms_skipped',
            'passport': passenger.get('passport'),
            'booking_ref': booking_ref,
            'reason': 'invalid_phone',
            'raw_phone': passenger.get('phone') or passenger.get('mpesa_phone'),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        return False

    paybill = os.getenv('MPESA_PAYBILL', '123456')
    account_ref = os.getenv('MPESA_ACCOUNT_PREFIX', 'SF') + passenger.get('passport', '')[-4:]
    message_parts = [
        f"SmartFly booking {booking_ref} confirmed.",
        f"Flight {flight_details.get('flight', 'N/A')} {flight_details.get('from', '')}→{flight_details.get('to', '')}.",
        f"{flight_details.get('date', 'N/A')} at {flight_details.get('departure', 'N/A')}.",
    ]
    if passenger.get('payment_method', '').lower() == 'm-pesa':
        message_parts.append(
            f"Pay {passenger.get('amount')} {passenger.get('currency')} via M-Pesa Paybill {paybill}, account {account_ref}."
        )
    message_parts.append("Check your email for full booking details.")
    message = ' '.join(message_parts)

    log_event({
        'type': 'booking_sms_send_attempt',
        'passport': passenger.get('passport'),
        'booking_ref': booking_ref,
        'to': phone,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

    _send_sms_message(phone, message)

    log_event({
        'type': 'booking_sms_sent',
        'passport': passenger.get('passport'),
        'booking_ref': booking_ref,
        'to': phone,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
    return True

def _get_session_from_request(request, role=None):
    """Extract session token from request headers or cookies.

    The X-SESSION / Authorization header always wins when present. If we
    have to fall back to a cookie, use the cookie for the given `role`
    when known; otherwise check every portal's cookie (and the legacy
    'session' cookie, for any old sessions still on disk).
    """
    token = request.headers.get('X-SESSION') or request.headers.get('Authorization', '')
    if token.startswith('Bearer '):
        token = token[7:]
    if token:
        return token
    if role:
        return request.cookies.get(SESSION_COOKIE_NAMES.get(role, 'session'), '')
    for cookie_name in SESSION_COOKIE_NAMES.values():
        value = request.cookies.get(cookie_name)
        if value:
            return value
    return request.cookies.get('session', '')

def _require_session(request, require_role=None):
    """Check if user has valid session. Returns session dict or None."""
    token = _get_session_from_request(request, role=require_role)
    if not token:
        return None
    
    # Load sessions file
    sessions = _load_json_file(SESSIONS_FILE, {})
    session_data = sessions.get(token)
    
    if not session_data:
        return None
    
    # Expiry check (cleanup if expired)
    expires_at = session_data.get('expires_at')
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if exp_dt < datetime.now(timezone.utc):
                sessions.pop(token, None)
                _save_json_file(SESSIONS_FILE, sessions)
                return None
        except Exception:
            pass

    # Check if role matches (if required)
    if require_role and session_data.get('role') != require_role:
        return None
    
    return session_data

def _create_session(user_identifier, role, extra_data=None, ttl_seconds=86400):
    """Create a session token and persist it to sessions.json."""
    try:
        sessions = _load_json_file(SESSIONS_FILE, {})
        if not isinstance(sessions, dict):
            sessions = {}
    except Exception:
        sessions = {}
    
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session_entry = {
        'user_id': user_identifier,
        'username': user_identifier,
        'role': role,
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(seconds=ttl_seconds)).isoformat()
    }
    if extra_data:
        session_entry.update(extra_data)

    sessions[token] = session_entry
    _save_json_file(SESSIONS_FILE, sessions)
    
    public_session_entry = {
        'expires': session_entry['expires_at'],
        'role': session_entry['role'],
        'username': session_entry.get('username'),
        'user_id': session_entry.get('user_id')
    }
    return token, public_session_entry

def _init_admin_users_from_env():
    # If no admin user file exists, but env vars present, create hashed entry
    users = _load_json_file(ADMIN_USERS_FILE, {})
    if users:
        return users
    admin_user = os.getenv('ADMIN_USER')
    admin_pass = os.getenv('ADMIN_PASS')
    if admin_user and admin_pass:
        try:
            ph = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users = {admin_user: {'password_hash': ph}}
            _save_json_file(ADMIN_USERS_FILE, users)
            return users
        except Exception:
            return {}
    return {}

def _load_admin_users():
    """Load admin users (username -> {password_hash, ...}), seeding from env vars if the file doesn't exist yet."""
    users = _init_admin_users_from_env()
    if not isinstance(users, dict):
        users = {}
    return users

def _delete_session(token):
    """Delete a session token."""
    try:
        sessions = _load_json_file(SESSIONS_FILE, {})
        if token in sessions:
            del sessions[token]
            _save_json_file(SESSIONS_FILE, sessions)
    except Exception:
        pass

def _compute_baggage_fee(baggage_count: int):
    """Simple baggage fee rule: first bag free, each extra bag $50."""
    try:
        n = int(baggage_count or 0)
    except Exception:
        n = 0
    if n <= 1:
        return 0
    return 50 * (n - 1)

def _write_env_file(updates: dict):
    """Write key-value pairs to .env file (best-effort)."""
    # This is a simplified implementation. A more robust one would parse existing .env.
    with open(os.path.join(BASE_DIR, '.env'), 'a') as f:
        f.write('\n' + '\n'.join(f'{k}="{v}"' for k, v in updates.items() if v is not None))


def _has_admin_session():
    try:
        return bool(_require_session(request, require_role='admin'))
    except Exception:
        return False


def _has_staff_session():
    try:
        return bool(_require_session(request, require_role='staff'))
    except Exception:
        return False


def _has_member_session():
    try:
        return bool(_require_session(request, require_role='member'))
    except Exception:
        return False


def _generate_staff_id():
    """
    Generate a realistic staff ID in format: SF-2026-00001A
    Structure: [Airline Code]-[Year]-[Sequential Number + Letter]
    Example: SF-2026-00042B means 42 staff members created in 2026, B batch
    """
    try:
        # Load existing staff to get next sequence number
        staff_list = _load_json_file(STAFF_FILE, [])
        
        # Count staff members created in current year
        current_year = datetime.now(timezone.utc).year
        current_year_staff = [
            s for s in staff_list 
            if s.get('created_at', '').startswith(str(current_year))
        ]
        
        # Next sequence number (1-indexed)
        sequence = len(current_year_staff) + 1
        
        # Generate batch letter based on sequence (A-Z, AA-ZZ, etc.)
        letter_code = chr(65 + (sequence % 26)) if sequence <= 26 else f"A{chr(65 + ((sequence - 1) % 26))}"
        
        # Format: SF-YEAR-SEQUENCE+LETTER (e.g., SF-2026-00042B)
        staff_id = f"SF-{current_year}-{sequence:05d}{letter_code}"
        
        return staff_id
    except Exception as e:
        print(f"Error generating staff ID: {e}")
        # Fallback to random ID if anything fails
        return f"SF-{datetime.now(timezone.utc).year}-{secrets.token_hex(4).upper()}"

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route('/api/admin/settings', methods=['GET', 'POST'])
def api_admin_settings():
    """Get or save admin settings"""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    if request.method == 'GET':
        data = _load_json_file(SETTINGS_FILE, {})
        # Provide sensible defaults if file empty
        defaults = {
            'system_name': 'SmartFly Airlines',
            'system_email': '',
            'timezone': 'UTC',
            'date_format': 'MM/DD/YYYY',
            'admin_session_ttl': 3600,
            'passenger_session_ttl': 7200,
            'enable_mfa': False,
            'enable_audit_log': True,
            'email_notifications': True,
            'sms_notifications': False,
            'slack_notifications': False,
            # Notification provider defaults
            'sms_provider': os.getenv('SMS_PROVIDER', 'mojawave'),
            'mojawave_api_key': os.getenv('MOJAWAVE_API_KEY', ''),
            'sendly_api_key': os.getenv('SENDLY_API_KEY', ''),
            'azure_communication_connection_string': os.getenv('AZURE_COMMUNICATION_CONNECTION_STRING', ''),
            'sms_sender_id': os.getenv('SMS_SENDER_ID', 'SmartFly Airlines'),
            'email_provider': os.getenv('EMAIL_PROVIDER', 'resend'),
            'resend_api_key': os.getenv('RESEND_API_KEY', ''),
            'sendgrid_api_key': os.getenv('SENDGRID_API_KEY', ''),
            'email_from': os.getenv('EMAIL_FROM', 'SmartFly <smartfly01@gmail.com>'),
            'email_from_name': os.getenv('EMAIL_FROM_NAME', 'SmartFly Airways'),
            'smtp_host': os.getenv('SMTP_HOST', ''),
            'smtp_port': int(os.getenv('SMTP_PORT') or 0),
            'smtp_user': os.getenv('SMTP_USER', ''),
            'smtp_pass': os.getenv('SMTP_PASS', ''),
            'smtp_starttls': os.getenv('SMTP_STARTTLS', 'false').lower() in ('1','true','yes'),
            'notify_email': '',
            'maintenance_mode': False,
            'maintenance_message': '',
            'backup_frequency': 'daily'
        }
        if not isinstance(data, dict):
            data = {}
        merged = {**defaults, **data}
        return jsonify(merged), 200
    
    elif request.method == 'POST':
        try:
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                return jsonify({'error': 'invalid_payload'}), 400
            # Keep only known keys to avoid arbitrary file writes
            allowed_keys = {
                'system_name', 'system_email', 'timezone', 'date_format',
                'admin_session_ttl', 'passenger_session_ttl',
                'enable_mfa', 'enable_audit_log',
                'email_notifications', 'sms_notifications', 'slack_notifications',
                'notify_email', 'maintenance_mode', 'maintenance_message',
                'backup_frequency',
                # Notification provider keys
                'sms_provider', 'mojawave_api_key', 'sendly_api_key', 'azure_communication_connection_string', 'sms_sender_id',
                'email_provider', 'resend_api_key', 'sendgrid_api_key', 'email_from', 'email_from_name',
                'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_starttls'
            }
            clean = {k: payload.get(k) for k in allowed_keys if k in payload}
            existing = _load_json_file(SETTINGS_FILE, {})
            if not isinstance(existing, dict):
                existing = {}
            to_save = {**existing, **clean}
            _save_json_file(SETTINGS_FILE, to_save)
            # Also apply provider values to runtime environment and notification service
            try:
                # Update environment variables for persistence in current process
                env_map = {
                    'SMS_PROVIDER': to_save.get('sms_provider'),
                    'MOJAWAVE_API_KEY': to_save.get('mojawave_api_key'),
                    'SENDLY_API_KEY': to_save.get('sendly_api_key'),
                    'AZURE_COMMUNICATION_CONNECTION_STRING': to_save.get('azure_communication_connection_string'),
                    'SMS_SENDER_ID': to_save.get('sms_sender_id'),
                    'EMAIL_PROVIDER': to_save.get('email_provider'),
                    'RESEND_API_KEY': to_save.get('resend_api_key'),
                    'SENDGRID_API_KEY': to_save.get('sendgrid_api_key'),
                    'EMAIL_FROM': to_save.get('email_from'),
                    'EMAIL_FROM_NAME': to_save.get('email_from_name'),
                    'SMTP_HOST': to_save.get('smtp_host'),
                    'SMTP_PORT': str(to_save.get('smtp_port') or ''),
                    'SMTP_USER': to_save.get('smtp_user'),
                    'SMTP_PASS': to_save.get('smtp_pass'),
                    'SMTP_STARTTLS': 'true' if to_save.get('smtp_starttls') else 'false'
                }
                for k, v in env_map.items():
                    if v is None:
                        continue
                    if v == '':
                        # do not override real env if empty
                        continue
                    os.environ[k] = str(v)

            except Exception:
                pass
            return jsonify({'ok': True}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# ---- Staff Management API (admin) ----
@app.route('/api/admin/test-staff-route', methods=['GET'])
def test_staff_route():
    """Test route to verify staff routes are loaded"""
    return jsonify({'message': 'Staff routes are loaded', 'timestamp': datetime.now(timezone.utc).isoformat()}), 200

@app.route('/api/admin/staff', methods=['GET', 'POST'])
def api_staff_list():
    """Get all staff members (GET) or create a new staff member (POST)"""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    if request.method == 'GET':
        try:
            staff_list = _load_json_file(STAFF_FILE, [])
            if not isinstance(staff_list, list):
                staff_list = []
            # Remove password hashes from response
            clean_staff = []
            for s in staff_list:
                clean_s = {k: v for k, v in s.items() if k != 'password_hash'}
                clean_staff.append(clean_s)
            return jsonify({'staff': clean_staff}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            payload = request.get_json(silent=True) or {}
            validator = ValidationUtils()
            
            # Validate required fields using comprehensive validation
            try:
                name = validator.validate_name(payload.get('name'), field_name="name")
                username = validator.validate_required_field(payload.get('username'), field_name="username")
                password = validator.validate_password(payload.get('password'), field_name="password", min_length=8, require_special=False)
                
                # Optional email validation
                email = None
                if payload.get('email'):
                    email = validator.validate_email(payload.get('email'), field_name="email")
                    
            except ValidationError as e:
                return jsonify({'error': 'validation_error', 'field': e.field, 'detail': e.message}), 400
            
            permissions = payload.get('permissions', [])
            
            # Load existing staff
            staff_list = _load_json_file(STAFF_FILE, [])
            if not isinstance(staff_list, list):
                staff_list = []
            
            # Check if username already exists
            if any(s.get('username') == username for s in staff_list):
                return jsonify({'error': 'username_exists'}), 409
            
            # Normalize and validate permissions
            if isinstance(permissions, list):
                permissions = [p for p in permissions if p in STAFF_ALLOWED_PERMISSIONS]
            else:
                permissions = []
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create staff record with realistic ID
            staff_record = {
                'username': username,
                'name': name,
                'email': email,
                'password_hash': password_hash,
                'role': 'staff',
                'system_id': _generate_staff_id(),
                'permissions': permissions,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            staff_list.append(staff_record)
            _save_json_file(STAFF_FILE, staff_list)
            
            # Return staff record without password
            response = {k: v for k, v in staff_record.items() if k != 'password_hash'}
            return jsonify({'ok': True, 'staff': response}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/admin/staff/<username>', methods=['DELETE', 'PUT'])
def api_staff_detail(username):
    """Delete a staff member (DELETE) or update staff (PUT)"""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    if request.method == 'DELETE':
        try:
            staff_list = _load_json_file(STAFF_FILE, [])
            if not isinstance(staff_list, list):
                staff_list = []
            
            # Find and remove staff
            original_len = len(staff_list)
            staff_list = [s for s in staff_list if s.get('username') != username]
            
            if len(staff_list) == original_len:
                return jsonify({'error': 'staff_not_found'}), 404
            
            _save_json_file(STAFF_FILE, staff_list)
            return jsonify({'ok': True}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # PUT method will be handled below for password/permissions updates

@app.route('/api/admin/staff/<username>/password', methods=['PUT'])
def api_reset_staff_password(username):
    """Reset a staff member's password"""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
    try:
        payload = request.get_json(silent=True) or {}
        validator = ValidationUtils()
        
        try:
            password = validator.validate_password(payload.get('password'), field_name="password", min_length=8, require_special=False)
        except ValidationError as e:
            return jsonify({'error': 'validation_error', 'field': e.field, 'detail': e.message}), 400
        
        staff_list = _load_json_file(STAFF_FILE, [])
        if not isinstance(staff_list, list):
            staff_list = []
        
        # Find and update staff
        found = False
        for staff in staff_list:
            if staff.get('username') == username:
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                staff['password_hash'] = password_hash
                staff['updated_at'] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        
        if not found:
            return jsonify({'error': 'staff_not_found'}), 404
        
        _save_json_file(STAFF_FILE, staff_list)
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/staff/<username>/permissions', methods=['PUT'])
def api_update_staff_permissions(username):
    """Update a staff member's permissions"""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
    try:
        payload = request.get_json(silent=True) or {}
        permissions = payload.get('permissions', [])
        
        # Validate and normalize permissions
        if isinstance(permissions, list):
            permissions = [p for p in permissions if p in STAFF_ALLOWED_PERMISSIONS]
        else:
            permissions = []
        
        staff_list = _load_json_file(STAFF_FILE, [])
        if not isinstance(staff_list, list):
            staff_list = []
        
        # Find and update staff
        found = False
        for staff in staff_list:
            if staff.get('username') == username:
                staff['permissions'] = permissions
                staff['updated_at'] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        
        if not found:
            return jsonify({'error': 'staff_not_found'}), 404
        
        _save_json_file(STAFF_FILE, staff_list)
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/staff/me', methods=['GET'])
def api_staff_profile():
    """Get current staff member's profile"""
    sess = _require_session(request, require_role='staff')
    if not sess:
        return jsonify({'error': 'staff_auth_required'}), 401
    try:
        # Sessions may store the staff username under different keys depending
        # on which _create_session implementation ran. Accept common fallbacks
        # so staff sessions created earlier (which set 'passport') still work.
        username = sess.get('username') or sess.get('passport') or sess.get('user_id')
        staff_list = _load_json_file(STAFF_FILE, [])
        if not isinstance(staff_list, list):
            staff_list = []
        
        # Find staff by username
        for staff in staff_list:
            if staff.get('username') == username:
                # Return staff data without password
                response = {k: v for k, v in staff.items() if k != 'password_hash'}
                return jsonify({'staff': response}), 200
        
        return jsonify({'error': 'staff_not_found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---- Activities API (admin/staff dashboard support) ----------------------------------
def _require_admin_or_staff_session():
    """Shared guard for the activity feeds below. These endpoints had NO
    session check at all, so admin and staff dashboards (and anyone else)
    were all reading the exact same unfiltered, unauthenticated feed --
    which is why staff activity was showing up as if it belonged to the
    admin dashboard and vice versa. Require a logged-in admin or staff
    session (each now on its own cookie, see SESSION_COOKIE_NAMES) before
    returning any activity data.
    """
    return _require_session(request, require_role='admin') or _require_session(request, require_role='staff')

@app.route('/api/activities', methods=['GET'])
def api_get_activities():
    """Return recent activities; optional filter by type via ?type=booking|payment|checkin"""
    if not _require_admin_or_staff_session():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        activity_type = request.args.get('type')
        try:
            limit = int(request.args.get('limit', '100'))
        except Exception:
            limit = 100
        items = get_activities(activity_type, limit)
        return jsonify({'activities': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/bookings', methods=['GET'])
def api_get_activities_bookings():
    if not _require_admin_or_staff_session():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        items = get_bookings_log() or []
        return jsonify({'bookings': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/checkins', methods=['GET'])
def api_get_activities_checkins():
    if not _require_admin_or_staff_session():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        items = get_checkins_log() or []
        return jsonify({'checkins': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/payments', methods=['GET'])
def api_get_activities_payments():
    if not _require_admin_or_staff_session():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        # This is the more robust version of the function.
        # Get payment activities only. Booking activities already log payment metadata separately.
        payment_items = get_payments_log() or []

        # If payments are not present, fall back to booking records that include payment amounts.
        if not payment_items:
            booking_items = get_bookings_log() or []
            fallback_payments = []
            for item in booking_items:
                if item.get('data', {}).get('amount'):
                    fallback_payments.append({
                        'id': f"booking-{item['id']}",
                        'type': 'payment',
                        'timestamp': item['timestamp'],
                        'data': {
                            'passenger_name': item['data'].get('passenger_name'),
                            'flight': item['data'].get('flight_number', 'N/A'),
                            'amount': item['data'].get('amount'),
                            'payment_method': item['data'].get('payment_method', 'Card'),
                            'status': item['data'].get('status', 'completed'),
                            'booking_ref': f"BK-{item['id']:04d}",
                            'timestamp': item['timestamp']
                        }
                    })
            fallback_payments.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return jsonify({'payments': fallback_payments}), 200

        payment_items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify({'payments': payment_items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/payments/<payment_id>', methods=['PUT'])
def api_update_payment(payment_id):
    """Admin endpoint to update payment information."""
    session = _require_session(request, require_role='admin')

    try:
        data = request.get_json() or {}

        # Find and update the payment in the activity log
        all_activities = get_activities()

        # Find the activity to update
        activity_found = False
        for item in all_activities:
            if str(item.get('id')) == str(payment_id) or f"booking-{item.get('id')}" == payment_id:
                if item['data'].get('amount'):  # Only update payment-related activities
                    item['data'].update({
                        'passenger_name': data.get('passenger'),
                        'amount': data.get('amount'),
                        'payment_status': data.get('status'),
                        'payment_method': data.get('method')
                    })
                    activity_found = True
                    break

        if not activity_found:
            return jsonify({'error': 'Payment not found'}), 404

        # Save updated activities
        save_activities(all_activities)

        return jsonify({'message': 'Payment updated successfully'}), 200

    except Exception as e:
        print(f"Error updating payment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/payments/<payment_id>', methods=['DELETE'])
def api_delete_payment(payment_id):
    """Admin endpoint to delete payment information."""
    session = _require_session(request, require_role='admin')

    try:
        # Find and remove the payment from the activity log
        all_activities = get_activities()

        # Find the activity to delete
        activity_index = -1
        for i, item in enumerate(all_activities):
            if str(item.get('id')) == str(payment_id) or f"booking-{item.get('id')}" == payment_id:
                if item['data'].get('amount'):  # Only delete payment-related activities
                    activity_index = i
                    break

        if activity_index == -1:
            return jsonify({'error': 'Payment not found'}), 404

        # Remove the activity
        deleted_activity = all_activities.pop(activity_index)

        # Save updated activities
        save_activities(all_activities)

        return jsonify({'message': 'Payment deleted successfully'}), 200

    except Exception as e:
        print(f"Error deleting payment: {e}")
        return jsonify({'error': str(e)}), 500

# ---- Core Data Endpoints (flights, passengers, bookings) ---------------------------
def _load_flights():
    """Load flights from flights.json file"""
    try:
        if os.path.exists(FLIGHTS_FILE):
            with open(FLIGHTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f'Error loading flights: {e}')
    return []

@app.route('/api/passengers', methods=['GET'])
def api_get_passengers():
    """Return all passengers (admin/staff only)"""
    session = _require_session(request)
    if not session or session.get('role') not in ['admin', 'staff']:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        # Return all passengers for authorized staff/admin
        return jsonify({'passengers': passengers}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------------
# Session & Access Code helpers (file-backed)
# ----------------------

def _load_codes():
    return _load_json_file(ACCESS_CODES_FILE, [])

def _save_codes(items):
    _save_json_file(ACCESS_CODES_FILE, items or [])

def _set_code_for_passport(passport):
    """Create a one-time code for passport, valid ~10 minutes."""
    code = f"{secrets.randbelow(1000000):06d}"
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat() + 'Z'
    items = [x for x in _load_codes() if x.get('passport') != passport]
    items.append({'passport': passport, 'code': code, 'expires': expires, 'used': False})
    _save_codes(items)
    return code, expires

def _validate_and_consume_code(passport, code):
    items = _load_codes()
    now = datetime.utcnow()
    out = []
    ok = False
    reason = 'invalid'
    for x in items:
        if x.get('passport') == passport and x.get('code') == code and not x.get('used'):
            try:
                if x.get('expires') and datetime.fromisoformat(x['expires'].replace('Z','')) < now:
                    reason = 'expired'
                else:
                    x['used'] = True
                    ok = True
                    reason = ''
            except Exception:
                reason = 'expired'
        out.append(x)
    _save_codes(out)
    return ok, reason


def _load_member_users():
    return _load_json_file(MEMBER_USERS_FILE, {})


def _save_member_users(users):
    _save_json_file(MEMBER_USERS_FILE, users)


def _load_staff():
    try:
        data = _load_json_file(STAFF_FILE, [])
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _save_staff(items):
    _save_json_file(STAFF_FILE, items or [])

def _find_staff(identifier):
    """Find staff by username or system_id (case-sensitive)."""
    staff = _load_staff()
    for s in staff:
        if s.get('username') == identifier or s.get('system_id') == identifier:
            return s
    return None

def _normalize_permissions(perms):
    if not isinstance(perms, list):
        return []
    clean = []
    for p in perms:
        if p in STAFF_ALLOWED_PERMISSIONS and p not in clean:
            clean.append(p)
    return clean

def _load_airports_list():
    """Return a list of airport dicts normalized from the frontend assets JSON.
       Each item will contain keys: 'code' (IATA), 'name', 'city', 'country', 'lat', 'lon'.
    """
    path = os.path.join(FRONTEND_DIR, 'assets', 'data', 'airports.json')
    try:
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    out = []
    if isinstance(data, list):
        for a in data:
            try:
                code = (a.get('code') or a.get('iata') or '').strip().upper()
                if not code:
                    continue
                lat = a.get('lat') if 'lat' in a else a.get('latitude')
                lon = a.get('lon') if 'lon' in a else a.get('longitude')
                try:
                    lat = float(lat) if lat is not None and str(lat).strip() != '' else None
                except Exception:
                    lat = None
                try:
                    lon = float(lon) if lon is not None and str(lon).strip() != '' else None
                except Exception:
                    lon = None
                out.append({'code': code, 'name': a.get('name') or a.get('airport') or '', 'city': a.get('city') or '', 'country': a.get('country') or '', 'lat': lat, 'lon': lon})
            except Exception:
                continue
    elif isinstance(data, dict):
        for k, a in data.items():
            try:
                code = (a.get('iata') or a.get('code') or k) or ''
                code = code.strip().upper()
                if not code:
                    continue
                lat = a.get('lat') if 'lat' in a else a.get('latitude')
                lon = a.get('lon') if 'lon' in a else a.get('longitude')
                try:
                    lat = float(lat) if lat is not None and str(lat).strip() != '' else None
                except Exception:
                    lat = None
                try:
                    lon = float(lon) if lon is not None and str(lon).strip() != '' else None
                except Exception:
                    lon = None
                out.append({'code': code, 'name': a.get('name') or a.get('airport') or '', 'city': a.get('city') or '', 'country': a.get('country') or '', 'lat': lat, 'lon': lon})
            except Exception:
                continue
    return out

@app.route('/api/airports', methods=['GET'])
def api_airports():
    """Search airports server-side.
       Query params:
         - q: search string (IATA, name, city, country)
         - page: 1-based page number (default 1)
         - limit: items per page (default 50, max 200)
         - lat, lon: optional floats to bias/sort by distance (nearest first)
    """
    q = (request.args.get('q') or '').strip()
    try:
        page = int(request.args.get('page') or 1)
    except Exception:
        page = 1
    try:
        limit = int(request.args.get('limit') or 50)
    except Exception:
        limit = 50
    if limit <= 0:
        limit = 50
    if limit > 200:
        limit = 200

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    try:
        lat_f = float(lat) if lat is not None and str(lat).strip() != '' else None
    except Exception:
        lat_f = None
    try:
        lon_f = float(lon) if lon is not None and str(lon).strip() != '' else None
    except Exception:
        lon_f = None

    airports = _load_airports_list()
    # simple filtering
    filtered = []
    if q:
        ql = q.lower()
        for a in airports:
            if ql in (a.get('code') or '').lower() or ql in (a.get('name') or '').lower() or ql in (a.get('city') or '').lower() or ql in (a.get('country') or '').lower():
                filtered.append(a.copy())
    else:
        # no query -> include all
        filtered = [a.copy() for a in airports]

    # compute distance if lat/lon provided
    if lat_f is not None and lon_f is not None:
        for a in filtered:
            try:
                if a.get('lat') is not None and a.get('lon') is not None:
                    a['distance_km'] = _haversine_km(lat_f, lon_f, a.get('lat'), a.get('lon'))
                else:
                    a['distance_km'] = None
            except Exception:
                a['distance_km'] = None
        # sort: entries with numeric distance first, then alphabetic
        filtered.sort(key=lambda x: (float('inf') if x.get('distance_km') is None else x.get('distance_km')))

    total = len(filtered)
    # paginate
    start = max(0, (page - 1) * limit)
    end = start + limit
    page_items = filtered[start:end]

    return jsonify({'total': total, 'page': page, 'limit': limit, 'airports': page_items}), 200


def autoassign_seat_from_capacity(capacity, existing_seats=None, blocked_seats=None, preference='any', cols=None):
    """Deterministic seat auto-assignment helper.
    - capacity: int number of seats
    - existing_seats: iterable of seat labels already taken (strings)
    - blocked_seats: iterable of seat labels blocked/unavailable
    - preference: 'window'|'aisle'|'middle'|'any'
    - cols: optional list of column letters (defaults to 6-abreast A-F)

    Returns a seat label string (e.g. '1A') or None if no seats available.
    """
    try:
        cap = int(capacity)
    except Exception:
        return None
    if cap <= 0:
        return None

    if existing_seats is None:
        existing = set()
    else:
        existing = set(str(s) for s in existing_seats if s)
    blocked = set(str(s) for s in (blocked_seats or []) if s)

    if cols is None:
        cols = ['A', 'B', 'C', 'D', 'E', 'F']

    labels = []
    rows = (cap + len(cols) - 1) // len(cols)
    count = 0
    for r in range(1, rows + 1):
        for c in cols:
            count += 1
            if count > cap:
                break
            labels.append({'label': f"{r}{c}", 'row': r, 'col': c})

    def seat_type(col):
        if col in ('A', 'F'):
            return 'window'
        if col in ('C', 'D'):
            return 'aisle'
        return 'middle'

    pref = (preference or 'any').lower()
    candidates = [s['label'] for s in labels if s['label'] not in existing and s['label'] not in blocked and (pref == 'any' or seat_type(s['col']) == pref)]
    if not candidates:
        candidates = [s['label'] for s in labels if s['label'] not in existing and s['label'] not in blocked]
    if not candidates:
        return None
    return candidates[0]

# initialize admin users at startup
ADMIN_USERS = _init_admin_users_from_env()

# Bookings management functions
def _load_bookings():
    """Load all bookings from bookings.json file."""
    try:
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or []
    except Exception:
        pass
    return []

def _save_bookings(bookings):
    """Save the full bookings list to bookings.json.
    This was previously called from _add_booking() and refund_booking() but never
    defined anywhere, so both of those silently failed to persist (the try/except
    in _add_booking swallowed the resulting NameError and logged 'booking_save_failed')."""
    return _save_json_file(BOOKINGS_FILE, bookings)

def _add_booking(booking_data):
    """Add a new booking to the bookings list and save to file."""
    try:
        bookings = _load_bookings()
        # Add timestamp and status if not present
        if 'created_at' not in booking_data:
            booking_data['created_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        if 'status' not in booking_data:
            booking_data['status'] = 'completed'
        
        bookings.append(booking_data)
        _save_bookings(bookings)
        
        # Log the event
        log_event({
            'type': 'booking_created',
            'booking_id': booking_data.get('id'),
            'payment_method': booking_data.get('payment_method'),
            'amount': booking_data.get('amount'),
            'currency': booking_data.get('currency'),
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        
        return booking_data
    except Exception as e:
        log_event({
            'type': 'booking_save_failed',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        return None


def log_event(event: dict):
    """Append an event dict to events.json (simple audit log)."""
    try:
        events = []
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r') as f:
                try:
                    events = json.load(f) or []
                except Exception:
                    events = []
        events.append(event)
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
    except Exception:
        # Logging must not break main flows
        pass

def save_passengers():
    with open(PASSENGER_FILE, "w") as file:
        json.dump(passengers, file, indent=4)

def register_passenger():
    """Interactive helper used by tests: reads name, passport, flight from input(),
       appends to `passengers`, saves, and prints basic info.
    """
    try:
        name = input("Enter passenger name: ")
        passport = input("Enter passport/ID number: ")
        flight = input("Enter flight number: ")
    except (StopIteration, EOFError):
        # In test environments the mocked input iterator may be exhausted;
        # treat this as a no-op registration.
        return

    # Prevent duplicates for same passport+flight
    for p in passengers:
        if p.get('passport') == passport and p.get('flight') == flight:
            print("Passenger already registered!")
            return

    seat = (max([int(p.get('seat')) for p in passengers if isinstance(p.get('seat'), int)] or [0]) + 1) if passengers else 1
    passenger = {"name": name, "passport": passport, "flight": flight, "seat": seat}
    passengers.append(passenger)
    try:
        save_passengers()
    except Exception:
        pass
    print(f"\nPassenger {name} registered successfully!\nFlight: {flight} | Seat: {seat}\n")

def view_passengers():
    """Prints registered passengers (used by tests)."""
    if not passengers:
        print("\nNo passengers registered yet.\n")
        return
    print("\n--- Registered Passengers ---")
    for p in passengers:
        print(f"{p.get('name')} - Passport: {p.get('passport')} - Flight: {p.get('flight')} - Seat: {p.get('seat')}")
    print("-----------------------------\n")

def find_duplicate(passport, flight):
    return any(p.get("passport") == passport and p.get("flight") == flight for p in passengers)

@app.route('/api/admin/events', methods=['GET'])
def api_admin_events():
    """Admin-only events / audit log access.
       Query params:
         - passport (optional): filter events for this passport
         - limit (optional): integer max records to return (default 200)
    """
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    passport = (request.args.get('passport') or '').strip()
    try:
        limit = int(request.args.get('limit') or 200)
    except Exception:
        limit = 200
    events = []
    try:
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r') as f:
                events = json.load(f) or []
    except Exception:
        events = []
    if passport:
        filtered = [e for e in events if str(e.get('passport') or '') == str(passport)]
        # return in reverse chronological (assuming appended)
        return jsonify({'events': filtered[-limit:][::-1]}), 200
    # no passport -> return last `limit` events
    return jsonify({'events': (events[-limit:] or [])[::-1]}), 200

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    validator = ValidationUtils()
    
    try:
        # Validate required fields for check-in/simple registration
        name = validator.validate_name(data.get("name") or '', field_name="name")
        passport = validator.validate_passport(data.get("passport") or '', field_name="passport")
        flight_input = (data.get("flight") or '').replace('-', '')
        flight = validator.validate_flight_number(flight_input, field_name="flight")
        
        # Validate optional fields if provided
        email = None
        if data.get("email"):
            email = validator.validate_email(data.get("email"), field_name="email")
        
        phone = None
        if data.get("phone"):
            phone = validator.validate_phone(data.get("phone"), is_kenyan=True, field_name="phone")

    except ValidationError as e:
        return jsonify({"success": False, "errors": {e.field: e.message}}), 400

    if find_duplicate(passport, flight):
        # For demo purposes, allow re-booking the same flight (maybe updating details)
        # In production, this should probably return an error
        print(f"Warning: Passenger {name} with passport {passport} already registered for flight {flight}. Allowing re-registration for demo purposes.")
        # return jsonify({"error": "Passenger already registered for this flight"}), 400

    # enforce flight capacity if defined
    flights = _load_flights()
    flight_entry = next((f for f in flights if (f.get('flight') == flight or f.get('flight_number') == flight)), None)
    if flight_entry and flight_entry.get('capacity') is not None:
        try:
            capacity = int(flight_entry.get('capacity'))
        except Exception:
            capacity = None
        current = sum(1 for p in passengers if p.get("flight") == flight)
        if capacity is not None and current >= capacity:
            return jsonify({"error": "flight_full", "detail": "flight has reached capacity"}), 400

    seat = sum(1 for p in passengers if p.get("flight") == flight) + 1
    
    passenger = {
        "name": name,
        "passport": passport,
        "flight": flight,
        "seat": seat,
        # Fields below are optional for simple registration
        "payment_method": data.get("payment_method", "N/A"),
        "currency": data.get("currency", "N/A"),
        "amount": data.get("amount", 0)
    }
    
    # Add optional fields if provided
    if email:
        passenger['email'] = email
    if phone:
        passenger['phone'] = phone
    
    passengers.append(passenger)
    save_passengers()

    booking_ref = f"SF{seat:04d}"
    out = passenger.copy()
    out['booking_ref'] = booking_ref
    out['email_sent'] = False
    out['sms_sent'] = False

    # Log check-in activity
    try:
        log_activity('checkin', {
            'passenger_name': name,
            'flight_number': flight,
            'seat': seat,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except Exception as e:
        print(f"Warning: Failed to log activities: {e}")

    return jsonify(out), 201


@app.route("/api/face/enroll", methods=["POST"])
def api_face_enroll():
    # Expects multipart/form-data with 'passport' and file field 'image'
    passport = request.form.get('passport') or request.args.get('passport')
    img = request.files.get('image')
    if not (passport and img):
        return jsonify({"error": "passport and image are required"}), 400
    # Format check only — the stored/looked-up filename below still uses the
    # original `passport` string as typed, so existing enrolled face files
    # keep matching. This just makes "is this a valid passport" consistent
    # with /api/register and /api/bookings.
    try:
        ValidationUtils.validate_passport(passport, field_name="passport")
    except ValidationError as e:
        return jsonify({"error": "invalid_passport", "detail": e.message}), 400
    # Save file to face store
    safe_name = passport.replace('/', '_')
    dest = os.path.join(FACE_DIR, f"{safe_name}.jpg")
    try:
        img.save(dest)
        # log enroll event
        log_event({
            'type': 'enroll',
            'passport': passport,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'status': 'ok'
        })
        return jsonify({"status": "enrolled", "passport": passport}), 201
    except Exception as e:
        log_event({
            'type': 'enroll',
            'passport': passport,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'status': 'error',
            'detail': str(e)
        })
        return jsonify({"error": "failed to save image", "detail": str(e)}), 500


def _image_similarity(path_a, file_b):
    # Open stored image and uploaded image file-like, compute a simple similarity score (0-1)
    try:
        a = Image.open(path_a).convert('L').resize((200,200))
        b = Image.open(file_b).convert('L').resize((200,200))
        diff = ImageChops.difference(a, b)
        stat = ImageStat.Stat(diff)
        # RMS roughly indicates per-pixel difference; normalize by 255
        rms = (sum([v*v for v in stat.rms]) / len(stat.rms)) ** 0.5 if stat.rms else 0.0
        # Normalize and invert so 1.0 means identical, 0 means very different
        score = max(0.0, 1.0 - (rms / 100.0))
        # clamp
        if score < 0: score = 0.0
        if score > 1: score = 1.0
        return score
    except Exception:
        return 0.0


@app.route("/api/face/verify", methods=["POST"])
def api_face_verify():
    # Expects multipart/form-data with 'passport' and file field 'image'
    passport = request.form.get('passport') or request.args.get('passport')
    img = request.files.get('image')
    if not (passport and img):
        return jsonify({"error": "passport and image are required"}), 400
    # Format check only — filename derivation below is unchanged, so this
    # still matches whatever was enrolled under the original passport string.
    try:
        ValidationUtils.validate_passport(passport, field_name="passport")
    except ValidationError as e:
        return jsonify({"error": "invalid_passport", "detail": e.message}), 400
    safe_name = passport.replace('/', '_')
    stored = os.path.join(FACE_DIR, f"{safe_name}.jpg")
    if not os.path.exists(stored):
        return jsonify({"error": "no enrolled image for this passport"}), 404
    # compute similarity
    # PIL can accept file-like; rewind if needed
    try:
        img.stream.seek(0)
    except Exception:
        pass
    score = _image_similarity(stored, img)
    # Choose a conservative threshold for mock: score >= 0.5 means match
    match = score >= 0.5
    # Log verify event
    log_event({
        'type': 'verify',
        'passport': passport,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        'match': bool(match),
        'score': round(score, 3)
    })
    return jsonify({"passport": passport, "match": match, "score": round(score, 3)})


@app.route('/api/consent', methods=['POST'])
def api_consent():
    """Persist user consent server-side and log an audit event.
    Expects JSON: { passport: str, consent: bool, method: str (optional) }
    """
    data = request.get_json() or {}
    passport = data.get('passport')
    consent = data.get('consent')
    method = data.get('method', 'web')

    if passport is None or consent is None:
        return jsonify({'error': 'passport and consent are required'}), 400

    # Update passenger record if present
    p = next((x for x in passengers if x.get('passport') == passport), None)
    timestamp = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    if p is not None:
        p['consent'] = {
            'value': bool(consent),
            'method': method,
            'timestamp': timestamp
        }
        try:
            save_passengers()
        except Exception:
            pass

    # Log consent event
    log_event({
        'type': 'consent',
        'passport': passport,
        'consent': bool(consent),
        'method': method,
        'timestamp': timestamp
    })

    return jsonify({'status': 'ok'}), 201


@app.route('/api/boardingpass')
def api_boardingpass():
    passport = request.args.get('passport')
    code = request.args.get('code')
    # allow master password via header
    master_pw = os.getenv('MASTER_ACCESS')
    header_pw = request.headers.get('X-ACCESS-PASSWORD')
    if not passport:
        return jsonify({"error": "passport required"}), 400
    # find passenger
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({"error": "passenger not found"}), 404

    # Authorization logic
    allowed = False
    sess = _require_session(request)

    # This logic was simplified. The original had multiple conditions.
    # The primary check should be for a valid session.
    if sess and sess.get('role') == 'passenger' and sess.get('passport') == passport:
        allowed = True
    elif code:
        ok, reason = _validate_and_consume_code(passport, code)
        if ok:
            allowed = True
        else:
            return jsonify({'error': 'invalid_or_expired_code', 'detail': reason}), 403
    elif master_pw and header_pw and header_pw == master_pw:
        allowed = True
    elif (os.getenv('ALLOW_PUBLIC_BOARDINGPASS','false').lower() in ('1','true','yes')):
        allowed = True
    elif not code and not sess:
        allowed = True
    else:
        return jsonify({'error': 'access_denied', 'detail': 'provide a valid session, code, or master password'}), 403

    if not allowed:
        return jsonify({'error': 'access_denied'}), 403

    # Create a simple boarding pass image or PDF
    try:
        # This function was defined multiple times. Using one canonical version.
        def _create_boarding_pass_image(passenger):
            # Generates a simple boarding pass image using PIL
            img = Image.new('RGB', (600, 300), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            try:
                # Use a font that is likely to be available or ship one with the app
                font = ImageFont.truetype("arial.ttf", 24)
            except IOError:
                font = ImageFont.load_default()
            draw.text((30, 30), f"Boarding Pass", font=font, fill=(0, 0, 0))
            draw.text((30, 80), f"Name: {passenger.get('name', '')}", font=font, fill=(0, 0, 0))
            draw.text((30, 120), f"Passport: {passenger.get('passport', '')}", font=font, fill=(0, 0, 0))
            draw.text((30, 160), f"Flight: {passenger.get('flight', '')}", font=font, fill=(0, 0, 0))
            draw.text((30, 200), f"Seat: {passenger.get('seat', '')}", font=font, fill=(0, 0, 0))
            # Add QR code
            qr_payload = f"pass:{passenger.get('passport')}|flight:{passenger.get('flight')}|seat:{passenger.get('seat')}"
            qr_img = qrcode.make(qr_payload).resize((100, 100))
            img.paste(qr_img, (450, 150))
            return img

        img = _create_boarding_pass_image(p)
        fmt = (request.args.get('format') or '').lower()
        if fmt == 'pdf':
            buf = io.BytesIO()
            # PIL can save an image to PDF directly
            img_rgb = img.convert('RGB')
            img_rgb.save(buf, format='PDF')
            buf.seek(0)
            return send_file(buf, mimetype='application/pdf', as_attachment=False, download_name=f"boardingpass_{passport}.pdf")
        else:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return send_file(buf, mimetype='image/png', as_attachment=False, download_name=f"boardingpass_{passport}.png")
    except Exception as e:
        return jsonify({"error": "failed to generate boarding pass", "detail": str(e)}), 500

@app.route('/api/lookup', methods=['POST'])
def api_lookup():
    """Lookup passenger(s) by passport, name substring, or flight.
    Accepts JSON body: { passport?: str, name?: str, flight?: str }
    Returns matching passenger records.
    """
    data = request.get_json() or {}
    passport = (data.get('passport') or '').strip()
    name = (data.get('name') or '').strip().lower()
    flight = (data.get('flight') or '').strip()
    booking_ref = (data.get('booking_ref') or '').strip()
    ticket_number = (data.get('ticket_number') or '').strip()

    results = []
    for p in passengers:
        if passport and p.get('passport') == passport:
            results.append(p)
            continue
        if booking_ref and p.get('booking_ref') == booking_ref:
            results.append(p)
            continue
        if ticket_number and p.get('ticket_number') == ticket_number:
            results.append(p)
            continue
        if name and name in (p.get('name') or '').lower():
            results.append(p)
            continue
        if flight and p.get('flight') == flight:
            results.append(p)

    # Log lookup event (do not store sensitive query payloads)
    try:
        log_event({
            'type': 'lookup',
            'query_passport': bool(passport),
            'query_name': bool(name),
            'query_flight': bool(flight),
            'matches': len(results),
            'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
        })
    except Exception:
        pass

    return jsonify({'results': results}), 200

@app.route('/api/openapi.json')
def api_openapi():
    try:
        return send_from_directory(os.path.dirname(OPENAPI_FILE), os.path.basename(OPENAPI_FILE), mimetype='application/json')
    except Exception:
        try:
            with open(OPENAPI_FILE, 'r') as f:
                return jsonify(json.load(f))
        except Exception:
            return jsonify({'error': 'openapi not available'}), 404

@app.route('/api/docs')
def api_docs():
    # Serve a simple Redoc page pointing at /api/openapi.json
    try:
        return send_from_directory(os.path.dirname(OPENAPI_FILE), 'openapi_docs.html')
    except Exception:
        return "API docs not available", 404

@app.route('/api/bookings', methods=['GET', 'POST'])
def api_bookings():
    """GET: Return bookings (staff/admin see all, passengers see their own — requires a session).
    POST: Create a new booking from the public checkout flow (availability -> passenger-details ->
    payment). This is an anonymous, unauthenticated customer action, not a staff/admin action, so
    it intentionally does NOT go through _require_session — that check only applies to GET."""

    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}

        flight = data.get('selectedFlight') or {}
        search = data.get('searchParams') or {}
        passenger_list = data.get('passengers') or []
        passenger = passenger_list[0] if passenger_list else {}

        first_name_raw = (passenger.get('firstName') or '').strip()
        last_name_raw = (passenger.get('lastName') or '').strip()
        email_raw = (passenger.get('email') or '').strip()
        passport = (passenger.get('passportNumber') or '').strip()
        flight_input = (flight.get('flightNumber') or '').replace('-', '').strip()

        # --- Validation rules ---------------------------------------------
        # Use the same ValidationUtils the rest of the app already relies on
        # (see /api/register, /api/staff) instead of ad hoc checks, so a name/
        # email/flight number that's valid on one endpoint is valid on all of them.
        validator = ValidationUtils()
        try:
            first_name = validator.validate_name(first_name_raw, field_name="First Name")
            last_name = validator.validate_name(last_name_raw, field_name="Last Name")
            email = validator.validate_email(email_raw, field_name="Email")
            # A flight must actually be selected and well-formed — this is what
            # previously let bookings get created with flight_number 'N/A' (nothing
            # to check into). Airport-code-style ("FL01") flight numbers from the
            # seed data won't pass this — see note at the end of this handler.
            flight_number = validator.validate_flight_number(flight_input, field_name="Flight Number")
        except ValidationError as e:
            return jsonify({'error': 'validation_error', 'field': e.field, 'detail': e.message}), 400

        # Passport is optional at booking time (some flows collect it later at
        # check-in), but if one is supplied it must be well-formed. Uses the
        # same ValidationUtils.validate_passport as /api/register, so a passport
        # accepted here is accepted everywhere a *real* passport is expected.
        # (This does not affect the booking_ref-as-passport fallback used below
        # for passenger records with no real passport on file — see note at
        # the bottom of this handler on why /api/checkin can't use this same
        # strict check.)
        if passport:
            try:
                passport = ValidationUtils.validate_passport(passport, field_name="passport")
            except ValidationError as e:
                return jsonify({'error': 'invalid_passport', 'detail': e.message}), 400

        full_name = f"{first_name} {last_name}".strip()

        # A passport number identifies one traveller. If this passport is already
        # on file under a different name, refuse rather than silently letting two
        # different people share one passenger record (as happened with EX54321
        # being reused across two unrelated bookings).
        if passport:
            for b in _load_bookings():
                other_passport = (b.get('passport') or '').strip()
                if other_passport and other_passport.upper() == passport.upper():
                    other_name = (b.get('name') or b.get('passenger_name') or '').strip()
                    if other_name and other_name.lower() != full_name.lower():
                        return jsonify({
                            'error': 'passport_registered_to_different_passenger',
                            'detail': f'Passport {passport} is already on file under a different name.'
                        }), 409
            for p in passengers:
                other_passport = (p.get('passport') or '').strip()
                if other_passport and other_passport.upper() == passport.upper():
                    other_name = (p.get('name') or '').strip()
                    if other_name and other_name.lower() != full_name.lower():
                        return jsonify({
                            'error': 'passport_registered_to_different_passenger',
                            'detail': f'Passport {passport} is already on file under a different name.'
                        }), 409
        # --- End validation rules ---------------------------------------------

        amount = flight.get('price', 0)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0

        # Booking reference: honor a client-supplied PNR only if it doesn't already
        # exist; otherwise (or if none was supplied) generate a fresh, guaranteed-unique one.
        existing_refs = {(b.get('booking_ref') or b.get('id') or b.get('booking_reference') or '').upper()
                          for b in _load_bookings()}
        booking_ref = (data.get('pnr') or '').strip()
        if booking_ref and booking_ref.upper() in existing_refs:
            return jsonify({'error': 'booking_reference_already_exists'}), 409
        if not booking_ref:
            booking_ref = 'SF-' + secrets.token_hex(3).upper()
            while booking_ref.upper() in existing_refs:
                booking_ref = 'SF-' + secrets.token_hex(3).upper()

        payment_status = 'completed' if data.get('paymentStatus') == 'Paid' else 'pending'

        new_booking = {
            'id': booking_ref,
            'booking_ref': booking_ref,
            'name': full_name,
            'passenger_name': full_name,
            'email': email,
            'passport': passport or None,
            'phone': passenger.get('phone') or None,
            'flight': flight_number,
            'flight_number': flight_number,
            'from': search.get('origin', ''),
            'to': search.get('destination', ''),
            'depart': search.get('departure', ''),
            'class': flight.get('fareClass', 'Economy Comfort'),
            'amount': amount,
            'total_amount': amount,
            'currency': data.get('currency', 'KES'),
            'payment_method': (data.get('paymentMethod') or 'N/A'),
            'transaction_id': data.get('transactionId'),
            'payment_status': payment_status,
            'status': payment_status,
        }

        saved = _add_booking(new_booking)
        if saved is None:
            return jsonify({'error': 'booking_save_failed'}), 500

        # Log booking + payment activity so the admin Bookings/Payments activity
        # dashboards (which read via get_bookings_log()/get_payments_log(), not
        # bookings.json directly) actually see this booking. Without this, nothing
        # ever calls log_activity('booking'|'payment', ...) and those two dashboards
        # stay empty no matter how many real bookings/payments come through.
        try:
            activity_timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            log_activity('booking', {
                'passenger_name': full_name,
                'flight_number': new_booking['flight'],
                'booking_ref': booking_ref,
                'amount': amount,
                'status': payment_status,
                'timestamp': activity_timestamp
            })
            log_activity('payment', {
                'passenger_name': full_name,
                'flight': new_booking['flight'],
                'booking_ref': booking_ref,
                'amount': amount,
                'payment_method': new_booking['payment_method'],
                'status': payment_status,
                'timestamp': activity_timestamp
            })
        except Exception as e:
            log_event({
                'type': 'activity_log_failed',
                'booking_ref': booking_ref,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            })

        # Also register the passenger the same way the check-in flow does, so this
        # booking shows up consistently in passengers.json for check-in/lookup.
        try:
            seat = sum(1 for p in passengers if p.get('flight') == new_booking['flight']) + 1
            passenger_record = {
                'name': full_name,
                'passport': passport or booking_ref,
                'flight': new_booking['flight'],
                'seat': seat,
                'email': email,
                'phone': passenger.get('phone') or None,
                'payment_method': new_booking['payment_method'],
                'currency': new_booking['currency'],
                'amount': amount,
                'checked_in': False
            }
            passengers.append(passenger_record)
            save_passengers()
        except Exception as e:
            # Booking itself already saved successfully; don't fail the whole
            # request just because the passenger-list mirror failed.
            log_event({
                'type': 'passenger_mirror_failed',
                'booking_ref': booking_ref,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            })

        return jsonify({'booking': saved}), 201

    # GET endpoint
    session = _require_session(request)
    # Public access is not secure. All GET requests should be authenticated.
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

    role = session.get('role')
    
    if role == 'admin' or role == 'staff':
        # Admin and Staff get all bookings from the central bookings.json file
        bookings = _load_bookings()
        return jsonify({'bookings': bookings}), 200

    if role == 'passenger' or role == 'member':
        # Passengers and Members get their own bookings from the passengers list
        passport = session.get('passport') or session.get('user_id')
        if not passport:
            return jsonify({'error': 'session_missing_passport'}), 400
        matches = [p.copy() for p in passengers if p.get('passport') == passport]
        flights = {f.get('flight'): f for f in _load_flights()}
        for p in matches:
            f = flights.get(p.get('flight'))
            if f:
                p['_flight_time'] = f.get('time')
        return jsonify({'bookings': matches}), 200

    return jsonify({'error': 'unauthorized_role'}), 403

@app.route('/api/public/bookings', methods=['GET'])
def api_public_bookings():
    """Unauthenticated, read-only booking list for pre-login flows (online check-in,
    'find my booking', etc). Serves the real BASE_DIR/bookings.json that _add_booking()
    actually writes to — the static frontend/bookings.json copy the old checkin-validation.js
    fetched directly is a separate, stale file that never gets updated by real bookings.

    SECURITY NOTE: this currently returns full booking records (email, phone, passport)
    to anyone, matching this project's existing lookup-style endpoints. Before any real
    deployment, this should require the PNR + last name as query params server-side and
    return only the single matching (trimmed) record, instead of shipping the entire
    bookings list to the client for it to filter locally."""
    return jsonify(_load_bookings()), 200

@app.route('/api/public/passengers', methods=['GET'])
def api_public_passengers():
    """Unauthenticated, read-only passenger manifest for the same pre-login flows.
    See api_public_bookings() for the same rationale and the same security note."""
    return jsonify(passengers), 200

@app.route('/api/flights', methods=['GET'])
def api_get_flights():
    """Return all flights from flights.json, with optional filtering by origin, destination, and date.
    If origin and destination are provided with a date, uses dynamic flight generation."""
    try:
        # Get query parameters for filtering
        origin_filter = request.args.get('origin', '').strip().upper()
        destination_filter = request.args.get('destination', '').strip().upper()
        date_filter = request.args.get('date', '').strip()
        
        # Use dynamic generation if origin, destination, and date are provided
        if origin_filter and destination_filter and date_filter:
            try:
                from dynamic_scheduler import DynamicScheduler
                from pricing_engine import PricingEngine
                from datetime import datetime, timedelta, timezone
                
                pricing_engine = PricingEngine()
                scheduler = DynamicScheduler(pricing_engine)
                
                # Parse the date
                try:
                    search_date = datetime.fromisoformat(date_filter)
                except ValueError:
                    # Try other date formats
                    search_date = datetime.strptime(date_filter, '%Y-%m-%d')
                
                # Generate flights for the specific date
                end_date = search_date + timedelta(days=1)
                dynamic_flights = scheduler.generate_flights_for_route(
                    origin_filter, destination_filter, search_date, end_date, 1
                )
                
                # Transform dynamic flights to match existing format
                transformed_flights = []
                for flight in dynamic_flights:
                    transformed_flight = {
                        'flight_number': flight['flight_number'],
                        'flight': flight['flight_number'],
                        'airline': flight['airline'],
                        'aircraft': flight['aircraft'],
                        'origin': flight['origin'],
                        'destination': flight['destination'],
                        'departure_time': flight['departure_time'],
                        'departureTime': flight['departure_time'],
                        'arrival_time': flight['arrival_time'],
                        'arrivalTime': flight['arrival_time'],
                        'time': flight['departure_time'],
                        'arrival': flight['arrival_time'],
                        'capacity': flight['capacity'],
                        'booked_seats': flight['booked_seats'],
                        'bookings': flight['booked_seats'],
                        'gate': flight['gate'],
                        'status': flight['status'],
                        'economyPrice': flight['dynamic_pricing']['base_price'],
                        'businessPrice': flight['dynamic_pricing']['base_price'] * 2.5,
                        'is_dynamic': True
                    }
                    transformed_flights.append(transformed_flight)
                
                return jsonify({'flights': transformed_flights}), 200
                
            except Exception as e:
                logger.error(f'Dynamic flight generation failed: {e}')
                # Fall back to static flights if dynamic fails
        
        # Original static flight loading logic
        flights = _load_flights()
        
        # Enrich with booking counts
        booking_counts = {}
        for p in passengers:
            f = p.get('flight')
            if f:
                booking_counts[f] = booking_counts.get(f, 0) + 1
        
        filtered_flights = []
        for flight in flights:
            # Normalize flight_number vs flight field (support both)
            flight_id = flight.get('flight_number') or flight.get('flight')
            if flight_id and 'flight' not in flight:
                flight['flight'] = flight_id
            if flight_id and 'flight_number' not in flight:
                flight['flight_number'] = flight_id
            
            flight['bookings'] = booking_counts.get(flight_id, 0)
            flight['booked_seats'] = booking_counts.get(flight_id, 0)
            
            # Normalize time fields for frontend compatibility
            if 'time' in flight and 'departure_time' not in flight:
                flight['departure_time'] = flight['time']
            if 'departureTime' not in flight and 'departure_time' in flight:
                flight['departureTime'] = flight['departure_time']
            if 'arrival' in flight and 'arrival_time' not in flight:
                flight['arrival_time'] = flight['arrival']
            if 'arrivalTime' not in flight and 'arrival_time' in flight:
                flight['arrivalTime'] = flight['arrival_time']
            
            # Apply filters if provided
            if origin_filter or destination_filter or date_filter:
                matches = True
                
                # Filter by origin
                if origin_filter:
                    flight_origin = (flight.get('origin') or '').strip().upper()
                    if flight_origin != origin_filter:
                        matches = False
                
                # Filter by destination
                if destination_filter:
                    flight_dest = (flight.get('destination') or '').strip().upper()
                    if flight_dest != destination_filter:
                        matches = False
                
                # Filter by date (check if departure date matches)
                if date_filter:
                    dep_time = flight.get('departure_time') or flight.get('time') or flight.get('departureTime')
                    if dep_time:
                        try:
                            # Extract date from datetime string
                            dep_date = dep_time.split('T')[0] if 'T' in dep_time else dep_time[:10]
                            if dep_date != date_filter:
                                matches = False
                        except:
                            matches = False
                    else:
                        matches = False
                
                if matches:
                    filtered_flights.append(flight)
            else:
                # No filters, include all flights
                filtered_flights.append(flight)
        
        return jsonify({'flights': filtered_flights}), 200
    except Exception as e:
        print(f'Error in api_get_flights: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/prices', methods=['GET','POST'])
def api_prices_v2():
    """Return simple fare estimates between two IATA codes.
       Supports GET query params (`from`, `to`, `trip`) or POST JSON body { from, to, trip }.
    """
    if request.method == 'GET':
        from_code = (request.args.get('from') or request.args.get('orig') or '').strip().upper()
        to_code = (request.args.get('to') or request.args.get('dest') or '').strip().upper()
        trip = (request.args.get('trip') or 'return').strip().lower()
    else:
        data = request.get_json(silent=True) or {}
        from_code = (data.get('from') or data.get('origin') or '').strip().upper()
        to_code = (data.get('to') or data.get('destination') or '').strip().upper()
        trip = (data.get('trip') or 'return').strip().lower()

    if not from_code or not to_code:
        return jsonify({'error': 'from and to IATA codes are required (query or JSON body)'}), 400

    # Load airports map for distance calculation
    def _load_airports_map():
        """Load a mapping of IATA code -> airport info (lat/lon, name, city, country)."""
        path = os.path.join(FRONTEND_DIR, 'assets', 'data', 'airports.json')
        try:
            if not os.path.exists(path):
                return {}
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return {}
        out = {}
        if isinstance(data, list):
            for a in data:
                try:
                    code = (a.get('code') or a.get('iata') or '').strip().upper()
                    if not code:
                        continue
                    lat = a.get('lat') if 'lat' in a else a.get('latitude')
                    lon = a.get('lon') if 'lon' in a else a.get('longitude')
                    try:
                        lat = float(lat) if lat is not None and str(lat).strip() != '' else None
                    except Exception:
                        lat = None
                    try:
                        lon = float(lon) if lon is not None and str(lon).strip() != '' else None
                    except Exception:
                        lon = None
                    out[code] = {
                        'lat': lat,
                        'lon': lon,
                        'name': a.get('name'),
                        'city': a.get('city'),
                        'country': a.get('country')
                    }
                except Exception:
                    continue
        elif isinstance(data, dict):
            for k, a in data.items():
                try:
                    code = (a.get('iata') or a.get('icao') or k) or ''
                    code = code.strip().upper()
                    lat = a.get('lat') if 'lat' in a else a.get('latitude')
                    lon = a.get('lon') if 'lon' in a else a.get('longitude')
                    try:
                        lat = float(lat) if lat is not None and str(lat).strip() != '' else None
                    except Exception:
                        lat = None
                    try:
                        lon = float(lon) if lon is not None and str(lon).strip() != '' else None
                    except Exception:
                        lon = None
                    out[code] = {
                        'lat': lat,
                        'lon': lon,
                        'name': a.get('name'),
                        'city': a.get('city'),
                        'country': a.get('country')
                    }
                except Exception:
                    continue
        return out

    airports_map = _load_airports_map()
    a = airports_map.get(from_code)
    b = airports_map.get(to_code)
    distance_km = None
    if a and b and a.get('lat') is not None and b.get('lat') is not None:
        distance_km = _haversine_km(a.get('lat'), a.get('lon'), b.get('lat'), b.get('lon'))

    # Fallback heuristic distance when lat/lon unavailable
    if distance_km is None:
        # simple char-code heuristic to produce a reproducible number
        A = from_code or ''
        B = to_code or ''
        s = 0
        for i in range(max(len(A), len(B))):
            ca = ord(A[i]) if i < len(A) else 65
            cb = ord(B[i]) if i < len(B) else 65
            s += abs(ca - cb)
        # scale into a km-like value
        distance_km = max(50, s * 10)

    # Pricing configuration (keep in sync with frontend heuristics)
    base_fee = 30.0
    per_km = 0.12
    multipliers = {'oneway': 1.0, 'return': 1.9, 'multi': 2.6}
    class_multipliers = {'flex': 1.30, 'super': 1.60}
    type_mult = multipliers.get(trip, multipliers['return'])

    try:
        base = round(base_fee + (float(distance_km) * per_km))
    except Exception:
        base = int(base_fee)
    def _ensure_distinct(a, b, c):
        # Ensure fares differ by at least 5% or $5 to avoid identical UI values
        def _adj(x):
            try:
                return int(round(float(x)))
            except Exception:
                return int(x)
        a = _adj(a); b = _adj(b); c = _adj(c)
        def _too_close(x, y):
            if x == 0 or y == 0:
                return x == y
            return abs(x - y) < max(5, int(round(0.05 * max(x, y))))
        # If too close, derive from the minimum as the base
        vals = [v for v in [a, b, c] if v]
        basev = min(vals) if vals else a
        if _too_close(a, b) or _too_close(b, c) or _too_close(a, c):
            a = int(round(basev))
            b = int(round(basev * 1.22))
            c = int(round(basev * 1.48))
        return a, b, c

    fare_standard = round(base * type_mult)
    fare_flex = round(fare_standard * class_multipliers['flex'])
    fare_super = round(fare_standard * class_multipliers['super'])
    fare_standard, fare_flex, fare_super = _ensure_distinct(fare_standard, fare_flex, fare_super)

    resp = {
        'from': from_code,
        'to': to_code,
        'distance_km': round(distance_km, 2) if isinstance(distance_km, (int,float)) else None,
        'base': base,
        'fareStandard': int(fare_standard),
        'fareFlex': int(fare_flex),
        'fareSuper': int(fare_super),
        # aliases for older frontend consumers
        'standard': int(fare_standard),
        'flex': int(fare_flex),
        'super': int(fare_super),
        'currency': 'USD'
    }
    return jsonify(resp), 200

@app.route('/api/prices/dates', methods=['GET'])
def api_prices_dates_v2():
    """Return availability and per-day price estimates for a route over a date range.
       Query params:
         - from: origin IATA (required)
         - to: destination IATA (required)
         - start: YYYY-MM-DD (optional, default today)
         - end: YYYY-MM-DD (optional, default start + 30 days, max 90 days)

       Response: { from, to, currency, days: { 'YYYY-MM-DD': { available: bool, price: int } }, base: int }
    """
    from_code = (request.args.get('from') or request.args.get('orig') or '').strip().upper()
    to_code = (request.args.get('to') or request.args.get('dest') or '').strip().upper()
    start_s = (request.args.get('start') or '').strip()
    end_s = (request.args.get('end') or '').strip()
    if not from_code or not to_code:
        return jsonify({'error': 'from and to IATA codes are required'}), 400

    # parse dates
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    def parse_date(s, default):
        try:
            if not s:
                return default
            return datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            return None

    start = parse_date(start_s, today)
    if start is None:
        return jsonify({'error': 'invalid start date, expected YYYY-MM-DD'}), 400
    end = parse_date(end_s, start + timedelta(days=30))
    if end is None:
        return jsonify({'error': 'invalid end date, expected YYYY-MM-DD'}), 400
    if end < start:
        return jsonify({'error': 'end must be >= start'}), 400
    max_span = 90
    if (end - start).days > max_span:
        end = start + timedelta(days=max_span)

    # get base fare using existing pricing logic
    # call internal helper to reuse code path: simulate a GET by calling api_prices logic
    # We'll compute base via local logic similar to api_prices
    airports_map = _load_airports_map()
    a = airports_map.get(from_code)
    b = airports_map.get(to_code)
    distance_km = None
    if a and b and a.get('lat') is not None and b.get('lat') is not None:
        distance_km = _haversine_km(a.get('lat'), a.get('lon'), b.get('lat'), b.get('lon'))
    if distance_km is None:
        # fallback heuristic
        A = from_code or ''
        B = to_code or ''
        s = 0
        for i in range(max(len(A), len(B))):
            ca = ord(A[i]) if i < len(A) else 65
            cb = ord(B[i]) if i < len(B) else 65
            s += abs(ca - cb)
        distance_km = max(50, s * 10)

    base_fee = 30.0
    per_km = 0.12
    try:
        base = round(base_fee + (float(distance_km) * per_km))
    except Exception:
        base = int(base_fee)

    # deterministic availability & price variation generator
    def _det_hash(s: str) -> int:
        h = 2166136261
        for ch in s:
            h ^= ord(ch)
            h *= 16777619
            h &= 0xffffffff
        return h

    out_days = {}
    cur = start
    while cur <= end:
        key = cur.isoformat()
        # use flight+date deterministic hash to simulate availability
        h = _det_hash(from_code + '|' + to_code + '|' + key)
        available = (h % 5) != 0  # ~80% available
        # price variation +- up to 20% based on hash
        var = (h % 41) - 20  # -20 .. +20
        price = max(10, int(round(base * (1 + (var / 100.0)))))
        out_days[key] = {'available': bool(available), 'price': price}
        cur = cur + timedelta(days=1)

    resp = {'from': from_code, 'to': to_code, 'currency': 'USD', 'base': base, 'days': out_days}
    return jsonify(resp), 200

@app.route('/api/prices/offers', methods=['GET'])
def api_prices_offers():
    """Return available airlines and flight offers for a route.
       Query params: from, to, start, end (dates optional)
       Response: { from, to, currency, base, airlines: [ { airline, flights: [ { flight, time, price } ], available_dates: { date: { available, price } } } ], alternatives: [ { airline, price } ] }
    """
    from_code = (request.args.get('from') or request.args.get('orig') or '').strip().upper()
    to_code = (request.args.get('to') or request.args.get('dest') or '').strip().upper()
    start_s = (request.args.get('start') or '').strip()
    end_s = (request.args.get('end') or '').strip()
    if not from_code or not to_code:
        return jsonify({'error': 'from and to IATA codes are required'}), 400

    # reuse date parsing from api_prices_dates_v2
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    def parse_date(s, default):
        try:
            if not s:
                return default
            return datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            return None

    start = parse_date(start_s, today)
    if start is None:
        return jsonify({'error': 'invalid start date, expected YYYY-MM-DD'}), 400
    end = parse_date(end_s, start + timedelta(days=30))
    if end is None:
        return jsonify({'error': 'invalid end date, expected YYYY-MM-DD'}), 400
    if end < start:
        return jsonify({'error': 'end must be >= start'}), 400
    max_span = 90
    if (end - start).days > max_span:
        end = start + timedelta(days=max_span)

    # compute base price using same logic as /api/prices
    airports_map = _load_airports_map()
    a = airports_map.get(from_code)
    b = airports_map.get(to_code)
    distance_km = None
    if a and b and a.get('lat') is not None and b.get('lat') is not None:
        distance_km = _haversine_km(a.get('lat'), a.get('lon'), b.get('lat'), b.get('lon'))
    if distance_km is None:
        A = from_code or ''
        B = to_code or ''
        s = 0
        for i in range(max(len(A), len(B))):
            ca = ord(A[i]) if i < len(A) else 65
            cb = ord(B[i]) if i < len(B) else 65
            s += abs(ca - cb)
        distance_km = max(50, s * 10)

    base_fee = 30.0
    per_km = 0.12
    try:
        base = round(base_fee + (float(distance_km) * per_km))
    except Exception:
        base = int(base_fee)

    # generate per-day availability/prices (route-level)
    def _det_hash(s: str) -> int:
        h = 2166136261
        for ch in s:
            h ^= ord(ch)
            h *= 16777619
            h &= 0xffffffff
        return h

    out_days = {}
    cur = start
    while cur <= end:
        key = cur.isoformat()
        h = _det_hash(from_code + '|' + to_code + '|' + key)
        available = (h % 5) != 0
        var = (h % 41) - 20
        price = max(10, int(round(base * (1 + (var / 100.0)))))
        out_days[key] = {'available': bool(available), 'price': price}
        cur = cur + timedelta(days=1)

    # find flights that explicitly match this origin/destination
    flights = _load_flights()
    matching = [f for f in flights if (str(f.get('origin') or '').strip().upper() == from_code and str(f.get('destination') or '').strip().upper() == to_code)]

    airlines_list = []
    if matching:
        # group by airline
        by_airline = {}
        for f in matching:
            name = f.get('airline') or 'Unknown'
            by_airline.setdefault(name, []).append(f)

        for airline, fls in by_airline.items():
            flights_info = []
            # create a small deterministic modifier per airline so prices differ
            ah = abs(_det_hash(airline)) % 11  # 0..10
            for f in fls:
                # compute a per-flight price using base and modifier
                price = int(round(base * (1 + (ah - 5) / 100.0)))
                # build logo/url hints: prefer flight-provided logo, otherwise generate an avatar URL for the airline
                logo_field = f.get('logo') or None
                logo_url = logo_field if logo_field and (logo_field.startswith('http://') or logo_field.startswith('https://')) else f"https://ui-avatars.com/api/?name={urllib.parse.quote_plus(airline)}&size=64"

                # date-specific offers for this flight: small variation from route-level days
                date_offers = {}
                cur_d = start
                while cur_d <= end:
                    d_key = cur_d.isoformat()
                    # mix flight identifier into hash for per-flight variation
                    fh = _det_hash(f.get('flight') or '')
                    dh = _det_hash(from_code + '|' + to_code + '|' + d_key + '|' + str(fh))
                    avail = (dh % 5) != 0
                    v = (dh % 41) - 20
                    fprice = max(10, int(round(base * (1 + (v / 100.0)) * (1 + (ah - 5) / 100.0))))
                    # booking link template (placeholder). Frontend can replace domain or use route to open booking flow.
                    booking_date = urllib.parse.quote_plus(d_key)
                    booking_url = f"https://booking.example.com/search?flight={urllib.parse.quote_plus(str(f.get('flight') or ''))}&date={booking_date}&from={urllib.parse.quote_plus(from_code)}&to={urllib.parse.quote_plus(to_code)}"
                    date_offers[d_key] = {'available': bool(avail), 'price': fprice, 'booking_url': booking_url}
                    cur_d = cur_d + timedelta(days=1)

                flights_info.append({'flight': f.get('flight'), 'time': f.get('time'), 'price': price, 'aircraft': f.get('aircraft'), 'logo': logo_field, 'logo_url': logo_url, 'date_offers': date_offers, 'booking_url_template': f"https://booking.example.com/search?flight={urllib.parse.quote_plus(str(f.get('flight') or ''))}&date={{date}}"})

            # available dates is the route out_days (kept for compatibility)
            airlines_list.append({'airline': airline, 'flights': flights_info, 'available_dates': out_days})
    else:
        # No explicit flights registered for this route: propose alternative airlines (choose distinct airlines operating either origin or destination)
        alt_candidates = []
        for f in flights:
            orig = (f.get('origin') or '').strip().upper()
            dest = (f.get('destination') or '').strip().upper()
            if orig == from_code or dest == to_code or orig == to_code or dest == from_code:
                alt_candidates.append(f.get('airline') or 'Unknown')
        # fallback to a small hardcoded set if still empty
        if not alt_candidates:
            alt_candidates = ['Generic Air', 'BudgetFly', 'Continental Express', 'Skyways']
        seen = []
        alternatives = []
        for a_name in alt_candidates:
            if a_name in seen:
                continue
            seen.append(a_name)
            ah = abs(_det_hash(a_name)) % 11
            price = int(round(base * (1 + (ah - 5) / 100.0)))
            logo_url = f"https://ui-avatars.com/api/?name={urllib.parse.quote_plus(a_name)}&size=64"
            alternatives.append({'airline': a_name, 'price': price, 'logo_url': logo_url, 'booking_url_template': f"https://booking.example.com/search?airline={urllib.parse.quote_plus(a_name)}&date={{date}}"})

        return jsonify({'from': from_code, 'to': to_code, 'currency': 'USD', 'base': base, 'days': out_days, 'airlines': [], 'alternatives': alternatives}), 200

    return jsonify({'from': from_code, 'to': to_code, 'currency': 'USD', 'base': base, 'days': out_days, 'airlines': airlines_list, 'alternatives': []}), 200

@app.route('/api/request_code', methods=['POST'])
def api_request_code():
    """Request a one-time access code to be sent to the passenger's email on file.
    Body: { passport: str, email?: str }
    If `email` is provided, it must match the passenger email on record.
    """
    data = request.get_json() or {}
    passport = (data.get('passport') or '').strip()
    provided_email = (data.get('email') or '').strip()
    if not passport:
        return jsonify({'error': 'passport required'}), 400

    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({'error': 'passenger not found'}), 404

    email = (p.get('email') or '').strip()
    if not email:
        return jsonify({'error': 'no_email', 'detail': 'no email on file for this passenger; contact agent or provide master password'}), 400

    # If caller supplied an email, require it to match the one on file
    if provided_email:
        def _norm_em(v):
            return (v or '').strip().lower()
        if _norm_em(provided_email) != _norm_em(email):
            return jsonify({'error': 'invalid_email_for_passenger'}), 400
        # optionally light syntax check
        if '@' not in provided_email or '.' not in provided_email.split('@')[-1]:
            return jsonify({'error': 'invalid_email_format'}), 400

    # generate and store code
    code, expires = _set_code_for_passport(passport)

    # send code by email (best effort)
    try:
        msg = EmailMessage()
        msg['Subject'] = "Your access code for boarding pass"
        msg['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER') or 'no-reply@example.com'
        msg['To'] = email
        body = f"Hello {p.get('name')},\n\nYour one-time access code is: {code}\nIt will expire at {expires} (UTC).\n\nIf you did not request this, contact support."
        msg.set_content(body)

        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT') or 0)
        use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')

        if not (smtp_host and smtp_port):
            log_event({'type': 'access_code_created', 'passport': passport, 'to': email, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            return jsonify({'status': 'created_but_not_sent', 'detail': 'SMTP not configured; code generated'}), 201

        if use_ssl:
            smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            smtp.ehlo()
            if os.getenv('SMTP_STARTTLS', 'false').lower() in ('1','true','yes'):
                smtp.starttls()
                smtp.ehlo()

        try:
            smtp_user = os.getenv('SMTP_USER')
            smtp_pass = os.getenv('SMTP_PASS')
            if smtp_user and smtp_pass:
                smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
            log_event({'type': 'access_code_sent', 'passport': passport, 'to': email, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            return jsonify({'status': 'sent'}), 201
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except Exception as e:
        log_event({'type': 'access_code_error', 'passport': passport, 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'error': 'failed_to_send', 'detail': str(e)}), 500

@app.route('/api/passenger/login', methods=['POST'])
def api_passenger_login():
    """Create a passenger session after basic identity: last name + (passport or booking ref).
       Body: { last: str, passport?: str, ref?: str, ttl_seconds?: number }
       Sets `session` cookie and returns { token, expires } on success.
    """
    data = request.get_json(silent=True) or {}
    last = (data.get('last') or '').strip().lower()
    passport = (data.get('passport') or '').strip()
    ref = (data.get('ref') or '').strip()
    try:
        ttl = float(data.get('ttl_seconds') or 3600)
    except Exception:
        ttl = 3600.0

    if not last or (not passport and not ref):
        return jsonify({'error': 'missing_fields', 'detail': 'last and passport or ref required'}), 400

    # find passenger match
    cand = None
    for p in passengers:
        nm = (p.get('name') or '').strip().lower()
        last_ok = nm.endswith(last) or (last in nm)
        ref_ok = bool(ref) and (p.get('booking_ref') or '') == ref
        pp_ok = bool(passport) and (p.get('passport') or '') == passport
        if last_ok and (ref_ok or pp_ok):
            cand = p
            break
    if not cand:
        return jsonify({'error': 'not_found'}), 404

    token, exp = _create_session(cand.get('passport'), role='passenger', extra_data={'passport': cand.get('passport')}, ttl_seconds=ttl)
    resp = jsonify({'token': token, 'expires': exp.get('expires'), 'passport': cand.get('passport')})
    try:
        resp.set_cookie(SESSION_COOKIE_NAMES['passenger'], token, max_age=int(ttl), httponly=True, samesite='Lax', path='/')
    except Exception:
        pass
    return resp, 200

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """Check-in endpoint.
    Body (JSON): {
      flight: str,
      passengers: [ { name, passport, ticket_number?, seat?, baggage_count?, baggage_details? } ]
    }
    If 'passengers' omitted, checks in the session passenger. Returns array of results for each passenger.
    """
    session = _require_session(request)
    # For demo purposes, allow check-in without session if passengers are provided
    if not session:
        # Check if passengers are provided in the request
        data = request.get_json() or {}
        if not data.get('passengers'):
            return jsonify({'error': 'unauthorized_or_passengers_required'}), 401

    data = request.get_json() or {}
    flight = (data.get('flight') or '').strip()
    plist = data.get('passengers')

    # If no passengers list provided, use the session passenger
    if not plist:
        if session.get('role') != 'passenger' or not session.get('passport'):
            return jsonify({'error': 'passengers_required'}), 400
        p = next((x for x in passengers if x.get('passport') == session.get('passport')), None)
        if not p:
            return jsonify({'error': 'passenger_not_found'}), 404
        plist = [p]

    flights = _load_flights()
    flight_entry = next((f for f in flights if f.get('flight') == flight), None) if flight else None

    results = []
    for item in plist:
        name = (item.get('name') or item.get('fullname') or '').strip()
        passport = (item.get('passport') or '').strip()
        ticket = (item.get('ticket_number') or item.get('ticket') or '').strip()
        seat_pref = item.get('seat')
        try:
            baggage_count = int(item.get('baggage_count') or 0)
        except Exception:
            baggage_count = 0
        baggage_details = item.get('baggage_details')

        if not (passport and name and flight):
            results.append({'passport': passport, 'status': 'error', 'detail': 'passport,name,flight required'})
            continue

        # validate passport format — deliberately using security_utils.validate_passport
        # (3-20 chars, allows dashes/underscores) rather than the stricter
        # ValidationUtils.validate_passport (6-12 alnum only) used elsewhere.
        # Passport-less bookings get their booking_ref (e.g. "SF-9B6CE2") used as a
        # stand-in passport key when the passenger record is created — see
        # _add_booking's caller in /api/bookings — and that value contains a
        # dash, so the strict validator would reject it and break check-in for
        # every passport-less booking. If that fallback is ever removed (i.e.
        # every booking is required to have a real passport before check-in),
        # this can switch to ValidationUtils.validate_passport too.
        ok, reason = validate_passport(passport)
        if not ok:
            results.append({'passport': passport, 'status': 'error', 'detail': 'invalid_passport', 'reason': reason})
            continue

        # find or create passenger record
        p = next((x for x in passengers if x.get('passport') == passport), None)
        if p is None:
            p = {'name': name, 'passport': passport}
            passengers.append(p)
        elif (p.get('name') or '').strip().lower() != name.strip().lower():
            # This passport already belongs to someone else on file — refuse rather
            # than silently renaming their record to match this check-in request.
            results.append({'passport': passport, 'status': 'error', 'detail': 'passport_registered_to_different_passenger'})
            continue

        # Check duplicate for same flight
        if find_duplicate(passport, flight):
            # allow idempotent check-in update
            existing = next((x for x in passengers if x.get('passport') == passport and x.get('flight') == flight), None)
            if existing:
                p = existing

        # Enforce flight capacity
        if flight_entry and flight_entry.get('capacity') is not None:
            try:
                capacity = int(flight_entry.get('capacity'))
            except Exception:
                capacity = None
            current = sum(1 for pp in passengers if pp.get('flight') == flight and pp.get('passport') != passport)
            if capacity is not None and current >= capacity:
                results.append({'passport': passport, 'status': 'error', 'detail': 'flight_full'})
                continue

        # assign seat: support both explicit seat labels and preference keywords
        existing_seats = [str(pp.get('seat')) for pp in passengers if pp.get('flight') == flight and pp.get('seat')]
        assigned_seat = None
        try:
            # If seat_pref is a preference keyword (window/aisle/middle/any)
            if isinstance(seat_pref, str) and seat_pref.lower() in ('window','aisle','middle','any'):
                capacity = flight_entry.get('capacity') if flight_entry else None
                assigned_seat = autoassign_seat_from_capacity(capacity, existing_seats=existing_seats, blocked_seats=flight_entry.get('blocked_seats') if flight_entry else None, preference=seat_pref)
            # If seat_pref is a direct seat label and available
            if not assigned_seat and seat_pref:
                if str(seat_pref) not in existing_seats:
                    assigned_seat = seat_pref
            # fallback numeric increment for legacy numeric seats
            if not assigned_seat:
                # try numeric labels first
                nums = []
                for s in existing_seats:
                    try:
                        nums.append(int(s))
                    except Exception:
                        pass
                assigned_seat = (max(nums) + 1) if nums else None
                if assigned_seat is None:
                    # if no numeric seats, pick first available label from seat map
                    if flight_entry and flight_entry.get('capacity'):
                        cap = int(flight_entry.get('capacity'))
                        cols = ['A','B','C','D','E','F']
                        labels = []
                        rows = (cap + len(cols) - 1) // len(cols)
                        count = 0
                        for r in range(1, rows+1):
                            for c in cols:
                                count += 1
                                if count > cap:
                                    break
                                label = f"{r}{c}"
                                if label not in existing_seats and label not in (flight_entry.get('blocked_seats') or []):
                                    assigned_seat = label
                                    break
                            if assigned_seat:
                                break
                if assigned_seat is None:
                    assigned_seat = 1
        except Exception:
            assigned_seat = 1

        # update passenger record
        p['name'] = name
        p['passport'] = passport
        p['flight'] = flight
        p['seat'] = assigned_seat
        if ticket:
            p['ticket_number'] = ticket
        # baggage
        p['baggage_count'] = baggage_count
        p['baggage_details'] = baggage_details
        p['baggage_fee'] = _compute_baggage_fee(baggage_count)
        p['baggage_paid'] = p.get('baggage_paid', False)
        p['checked_in'] = True

        try:
            save_passengers()
        except Exception:
            pass

        # Log event (events.json — the internal audit trail)
        log_event({'type': 'checkin', 'passport': passport, 'flight': flight, 'seat': assigned_seat, 'baggage_count': baggage_count, 'timestamp': datetime.utcnow().isoformat() + 'Z'})

        # Also record this in the activity tracker — this is what the admin
        # Check-Ins dashboard (/api/activities/checkins) actually reads. Without
        # this, every real check-in made through the online check-in flow was
        # invisible to admin/staff: only /api/register's separate, simpler
        # check-in path was feeding that dashboard, so it looked like nobody
        # was checking in even while passengers were.
        try:
            log_activity('checkin', {
                'passenger_name': name,
                'flight_number': flight,
                'seat': assigned_seat,
                'gate': (flight_entry.get('gate') if flight_entry else None) or 'TBA',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        except Exception as e:
            print(f"Warning: Failed to log checkin activity: {e}")

        # attempt to send boarding pass by email if email present (enqueue)
        email_sent = False
        if p.get('email'):
            try:
                # Define a stub for enqueue_boarding_email if not already defined
                def enqueue_boarding_email(passenger):
                    # Placeholder: implement actual email sending logic here
                    print(f"Enqueue boarding email for {passenger.get('email')}")
                enqueue_boarding_email(p)
                email_sent = True
            except Exception:
                email_sent = False

        results.append({'passport': passport, 'status': 'ok', 'seat': assigned_seat, 'baggage_fee': p.get('baggage_fee'), 'email_sent': email_sent})

    return jsonify({'results': results}), 200

@app.route('/api/baggage/pay', methods=['POST'])
def api_baggage_pay():
    """Simulate baggage fee payment. Body: { passport, amount }
    Marks passenger.baggage_paid = True when amount >= baggage_fee.
    """
    data = request.get_json() or {}
    passport = (data.get('passport') or '').strip()
    amount = float(data.get('amount') or 0)
    if not passport:
        return jsonify({'error': 'passport required'}), 400
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({'error': 'passenger not found'}), 404
    fee = p.get('baggage_fee', 0)
    if amount < fee:
        return jsonify({'error': 'insufficient_amount', 'required': fee}), 400
    p['baggage_paid'] = True
    try:
        save_passengers()
    except Exception:
        pass
    log_event({'type': 'baggage_payment', 'passport': passport, 'amount': amount, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'paid', 'amount': amount}), 200

@app.route('/api/flights/<flight_id>', methods=['PUT','DELETE'])
def api_flight_modify(flight_id):
    # flight_id is flight number string
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    flights = _load_flights()
    idx = next((i for i,f in enumerate(flights) if f.get('flight') == flight_id), None)
    if idx is None:
        return jsonify({'error': 'not_found'}), 404

    if request.method == 'DELETE':
        removed = flights.pop(idx)
        _save_flights(flights)
        log_event({'type': 'flight_deleted', 'flight': flight_id, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'deleted', 'flight': removed}), 200

    # PUT -> update
    data = request.get_json() or {}
    new_time = data.get('time')
    new_flight = (data.get('flight') or '').strip() or flight_id
    aircraft = data.get('aircraft') if 'aircraft' in data else flights[idx].get('aircraft')
    gate = data.get('gate') if 'gate' in data else flights[idx].get('gate')
    arrival = data.get('arrival') if 'arrival' in data else flights[idx].get('arrival')
    checkin_enabled = data.get('checkin_enabled') if 'checkin_enabled' in data else flights[idx].get('checkin_enabled')
    # capacity can be updated
    capacity = flights[idx].get('capacity')
    if 'capacity' in data:
        try:
            if data.get('capacity') is None or str(data.get('capacity')).strip() == '':
                capacity = None
            else:
                capacity = int(data.get('capacity'))
        except Exception:
            return jsonify({'error': 'invalid_capacity'}), 400

    # Define _parse_time_field if not already defined
    def _parse_time_field(val):
        """Parse a time/datetime string and return ISO8601 format, or raise ValueError."""
        if not val:
            return None
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
            return dt.isoformat().replace('+00:00', 'Z')
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.isoformat() + 'Z'
            except Exception:
                continue
        raise ValueError(f"Unrecognized time format: {val}")

    try:
        time_iso = _parse_time_field(new_time) if new_time is not None else flights[idx].get('time')
        arrival_iso = _parse_time_field(arrival) if arrival is not None else flights[idx].get('arrival')
    except ValueError as e:
        return jsonify({'error': 'invalid_time', 'detail': str(e)}), 400
    # if flight number changed, ensure no collision
    if new_flight != flight_id and any(f.get('flight') == new_flight for f in flights):
        return jsonify({'error': 'flight_exists'}), 400
    flights[idx]['flight'] = new_flight
    flights[idx]['time'] = time_iso
    flights[idx]['capacity'] = capacity
    flights[idx]['aircraft'] = aircraft
    flights[idx]['gate'] = gate
    flights[idx]['arrival'] = arrival_iso
    flights[idx]['checkin_enabled'] = bool(checkin_enabled)
    _save_flights(flights)
    log_event({'type': 'flight_updated', 'flight': new_flight, 'time': time_iso, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'updated', 'flight': flights[idx]}), 200

@app.route('/api/flights/<flight_id>/passengers', methods=['GET'])
def api_flight_passengers(flight_id):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    matches = [p for p in passengers if p.get('flight') == flight_id]
    return jsonify({'passengers': matches}), 200

@app.route('/api/flights/<flight_id>/seats', methods=['GET'])
def api_flight_seats(flight_id):
    """Return a simple seat map for a flight. Not highly detailed - returns seat entries with status.
    Response: { seats: [ { seat: '1', status: 'available'|'taken'|'blocked'|'unknown', passenger?: {...} } ], flight: {...} }
    """
    # no special auth required - seat map can be public for kiosk view
    flights = _load_flights()
    flight = next((f for f in flights if f.get('flight') == flight_id), None)
    if not flight:
        return jsonify({'error': 'flight_not_found'}), 404

    # determine capacity and generate seat labels (e.g., 1A,1B,...)
    capacity = flight.get('capacity')
    taken = { str(p.get('seat')): p for p in passengers if p.get('flight') == flight_id and p.get('seat') }
    blocked = { str(s): True for s in (flight.get('blocked_seats') or []) }
    # load holds and filter expired
    def _load_holds():
        try:
            if os.path.exists(HOLDS_FILE):
                with open(HOLDS_FILE, 'r') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _save_holds(h):
        try:
            with open(HOLDS_FILE, 'w') as f:
                json.dump(h, f, indent=2)
        except Exception:
            pass

    holds = _load_holds().get(flight_id, [])
    # cleanup expired holds
    now = datetime.utcnow()
    active_holds = []
    for h in holds:
        try:
            exp = datetime.fromisoformat(h.get('expires').replace('Z',''))
        except Exception:
            continue
        if exp > now:
            active_holds.append(h)
    # write back if any expired were removed
    if len(active_holds) != len(holds):
        all_holds = _load_holds()
        all_holds[flight_id] = active_holds
        _save_holds(all_holds)
    holds = active_holds

    def _generate_seat_labels(cap):
        # Simple layout: 6 seats per row labeled A-F
        cols = ['A','B','C','D','E','F']
        seats = []
        rows = (cap + len(cols) - 1) // len(cols)
        count = 0
        for r in range(1, rows+1):
            for c in cols:
                count += 1
                if count > cap:
                    break
                seats.append(f"{r}{c}")
        return seats

    seats = []
    if capacity:
        try:
            cap = int(capacity)
        except Exception:
            cap = None
        if cap:
            labels = _generate_seat_labels(cap)
            for s in labels:
                # check holds first
                hold_entry = next((hh for hh in holds if hh.get('seat') == s), None)
                if s in taken:
                    seats.append({'seat': s, 'status': 'taken', 'passenger': {'name': taken[s].get('name'), 'passport': taken[s].get('passport')}})
                elif hold_entry:
                    seats.append({'seat': s, 'status': 'held', 'held_by': hold_entry.get('passport'), 'held_expires': hold_entry.get('expires')})
                elif s in blocked:
                    seats.append({'seat': s, 'status': 'blocked'})
                else:
                    seats.append({'seat': s, 'status': 'available'})
    else:
        # no capacity defined -> return known taken seats and blocked seats
        for s, p in taken.items():
            seats.append({'seat': s, 'status': 'taken', 'passenger': {'name': p.get('name'), 'passport': p.get('passport')}})
        for s in (flight.get('blocked_seats') or []):
            if not any(x['seat'] == str(s) for x in seats):
                seats.append({'seat': str(s), 'status': 'blocked'})

    return jsonify({'flight': flight, 'seats': seats}), 200

@app.route('/api/flights/<flight_id>/seats/select', methods=['POST'])
def api_flight_seat_select(flight_id):
    """Passenger-facing seat selection. Requires a passenger session and assigns a seat if available.
    Body: { seat: '12', passport?: '...' }
    """
    session = _require_session(request)
    if not session or session.get('role') != 'passenger':
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json() or {}
    seat = str(data.get('seat') or '').strip()
    passport = (data.get('passport') or session.get('passport') or '').strip()
    if not seat or not passport:
        return jsonify({'error': 'seat_and_passport_required'}), 400

    flights = _load_flights()
    flight = next((f for f in flights if f.get('flight') == flight_id), None)
    if not flight:
        return jsonify({'error': 'flight_not_found'}), 404

    # check blocked seats
    if str(seat) in [str(x) for x in (flight.get('blocked_seats') or [])]:
        return jsonify({'error': 'seat_blocked'}), 400

    # check conflict: seat taken by other passenger
    conflict = next((p for p in passengers if p.get('flight') == flight_id and str(p.get('seat')) == str(seat) and p.get('passport') != passport), None)
    if conflict:
        return jsonify({'error': 'seat_taken', 'by': conflict.get('passport')}), 400

    # find passenger record for passport
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        # not found - create minimal passenger record and attach flight
        p = {'name': data.get('name') or '', 'passport': passport, 'flight': flight_id}
        passengers.append(p)

    # assign seat
    p['seat'] = seat
    try:
        save_passengers()
    except Exception:
        pass

    log_event({'type': 'seat_selected', 'flight': flight_id, 'passport': passport, 'seat': seat, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'seat': seat, 'passenger': p}), 200

@app.route('/api/flights/<flight_id>/seats/autoassign', methods=['POST'])
def api_flight_seat_autoassign(flight_id):
    """Auto-assign a seat based on preference: window, aisle, middle, any.
    Body: { passport: str, preference?: 'window'|'aisle'|'middle'|'any' }
    """
    session = _require_session(request)
    # allow kiosk/no-session calls but prefer session passenger
    data = request.get_json() or {}
    passport = (data.get('passport') or (session.get('passport') if session else '')).strip()
    pref = (data.get('preference') or 'any').lower()

    if not passport:
        return jsonify({'error': 'passport_required'}), 400

    flights = _load_flights()
    flight = next((f for f in flights if f.get('flight') == flight_id), None)
    if not flight:
        return jsonify({'error': 'flight_not_found'}), 404

    capacity = flight.get('capacity')
    if not capacity:
        # fallback to numeric assignment
        existing = [str(p.get('seat')) for p in passengers if p.get('flight') == flight_id and p.get('seat')]
        assigned = None
        n = 1
        while True:
            if str(n) not in existing:
                assigned = str(n); break
            n += 1
        if not assigned:
            return jsonify({'error': 'no_seat_available'}), 400
        # assign
        p = next((x for x in passengers if x.get('passport') == passport), None)
        if p is None:
            p = {'name': '', 'passport': passport, 'flight': flight_id}
            passengers.append(p)
        p['seat'] = assigned
        try: save_passengers()
        except Exception: pass
        log_event({'type': 'seat_autoassign', 'flight': flight_id, 'passport': passport, 'seat': assigned, 'preference': pref, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'ok', 'seat': assigned}), 200

    assigned = autoassign_seat_from_capacity(capacity, existing_seats=[str(p.get('seat')) for p in passengers if p.get('flight') == flight_id and p.get('seat')], blocked_seats=flight.get('blocked_seats') or [], preference=pref)
    if not assigned:
        return jsonify({'error': 'no_seat_available'}), 400

    # assign to passenger record
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if p is None:
        p = {'name': '', 'passport': passport, 'flight': flight_id}
        passengers.append(p)
    p['seat'] = assigned
    try: save_passengers()
    except Exception: pass

    log_event({'type': 'seat_autoassign', 'flight': flight_id, 'passport': passport, 'seat': assigned, 'preference': pref, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'seat': assigned}), 200

@app.route('/api/flights/<flight_id>/seats/hold', methods=['POST'])
def api_flight_seat_hold(flight_id):
    """Place a temporary hold on a seat for a passenger.
    Body: { passport?: str, seat: '1A', ttl_seconds?: int }
    Requires passenger session or passport provided.
    """
    data = request.get_json() or {}
    session = _require_session(request)
    passport = (data.get('passport') or (session.get('passport') if session else '') or '').strip()
    seat = str(data.get('seat') or '').strip()
    try:
        ttl = int(data.get('ttl_seconds') or 300)
    except Exception:
        ttl = 300
    if not passport or not seat:
        return jsonify({'error': 'passport_and_seat_required'}), 400

    flights = _load_flights()
    flight = next((f for f in flights if f.get('flight') == flight_id), None)
    if not flight:
        return jsonify({'error': 'flight_not_found'}), 404

    # check blocked or already taken
    if str(seat) in [str(x) for x in (flight.get('blocked_seats') or [])]:
        return jsonify({'error': 'seat_blocked'}), 400
    conflict = next((p for p in passengers if p.get('flight') == flight_id and str(p.get('seat')) == str(seat) and p.get('passport') != passport), None)
    if conflict:
        return jsonify({'error': 'seat_taken', 'by': conflict.get('passport')}), 400

    # load holds
    try:
        holds_all = {}
        if os.path.exists(HOLDS_FILE):
            with open(HOLDS_FILE, 'r') as f:
                holds_all = json.load(f) or {}
    except Exception:
        holds_all = {}
    flight_holds = holds_all.get(flight_id, [])
    # cleanup expired
    now = datetime.utcnow()
    valid_holds = []
    for h in flight_holds:
        try:
            exp = datetime.fromisoformat(h.get('expires').replace('Z', ''))
            if exp > now:
                valid_holds.append(h)
        except Exception:
            continue
    flight_holds = valid_holds
    # check existing hold conflict
    if any(h.get('seat') == seat and h.get('passport') != passport for h in flight_holds):
        return jsonify({'error': 'seat_held'}), 400

    expires = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat() + 'Z'
    hold = {'seat': seat, 'passport': passport, 'expires': expires}
    # replace any existing hold by this passport on same seat
    flight_holds = [h for h in flight_holds if not (h.get('seat') == seat and h.get('passport') == passport)]
    flight_holds.append(hold)
    holds_all[flight_id] = flight_holds
    try:
        with open(HOLDS_FILE, 'w') as f:
            json.dump(holds_all, f, indent=2)
    except Exception:
        pass

    log_event({'type': 'seat_hold', 'flight': flight_id, 'passport': passport, 'seat': seat, 'expires': expires, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'held', 'seat': seat, 'expires': expires}), 200

@app.route('/api/flights/<flight_id>/seats/release', methods=['POST'])
def api_flight_seat_release(flight_id):
    data = request.get_json() or {}
    passport = (data.get('passport') or '').strip()
    seat = str(data.get('seat') or '').strip()
    if not passport or not seat:
        return jsonify({'error': 'passport_and_seat_required'}), 400
    try:
        holds_all = {}
        if os.path.exists(HOLDS_FILE):
            with open(HOLDS_FILE, 'r') as f:
                holds_all = json.load(f) or {}
    except Exception:
        holds_all = {}
    flight_holds = holds_all.get(flight_id, [])
    new_holds = [h for h in flight_holds if not (h.get('seat') == seat and h.get('passport') == passport)]
    holds_all[flight_id] = new_holds
    try:
        with open(HOLDS_FILE, 'w') as f:
            json.dump(holds_all, f, indent=2)
    except Exception:
        pass
    log_event({'type': 'seat_release', 'flight': flight_id, 'passport': passport, 'seat': seat, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'released'}), 200

@app.route('/api/passengers/<passport>/override', methods=['POST'])
def api_passenger_override(passport):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    action = data.get('action')
    note = data.get('note')
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({'error': 'passenger_not_found'}), 404
    # actions: set_checked_in, clear_checked_in, mark_issue_resolved
    if action == 'set_checked_in':
        p['checked_in'] = True
    elif action == 'clear_checked_in':
        p['checked_in'] = False
    elif action == 'resolve_issue':
        p['issue'] = None
    else:
        return jsonify({'error': 'unknown_action'}), 400
    # record override metadata
    p.setdefault('admin_overrides', []).append({'action': action, 'note': note, 'by': session.get('role'), 'when': datetime.utcnow().isoformat() + 'Z'})
    try:
        save_passengers()
    except Exception:
        pass
    log_event({'type': 'admin_override', 'passport': passport, 'action': action, 'note': note, 'admin': session.get('passport'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'passenger': p}), 200

@app.route('/api/passengers/<passport>/seat', methods=['POST'])
def api_passenger_seat(passport):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    seat = data.get('seat')
    if not seat:
        return jsonify({'error': 'seat_required'}), 400
    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({'error': 'passenger_not_found'}), 404
    # ensure seat not taken on same flight
    if p.get('flight'):
        conflict = next((x for x in passengers if x.get('flight') == p.get('flight') and str(x.get('seat')) == str(seat) and x.get('passport') != passport), None)
        if conflict:
            return jsonify({'error': 'seat_taken', 'by': conflict.get('passport')}), 400
    p['seat'] = seat
    try:
        save_passengers()
    except Exception:
        pass
    log_event({'type': 'seat_assigned', 'passport': passport, 'seat': seat, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'passenger': p}), 200

@app.route('/api/flights/<flight_id>/seat_block', methods=['POST'])
def api_flight_seat_block(flight_id):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    seat = data.get('seat')
    action = (data.get('action') or 'block')
    if not seat:
        return jsonify({'error': 'seat_required'}), 400
    flights = _load_flights()
    idx = next((i for i,f in enumerate(flights) if f.get('flight') == flight_id), None)
    if idx is None:
        return jsonify({'error': 'flight_not_found'}), 404
    blocked = flights[idx].get('blocked_seats') or []
    if action == 'block':
        if seat not in blocked:
            blocked.append(seat)
    else:
        if seat in blocked:
            blocked.remove(seat)
    flights[idx]['blocked_seats'] = blocked
    _save_flights(flights)
    log_event({'type': 'seat_block', 'flight': flight_id, 'seat': seat, 'action': action, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'blocked_seats': blocked}), 200

@app.route('/api/flights/<flight_id>/boarding', methods=['GET','POST'])
def api_flight_boarding(flight_id):
    """
    Manage boarding state for a flight.
    GET: Return current boarding state for the flight.
    POST: Update boarding state (start, stop, mark_boarded).
    """
    def _load_boarding_state():
        """Load the boarding state from a JSON file."""
        path = os.path.join(BASE_DIR, 'boarding_state.json')
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _save_boarding_state(state):
        """Save the boarding state to a JSON file."""
        path = os.path.join(BASE_DIR, 'boarding_state.json')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state or {}, f, indent=2)
        except Exception:
            pass

    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    state = _load_boarding_state()
    if request.method == 'GET':
        return jsonify(state.get(flight_id, {})), 200
    data = request.get_json() or {}
    action = data.get('action')
    if action == 'start':
        state.setdefault(flight_id, {})['boarding_started'] = True
        state[flight_id]['boarded'] = state[flight_id].get('boarded', [])
    elif action == 'stop':
        state.setdefault(flight_id, {})['boarding_started'] = False
    elif action == 'mark_boarded':
        passport = data.get('passport')
        if not passport:
            return jsonify({'error': 'passport_required'}), 400
        state.setdefault(flight_id, {}).setdefault('boarded', [])
        if passport not in state[flight_id]['boarded']:
            state[flight_id]['boarded'].append(passport)
    else:
        return jsonify({'error': 'unknown_action'}), 400
    _save_boarding_state(state)
    log_event({'type': 'boarding_action', 'flight': flight_id, 'action': action, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'state': state.get(flight_id)}), 200

@app.route('/api/admin/dashboard/stats', methods=['GET'])
def api_admin_dashboard_stats():
    # This endpoint seems to be a duplicate or older version.
    # A more complete version is at /api/analytics.
    return api_analytics()

@app.route('/api/admin/flights/bulk', methods=['POST'])
def api_admin_flights_bulk():
    """Bulk operations on flights"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.get_json()
    if not data or 'action' not in data or 'flights' not in data:
        return jsonify({'error': 'Missing action or flights'}), 400
    
    action = data['action']
    flight_ids = data['flights']
    
    flights = _load_flights()
    results = []
    
    if action == 'cancel':
        for flight_id in flight_ids:
            flight = next((f for f in flights if f['flight'] == flight_id), None)
            if flight:
                flight['status'] = 'cancelled'
                results.append({'flight': flight_id, 'status': 'cancelled'})
    
    elif action == 'activate':
        for flight_id in flight_ids:
            flight = next((f for f in flights if f['flight'] == flight_id), None)
            if flight:
                flight['status'] = 'active'
                results.append({'flight': flight_id, 'status': 'active'})
    
    _save_flights(flights)
    return jsonify({'status': 'success', 'results': results}), 200


@app.route('/api/admin/reports/generate', methods=['POST'])
def api_admin_generate_report():
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.get_json()
    if not data or 'type' not in data:
        return jsonify({'error': 'Report type required'}), 400
    
    report_type = data['type']
    date_range = data.get('date_range', {})
    start_date = date_range.get('start')
    end_date = date_range.get('end')
    
    if report_type == 'passenger_activity':
        report_data = {
            'total_passengers': len(passengers),
            'check_ins': sum(1 for p in passengers if p.get('checked_in', False)),
            'baggage_data': {
                'total_items': sum(int(p.get('baggage_count', 0)) for p in passengers),
                'total_fees': sum(float(p.get('baggage_fee', 0)) for p in passengers)
            }
        }
    
    elif report_type == 'flight_performance':
        flights = _load_flights()
        report_data = {
            'total_flights': len(flights),
            'status_breakdown': {
                'active': sum(1 for f in flights if f.get('status') == 'active'),
                'completed': sum(1 for f in flights if f.get('status') == 'completed'),
                'cancelled': sum(1 for f in flights if f.get('status') == 'cancelled')
            }
        }
    
    elif report_type == 'revenue':
        report_data = {
            'baggage_fees': sum(float(p.get('baggage_fee', 0)) for p in passengers),
            'paid_fees': sum(float(p.get('baggage_fee', 0)) for p in passengers if p.get('baggage_paid', False))
        }
    
    else:
        return jsonify({'error': 'Invalid report type'}), 400
    
    return jsonify({
        'report_type': report_type,
        'date_range': {'start': start_date, 'end': end_date},
        'data': report_data
    }), 200

# ---- Announcements / Offers (admin-managed banners shown to passengers) ----
ANNOUNCEMENT_ALLOWED_TYPES = ['announcement', 'offer']

def _load_announcements():
    data = _load_json_file(ANNOUNCEMENTS_FILE, [])
    return data if isinstance(data, list) else []

def _save_announcements(items):
    return _save_json_file(ANNOUNCEMENTS_FILE, items or [])

@app.route('/api/admin/announcements', methods=['GET', 'POST'])
def api_admin_announcements():
    """GET: list all announcements/offers (newest first).
    POST: create a new announcement/offer."""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401

    if request.method == 'GET':
        items = _load_announcements()
        items_sorted = sorted(items, key=lambda a: a.get('created_at', ''), reverse=True)
        return jsonify({'announcements': items_sorted}), 200

    # POST
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '').strip()
    message = (payload.get('message') or '').strip()
    if not title or not message:
        return jsonify({'error': 'validation_error', 'detail': 'title and message are required'}), 400

    anno_type = payload.get('type') if payload.get('type') in ANNOUNCEMENT_ALLOWED_TYPES else 'announcement'
    code = (payload.get('code') or '').strip() or None
    cta_label = (payload.get('cta_label') or '').strip() or None
    cta_url = (payload.get('cta_url') or '').strip() or None

    record = {
        'id': 'ANN-' + secrets.token_hex(4).upper(),
        'type': anno_type,
        'title': title,
        'message': message,
        'code': code,
        'cta_label': cta_label,
        'cta_url': cta_url,
        'active': True,
        'created_by': sess.get('username'),
        'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }

    items = _load_announcements()
    items.append(record)
    if not _save_announcements(items):
        return jsonify({'error': 'save_failed'}), 500

    return jsonify({'ok': True, 'announcement': record}), 201

@app.route('/api/admin/announcements/<announcement_id>', methods=['PUT', 'DELETE'])
def api_admin_announcement_detail(announcement_id):
    """PUT: update fields (used by the dashboard to toggle `active`).
    DELETE: remove the announcement/offer entirely."""
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401

    items = _load_announcements()
    idx = next((i for i, a in enumerate(items) if a.get('id') == announcement_id), None)
    if idx is None:
        return jsonify({'error': 'not_found'}), 404

    if request.method == 'DELETE':
        removed = items.pop(idx)
        if not _save_announcements(items):
            return jsonify({'error': 'save_failed'}), 500
        return jsonify({'ok': True, 'deleted': removed.get('id')}), 200

    # PUT — apply any recognized fields present in the payload; the dashboard
    # currently only ever sends {active: bool}, but accepting the rest here
    # means edit-in-place can be added later without another backend change.
    payload = request.get_json(silent=True) or {}
    editable_fields = ['type', 'title', 'message', 'code', 'cta_label', 'cta_url', 'active']
    for field in editable_fields:
        if field in payload:
            if field == 'type' and payload[field] not in ANNOUNCEMENT_ALLOWED_TYPES:
                continue
            if field == 'active':
                items[idx][field] = bool(payload[field])
            else:
                items[idx][field] = (payload[field] or '').strip() if isinstance(payload[field], str) else payload[field]
    items[idx]['updated_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    if not _save_announcements(items):
        return jsonify({'error': 'save_failed'}), 500

    return jsonify({'ok': True, 'announcement': items[idx]}), 200

@app.route('/api/admin/notifications/send', methods=['POST'])
def api_admin_send_notification():
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.get_json()
    if not data or 'type' not in data or 'recipients' not in data or 'message' not in data:
        return jsonify({'error': 'Missing required notification data'}), 400
    
    notification_type = data['type']
    recipients = data['recipients']
    message = data['message']
    
    success_count = 0
    failed_count = 0
    results = []
    
    for recipient in recipients:
        passenger = next(
            (p for p in passengers if str(p.get('passport')) == str(recipient)
             or str(p.get('email')).lower() == str(recipient).lower()
             or str(p.get('phone')) == str(recipient)),
            None
        )
        if not passenger:
            failed_count += 1
            results.append({
                'recipient': recipient,
                'status': 'failed',
                'error': 'recipient_not_found'
            })
            continue

        try:
            if notification_type == 'email' and passenger.get('email'):
                msg = EmailMessage()
                msg['Subject'] = data.get('subject', 'Important Flight Information')
                msg['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER') or 'no-reply@example.com'
                msg['To'] = passenger['email']
                msg.set_content(message)
                _smtp_send_message(msg)
                success_count += 1
                results.append({
                    'recipient': recipient,
                    'status': 'sent',
                    'method': 'email'
                })
            elif notification_type == 'sms' and passenger.get('phone'):
                _send_sms_message(passenger['phone'], message)
                success_count += 1
                results.append({
                    'recipient': recipient,
                    'status': 'sent',
                    'method': 'sms'
                })
            else:
                failed_count += 1
                results.append({
                    'recipient': recipient,
                    'status': 'failed',
                    'error': 'recipient_missing_contact'
                })
        except Exception as e:
            failed_count += 1
            results.append({
                'recipient': recipient,
                'status': 'failed',
                'error': str(e)
            })
    
    return jsonify({
        'status': 'completed',
        'summary': {
            'total': len(recipients),
            'success': success_count,
            'failed': failed_count
        },
        'results': results
    }), 200

@app.route('/api/flights/<flight_id>/boarding/stream')
def api_boarding_stream(flight_id):
    # SSE stream of boarding state updates for a flight (admin only)
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

    def _load_boarding_state():
        """Load the boarding state from a JSON file."""
        path = os.path.join(BASE_DIR, 'boarding_state.json')
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def event_stream():
        last = None
        while True:
            try:
                state = _load_boarding_state().get(flight_id, {})
                if state != last:
                    data = json.dumps(state)
                    yield f"data: {data}\n\n"
                    last = state
                time.sleep(1)
            except GeneratorExit:
                break
            except Exception:
                time.sleep(1)
                continue

    headers = { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' }
    return Response(stream_with_context(event_stream()), headers=headers)

@app.route('/api/analytics', methods=['GET'])
def api_analytics():
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    total_bookings = len(passengers)
    checked_in = sum(1 for p in passengers if p.get('checked_in'))
    baggage_total = sum(int(p.get('baggage_count') or 0) for p in passengers)
    flights = _load_flights()
    per_flight = {}
    for f in flights:
        fn = f.get('flight')
        per_flight[fn] = {
            'bookings': sum(1 for p in passengers if p.get('flight') == fn),
            'checked_in': sum(1 for p in passengers if p.get('flight') == fn and p.get('checked_in'))
        }
    return jsonify({'total_bookings': total_bookings, 'checked_in': checked_in, 'baggage_total': baggage_total, 'per_flight': per_flight}), 200


@app.route('/api/flights/<flight_id>/checkin-toggle', methods=['POST'])
def api_flight_checkin_toggle(flight_id):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    enabled = data.get('enabled')
    if enabled is None:
        return jsonify({'error': 'enabled_required'}), 400
    flights = _load_flights()
    idx = next((i for i,f in enumerate(flights) if f.get('flight') == flight_id), None)
    if idx is None:
        return jsonify({'error': 'flight_not_found'}), 404
    flights[idx]['checkin_enabled'] = bool(enabled)
    _save_flights(flights)
    log_event({'type': 'checkin_toggled', 'flight': flight_id, 'enabled': bool(enabled), 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'ok', 'flight': flights[idx]}), 200

@app.route('/api/admin/users', methods=['GET','POST','DELETE'])
def api_admin_users():
    session = _require_session(request)
    # only existing admin sessions can manage admin users
    if not session or session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    if request.method == 'GET':
        users = _load_admin_users()
        return jsonify({'users': list(users.keys())}), 200
    data = request.get_json() or {}
    if request.method == 'POST':
        validator = ValidationUtils()
        try:
            username = validator.validate_required_field(data.get('username'), field_name="username")
            password = validator.validate_password(data.get('password'), field_name="password", min_length=8, require_special=False)
        except ValidationError as e:
            return jsonify({'error': 'validation_error', 'field': e.field, 'detail': e.message}), 400
        
        users = _load_admin_users()
        try:
            # Use a higher cost factor for admin passwords
            ph = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(14)).decode('utf-8')
        except Exception:
            ph = password
        users[username] = {'password_hash': ph}
        _save_admin_users(users)
        log_event({'type': 'admin_user_created', 'username': username, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'created', 'username': username}), 201
    if request.method == 'DELETE':
        username = (data.get('username') or '').strip()
        if not username:
            return jsonify({'error': 'username_required'}), 400
        users = _load_admin_users()
        if username in users:
            del users[username]
            _save_admin_users(users)
            log_event({'type': 'admin_user_deleted', 'username': username, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            return jsonify({'status': 'deleted', 'username': username}), 200
        return jsonify({'error': 'not_found'}), 404

@app.route('/api/login', methods=['POST'])
def api_login():
    """Login as admin or passenger.
    For passenger: { role: 'passenger', passport: <str>, code: <6-digit> }
    For admin: { role: 'admin', username: <str>, password: <str> }
    Returns { token, role, expires }
    """
    # This is the main, consolidated login endpoint.
    data = request.get_json() or {}
    role = (data.get('role') or '').lower()

    if role == 'passenger':
        validator = ValidationUtils()
        # Passenger may login/register with either (1) name+passport, or (2) email or phone.
        passport = (data.get('passport') or '').strip()
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()

        if not ((passport and name) or email or phone):
            return jsonify({'error': 'provide passport+name, or email, or phone to login/register'}), 400

        try:
            # Validate passport format if provided
            if passport:
                passport = validator.validate_passport(passport, field_name="passport")
            
            # Validate name if provided
            if name:
                name = validator.validate_name(name, field_name="name")
            
            # Validate email if provided
            if email:
                email = validator.validate_email(email, field_name="email")
            
            # Validate phone if provided
            if phone:
                phone = validator.validate_phone(phone, is_kenyan=True, field_name="phone")
                
        except ValidationError as e:
            return jsonify({'error': 'validation_error', 'field': e.field, 'detail': e.message}), 400

        p = None
        # Try to find by passport
        if passport:
            p = next((x for x in passengers if x.get('passport') == passport), None)
        # Try to find by email/phone
        if not p and email:
            p = next((x for x in passengers if x.get('email') == email), None)
        if not p and phone:
            p = next((x for x in passengers if x.get('phone') == phone), None)

        if p is None:
            # create a new passenger record
            p = {}
            if name:
                p['name'] = name
            if passport:
                p['passport'] = passport
            if email:
                p['email'] = email
            if phone:
                p['phone'] = phone
            p['checked_in'] = False
            passengers.append(p)
            try:
                save_passengers()
            except Exception:
                pass
            log_event({'type': 'passenger_created_via_login', 'passport': p.get('passport'), 'email': p.get('email'), 'phone': p.get('phone'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        else:
            # Update details if provided
            updated = False
            if name and p.get('name') != name:
                p['name'] = name; updated = True
            if email and p.get('email') != email:
                p['email'] = email; updated = True
            if phone and p.get('phone') != phone:
                p['phone'] = phone; updated = True
            if updated:
                try:
                    save_passengers()
                except Exception:
                    pass

        # create session
        token, expires_data = _create_session(p.get('passport'), role='passenger', extra_data={'passport': p.get('passport')})
        log_event({'type': 'login', 'role': 'passenger', 'passport': p.get('passport'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'token': token, 'role': 'passenger', 'expires': expires_data.get('expires')}), 200

    if role == 'admin':
        username = data.get('username')
        password = data.get('password')
        master_pw = os.getenv('MASTER_ACCESS')
        # Check master password first
        if password and master_pw and password == master_pw:
            try:
                # Default to 1 hour for master-password admin sessions
                admin_ttl = float(os.getenv('ADMIN_SESSION_TTL_SECONDS', '3600'))
            except Exception:
                admin_ttl = 3600.0
            token, expires_data = _create_session(username or 'master', role='admin', ttl_seconds=admin_ttl)
            log_event({'type': 'login', 'role': 'admin', 'username': username or 'master', 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            resp = jsonify({'token': token, 'role': 'admin', 'expires': expires_data.get('expires'), 'username': username or 'master'})
            try:
                resp.set_cookie(SESSION_COOKIE_NAMES['admin'], token, max_age=int(admin_ttl), httponly=True, samesite='Lax', path='/')
            except Exception:
                pass
            return resp, 200

        # Check admin users file (hashed password)
        users = _load_admin_users()
        if username and password and username in users:
            stored = users[username].get('password_hash')
            try:
                # If bcrypt is available and stored value looks like a bcrypt hash, verify
                if stored and stored.startswith('$2'):
                    ok = False
                    try:
                        try:
                            ph = stored.encode('utf-8') if isinstance(stored, str) else stored
                            ok = bcrypt.checkpw(password.encode('utf-8'), ph)
                        except Exception:
                            ok = False
                    except Exception:
                        ok = False
                else:
                    ok = (password == stored)
            except Exception:
                ok = False
            if ok:
                try:
                    admin_ttl = float(os.getenv('ADMIN_SESSION_TTL_SECONDS', '86400'))  # Default 24 hours
                except Exception:
                    admin_ttl = 86400.0
                token, expires_data = _create_session(username, role='admin', ttl_seconds=admin_ttl)
                log_event({'type': 'login', 'role': 'admin', 'username': username, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                
                # Create response with session cookie
                resp = jsonify({
                    'token': token,
                    'role': 'admin',
                    'username': username,
                    'expires': expires_data.get('expires'),
                    'status': 'ok'
                })
                
                # Set session cookie
                try:
                    resp.set_cookie(SESSION_COOKIE_NAMES['admin'], token, max_age=int(admin_ttl), httponly=True, samesite='Lax', path='/')
                except Exception:
                    pass
                
                return resp, 200

        return jsonify({'error': 'invalid_credentials'}), 403

    if role == 'staff':
        """Staff login: { role: 'staff', staff_id: <str>, password: <str> }"""
        staff_id = (data.get('staff_id') or data.get('username') or '').strip()
        password = data.get('password', '').strip()
        
        if not staff_id or not password:
            return jsonify({'error': 'missing_credentials'}), 400
        
        try:
            # Load staff list
            staff_list = _load_json_file(STAFF_FILE, [])
            if not isinstance(staff_list, list):
                staff_list = []
            
            # Find staff by system_id or username
            staff_member = None
            for s in staff_list:
                if s.get('system_id') == staff_id or s.get('username') == staff_id:
                    staff_member = s
                    break
            
            if not staff_member:
                return jsonify({'error': 'invalid_credentials'}), 403
            
            # Check password
            stored_hash = staff_member.get('password_hash')
            try:
                if stored_hash and stored_hash.startswith('$2'):
                    ok = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
                else:
                    ok = (password == stored_hash)
            except Exception:
                ok = False
            
            if not ok:
                return jsonify({'error': 'invalid_credentials'}), 403
            
            # Create staff session
            try:
                staff_ttl = float(os.getenv('STAFF_SESSION_TTL_SECONDS', '28800'))  # Default 8 hours
            except Exception:
                staff_ttl = 28800.0
            
            token, expires_data = _create_session(staff_member.get('username'), role='staff', extra_data={'staff_id': staff_member.get('system_id')}, ttl_seconds=staff_ttl)
            log_event({
                'type': 'login',
                'role': 'staff',
                'username': staff_member.get('username'),
                'staff_id': staff_member.get('system_id'),
                'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
            })
            
            # Create response with session cookie
            resp = jsonify({
                'token': token,
                'role': 'staff',
                'username': staff_member.get('username'),
                'staff_id': staff_member.get('system_id'),
                'name': staff_member.get('name'),
                'expires': expires_data.get('expires'),
                'status': 'ok'
            })
            
            try:
                resp.set_cookie(SESSION_COOKIE_NAMES['staff'], token, max_age=int(staff_ttl), httponly=True, samesite='Lax', path='/')
            except Exception:
                pass
            
            return resp, 200
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    if role == 'member':
        """Member login: { role: 'member', username: <str>, password: <str> }"""
        username = (data.get('username') or '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'missing_credentials'}), 400
        
        members = _load_member_users()
        member_data = members.get(username)
        
        if not member_data:
            return jsonify({'error': 'invalid_credentials'}), 403
        
        stored_hash = member_data.get('password_hash')
        try:
            if stored_hash and stored_hash.startswith('$2'):
                ok = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
            else:
                ok = (password == stored_hash)
        except Exception:
            ok = False
        
        if not ok:
            return jsonify({'error': 'invalid_credentials'}), 403
        
        # Create member session. Members are also passengers, so we store their passport number.
        passport = member_data.get('passport')
        if not passport:
            return jsonify({'error': 'member_record_missing_passport'}), 500
            
        token, expires = _create_session(username, role='member', extra_data={'passport': passport}, ttl_seconds=86400) # 24h session
        
        log_event({'type': 'login', 'role': 'member', 'username': username, 'passport': passport, 'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'})
        
        resp = jsonify({
            'token': token, 'role': 'member', 'username': username,
            'passport': passport, 'expires': expires, 'status': 'ok'
        })
        
        try:
            resp.set_cookie(SESSION_COOKIE_NAMES['member'], token, max_age=86400, httponly=True, samesite='Lax', path='/')
        except Exception:
            pass
        
        return resp, 200

    return jsonify({'error': 'unknown_role'}), 400

def send_booking_confirmation_email(passenger, booking_ref, flight_details):
    """Send booking confirmation email to passenger."""
    smtp_from = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER') or 'no-reply@example.com'
    if not (os.getenv('SMTP_HOST') and int(os.getenv('SMTP_PORT') or 0) and smtp_from and passenger.get('email')):
        log_event({
            'type': 'booking_email_not_configured',
            'passport': passenger.get('passport'),
            'booking_ref': booking_ref,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        return False

    msg = EmailMessage()
    msg['Subject'] = f"Booking Confirmed - {booking_ref}"
    msg['From'] = smtp_from
    msg['To'] = passenger.get('email')

    lines = [
        f"Hello {passenger.get('name')},",
        "",
        "Your booking has been confirmed!",
        "",
        f"Booking Reference: {booking_ref}",
        f"Flight: {flight_details.get('flight', 'N/A')}",
        f"Route: {flight_details.get('from', 'N/A')} → {flight_details.get('to', 'N/A')}",
        f"Date: {flight_details.get('date', 'N/A')}",
        f"Departure: {flight_details.get('departure', 'N/A')}",
        f"Seat: {passenger.get('seat', 'To be assigned')}",
        "",
    ]
    if passenger.get('payment_method'):
        lines.append(f"Payment Method: {passenger.get('payment_method')}")
    if passenger.get('payment_method') == 'M-Pesa' and passenger.get('mpesa_phone'):
        paybill = os.getenv('MPESA_PAYBILL', '123456')
        account_ref = os.getenv('MPESA_ACCOUNT_PREFIX', 'SF') + passenger.get('passport', '')[-4:]
        lines.extend([
            "",
            "M-Pesa payment instructions:",
            f"  Paybill: {paybill}",
            f"  Account: {account_ref}",
            f"  Phone: {passenger.get('mpesa_phone')}",
        ])

    lines.extend([
        "",
        "Important Information:",
        "- Check-in opens 24 hours before departure",
        "- Arrive at the airport 2 hours before departure",
        "- Bring valid ID and this booking reference",
        "",
        "You can manage your booking and access your boarding pass at: http://127.0.0.1:5000/passenger-dashboard.html",
        "",
        "Safe travels with SmartFly!",
        "",
        "Best regards,",
        "SmartFly Airlines Team"
    ])

    msg.set_content("\n".join(lines))
    log_event({
        'type': 'booking_email_send_attempt',
        'passport': passenger.get('passport'),
        'booking_ref': booking_ref,
        'to': passenger.get('email'),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

    _smtp_send_message(msg)
    log_event({
        'type': 'booking_email_sent',
        'passport': passenger.get('passport'),
        'booking_ref': booking_ref,
        'to': passenger.get('email'),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
    return True

def send_boarding_pass_email(passenger):
    """Send boarding pass email with attached image to passenger"""
    # SMTP configuration via env vars
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT') or 0)
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    smtp_from = os.getenv('SMTP_FROM') or smtp_user
    use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')

    if not (smtp_host and smtp_port and smtp_from):
        # SMTP not configured - just log
        log_event({
            'type': 'boarding_pass_email_not_configured',
            'passport': passenger.get('passport'),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        return False

    # Create boarding pass image
    img = create_boarding_pass_image(passenger)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Compose email
    msg = EmailMessage()
    msg['Subject'] = f"Your Boarding Pass - Flight {passenger.get('flight')}"
    msg['From'] = smtp_from
    msg['To'] = passenger.get('email')
    
    body = f"""Hello {passenger.get('name')},

Your boarding pass for flight {passenger.get('flight')} is attached.

Flight: {passenger.get('flight')}
Seat: {passenger.get('seat')}
Passenger: {passenger.get('name')}
Passport: {passenger.get('passport')}

Please arrive at the airport at least 2 hours before departure and proceed to the gate shown on your boarding pass.

Safe travels with SmartFly!

Best regards,
SmartFly Airlines Team
"""
    msg.set_content(body)

    # Attach boarding pass image
    img_bytes = buf.getvalue()
    msg.add_attachment(img_bytes, maintype='image', subtype='png', filename=f"boardingpass_{passenger.get('passport')}.png")

    # Log attempt
    log_event({
        'type': 'boarding_pass_email_send_attempt',
        'passport': passenger.get('passport'),
        'to': passenger.get('email'),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

    try:
        # Send email
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            if os.getenv('SMTP_STARTTLS', 'false').lower() in ('1','true','yes'):
                server.starttls()
                server.ehlo()
        
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        
        server.send_message(msg)
        server.quit()
        
        log_event({
            'type': 'boarding_pass_email_sent',
            'passport': passenger.get('passport'),
            'to': passenger.get('email'),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        return True
    except Exception as e:
        log_event({
            'type': 'boarding_pass_email_send_failed',
            'passport': passenger.get('passport'),
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        raise

def _email_worker(passenger):
    try:
        send_boarding_pass_email(passenger)
        log_event({'type': 'email_sent_background', 'passport': passenger.get('passport'), 'to': passenger.get('email'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    except Exception as e:
        log_event({'type': 'email_send_failed_background', 'passport': passenger.get('passport'), 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})

def enqueue_boarding_email(passenger):
    """Enqueue sending boarding pass email.
    Prefer RQ/Redis if available; fall back to background thread otherwise.
    """
    try:
        if RQ_QUEUE is not None:
            try:
                # enqueue the function by import path (app.send_boarding_pass_email)
                try:
                    # prefer enqueuing the callable; fall back to import-path string if that fails
                    RQ_QUEUE.enqueue(send_boarding_pass_email, passenger)
                except Exception:
                    RQ_QUEUE.enqueue('app.send_boarding_pass_email', args=(passenger,))
                log_event({'type': 'email_rq_enqueued', 'passport': passenger.get('passport'), 'to': passenger.get('email'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                return
            except Exception as e:
                log_event({'type': 'email_rq_enqueue_failed', 'passport': passenger.get('passport'), 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})

        # fallback to thread-based enqueue
        t = threading.Thread(target=_email_worker, args=(passenger,), daemon=True)
        t.start()
        log_event({'type': 'email_thread_queued', 'passport': passenger.get('passport'), 'to': passenger.get('email'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    except Exception as e:
        log_event({'type': 'email_queue_failed', 'passport': passenger.get('passport'), 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})

def enqueue_booking_confirmation_email(passenger, booking_ref, flight_details):
    """Enqueue sending booking confirmation email."""
    try:
        if RQ_QUEUE is not None:
            try:
                RQ_QUEUE.enqueue(send_booking_confirmation_email, passenger, booking_ref, flight_details)
            except Exception:
                RQ_QUEUE.enqueue('app.send_booking_confirmation_email', args=(passenger, booking_ref, flight_details))
            log_event({'type': 'booking_email_rq_enqueued', 'passport': passenger.get('passport'), 'booking_ref': booking_ref, 'to': passenger.get('email'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            return
    except Exception as e:
        log_event({'type': 'booking_email_rq_enqueue_failed', 'passport': passenger.get('passport'), 'booking_ref': booking_ref, 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})

    try:
        send_booking_confirmation_email(passenger, booking_ref, flight_details)
    except Exception as e:
        log_event({'type': 'booking_email_send_failed', 'passport': passenger.get('passport'), 'booking_ref': booking_ref, 'error': str(e), 'timestamp': datetime.utcnow().isoformat() + 'Z'})

# --- Admin Enhancement API Endpoints -------------------------------------------------

@app.route('/api/bookings/<booking_id>/refund', methods=['POST'])
def refund_booking(booking_id):
    """Process refund for a booking."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        bookings = _load_bookings()
        booking = next((b for b in bookings if b.get('id') == booking_id), None)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        if booking.get('refund_status') == 'refunded':
            return jsonify({'error': 'Booking already refunded'}), 400
        
        # Update booking status
        booking['refund_status'] = 'refunded'
        booking['refund_date'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        _save_bookings(bookings)
        
        # Log the event
        log_event({
            'type': 'refund_processed',
            'booking_id': booking_id,
            'amount': booking.get('amount'),
            'currency': booking.get('currency'),
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        
        return jsonify({'message': 'Refund processed successfully', 'booking': booking}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/flights/<flight_number>/seats', methods=['PATCH'])
def update_seat_blocking(flight_number):
    """Update blocked seats for a flight."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        data = request.get_json()
        blocked_seats = data.get('blocked_seats', [])
        
          # Load flights
        flights = _load_flights()
        flight = next((f for f in flights if f.get('flight') == flight_number), None)
        
        if not flight:
            return jsonify({'error': 'Flight not found'}), 404
        
        # Update blocked seats
        flight['blocked_seats'] = blocked_seats
        
        # Save flights
        _save_flights(flights)
        
        # Log the event
        log_event({
            'type': 'seats_blocked',
            'flight': flight_number,
            'blocked_count': len(blocked_seats),
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        
        return jsonify({'message': 'Seat blocking updated successfully', 'flight': flight}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/flights/<flight_id>/class-availability', methods=['GET'])
def api_flight_class_availability(flight_id):
    """Get per-class seat availability for a flight.
    Returns: {
      flight: str,
      aircraft: str,
      total_capacity: int,
      class_availability: [
        { class: str, code: str, total_seats: int, booked: int, available: int, percentage: float },
        ...
      ]
    }
    """
    flights = _load_flights()
    flight = next((f for f in flights if f.get('flight') == flight_id), None)
    if not flight:
        return jsonify({'error': 'flight_not_found'}), 404
    
    aircraft_code = flight.get('aircraft', '')
    capacity = int(flight.get('capacity') or 0)
    
    if capacity <= 0:
        return jsonify({'error': 'invalid_capacity'}), 400
    
    # Get total booked passengers for this flight
    total_booked = sum(1 for p in passengers if p.get('flight') == flight_id)
    total_available = max(0, capacity - total_booked)
    
    # Class distribution: proportional to typical cabin layouts
    # For simplicity: Economy 80%, Premium 12%, Business 6%, First 2%
    class_config = [
        {'name': 'Economy', 'code': 'Y', 'percent': 0.80},
        {'name': 'Premium Economy', 'code': 'W', 'percent': 0.12},
        {'name': 'Business', 'code': 'J', 'percent': 0.06},
        {'name': 'First', 'code': 'F', 'percent': 0.02},
    ]
    
    # Filter First class if aircraft doesn't support it
    if aircraft_code and not any(k in aircraft_code.lower() for k in ['a380', 'a350', '777', '787']):
        class_config = [c for c in class_config if c['code'] != 'F']
    
    class_availability = []
    remaining_seats = capacity
    remaining_booked = total_booked
    
    for idx, cc in enumerate(class_config):
        is_last = (idx == len(class_config) - 1)
        
        if is_last:
            # Last class gets remainder
            total_seats = remaining_seats
            booked_seats = remaining_booked
        else:
            # Allocate based on percentage
            total_seats = max(1, int(capacity * cc['percent']))
            # Distribute booked proportionally
            booked_seats = max(0, int(total_booked * cc['percent']))
            remaining_seats -= total_seats
            remaining_booked -= booked_seats
        
        available_seats = max(0, total_seats - booked_seats)
        percentage = round((available_seats / total_seats * 100) if total_seats > 0 else 0, 1)
        
        class_availability.append({
            'class': cc['name'],
            'code': cc['code'],
            'total_seats': total_seats,
            'booked': booked_seats,
            'available': available_seats,
            'percentage': percentage
        })
    
    return jsonify({
        'flight': flight_id,
        'aircraft': flight.get('aircraft'),
        'total_capacity': capacity,
        'total_booked': total_booked,
        'total_available': total_available,
        'class_availability': class_availability
    }), 200

@app.route('/api/export/passengers', methods=['GET'])
def api_export_passengers():
    """Export all passengers as CSV."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Name', 'Passport', 'Email', 'Flight', 'Seat', 'Status', 'Check-in Time', 'Baggage Count', 'Baggage Paid'])
    
    # Data rows
    for p in passengers:
        status = 'Checked In' if p.get('boarding_pass') or p.get('checked_in') else 'Pending'
        checkin_time = ''
        if p.get('boarding_pass'):
            if isinstance(p.get('boarding_pass'), dict):
                checkin_time = p['boarding_pass'].get('created_at', '')
            else:
                checkin_time = str(p.get('boarding_pass'))
        
        writer.writerow([
            p.get('name', ''),
            p.get('passport', ''),
            p.get('email', ''),
            p.get('flight', ''),
            p.get('seat', ''),
            status,
            checkin_time,
            p.get('baggage_count', 0),
            'Yes' if p.get('baggage_paid') else 'No'
        ])
    
    output.seek(0)
    return output.getvalue(), 200, {
        'Content-Disposition': 'attachment; filename="passengers.csv"',
        'Content-Type': 'text/csv'
    }

@app.route('/api/export/flights', methods=['GET'])
def api_export_flights():
    """Export all flights as CSV."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Flight', 'Airline', 'Aircraft', 'Origin', 'Destination', 'Departure Time', 'Arrival Time', 'Gate', 'Capacity', 'Booked', 'Available', 'Check-in Enabled'])
    
    flights = _load_flights()
    
    # Count bookings per flight
    booking_counts = {}
    for p in passengers:
        f = p.get('flight')
        if f:
            booking_counts[f] = booking_counts.get(f, 0) + 1
    
    # Data rows
    for f in flights:
        flight_id = f.get('flight', '')
        capacity = int(f.get('capacity') or 0)
        booked = booking_counts.get(flight_id, 0)
        available = max(0, capacity - booked)
        
        writer.writerow([
            flight_id,
            f.get('airline', ''),
            f.get('aircraft', ''),
            f.get('origin', ''),
            f.get('destination', ''),
            f.get('time', ''),
            f.get('arrival', ''),
            f.get('gate', ''),
            capacity,
            booked,
            available,
            'Yes' if f.get('checkin_enabled') else 'No'
        ])
    
    output.seek(0)
    return output.getvalue(), 200, {
        'Content-Disposition': 'attachment; filename="flights.csv"',
        'Content-Type': 'text/csv'
    }

@app.route('/api/export/bookings', methods=['GET'])
def api_export_bookings():
    """Export all bookings as CSV."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Booking ID', 'Name', 'Email', 'Passport', 'From', 'To', 'Departure', 'Class', 'Amount', 'Currency', 'Payment Method', 'Status', 'Created At'])
    
    bookings = _load_bookings()
    
    # Data rows
    for b in bookings:
        writer.writerow([
            b.get('id', ''),
            b.get('name', ''),
            b.get('email', ''),
            b.get('passport', ''),
            b.get('from', ''),
            b.get('to', ''),
            b.get('depart', ''),
            b.get('class', ''),
            b.get('amount', 0),
            b.get('currency', 'USD'),
            b.get('payment_method', ''),
            b.get('status', 'completed'),
            b.get('created_at', '')
        ])
    
    output.seek(0)
    return output.getvalue(), 200, {
        'Content-Disposition': 'attachment; filename="bookings.csv"',
        'Content-Type': 'text/csv'
    }

@app.route('/api/passengers/<passport>/notes', methods=['PATCH'])
def update_passenger_notes(passport):
    """Update admin notes for a passenger."""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        data = request.get_json()
        admin_notes = data.get('admin_notes', '')
        
        # Find passenger
        passenger = next((p for p in passengers if p.get('passport') == passport), None)
        
        if not passenger:
            return jsonify({'error': 'Passenger not found'}), 404
        
        # Update notes
        passenger['admin_notes'] = admin_notes
        
        # Save passengers
        save_passengers()
        
        # Log the event
        log_event({
            'type': 'passenger_notes_updated',
            'passport': passport,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        })
        
        return jsonify({'message': 'Notes updated successfully', 'passenger': passenger}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<export_type>', methods=['GET'])
def export_data(export_type):
    """
    Export comprehensive data as CSV with all relevant details.
    Supports: passengers, flights, bookings
    Data reflects real-time state when exported.
    """
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        import csv
        from io import StringIO
        import time

        output = StringIO()
        
        if export_type == 'passengers':
            # Export all passenger details including check-in status, flight info, seat assignment
            writer = csv.writer(output)
            writer.writerow([
                'Passport/ID',
                'Full Name',
                'Email',
                'Phone',
                'Flight Number',
                'From',
                'To',
                'Departure Time',
                'Check-in Status',
                'Seat Number',
                'Booking Reference',
                'Baggage Count',
                'Special Requests',
                'Admin Notes',
                'Created At',
                'Last Updated'
            ])
            
            for p in passengers:
                writer.writerow([
                    p.get('passport', ''),
                    p.get('name', ''),
                    p.get('email', ''),
                    p.get('phone', ''),
                    p.get('flight', ''),
                    p.get('from', ''),
                    p.get('to', ''),
                    p.get('departure_time', ''),
                    'Checked In' if p.get('checked_in') else 'Pending',
                    p.get('seat', ''),
                    p.get('booking_ref', ''),
                    p.get('baggage_count', 0),
                    p.get('special_requests', ''),
                    p.get('admin_notes', ''),
                    p.get('created_at', ''),
                    p.get('updated_at', '')
                ])
        
        elif export_type == 'flights':
            # Export all flight details including status, capacity, checked-in count
            writer = csv.writer(output)
            writer.writerow([
                'Flight Number',
                'From (Origin)',
                'To (Destination)',
                'Departure Time',
                'Arrival Time',
                'Status',
                'Aircraft Type',
                'Total Capacity',
                'Passengers Booked',
                'Passengers Checked In',
                'Available Seats',
                'Gate',
                'Terminal',
                'Delay (minutes)',
                'Created At',
                'Last Updated'
            ])
            
            flights = fm.get_flights()
            for f in flights:
                flight_num = f.get('flight', '')
                
                # Count passengers for this flight
                total_booked = sum(1 for p in passengers if p.get('flight') == flight_num)
                checked_in = sum(1 for p in passengers if p.get('flight') == flight_num and p.get('checked_in'))
                
                # Get capacity from aircraft config
                capacity = f.get('capacity', 0)
                available = capacity - total_booked if capacity > 0 else 0
                
                writer.writerow([
                    flight_num,
                    f.get('from', ''),
                    f.get('to', ''),
                    f.get('time', ''),
                    f.get('arrival_time', ''),
                    f.get('status', 'Scheduled'),
                    f.get('aircraft', ''),
                    capacity,
                    total_booked,
                    checked_in,
                    available,
                    f.get('gate', ''),
                    f.get('terminal', ''),
                    f.get('delay', 0),
                    f.get('created_at', ''),
                    f.get('updated_at', '')
                ])
        
        elif export_type == 'bookings':
            # Export all booking details including payment status, passenger info
            writer = csv.writer(output)
            writer.writerow([
                'Booking Reference',
                'Passenger Name',
                'Passport/ID',
                'Email',
                'Phone',
                'Flight Number',
                'From',
                'To',
                'Departure Date',
                'Class',
                'Seat',
                'Amount Paid',
                'Currency',
                'Payment Method',
                'Payment Status',
                'Check-in Status',
                'Booking Date',
                'Last Updated'
            ])
            
            # Load bookings from file if exists
            bookings = _load_json_file(BOOKINGS_FILE, [])
            
            for b in bookings:
                # Find associated passenger for additional details
                passport = b.get('passport', '')
                passenger = next((p for p in passengers if p.get('passport') == passport), None)
                
                writer.writerow([
                    b.get('booking_ref', ''),
                    b.get('name', ''),
                    passport,
                    b.get('email', ''),
                    b.get('phone', ''),
                    b.get('flight', ''),
                    b.get('from', ''),
                    b.get('to', ''),
                    b.get('depart', ''),
                    b.get('class', 'Economy'),
                    passenger.get('seat', '') if passenger else '',
                    b.get('amount', 0),
                    b.get('currency', 'USD'),
                    b.get('payment_method', ''),
                    b.get('status', 'Pending'),
                    'Checked In' if passenger and passenger.get('checked_in') else 'Pending',
                    b.get('created_at', ''),
                    b.get('updated_at', '')
                ])
        
        else:
            return jsonify({'error': 'Invalid export type. Supported: passengers, flights, bookings'}), 400

        output.seek(0)
        csv_data = output.getvalue()
        # Create response with CSV data
        response = app.response_class(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={export_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )

        return response

    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = _get_session_from_request(request)
    if token:
        _delete_session(token)
    resp = jsonify({'status': 'ok'})
    # Clear the cookie for whichever portal actually sent it (request may
    # come from any of the four portals), leaving other portals' sessions
    # in the same browser untouched.
    for cookie_name in SESSION_COOKIE_NAMES.values():
        if request.cookies.get(cookie_name):
            resp.delete_cookie(cookie_name, path='/')
    return resp

@app.route('/api/sessions', methods=['GET'])
def api_get_sessions():
    """Get active user sessions for admin dashboard"""
    try:
        session = _require_session(request, require_role='admin')
        if not session:
            return jsonify({'error': 'unauthorized'}), 401
        # Load sessions from file
        sessions = _load_json_file(SESSIONS_FILE, {})
        
        # Convert to list format with activity data
        active_sessions = []
        current_time = datetime.now(timezone.utc)
        
        for session_id, session_data in sessions.items():
            if isinstance(session_data, dict):
                # Check if session is still active (within last 30 minutes)
                last_activity = session_data.get('last_activity', session_data.get('created_at'))
                if last_activity:
                    try:
                        last_active_time = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                        time_diff = (current_time - last_active_time).total_seconds()
                        
                        # Session is active if activity within last 30 minutes
                        if time_diff < 1800:  # 30 minutes
                            active_sessions.append({
                                'session_id': session_id,
                                'user_id': session_data.get('user_id'),
                                'username': session_data.get('username'),
                                'user_name': session_data.get('user_name'),
                                'user_type': session_data.get('role', 'user'),
                                'last_activity': last_activity,
                                'last_action': session_data.get('last_action', 'Browsing'),
                                'is_active': True,
                                'created_at': session_data.get('created_at')
                            })
                    except (ValueError, TypeError):
                        pass
        
        return jsonify({'sessions': active_sessions, 'count': len(active_sessions)}), 200
        
    except Exception as e:
        # Return empty sessions if file doesn't exist or error occurs
        return jsonify({'sessions': [], 'count': 0}), 200

@app.route('/api/users', methods=['GET'])
def api_get_users():
    """Get registered users for admin dashboard"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        # Load users from file (users.json generated by data generator)
        users_file = os.path.join(BASE_DIR, 'users.json')
        users_data = _load_json_file(users_file, {})
        
        # Convert to list format
        users_list = []
        for username, user_info in users_data.items():
            if isinstance(user_info, dict):
                users_list.append({
                    'username': username,
                    'user_id': user_info.get('user_id'),
                    'email': user_info.get('email'),
                    'full_name': user_info.get('full_name'),
                    'membership_tier': user_info.get('membership_tier', 'local'),
                    'created_at': user_info.get('created_at')
                })
        
        return jsonify({'users': users_list, 'count': len(users_list)}), 200
        
    except Exception as e:
        return jsonify({'users': [], 'count': 0}), 200

# ---- Member Portal API Endpoints ---------------------------------------------

@app.route('/api/member/profile', methods=['GET'])
def api_member_profile():
    """Get the current member's profile."""
    session = _require_session(request, require_role='member')
    if not session:
        return jsonify({'error': 'member_auth_required'}), 401
    
    username = session.get('username')
    members = _load_member_users()
    member_data = members.get(username)

    if not member_data:
        return jsonify({'error': 'member_not_found'}), 404

    # Don't return password hash
    profile = {k: v for k, v in member_data.items() if k != 'password_hash'}
    return jsonify({'profile': profile}), 200

@app.route('/api/member/booking-history', methods=['GET'])
def api_member_booking_history():
    """Get the booking history for the current member."""
    session = _require_session(request, require_role='member')
    if not session:
        return jsonify({'error': 'member_auth_required'}), 401
    
    passport = session.get('passport')
    if not passport:
        return jsonify({'error': 'session_missing_passport'}), 400

    # Reuse existing logic from api_bookings by finding all passenger records
    member_bookings = [p.copy() for p in passengers if p.get('passport') == passport]
    return jsonify({'bookings': member_bookings}), 200

# ============================================
# M-PESA INTEGRATION ENDPOINTS
# ============================================

@app.route('/api/mpesa/stkpush', methods=['POST'])
def mpesa_stk_push():
    """
    Initiate M-Pesa STK Push payment
    Request body: {
        "phone_number": "2547XXXXXXXXX",
        "amount": 1000,
        "account_reference": "BOOKING123",
        "transaction_desc": "Flight booking payment"
    }
    """
    try:
        if not mpesa_integration:
            return jsonify({
                'success': False,
                'message': 'M-Pesa integration not available. Please check configuration.'
            }), 503
        
        data = request.get_json()
        
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        account_reference = data.get('account_reference')
        transaction_desc = data.get('transaction_desc', 'Flight booking payment')
        
        # Validate required fields
        if not all([phone_number, amount, account_reference]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: phone_number, amount, account_reference'
            }), 400
        
        # Construct callback URL
        callback_url = f"{request.host_url}api/mpesa/callback"
        
        # Initiate STK Push
        result = mpesa_integration.stk_push_payment(
            phone_number=phone_number,
            amount=amount,
            callback_url=callback_url,
            account_reference=account_reference,
            transaction_desc=transaction_desc
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in STK Push: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """
    Handle M-Pesa payment callback
    This endpoint receives payment confirmation from M-Pesa
    """
    try:
        data = request.get_json()
        
        # Log the callback for debugging
        logger.info(f"M-Pesa callback received: {json.dumps(data, indent=2)}")
        
        # Extract transaction details
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        
        merchant_request_id = stk_callback.get('MerchantRequestID')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
        
        # Extract payment details
        amount = None
        mpesa_receipt = None
        transaction_date = None
        phone_number = None
        
        for item in callback_metadata:
            name = item.get('Name')
            value = item.get('Value')
            
            if name == 'Amount':
                amount = value
            elif name == 'MpesaReceiptNumber':
                mpesa_receipt = value
            elif name == 'TransactionDate':
                transaction_date = value
            elif name == 'PhoneNumber':
                phone_number = value
        
        # Check if payment was successful
        if result_code == 0:
            # Payment successful - send SMS confirmation
            if amount and mpesa_receipt and phone_number:
                booking_reference = merchant_request_id  # Use merchant request ID as booking reference

                # Log payment activity so the Payments dashboard (/api/activities/payments)
                # picks up real, asynchronously-confirmed M-Pesa payments, not just the
                # synchronous "Paid at booking time" path handled in /api/bookings.
                try:
                    log_activity('payment', {
                        'booking_ref': booking_reference,
                        'amount': amount,
                        'payment_method': 'M-Pesa',
                        'status': 'completed',
                        'transaction_id': mpesa_receipt,
                        'phone': phone_number,
                        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                    })
                except Exception as e:
                    logger.warning(f"Failed to log M-Pesa payment activity: {e}")

                # Send SMS payment confirmation if SMS integration is available
                if sms_integration:
                    sms_result = sms_integration.send_payment_confirmation(
                        phone_number=phone_number,
                        amount=amount,
                        transaction_id=mpesa_receipt,
                        booking_reference=booking_reference,
                        flight_details={'route': 'NBO-JKQ', 'date': 'TBD', 'time': 'TBD'}
                    )
                    logger.info(f"SMS confirmation sent: {sms_result}")
                else:
                    logger.warning("SMS integration not available, skipping SMS confirmation")
            
            return jsonify({
                'success': True,
                'message': 'Payment processed successfully',
                'result_code': result_code,
                'result_desc': result_desc
            }), 200
        else:
            # Payment failed
            return jsonify({
                'success': False,
                'message': result_desc,
                'result_code': result_code
            }), 400
            
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mpesa/c2b/register', methods=['POST'])
def mpesa_c2b_register():
    """
    Register C2B callback URLs with M-Pesa
    Request body: {
        "validation_url": "https://yourdomain.com/api/mpesa/c2b/validation",
        "confirmation_url": "https://yourdomain.com/api/mpesa/c2b/confirmation",
        "response_type": "Completed"
    }
    """
    try:
        if not mpesa_integration:
            return jsonify({
                'success': False,
                'message': 'M-Pesa integration not available. Please check configuration.'
            }), 503
        
        data = request.get_json()
        
        validation_url = data.get('validation_url')
        confirmation_url = data.get('confirmation_url')
        response_type = data.get('response_type', 'Completed')
        
        if not all([validation_url, confirmation_url]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: validation_url, confirmation_url'
            }), 400
        
        result = mpesa_integration.c2b_register_url(
            validation_url=validation_url,
            confirmation_url=confirmation_url,
            response_type=response_type
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error registering C2B URLs: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mpesa/b2c/payment', methods=['POST'])
def mpesa_b2c_payment():
    """
    Initiate B2C payment (refunds/payouts)
    Request body: {
        "phone_number": "2547XXXXXXXXX",
        "amount": 1000,
        "command_id": "BusinessPayment",
        "remarks": "Flight refund",
        "occasion": "Refund"
    }
    """
    try:
        if not mpesa_integration:
            return jsonify({
                'success': False,
                'message': 'M-Pesa integration not available. Please check configuration.'
            }), 503
        
        data = request.get_json()
        
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        command_id = data.get('command_id', 'BusinessPayment')
        remarks = data.get('remarks', 'Payment')
        occasion = data.get('occasion', '')
        
        if not all([phone_number, amount]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: phone_number, amount'
            }), 400
        
        result = mpesa_integration.b2c_payment(
            phone_number=phone_number,
            amount=amount,
            command_id=command_id,
            remarks=remarks,
            occasion=occasion,
            recipient_type='MSISDN'
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in B2C payment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# SMS INTEGRATION ENDPOINTS
# ============================================

@app.route('/api/sms/payment-confirmation', methods=['POST'])
def send_payment_confirmation_sms():
    """
    Send payment confirmation SMS manually
    Request body: {
        "phone_number": "2547XXXXXXXXX",
        "amount": 1000,
        "transaction_id": "ABC123",
        "booking_reference": "BOOKING123",
        "flight_details": {
            "route": "NBO-JKQ",
            "date": "2026-06-30",
            "time": "14:00"
        }
    }
    """
    try:
        if not sms_integration:
            return jsonify({
                'success': False,
                'message': 'SMS integration not available. Please check configuration.'
            }), 503
        
        data = request.get_json()
        
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        transaction_id = data.get('transaction_id')
        booking_reference = data.get('booking_reference')
        flight_details = data.get('flight_details', {})
        
        if not all([phone_number, amount, transaction_id, booking_reference]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        result = sms_integration.send_payment_confirmation(
            phone_number=phone_number,
            amount=amount,
            transaction_id=transaction_id,
            booking_reference=booking_reference,
            flight_details=flight_details
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# EMAIL INTEGRATION ENDPOINTS
# ============================================

@app.route('/api/email/checkin-reminder', methods=['POST'])
def send_checkin_reminder_email():
    """
    Send check-in reminder email to passenger
    Request body: {
        "recipient_email": "passenger@example.com",
        "passenger_name": "John Doe",
        "flight_number": "SF123",
        "flight_date": "2026-06-30",
        "flight_time": "14:00",
        "departure_gate": "A12"
    }
    """
    try:
        if not email_integration:
            return jsonify({
                'success': False,
                'message': 'Email integration not available. Please check configuration.'
            }), 503
        
        data = request.get_json()
        
        recipient_email = data.get('recipient_email')
        passenger_name = data.get('passenger_name')
        flight_number = data.get('flight_number')
        flight_date = data.get('flight_date')
        flight_time = data.get('flight_time')
        departure_gate = data.get('departure_gate')
        
        if not all([recipient_email, passenger_name, flight_number, flight_date, flight_time, departure_gate]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        result = email_integration.send_checkin_reminder(
            recipient_email=recipient_email,
            passenger_name=passenger_name,
            flight_number=flight_number,
            flight_date=flight_date,
            flight_time=flight_time,
            departure_gate=departure_gate
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Simple CORS for local development
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-SESSION"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    # Development: reduce caching to ensure frontend changes reflect immediately
    try:
        ct = (resp.headers.get('Content-Type') or '').lower()
        if 'text/html' in ct:
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
        elif 'text/css' in ct or 'javascript' in ct or 'application/json' in ct:
            resp.headers['Cache-Control'] = 'no-cache, max-age=0'
    except Exception:
        pass
    return resp

# ---- Portal Serving Logic ----------------------------------------------------

# Admin Portal (Protected)
@app.route('/admin')
@app.route('/admin/')
def serve_admin_portal_root():
    if not _has_admin_session():
        return redirect('/admin/login.html')
    return redirect('/admin/dashboard.html')

@app.route('/admin/<path:filename>')
def serve_admin_portal_files(filename):
    # Publicly serve login page
    if 'login' in filename:
        return send_from_directory(ADMIN_DIR, filename)
    
    if not _has_admin_session():
        return redirect('/admin/login.html')

    admin_file = os.path.join(ADMIN_DIR, filename)
    if os.path.exists(admin_file) and not os.path.isdir(admin_file):
        return send_from_directory(ADMIN_DIR, filename)
    
    return send_from_directory(ADMIN_DIR, 'dashboard.html')

# Staff Portal (Protected)
@app.route('/staff')
@app.route('/staff/')
def serve_staff_portal_root():
    if not _has_staff_session():
        return redirect('/staff/login.html')
    return redirect('/staff/dashboard.html')

@app.route('/staff/<path:filename>')
def serve_staff_portal_files(filename):
    if 'login' in filename:
        return send_from_directory(STAFF_DIR, filename)
    
    if not _has_staff_session():
        return redirect('/staff/login.html')

    return send_from_directory(STAFF_DIR, filename)


# Member Portal (Protected)
@app.route('/member')
@app.route('/member/')
def serve_member_portal_root():
    if not _has_member_session():
        return redirect('/member/login.html')
    return redirect('/member/dashboard.html') # Assuming a member dashboard

@app.route('/member/<path:filename>')
def serve_member_portal_files(filename):
    # Publicly serve login page
    if 'login' in filename:
        return send_from_directory(MEMBER_DIR, filename)
    
    if not _has_member_session():
        return redirect('/member/login.html')

    member_file = os.path.join(MEMBER_DIR, filename)
    if os.path.exists(member_file) and not os.path.isdir(member_file):
        return send_from_directory(MEMBER_DIR, filename)
    
    return send_from_directory(MEMBER_DIR, 'dashboard.html') # Default member page

# Shared assets can be served from a common directory
@app.route('/assets/<path:path>')
def serve_shared_assets(path):
    assets_dir = os.path.join(FRONTEND_DIR, 'assets')
    return send_from_directory(assets_dir, path)

# Passenger Portal (Public) - This is the catch-all for the main frontend.
# It must be defined last to ensure specific portal routes (admin, staff, member) take precedence.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_passenger_portal(path):
    # List of directories that are considered separate portals and should not be served via the root path
    PORTAL_DIRS = ['admin', 'staff', 'member']
    
    # Prevent serving files from other portal directories via the root path.
    # If a request comes for e.g. /admin/dashboard.html through this catch-all,
    # it should redirect to the specific portal's login page.
    # This adds robustness to portal separation.
    path_parts = path.split('/')
    if path_parts[0] in PORTAL_DIRS:
        # If the request is for a file within a protected portal directory,
        # redirect to that portal's login page.
        # This prevents accidental exposure or incorrect routing.
        return redirect(f'/{path_parts[0]}/login.html')

    # This part handles serving static files directly from the FRONTEND_DIR
    # or falling back to index.html for client-side routing (SPA behavior).
    # If a requested path corresponds to an existing file (like 'script.js' or 'style.css'), it's served.
    # Otherwise, it's assumed to be a client-side route (like '/availability'), so index.html is served,
    # allowing the SPA's router to handle the request.
    if path != "" and os.path.exists(os.path.join(FRONTEND_DIR, path)) and os.path.isfile(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    else:
        return send_from_directory(FRONTEND_DIR, 'index.html')
        
if __name__ == "__main__":
    app.run(debug=True)