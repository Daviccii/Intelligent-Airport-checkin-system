# ...existing code...
from flask import Flask, request, jsonify, send_from_directory, redirect, send_file
from flask_cors import CORS
from security_utils import security_manager, sanitize_input, validate_passport, require_admin
import bcrypt
from flight_manager import FlightManager
from activity_tracker import log_activity, get_activities, get_bookings_log, get_checkins_log, get_payments_log
import json
import os
from dotenv import load_dotenv
import threading
from PIL import Image, ImageChops, ImageStat
import io
import random
from datetime import datetime, timedelta, timezone
import smtplib
from email.message import EmailMessage
import urllib.parse
import qrcode
import secrets

# Load environment variables from .env file
load_dotenv()

# Basic file/directory configuration (safe defaults)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))
ADMIN_DIR = os.path.join(FRONTEND_DIR, 'admin')
EVENTS_FILE = os.path.join(BASE_DIR, 'events.json')
PASSENGER_FILE = os.path.join(BASE_DIR, 'passengers.json')
SESSIONS_FILE = os.path.join(BASE_DIR, 'sessions.json')
ACCESS_CODES_FILE = os.path.join(BASE_DIR, 'access_codes.json')
ADMIN_USERS_FILE = os.path.join(BASE_DIR, 'admin_users.json')
HOLDS_FILE = os.path.join(BASE_DIR, 'holds.json')
OPENAPI_FILE = os.path.join(BASE_DIR, 'openapi.json')
BOOKINGS_FILE = os.path.join(BASE_DIR, 'bookings.json')
FLIGHTS_FILE = os.path.join(BASE_DIR, 'flights.json')
FACE_DIR = os.path.join(BASE_DIR, 'face_store')
SETTINGS_FILE = os.path.join(BASE_DIR, 'system_config.json')
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


# ---------------------------------------------------------------------------
# Helper: minimal admin session check for protected admin HTML pages.
# Accepts either the session cookie set by the frontend login flow or a Bearer
# token header, and only controls access to static admin HTML. API routes still
# rely on their own auth decorators.
def _has_admin_session():
    token = request.cookies.get('session') or request.headers.get('Authorization')
    if not token:
        cookie_header = request.headers.get('Cookie', '')
        for part in cookie_header.split(';'):
            if part.strip().startswith('session='):
                token = part.split('=', 1)[1]
                break
    return bool(token)

@app.route('/api/admin/settings', methods=['GET'])
def api_get_admin_settings():
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
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
        'notify_email': '',
        'maintenance_mode': False,
        'maintenance_message': '',
        'backup_frequency': 'daily'
    }
    if not isinstance(data, dict):
        data = {}
    merged = {**defaults, **data}
    return jsonify(merged), 200

@app.route('/api/admin/settings', methods=['POST'])
def api_save_admin_settings():
    sess = _require_session(request, require_role='admin')
    if not sess:
        return jsonify({'error': 'admin_auth_required'}), 401
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
            'backup_frequency'
        }
        clean = {k: payload.get(k) for k in allowed_keys if k in payload}
        existing = _load_json_file(SETTINGS_FILE, {})
        if not isinstance(existing, dict):
            existing = {}
        to_save = {**existing, **clean}
        _save_json_file(SETTINGS_FILE, to_save)
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Basic page routes for static frontend
@app.route('/')
def serve_root():
    return send_from_directory(FRONTEND_DIR, 'index.html')

# ---- Activities API (admin dashboard support) ---------------------------------------
@app.route('/api/activities', methods=['GET'])
def api_get_activities():
    """Return recent activities; optional filter by type via ?type=booking|payment|checkin"""
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
    try:
        items = get_bookings_log() or []
        return jsonify({'bookings': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/checkins', methods=['GET'])
def api_get_activities_checkins():
    try:
        items = get_checkins_log() or []
        return jsonify({'checkins': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/payments', methods=['GET'])
def api_get_activities_payments():
    try:
        items = get_payments_log() or []
        return jsonify({'payments': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities/log', methods=['POST'])
def api_log_activity():
    """Allow logging a new activity from the frontend (optional)."""
    try:
        payload = request.get_json(silent=True) or {}
        activity_type = payload.get('type')
        data = payload.get('data') or {}
        if not activity_type:
            return jsonify({'error': 'missing_type'}), 400
        item = log_activity(activity_type, data)
        if not item:
            return jsonify({'error': 'log_failed'}), 500
        return jsonify({'ok': True, 'activity': item}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---- Core Data Endpoints (flights, passengers, bookings) ---------------------------
@app.route('/api/flights', methods=['GET'])
def api_get_flights():
    """Return all flights from flights.json"""
    try:
        flights = _load_flights()
        # Enrich with booking counts
        booking_counts = {}
        for p in passengers:
            f = p.get('flight')
            if f:
                booking_counts[f] = booking_counts.get(f, 0) + 1
        
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
        
        return jsonify({'flights': flights}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/passengers', methods=['GET'])
def api_get_passengers():
    """Return all passengers"""
    try:
        return jsonify({'passengers': passengers}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bookings', methods=['GET'])
def api_get_bookings():
    """Return all bookings"""
    try:
        bookings = _load_bookings()
        return jsonify({'bookings': bookings}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/dashboard.html')
def serve_admin_dashboard():
    return send_from_directory(FRONTEND_DIR, 'admin-dashboard.html')


# ----------------------
# Session & Access Code helpers (file-backed)
# ----------------------

def _load_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except Exception:
        return default

def _save_json_file(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _load_sessions():
    return _load_json_file(SESSIONS_FILE, [])

def _save_sessions(items):
    _save_json_file(SESSIONS_FILE, items or [])

def _create_session(role, passport=None, ttl_seconds=3600.0):
    token = secrets.token_urlsafe(24)
    exp = (datetime.utcnow() + timedelta(seconds=float(ttl_seconds))).isoformat() + 'Z'
    sess = {
        'token': token,
        'role': role,
        'passport': passport,
        'expires': exp
    }
    items = _load_sessions()
    # prune expired
    now = datetime.utcnow()
    kept = []
    for s in items:
        try:
            if s.get('expires') and datetime.fromisoformat(s['expires'].replace('Z','')) > now:
                kept.append(s)
        except Exception:
            continue
    kept.append(sess)
    _save_sessions(kept)
    return token, exp

def _get_session(token):
    if not token:
        return None
    items = _load_sessions()
    now = datetime.utcnow()
    for s in items:
        try:
            if s.get('token') == token and s.get('expires') and datetime.fromisoformat(s['expires'].replace('Z','')) > now:
                return s
        except Exception:
            continue
    return None

def _require_session(req, require_role=None):
    """Check for valid session. Supports:
    1. session cookie
    2. X-SESSION header
    3. Authorization: Bearer <token> (JWT)
    """
    token = req.headers.get('X-SESSION') or req.cookies.get('session')
    
    # If no session token, try Authorization header (JWT)
    if not token:
        auth_header = req.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Strip 'Bearer '
    
    sess = _get_session(token)
    if not sess:
        # Try JWT token as fallback
        if token:
            try:
                data = security_manager.verify_token(token)
                if data[0]:  # If verification succeeded
                    # Create a pseudo-session from JWT
                    sess = {
                        'token': token,
                        'role': data[1].get('role', 'passenger'),
                        'passport': data[1].get('user_id') if data[1].get('role') == 'passenger' else None,
                        'expires': data[1].get('exp')
                    }
            except Exception:
                pass
    
    if not sess:
        return None
    if require_role and sess.get('role') != require_role:
        return None
    return sess

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


def _load_admin_users():
    try:
        with open(ADMIN_USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


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

def _compute_baggage_fee(baggage_count: int):
    """Simple baggage fee rule: first bag free, each extra bag $50."""
    try:
        n = int(baggage_count or 0)
    except Exception:
        n = 0
    if n <= 1:
        return 0
    return 50 * (n - 1)


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

def _load_access_codes():
    try:
        with open(ACCESS_CODES_FILE, 'r') as f:
            return json.load(f) or {}
    except Exception:
        return {}

def _load_admin_users():
    try:
        if os.path.exists(ADMIN_USERS_FILE):
            with open(ADMIN_USERS_FILE, 'r') as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_admin_users(users: dict):
    try:
        with open(ADMIN_USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception:
        pass


def _init_admin_users_from_env():
    # If no admin user file exists, but env vars present, create hashed entry
    users = _load_admin_users()
    if users:
        return users
    admin_user = os.getenv('ADMIN_USER')
    admin_pass = os.getenv('ADMIN_PASS')
    if admin_user and admin_pass:
        try:
            # bcrypt may not be available - fall back to plain storage if missing
            try:
                ph = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            except Exception:
                ph = admin_pass
            users = {admin_user: {'password_hash': ph}}
            _save_admin_users(users)
            return users
        except Exception:
            return {}
    return {}


# initialize admin users at startup
ADMIN_USERS = _init_admin_users_from_env()

def _save_access_codes(codes: dict):
    try:
        with open(ACCESS_CODES_FILE, 'w') as f:
            json.dump(codes, f, indent=2)
    except Exception:
        pass

def _generate_code():
    return f"{random.randint(0, 999999):06d}"

def _set_code_for_passport(passport: str, ttl_minutes: int = 10):
    codes = _load_access_codes()
    code = _generate_code()
    expires = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat() + 'Z'
    codes[passport] = {'code': code, 'expires': expires}
    _save_access_codes(codes)
    return code, expires

def _validate_and_consume_code(passport: str, code: str):
    codes = _load_access_codes()
    entry = codes.get(passport)
    if not entry:
        return False, 'no_code'
    if entry.get('code') != code:
        return False, 'invalid_code'
    try:
        expires = datetime.fromisoformat(entry.get('expires').replace('Z',''))
    except Exception:
        return False, 'invalid_expires'
    if datetime.utcnow() > expires:
        # expired
        try:
            del codes[passport]
            _save_access_codes(codes)
        except Exception:
            pass
        return False, 'expired'
    # consume
    try:
        del codes[passport]
        _save_access_codes(codes)
    except Exception:
        pass
    return True, 'ok'

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

def _save_bookings(bookings_list):
    """Save bookings list to bookings.json file."""
    try:
        with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bookings_list, f, indent=2)
    except Exception:
        pass

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

# Flights management functions
def _load_flights():
    """Load all flights from flights.json file."""
    try:
        if os.path.exists(FLIGHTS_FILE):
            with open(FLIGHTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or []
    except Exception:
        pass
    return []

def _save_flights(flights_list):
    """Save flights list to flights.json file."""
    try:
        with open(FLIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(flights_list, f, indent=2)
    except Exception:
        pass


# --- simple session store (file-backed) ------------------------------------------------
SESSIONS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "sessions.json"))

if not os.path.exists(SESSIONS_FILE):
    try:
        with open(SESSIONS_FILE, 'w') as f:
            json.dump({}, f)
    except Exception:
        pass

def _load_sessions():
    try:
        with open(SESSIONS_FILE, 'r') as f:
            return json.load(f) or {}
    except Exception:
        return {}

def _save_sessions(sessions: dict):
    try:
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
    except Exception:
        pass

def _create_session(role: str, passport: str = None, ttl_minutes: int = 60, ttl_seconds: float = None):
    """Create a session token.
    By default uses ttl_minutes. If ttl_seconds is provided it takes precedence and allows short lifetimes (e.g., admin testing).
    """
    token = __import__('uuid').uuid4().hex
    if ttl_seconds is not None:
        expires = (datetime.utcnow() + timedelta(seconds=float(ttl_seconds))).isoformat() + 'Z'
    else:
        expires = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat() + 'Z'
    sessions = _load_sessions()
    sessions[token] = {'role': role, 'passport': passport, 'expires': expires}
    _save_sessions(sessions)
    return token, expires

def _get_session(token: str):
    if not token:
        return None
    sessions = _load_sessions()
    entry = sessions.get(token)
    if not entry:
        return None
    try:
        exp = datetime.fromisoformat(entry.get('expires').replace('Z',''))
    except Exception:
        return None
    if datetime.utcnow() > exp:
        try:
            del sessions[token]
            _save_sessions(sessions)
        except Exception:
            pass
        return None
    return entry

def _delete_session(token: str):
    sessions = _load_sessions()
    if token in sessions:
        try:
            del sessions[token]
            _save_sessions(sessions)
        except Exception:
            pass

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


def _load_bookings():
    """Load all bookings from bookings.json"""
    try:
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, 'r') as f:
                return json.load(f) or []
    except Exception:
        pass
    return []


def _save_bookings(bookings: list):
    """Save bookings to bookings.json"""
    try:
        with open(BOOKINGS_FILE, 'w') as f:
            json.dump(bookings, f, indent=2)
    except Exception:
        pass


def _add_booking(booking: dict):
    """Add a new booking to the bookings file"""
    bookings = _load_bookings()
    booking['id'] = booking.get('id') or f"BK{len(bookings) + 1}"
    booking['created_at'] = booking.get('created_at') or datetime.utcnow().isoformat() + 'Z'
    booking['status'] = booking.get('status') or 'completed'
    bookings.append(booking)
    _save_bookings(bookings)
    log_event({
        'type': 'booking_created',
        'booking_id': booking.get('id'),
        'passenger_name': booking.get('name'),
        'payment_method': booking.get('payment_method'),
        'amount': booking.get('amount'),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
    return booking


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

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
# register airports route (defined earlier in the file)
try:
    app.add_url_rule('/api/airports', 'api_airports', api_airports, methods=['GET'])
except Exception:
    # If the function isn't defined yet for some reason, we'll rely on module load order.
    pass

@app.route("/api/passengers", methods=["GET", "DELETE"])
def api_get_passengers():
    if request.method == "GET":
        return jsonify(passengers)
    
    if request.method == "DELETE":
        # Clear all passengers
        passengers.clear()
        save_passengers()
        return jsonify({"message": "All passengers deleted successfully"}), 200


@app.route('/api/admin/passengers', methods=['POST','PUT','DELETE'])
def api_admin_passengers():
    """Admin-only passenger CRUD. Uses JSON body for inputs.
       POST: create passenger { name, passport, flight, seat?, email? }
       PUT: update passenger identified by passport and flight: { passport, flight, fields... }
       DELETE: delete passenger(s) by passport and optional flight: { passport, flight? }
    """
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    if request.method == 'POST':
        name = sanitize_input(data.get('name') or '')
        passport = sanitize_input(data.get('passport') or '')
        flight = sanitize_input(data.get('flight') or '')
        email = sanitize_input(data.get('email') or '')
        seat = data.get('seat')
        if not (name and passport and flight):
            return jsonify({'error': 'name, passport and flight are required'}), 400
        ok, reason = validate_passport(passport)
        if not ok:
            return jsonify({'error': 'invalid_passport', 'detail': reason}), 400
        if find_duplicate(passport, flight):
            return jsonify({'error': 'duplicate_passenger'}), 400
        # determine seat if not provided
        if seat is None:
            seat = sum(1 for p in passengers if p.get('flight') == flight) + 1
        p = {'name': name, 'passport': passport, 'flight': flight, 'seat': seat}
        if email:
            p['email'] = email
        passengers.append(p)
        try:
            save_passengers()
        except Exception:
            pass
        log_event({'type': 'admin_create_passenger', 'passport': passport, 'flight': flight, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify(p), 201

    if request.method == 'PUT':
        passport = sanitize_input(data.get('passport') or '')
        flight = sanitize_input(data.get('flight') or '')
        if not passport or not flight:
            return jsonify({'error': 'passport and flight required to identify record'}), 400
        # find passenger index
        idx = next((i for i,p in enumerate(passengers) if str(p.get('passport')) == str(passport) and str(p.get('flight')) == str(flight)), None)
        if idx is None:
            return jsonify({'error': 'passenger_not_found'}), 404
        # allowed update fields
        allowed = {'name','email','phone','seat','checked_in','baggage_count','baggage_paid','baggage_details'}
        changed = {}
        for k,v in data.items():
            if k in allowed:
                passengers[idx][k] = v
                changed[k] = v
        try:
            save_passengers()
        except Exception:
            pass
        log_event({'type': 'admin_update_passenger', 'passport': passport, 'flight': flight, 'changed': changed, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'updated', 'passenger': passengers[idx]}), 200

    if request.method == 'DELETE':
        passport = sanitize_input(data.get('passport') or '')
        flight = sanitize_input(data.get('flight') or '')
        if not passport:
            return jsonify({'error': 'passport required to delete passenger(s)'}), 400
        before = len(passengers)
        if flight:
            # remove matching passport+flight
            passengers[:] = [p for p in passengers if not (str(p.get('passport')) == str(passport) and str(p.get('flight')) == str(flight))]
        else:
            # remove all records with this passport
            passengers[:] = [p for p in passengers if not (str(p.get('passport')) == str(passport))]
        removed = before - len(passengers)
        try:
            save_passengers()
        except Exception:
            pass
        log_event({'type': 'admin_delete_passenger', 'passport': passport, 'flight': flight or 'ALL', 'removed': removed, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'deleted', 'removed': removed}), 200


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
    name = sanitize_input(data.get("name") or '')
    passport = sanitize_input(data.get("passport") or '')
    email = sanitize_input(data.get("email") or '')
    flight = sanitize_input(data.get("flight") or '')

    if not (name and passport and flight):
        return jsonify({"error": "name, passport and flight are required"}), 400

    # validate passport format
    ok, reason = validate_passport(passport)
    if not ok:
        return jsonify({"error": "invalid_passport", "detail": reason}), 400

    if find_duplicate(passport, flight):
        return jsonify({"error": "Passenger already registered for this flight"}), 400

    # enforce flight capacity if defined
    flights = _load_flights()
    flight_entry = next((f for f in flights if f.get('flight') == flight), None)
    if flight_entry and flight_entry.get('capacity') is not None:
        try:
            capacity = int(flight_entry.get('capacity'))
        except Exception:
            capacity = None
        current = sum(1 for p in passengers if p.get("flight") == flight)
        if capacity is not None and current >= capacity:
            return jsonify({"error": "flight_full", "detail": "flight has reached capacity"}), 400

    seat = sum(1 for p in passengers if p.get("flight") == flight) + 1
    passenger = {"name": name, "passport": passport, "flight": flight, "seat": seat}
    if email:
        passenger['email'] = email
    passengers.append(passenger)
    save_passengers()
    # attempt to send boarding pass by email if configured
    email_sent = False
    try:
        if passenger.get('email'):
            # enqueue email send in background to avoid blocking
            enqueue_boarding_email(passenger)
            email_sent = True
    except Exception:
        email_sent = False

    out = passenger.copy()
    out['email_sent'] = email_sent
    return jsonify(out), 201


@app.route("/api/face/enroll", methods=["POST"])
def api_face_enroll():
    # Expects multipart/form-data with 'passport' and file field 'image'
    passport = request.form.get('passport') or request.args.get('passport')
    img = request.files.get('image')
    if not (passport and img):
        return jsonify({"error": "passport and image are required"}), 400
    ok, reason = validate_passport(passport)
    if not ok:
        return jsonify({"error": "invalid_passport", "detail": reason}), 400
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
    ok, reason = validate_passport(passport)
    if not ok:
        return jsonify({"error": "invalid_passport", "detail": reason}), 400
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

# Authorization: Prefer session-based passenger access (no one-time code required anymore).
# 1) If request carries a valid passenger session that matches the requested passport -> allow
# 2) Else if a code is provided, validate (backwards compatibility)
# 3) Else allow master password via X-ACCESS-PASSWORD
    allowed = False
    # check session token
    token = request.headers.get('X-SESSION') or request.cookies.get('session')
    sess = None
    if token:
        sess = _get_session(token)
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
    # Optional public access gate for demos only (off by default)
    elif (os.getenv('ALLOW_PUBLIC_BOARDINGPASS','false').lower() in ('1','true','yes')):
        allowed = True
    else:
        return jsonify({'error': 'access_denied', 'detail': 'provide a valid session, code, or master password'}), 403

    # Create a simple boarding pass image or PDF
    try:
        img = create_boarding_pass_image(p)
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
    """GET: Return bookings: admin sees all, passenger sees only their own.
       POST: Create a new booking from payment confirmation (no session required for public bookings).
    """
    if request.method == 'POST':
        # Handle new booking from payment page (no session required - public endpoint)
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['id', 'name', 'email', 'passport', 'phone', 'from', 'to', 'depart', 'payment_method']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({'error': 'missing_required_fields', 'missing': missing}), 400
        
        # Create booking record in bookings.json
        booking = {
            'id': data.get('id'),
            'passenger_name': sanitize_input(data.get('name') or ''),
            'name': sanitize_input(data.get('name') or ''),
            'email': sanitize_input(data.get('email') or ''),
            'passport': sanitize_input(data.get('passport') or ''),
            'phone': sanitize_input(data.get('phone') or ''),
            'country': sanitize_input(data.get('country') or ''),
            'from': sanitize_input(data.get('from') or ''),
            'to': sanitize_input(data.get('to') or ''),
            'depart': sanitize_input(data.get('depart') or ''),
            'flight_number': sanitize_input(data.get('flight_number') or data.get('flight') or 'N/A'),
            'return': sanitize_input(data.get('return') or ''),
            'class': sanitize_input(data.get('class') or 'economy'),
            'fare': sanitize_input(data.get('fare') or '0'),
            'total_amount': float(data.get('amount') or 0),
            'amount': float(data.get('amount') or 0),
            'currency': sanitize_input(data.get('currency') or 'USD'),
            'payment_method': sanitize_input(data.get('payment_method') or ''),
            'payment_status': 'completed',
            'status': 'completed',
            'booking_date': datetime.utcnow().isoformat() + 'Z',
            'created_at': datetime.utcnow().isoformat() + 'Z',
        }
        
        # Save booking
        saved_booking = _add_booking(booking)
        
        # Log the booking activity
        log_activity('booking', {
            'passenger_name': booking.get('passenger_name'),
            'flight_number': booking.get('flight_number'),
            'from': booking.get('from'),
            'to': booking.get('to'),
            'amount': booking.get('amount'),
            'payment_method': booking.get('payment_method'),
            'timestamp': booking.get('created_at')
        })
        
        return jsonify({'status': 'ok', 'booking': saved_booking}), 201
    
    # GET endpoint
    session = _require_session(request)
    if not session:
        # No session - return all bookings (for admin dashboard without auth)
        bookings = _load_bookings()
        return jsonify({'bookings': bookings}), 200
    if session.get('role') == 'admin':
        # Admin gets bookings from bookings.json (payment records)
        bookings = _load_bookings()
        return jsonify(bookings), 200
    # passenger - gets their own bookings from passengers list
    passport = session.get('passport')
    matches = [p.copy() for p in passengers if p.get('passport') == passport]
    flights = {f.get('flight'): f for f in _load_flights()}
    for p in matches:
        f = flights.get(p.get('flight'))
        if f:
            p['_flight_time'] = f.get('time')
    return jsonify({'bookings': matches}), 200


@app.route('/api/flights', methods=['GET','POST'])
def api_flights():
    """GET: list flights (aggregated from passengers + flights.json if present)
       POST (admin only): add a flight { flight: str, meta?: dict }
    """
    if request.method == 'GET':
        # Filters
        date_q = (request.args.get('date') or '').strip()
        origin_q = (request.args.get('origin') or '').strip().upper()
        dest_q = (request.args.get('destination') or '').strip().upper()
        avail_only = (request.args.get('availableOnly') or '').lower() == 'true'

        flights = _load_flights()

        # passenger counts
        counts = {}
        for p in passengers:
            f = p.get('flight')
            if not f:
                continue
            counts[f] = counts.get(f, 0) + 1

        def to_date_iso(dt_str):
            try:
                dt = datetime.fromisoformat(dt_str.replace('Z', ''))
                return dt.date().isoformat()
            except Exception:
                return None

        def base_price(f):
            aircraft = (f.get('aircraft') or '').lower()
            cap = int(f.get('capacity') or 0)
            if 'a380' in aircraft or '777' in aircraft or '787' in aircraft or 'a350' in aircraft:
                tier = 200
            elif 'a320' in aircraft or '737' in aircraft:
                tier = 120
            else:
                tier = 90
            size_factor = 1.0 if cap >= 220 else (0.9 if cap >= 180 else 0.8)
            return round(size_factor * tier, 2)

        CLASS_FACTORS = [
            {'class': 'Economy', 'code': 'Y', 'mult': 1.0, 'amenities': ['Standard seat', '1 carry-on']},
            {'class': 'Premium Economy', 'code': 'W', 'mult': 1.4, 'amenities': ['Extra legroom', 'Priority boarding']},
            {'class': 'Business', 'code': 'J', 'mult': 2.5, 'amenities': ['Lie-flat (on widebody)', 'Lounge access']},
            {'class': 'First', 'code': 'F', 'mult': 4.0, 'amenities': ['Suite (on A380/777)', 'Premium dining']},
        ]

        enriched = []
        for fl in flights:
            dep_date = to_date_iso(fl.get('time'))
            if date_q and dep_date != date_q:
                continue
            if origin_q and (fl.get('origin') or '').upper() != origin_q:
                continue
            if dest_q and (fl.get('destination') or '').upper() != dest_q:
                continue
            if avail_only and not fl.get('checkin_enabled'):
                continue

            base = base_price(fl)
            classes = []
            for c in CLASS_FACTORS:
                if c['code'] == 'F' and not any(k in (fl.get('aircraft') or '').lower() for k in ['a380', '777', '787']):
                    continue
                price = round(base * c['mult'], 2)
                classes.append({
                    'name': c['class'],
                    'code': c['code'],
                    'price': price,
                    'currency': 'USD',
                    'amenities': c['amenities']
                })

            enriched.append({
                'flight': fl.get('flight'),
                'airline': fl.get('airline'),
                'aircraft': fl.get('aircraft'),
                'origin': fl.get('origin'),
                'destination': fl.get('destination'),
                'departure_time': fl.get('time'),
                'arrival_time': fl.get('arrival'),
                'date': dep_date,
                'gate': fl.get('gate'),
                'capacity': fl.get('capacity'),
                'checkin_enabled': fl.get('checkin_enabled'),
                'classes': classes,
                'bookings': counts.get(fl.get('flight'), 0)
            })

        return jsonify({'total': len(enriched), 'flights': enriched}), 200

    # POST -> admin only (create flight)
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() or {}
    flight = (data.get('flight') or '').strip()
    time = data.get('time')
    aircraft = (data.get('aircraft') or '').strip() or None
    gate = (data.get('gate') or '').strip() or None
    airline = (data.get('airline') or '').strip() or None
    logo = (data.get('logo') or '').strip() or None
    arrival = data.get('arrival')
    checkin_enabled = data.get('checkin_enabled') if 'checkin_enabled' in data else True
    if not flight:
        return jsonify({'error': 'flight required'}), 400
    try:
        time_iso = _parse_time_field(time) if time else None
        arrival_iso = _parse_time_field(arrival) if arrival else None
    except ValueError as e:
        return jsonify({'error': 'invalid_time', 'detail': str(e)}), 400

    flights = _load_flights()
    # prevent duplicates
    if any(f.get('flight') == flight for f in flights):
        return jsonify({'error': 'flight_exists'}), 400
    # capacity (optional)
    capacity = None
    try:
        if data.get('capacity') is not None and str(data.get('capacity')).strip() != '':
            capacity = int(data.get('capacity'))
    except Exception:
        return jsonify({'error': 'invalid_capacity'}), 400
    entry = {'flight': flight, 'time': time_iso, 'capacity': capacity, 'aircraft': aircraft, 'gate': gate, 'arrival': arrival_iso, 'checkin_enabled': bool(checkin_enabled), 'blocked_seats': [], 'airline': airline, 'logo': logo}
    flights.append(entry)
    _save_flights(flights)
    log_event({'type': 'flight_created', 'flight': flight, 'time': time_iso, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
    return jsonify({'status': 'created', 'flight': entry}), 201


# Pricing API: compute distance-based fares using airport lat/lon
def _calculate_flight_price(origin, destination):
    """Calculate a realistic flight price based on distance between airports.
    Uses haversine distance formula and a base price model.
    """
    try:
        airports = _load_airports_map()
        origin_code = str(origin).strip().upper()
        dest_code = str(destination).strip().upper()
        
        origin_data = airports.get(origin_code)
        dest_data = airports.get(dest_code)
        
        if not origin_data or not dest_data:
            # Default price if airport data not found
            return round(random.uniform(250, 450), 2)
        
        origin_lat = origin_data.get('lat')
        origin_lon = origin_data.get('lon')
        dest_lat = dest_data.get('lat')
        dest_lon = dest_data.get('lon')
        
        if origin_lat is None or origin_lon is None or dest_lat is None or dest_lon is None:
            # Default price if coordinates not available
            return round(random.uniform(250, 450), 2)
        
        # Calculate distance
        distance = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        
        if distance is None or distance == 0:
            return round(random.uniform(250, 450), 2)
        
        # Pricing model:
        # Base fare: $150
        # Per km: $0.08 for short flights (<1500km), $0.06 for medium (1500-5000km), $0.04 for long (>5000km)
        # Plus variance to avoid identical prices
        base_fare = 150
        if distance < 1500:
            per_km_rate = 0.10
        elif distance < 5000:
            per_km_rate = 0.06
        else:
            per_km_rate = 0.04
        
        distance_fare = distance * per_km_rate
        subtotal = base_fare + distance_fare
        
        # Add some variance (±15%) to make prices more realistic
        variance = random.uniform(0.85, 1.15)
        final_price = subtotal * variance
        
        return round(final_price, 2)
    except Exception:
        # Fallback to random price on any error
        return round(random.uniform(200, 500), 2)


    """Load a simple mapping of IATA -> { lat, lon, name, city } from the frontend assets folder.
       Returns a dict keyed by uppercase IATA code.
    """
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
                code = (a.get('code') or a.get('iata') or '')
                if not code: continue
                code = code.strip().upper()
                lat = a.get('lat') if 'lat' in a else a.get('latitude')
                lon = a.get('lon') if 'lon' in a else a.get('longitude')
                try:
                    lat = float(lat) if lat is not None else None
                except Exception:
                    lat = None
                try:
                    lon = float(lon) if lon is not None else None
                except Exception:
                    lon = None
                out[code] = {'lat': lat, 'lon': lon, 'name': a.get('name'), 'city': a.get('city'), 'country': a.get('country')}
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
                    lat = float(lat) if lat is not None else None
                except Exception:
                    lat = None
                try:
                    lon = float(lon) if lon is not None else None
                except Exception:
                    lon = None
                out[code] = {'lat': lat, 'lon': lon, 'name': a.get('name'), 'city': a.get('city'), 'country': a.get('country')}
            except Exception:
                continue
    return out

def _haversine_km(lat1, lon1, lat2, lon2):
    try:
        import math
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2.0)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return r * c
    except Exception:
        return None


def _load_flights():
    """Load flights from `flights.json` in the backend directory.
       Returns a list of flight dicts (or empty list if file missing/invalid).
    """
    try:
        path = os.path.join(BASE_DIR, 'flights.json')
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f) or []
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_flights(flights: list):
    """Save flights list to `flights.json` (best-effort, swallows errors)."""
    try:
        path = os.path.join(BASE_DIR, 'flights.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(flights or [], f, indent=2)
    except Exception:
        pass


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

    token, exp = _create_session('passenger', cand.get('passport'), ttl_seconds=ttl)
    resp = jsonify({'token': token, 'expires': exp, 'passport': cand.get('passport')})
    try:
        resp.set_cookie('session', token, max_age=int(ttl), httponly=True, samesite='Lax')
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
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

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

        # validate passport format
        ok, reason = validate_passport(passport)
        if not ok:
            results.append({'passport': passport, 'status': 'error', 'detail': 'invalid_passport', 'reason': reason})
            continue

        # find or create passenger record
        p = next((x for x in passengers if x.get('passport') == passport), None)
        if p is None:
            p = {'name': name, 'passport': passport}
            passengers.append(p)

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

        # Log event
        log_event({'type': 'checkin', 'passport': passport, 'flight': flight, 'seat': assigned_seat, 'baggage_count': baggage_count, 'timestamp': datetime.utcnow().isoformat() + 'Z'})

        # attempt to send boarding pass by email if email present (enqueue)
        email_sent = False
        if p.get('email'):
            try:
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
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    # Calculate statistics
    total_passengers = len(passengers)
    total_flights = len(_load_flights())
    
    # Check-in statistics
    checked_in_count = sum(1 for p in passengers if p.get('checked_in', False))
    check_in_rate = (checked_in_count / total_passengers * 100) if total_passengers > 0 else 0
    
    # Flight statistics
    flights = _load_flights()
    active_flights = sum(1 for f in flights if f.get('status') == 'active')
    cancelled_flights = sum(1 for f in flights if f.get('status') == 'cancelled')
    
    # Baggage statistics
    total_baggage = sum(int(p.get('baggage_count', 0)) for p in passengers)
    baggage_fees = sum(float(p.get('baggage_fee', 0)) for p in passengers)
    
    return jsonify({
        'passengers': {
            'total': total_passengers,
            'checked_in': checked_in_count,
            'check_in_rate': round(check_in_rate, 2)
        },
        'flights': {
            'total': total_flights,
            'active': active_flights,
            'cancelled': cancelled_flights
        },
        'baggage': {
            'total_count': total_baggage,
            'total_fees': round(baggage_fees, 2)
        }
    }), 200

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

@app.route('/api/admin/flights', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_flights():
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

    if request.method == 'GET':
        flights = _load_flights()
        return jsonify({'flights': flights}), 200
    
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'flight' not in data:
            return jsonify({'error': 'Missing flight information'}), 400
        
        flights = _load_flights()
        if any(f['flight'] == data['flight'] for f in flights):
            return jsonify({'error': 'Flight already exists'}), 400
        
        new_flight = {
            'flight': data['flight'],
            'origin': data.get('origin'),
            'destination': data.get('destination'),
            'date': data.get('date'),
            'time': data.get('time'),
            'capacity': data.get('capacity'),
            'status': data.get('status', 'scheduled')
        }
        
        flights.append(new_flight)
        _save_flights(flights)
        return jsonify({'status': 'success', 'flight': new_flight}), 201

@app.route('/api/admin/flights/<flight_id>', methods=['GET', 'PUT', 'DELETE'])
def api_admin_flight(flight_id):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

    flights = _load_flights()
    flight_index = next((i for i, f in enumerate(flights) if f['flight'] == flight_id), None)
    
    if flight_index is None:
        return jsonify({'error': 'Flight not found'}), 404

    if request.method == 'GET':
        return jsonify({'flight': flights[flight_index]}), 200
    
    if request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No update data provided'}), 400
        
        flights[flight_index].update({
            'origin': data.get('origin', flights[flight_index]['origin']),
            'destination': data.get('destination', flights[flight_index]['destination']),
            'date': data.get('date', flights[flight_index]['date']),
            'time': data.get('time', flights[flight_index]['time']),
            'capacity': data.get('capacity', flights[flight_index]['capacity']),
            'status': data.get('status', flights[flight_index]['status'])
        })
        
        _save_flights(flights)
        return jsonify({'status': 'success', 'flight': flights[flight_index]}), 200
    
    if request.method == 'DELETE':
        deleted_flight = flights.pop(flight_index)
        _save_flights(flights)
        return jsonify({'status': 'success', 'deleted': deleted_flight}), 200



@app.route('/api/admin/system/config', methods=['GET', 'PUT'])
def api_admin_system_config():
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    
    config_file = os.path.join(os.path.dirname(__file__), "system_config.json")
    
    if request.method == 'GET':
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {
                    'check_in': {
                        'enabled': True,
                        'start_hours_before': 24,
                        'end_hours_before': 1
                    },
                    'baggage': {
                        'max_items': 3,
                        'free_items': 1,
                        'fee_per_extra_item': 50
                    },
                    'notifications': {
                        'email_enabled': True,
                        'sms_enabled': False
                    }
                }
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
            return jsonify(config), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No configuration data provided'}), 400
        try:
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            return jsonify({'status': 'success', 'config': data}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

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
        passenger = next((p for p in passengers if p['passport'] == recipient), None)
        if passenger:
            try:
                if notification_type == 'email' and passenger.get('email'):
                    # Send email notification
                    msg = EmailMessage()
                    msg['Subject'] = data.get('subject', 'Important Flight Information')
                    msg['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER')
                    msg['To'] = passenger['email']
                    msg.set_content(message)
                    
                    smtp_host = os.getenv('SMTP_HOST')
                    smtp_port = int(os.getenv('SMTP_PORT') or 0)
                    if smtp_host and smtp_port:
                        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                            smtp.send_message(msg)
                            success_count += 1
                            results.append({
                                'recipient': recipient,
                                'status': 'sent',
                                'method': 'email'
                            })
                    
                elif notification_type == 'sms' and passenger.get('phone'):
                    # SMS notification logic would go here
                    # For now, we'll just log it
                    success_count += 1
                    results.append({
                        'recipient': recipient,
                        'status': 'sent',
                        'method': 'sms'
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

@app.route('/api/admin/passengers/<passport>', methods=['GET', 'PUT', 'DELETE'])
def api_admin_passenger(passport):
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    # Support identifying a specific booking by optional 'flight' parameter (query or JSON body)
    flight = (request.args.get('flight') or (request.get_json(silent=True) or {}).get('flight') or '').strip()

    # find all indices for this passport
    indices = [i for i, p in enumerate(passengers) if str(p.get('passport')) == str(passport)]
    if not indices:
        return jsonify({'error': 'Passenger not found'}), 404

    # helper to select index based on flight if provided
    def _select_index():
        if flight:
            idx = next((i for i, p in enumerate(passengers) if str(p.get('passport')) == str(passport) and str(p.get('flight') or '') == str(flight)), None)
            return idx
        # if only one record exists for this passport, return it
        if len(indices) == 1:
            return indices[0]
        # ambiguous: multiple bookings for same passport, caller should specify flight
        return None

    if request.method == 'GET':
        # If flight specified, return that record; otherwise return all records for this passport
        if flight:
            idx = _select_index()
            if idx is None:
                return jsonify({'error': 'Passenger for specified flight not found'}), 404
            return jsonify({'passenger': passengers[idx]}), 200
        matched = [p for i, p in enumerate(passengers) if i in indices]
        return jsonify({'passengers': matched}), 200

    if request.method == 'PUT':
        data = request.get_json() or {}
        if not data:
            return jsonify({'error': 'No update data provided'}), 400
        idx = _select_index()
        if idx is None:
            return jsonify({'error': 'multiple_records_found', 'detail': 'Specify flight to identify which booking to update'}), 400

        # allowed updates
        allowed = {'name', 'email', 'flight', 'seat', 'checked_in', 'phone', 'baggage_count', 'baggage_paid', 'baggage_details'}
        changed = {}
        for k, v in data.items():
            if k in allowed:
                passengers[idx][k] = v
                changed[k] = v
        try:
            save_passengers()
        except Exception:
            pass
        log_event({'type': 'admin_update_passenger', 'passport': passport, 'flight': passengers[idx].get('flight'), 'changed': changed, 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'success', 'passenger': passengers[idx]}), 200

    if request.method == 'DELETE':
        # If flight specified, delete that booking; otherwise delete all bookings for passport
        removed = []
        if flight:
            new_list = [p for p in passengers if not (str(p.get('passport')) == str(passport) and str(p.get('flight') or '') == str(flight))]
            removed = [p for p in passengers if (str(p.get('passport')) == str(passport) and str(p.get('flight') or '') == str(flight))]
            passengers[:] = new_list
        else:
            removed = [p for p in passengers if str(p.get('passport')) == str(passport)]
            passengers[:] = [p for p in passengers if not (str(p.get('passport')) == str(passport))]
        try:
            save_passengers()
        except Exception:
            pass
        log_event({'type': 'admin_delete_passenger', 'passport': passport, 'flight': flight or 'ALL', 'removed': len(removed), 'by': session.get('role'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'status': 'success', 'removed': len(removed), 'deleted': removed}), 200

@app.route('/api/flights/<flight_id>/boarding/stream')
def api_boarding_stream(flight_id):
    # SSE stream of boarding state updates for a flight (admin only)
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'unauthorized'}), 401

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


@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
    
    users = _load_admin_users()
    username = data['username']
    password = data['password']
    
    if username in users:
        stored_hash = users[username]['password_hash']
        try:
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                    # admin sessions have a short TTL for the admin portal (seconds), configurable via ADMIN_SESSION_TTL_SECONDS
                    try:
                        # Default admin session TTL to 1 hour unless overridden
                        admin_ttl = float(os.getenv('ADMIN_SESSION_TTL_SECONDS', '3600'))
                    except Exception:
                        admin_ttl = 3600.0
                    token, expires = _create_session('admin', None, ttl_seconds=admin_ttl)
                log_event({
                    'type': 'admin_login',
                    'username': username,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })
                resp = jsonify({
                    'token': token,
                    'role': 'admin',
                    'expires': expires,
                    'username': username
                })
                try:
                    # set a cookie so browser navigation to admin pages includes session
                    resp.set_cookie('session', token, max_age=int(admin_ttl), httponly=True, samesite='Lax')
                except Exception:
                    pass
                return resp, 200
        except Exception:
            pass
    
    return jsonify({'error': 'Invalid credentials'}), 401

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
        username = (data.get('username') or '').strip()
        password = data.get('password')
        if not (username and password):
            return jsonify({'error': 'username_and_password_required'}), 400
        users = _load_admin_users()
        try:
            ph = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
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
    data = request.get_json() or {}
    role = (data.get('role') or '').lower()

    if role == 'passenger':
        # Passenger may login/register with either (1) name+passport, or (2) email or phone.
        passport = (data.get('passport') or '').strip()
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()

        if not ((passport and name) or email or phone):
            return jsonify({'error': 'provide passport+name, or email, or phone to login/register'}), 400

        # validate passport format if provided
        if passport:
            ok, reason = validate_passport(passport)
            if not ok:
                return jsonify({'error': 'invalid_passport', 'detail': reason}), 400

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
        token, expires = _create_session('passenger', p.get('passport'))
        log_event({'type': 'login', 'role': 'passenger', 'passport': p.get('passport'), 'timestamp': datetime.utcnow().isoformat() + 'Z'})
        return jsonify({'token': token, 'role': 'passenger', 'expires': expires}), 200

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
            token, expires = _create_session('admin', None, ttl_seconds=admin_ttl)
            log_event({'type': 'login', 'role': 'admin', 'username': username or 'master', 'timestamp': datetime.utcnow().isoformat() + 'Z'})
            return jsonify({'token': token, 'role': 'admin', 'expires': expires}), 200

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
                token, expires = _create_session('admin', None, ttl_seconds=admin_ttl)
                log_event({'type': 'login', 'role': 'admin', 'username': username, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                
                # Create response with session cookie
                resp = jsonify({
                    'token': token,
                    'role': 'admin',
                    'username': username,
                    'expires': expires,
                    'status': 'ok'
                })
                
                # Set session cookie
                try:
                    resp.set_cookie('session', token, max_age=int(admin_ttl), httponly=True, samesite='Lax', path='/')
                except Exception:
                    pass
                
                return resp, 200

        return jsonify({'error': 'invalid_credentials'}), 403

    return jsonify({'error': 'unknown_role'}), 400


@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.headers.get('X-SESSION') or request.cookies.get('session')
    if token:
        _delete_session(token)
    return jsonify({'status': 'ok'})

# Serve admin static files only to authenticated admin sessions.
@app.route('/admin')
@app.route('/admin/')
def admin_root():
    # Redirect to the dashboard entrypoint
    return redirect('/admin/dashboard.html')


@app.route('/admin/<path:filename>')
def admin_files(filename):
    # Only allow serving admin files to an authenticated admin session
    session = _require_session(request, require_role='admin')
    if not session:
        return redirect('/admin-login.html')
    # serve from frontend/admin directory
    admin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'admin'))
    # Allow common admin HTML pages; otherwise redirect HTML requests to the canonical dashboard
    # This keeps static assets (css/js/png/svg/woff, etc.) served directly while preventing stray HTML pages.
    allowed_html = {
        'dashboard.html', 'flights.html', 'bookings.html', 'users.html', 'reports.html', 'settings.html', 'merged-dashboard.html'
    }
    lower = filename.lower()
    if lower.endswith('.html'):
        base = os.path.basename(lower)
        if base not in allowed_html:
            return redirect('/admin/dashboard.html')
    return send_from_directory(admin_dir, filename)


@app.route('/admin-login.html', methods=['GET'])
def admin_login_page():
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    return send_from_directory(frontend_dir, 'admin-login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login_server():
    # Server-side login handler for admin login form
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    if not username or not password:
        return redirect('/admin-login.html?error=1')
    users = _load_admin_users()
    if username in users:
        stored_hash = users[username].get('password_hash')
        try:
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                try:
                    admin_ttl = float(os.getenv('ADMIN_SESSION_TTL_SECONDS', '3600'))
                except Exception:
                    admin_ttl = 3600.0
                token, expires = _create_session('admin', None, ttl_seconds=admin_ttl)
                log_event({'type': 'admin_login', 'username': username, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                resp = redirect('/admin/dashboard.html')
                try:
                    resp.set_cookie('session', token, max_age=int(admin_ttl), httponly=True, samesite='Lax')
                except Exception:
                    pass
                return resp
        except Exception:
            pass
    return redirect('/admin-login.html?error=1')


@app.route('/admin.html')
def serve_root_admin_html():
    # Protect the legacy /admin.html page as well
    session = _require_session(request, require_role='admin')
    if not session:
        return redirect('/admin-login.html')
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    return send_from_directory(frontend_dir, 'admin.html')


def create_boarding_pass_image(p):
    """Create a professional, stylish boarding pass with SmartFly branding and modern design."""
    from PIL import ImageDraw, ImageFont
    
    # Dimensions: 1200x600 for high quality, 16:10 aspect (typical boarding pass)
    width, height = 1200, 600
    
    # Create base image with WHITE background (clean, professional)
    bg = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(bg)
    
    # SmartFly colors
    smartfly_blue_dark = (11, 116, 222)  # #0B74DE
    smartfly_blue_light = (230, 240, 250)  # Very light blue for subtle backgrounds
    smartfly_accent = (255, 102, 0)  # #FF6600 (orange accent)
    text_dark = (33, 33, 33)  # Dark gray instead of pure black
    text_light = (100, 100, 100)  # Light gray for labels
    
    # Draw subtle light blue background on right side only (decorative, not obscuring)
    draw.rectangle([(600, 0), (width, height)], fill=smartfly_blue_light)
    
    # Draw header bar at top (darker blue)
    draw.rectangle([(0, 0), (width, 85)], fill=smartfly_blue_dark)
    
    # Draw accent stripe below header
    draw.rectangle([(0, 85), (width, 92)], fill=smartfly_accent)
    
    # Load fonts (with fallback)
    try:
        font_title = ImageFont.truetype('arial.ttf', 52)
        font_large = ImageFont.truetype('arial.ttf', 32)
        font_medium = ImageFont.truetype('arial.ttf', 22)
        font_small = ImageFont.truetype('arial.ttf', 16)
        font_label = ImageFont.truetype('arial.ttf', 12)
        font_tiny = ImageFont.truetype('arial.ttf', 11)
    except Exception:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # Draw SmartFly logo/text at top left (WHITE text on dark blue)
    draw.text((25, 20), "SmartFly", fill=(255, 255, 255), font=font_title)
    
    # Draw "BOARDING PASS" below header
    draw.text((25, 110), "BOARDING PASS", fill=smartfly_blue_dark, font=font_large)
    
    # Draw checked-in status badge in top right
    draw.rectangle([(width - 200, 20), (width - 25, 70)], fill=smartfly_accent)
    draw.text((width - 190, 30), "✓ CHECKED IN", fill=(255, 255, 255), font=font_small)
    
    # Main content area starts here
    content_y = 150
    
    # LEFT SECTION: Passenger and Document Info
    left_x = 25
    
    # Passenger Name
    draw.text((left_x, content_y), "PASSENGER", fill=text_light, font=font_label)
    draw.text((left_x, content_y + 18), p.get('name', 'N/A').upper(), fill=text_dark, font=font_large)
    
    # Document Number
    draw.text((left_x, content_y + 70), "DOCUMENT NO.", fill=text_light, font=font_label)
    draw.text((left_x, content_y + 88), p.get('passport', 'N/A'), fill=text_dark, font=font_medium)
    
    # MIDDLE SECTION: Flight Info (prominent)
    middle_x = 380
    
    # Flight Number (VERY LARGE AND PROMINENT)
    draw.text((middle_x, content_y - 15), "FLIGHT", fill=text_light, font=font_label)
    draw.text((middle_x, content_y + 15), p.get('flight', 'N/A').upper(), fill=smartfly_blue_dark, font=font_title)
    
    # RIGHT SECTION: Seat Number
    right_x = width - 250
    
    # Seat (large, in accent color)
    draw.text((right_x, content_y), "SEAT", fill=text_light, font=font_label)
    draw.text((right_x, content_y + 18), str(p.get('seat', 'N/A')), fill=smartfly_accent, font=font_title)
    
    # Separator line (subtle)
    draw.line([(25, 310), (width - 25, 310)], fill=(220, 220, 220), width=2)
    
    # BOTTOM SECTION: Flight Details (4 columns)
    bottom_y = 340
    
    # Column 1: From
    col1_x = 25
    draw.text((col1_x, bottom_y), "FROM", fill=text_light, font=font_label)
    draw.text((col1_x, bottom_y + 20), "JFK", fill=text_dark, font=font_large)
    
    # Column 2: To
    col2_x = 300
    draw.text((col2_x, bottom_y), "TO", fill=text_light, font=font_label)
    draw.text((col2_x, bottom_y + 20), "LHR", fill=text_dark, font=font_large)
    
    # Column 3: Gate
    col3_x = 550
    draw.text((col3_x, bottom_y), "GATE", fill=text_light, font=font_label)
    draw.text((col3_x, bottom_y + 20), "B22", fill=text_dark, font=font_large)
    
    # Column 4: Class
    col4_x = 750
    draw.text((col4_x, bottom_y), "CLASS", fill=text_light, font=font_label)
    draw.text((col4_x, bottom_y + 20), "ECONOMY", fill=text_dark, font=font_medium)
    
    # Second row: Boarding and Departure times
    second_row_y = 440
    
    draw.text((col1_x, second_row_y), "BOARDING", fill=text_light, font=font_label)
    draw.text((col1_x, second_row_y + 20), "15:00", fill=text_dark, font=font_medium)
    
    draw.text((col2_x, second_row_y), "DEPARTURE", fill=text_light, font=font_label)
    draw.text((col2_x, second_row_y + 20), "15:30", fill=text_dark, font=font_medium)
    
    draw.text((col3_x, second_row_y), "ARRIVAL", fill=text_light, font=font_label)
    draw.text((col3_x, second_row_y + 20), "19:45", fill=text_dark, font=font_medium)
    
    draw.text((col4_x, second_row_y), "BAGGAGE", fill=text_light, font=font_label)
    draw.text((col4_x, second_row_y + 20), "1 BAG", fill=text_dark, font=font_medium)
    
    # QR CODE (bottom right, with white background box)
    qr_payload = f"pass:{p.get('passport')}|flight:{p.get('flight')}|seat:{p.get('seat')}"
    qr = qrcode.make(qr_payload).resize((160, 160))
    
    # Draw white box with border for QR code
    qr_x = width - 210
    qr_y = 360
    draw.rectangle([(qr_x - 12, qr_y - 12), (qr_x + 172, qr_y + 172)], 
                   fill=(255, 255, 255), outline=smartfly_blue_dark, width=3)
    bg.paste(qr, (qr_x, qr_y))
    
    # Footer
    footer_y = height - 35
    draw.text((col1_x, footer_y), "Present this pass at the gate • Keep throughout journey", 
              fill=text_light, font=font_tiny)
    draw.text((col1_x, footer_y + 16), f"Boarding Pass #{p.get('passport', '000000')[-6:]} • Valid only with proper identification", 
              fill=text_light, font=font_tiny)
    
    return bg


def send_boarding_pass_email(passenger):
    # SMTP configuration via env vars
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT') or 0)
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    smtp_from = os.getenv('SMTP_FROM') or smtp_user
    use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')

    if not (smtp_host and smtp_port and smtp_from):
        # SMTP not configured
        raise RuntimeError('SMTP not configured')

    # Create boarding pass image
    img = create_boarding_pass_image(passenger)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Compose email
    msg = EmailMessage()
    msg['Subject'] = f"Your boarding pass for {passenger.get('flight')}"
    msg['From'] = smtp_from
    msg['To'] = passenger.get('email')
    body = f"Hello {passenger.get('name')},\n\nAttached is your boarding pass for flight {passenger.get('flight')}, seat {passenger.get('seat')}.\n\nSafe travels."
    msg.set_content(body)

    # Attach PNG
    img_bytes = buf.getvalue()
    msg.add_attachment(img_bytes, maintype='image', subtype='png', filename=f"boardingpass_{passenger.get('passport')}.png")

    # Log attempt
    log_event({
        'type': 'email_send_attempt',
        'passport': passenger.get('passport'),
        'to': passenger.get('email'),
        'smtp_host': smtp_host,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    })

    # Send
    if use_ssl:
        smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
    else:
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        smtp.ehlo()
        if os.getenv('SMTP_STARTTLS', 'false').lower() in ('1','true','yes'):
            smtp.starttls()
            smtp.ehlo()

    try:
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)
        # success log
        log_event({
            'type': 'email_sent',
            'passport': passenger.get('passport'),
            'to': passenger.get('email'),
            'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'status': 'ok'
        })
    except Exception as e:
        # failure log
        log_event({
            'type': 'email_sent',
            'passport': passenger.get('passport'),
            'to': passenger.get('email'),
            'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'status': 'error',
            'detail': str(e)
        })
        raise
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


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

# Serve frontend files (single, canonical handlers)
@app.route("/", defaults={'path': 'index.html'})
@app.route("/<path:path>")
def index(path):
    try:
        # If the requested path doesn't exist or is a directory, fall back to the
        # canonical `index.html` and ensure we send it with an HTML mimetype so
        # browsers correctly render the page (some clients may otherwise treat
        # unknown responses as plain text).
        full_path = os.path.join(FRONTEND_DIR, path)
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            return send_from_directory(FRONTEND_DIR, "index.html", mimetype='text/html')

        # If an explicit HTML file was requested, ensure the response is
        # delivered as text/html.
        if path.lower().endswith('.html') or path.lower().endswith('.htm'):
            return send_from_directory(FRONTEND_DIR, path, mimetype='text/html')

        # Otherwise allow Flask to guess the mimetype for static assets.
        return send_from_directory(FRONTEND_DIR, path)
    except Exception:
        return send_from_directory(FRONTEND_DIR, "index.html", mimetype='text/html')


@app.route("/style.css")
def style():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/checkin")
def checkin():
    return send_from_directory(FRONTEND_DIR, "checkin.html", mimetype="text/html")


@app.route("/lookup")
def lookup():
    return send_from_directory(FRONTEND_DIR, "lookup.html", mimetype="text/html")


@app.route("/login")
def login():
    return send_from_directory(FRONTEND_DIR, "login.html", mimetype="text/html")


@app.route("/passenger")
def passenger():
    return send_from_directory(FRONTEND_DIR, "passenger.html", mimetype="text/html")


@app.route('/admin/checkins.html')
def admin_checkins_page():
    if not _has_admin_session():
        return redirect('/admin-login.html')
    return send_from_directory(ADMIN_DIR, 'checkins.html', mimetype='text/html')


@app.route('/admin/payments.html')
def admin_payments_page():
    if not _has_admin_session():
        return redirect('/admin-login.html')
    return send_from_directory(ADMIN_DIR, 'payments.html', mimetype='text/html')


@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), path)


# --- Admin Enhancement API Endpoints -------------------------------------------------

@app.route('/api/bookings/<booking_id>/refund', methods=['POST'])
@require_admin
def refund_booking(booking_id):
    """Process refund for a booking."""
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
@require_admin
def update_seat_blocking(flight_number):
    """Update blocked seats for a flight."""
    try:
        data = request.get_json()
        blocked_seats = data.get('blocked_seats', [])
        
        # Load flights
        flights = flight_manager.load_flights()
        flight = next((f for f in flights if f.get('flight') == flight_number), None)
        
        if not flight:
            return jsonify({'error': 'Flight not found'}), 404
        
        # Update blocked seats
        flight['blocked_seats'] = blocked_seats
        
        # Save flights
        flight_manager.save_flights(flights)
        
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
@require_admin
def update_passenger_notes(passport):
    """Update admin notes for a passenger."""
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
        save_passengers_to_file()
        
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
@require_admin
def export_data(export_type):
    """
    Export comprehensive data as CSV with all relevant details.
    Supports: passengers, flights, bookings
    Data reflects real-time state when exported.
    """
    try:
        import csv
        from io import StringIO
        
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


@app.route('/api/sessions', methods=['GET'])
def api_get_sessions():
    """Get active user sessions for admin dashboard"""
    try:
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


# Simple CORS for local development
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,OPTIONS"
    return resp

# Serve the SPA index at '/'
@app.route('/')
def _serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

if __name__ == "__main__":
    # Load persisted passengers into memory when starting the server
    try:
        if os.path.exists(PASSENGER_FILE):
            with open(PASSENGER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f) or []
                if isinstance(data, list):
                    passengers.clear()
                    passengers.extend(data)
    except Exception:
        pass

    app.run(debug=True, host="127.0.0.1", port=5000)


# ============================================================
# ACTIVITY TRACKING ENDPOINTS
# ============================================================

@app.route('/api/activities', methods=['GET'])
def api_get_activities():
    """Get all recorded activities (admin only)"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    activity_type = request.args.get('type')  # Optional filter: booking, payment, checkin, flight_status
    limit = int(request.args.get('limit', 100))
    
    activities = get_activities(activity_type, limit)
    return jsonify({'activities': activities, 'total': len(activities)}), 200

@app.route('/api/activities/bookings', methods=['GET'])
def api_get_bookings_activities():
    """Get all booking activities (admin only)"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    bookings = get_bookings_log()
    return jsonify({'bookings': bookings, 'total': len(bookings)}), 200

@app.route('/api/activities/checkins', methods=['GET'])
def api_get_checkins_activities():
    """Get all check-in activities (admin only)"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    checkins = get_checkins_log()
    return jsonify({'checkins': checkins, 'total': len(checkins)}), 200

@app.route('/api/activities/payments', methods=['GET'])
def api_get_payments_activities():
    """Get all payment activities (admin only)"""
    session = _require_session(request, require_role='admin')
    if not session:
        return jsonify({'error': 'admin_auth_required'}), 401
    
    payments = get_payments_log()
    return jsonify({'payments': payments, 'total': len(payments)}), 200

@app.route('/api/activities/log', methods=['POST'])
def api_log_activity():
    """Log a new activity (called from frontend)"""
    data = request.get_json() or {}
    activity_type = data.get('type')
    activity_data = data.get('data', {})
    
    if not activity_type:
        return jsonify({'error': 'activity_type_required'}), 400
    
    logged = log_activity(activity_type, activity_data)
    if logged:
        return jsonify({'status': 'ok', 'activity': logged}), 201
    return jsonify({'error': 'failed_to_log'}), 500
# ...existing code...