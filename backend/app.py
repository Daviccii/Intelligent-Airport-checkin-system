# ...existing code...
from flask import Flask, request, jsonify, send_from_directory, redirect
from security_utils import security_manager, require_admin, sanitize_input, validate_passport
from flight_manager import FlightManager
import json
import os
import threading
from PIL import Image, ImageChops, ImageStat
import io
import qrcode
from flask import send_file
import smtplib
from email.message import EmailMessage
# Load .env for local development if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except Exception:
    pass
import random
from datetime import datetime, timedelta, timezone
import bcrypt
import time
from flask import Response, stream_with_context

PASSENGER_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "passengers.json"))
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
FACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "face_store"))
EVENTS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "events.json"))
ACCESS_CODES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "access_codes.json"))
ADMIN_USERS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin_users.json"))
FLIGHTS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "flights.json"))
BOARDING_STATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "boarding_state.json"))
OPENAPI_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "openapi.json"))
HOLDS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "holds.json"))

# Try to initialize Redis/RQ if configured
RQ_QUEUE = None
try:
    import redis as _redis
    from rq import Queue as _Queue
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    _redis_conn = _redis.from_url(REDIS_URL)
    RQ_QUEUE = _Queue('default', connection=_redis_conn)
except Exception:
    RQ_QUEUE = None


# Ensure face_store exists
if not os.path.exists(FACE_DIR):
    try:
        os.makedirs(FACE_DIR, exist_ok=True)
    except Exception:
        pass

# Load passengers if file exists
if os.path.exists(PASSENGER_FILE):
    with open(PASSENGER_FILE, "r") as file:
        passengers = json.load(file)
else:
    passengers = []

# Ensure events file exists
if not os.path.exists(EVENTS_FILE):
    try:
        with open(EVENTS_FILE, 'w') as f:
            json.dump([], f)
    except Exception:
        pass

# Ensure access codes file exists
if not os.path.exists(ACCESS_CODES_FILE):
    try:
        with open(ACCESS_CODES_FILE, 'w') as f:
            json.dump({}, f)
    except Exception:
        pass

# Ensure flights file exists
if not os.path.exists(FLIGHTS_FILE):
    try:
        with open(FLIGHTS_FILE, 'w') as f:
            json.dump([], f)
    except Exception:
        pass

def _load_flights():
    try:
        with open(FLIGHTS_FILE, 'r') as f:
            return json.load(f) or []
    except Exception:
        return []

def _save_flights(flights: list):
    try:
        with open(FLIGHTS_FILE, 'w') as f:
            json.dump(flights, f, indent=2)
    except Exception:
        pass


def _load_boarding_state():
    try:
        if os.path.exists(BOARDING_STATE_FILE):
            with open(BOARDING_STATE_FILE, 'r') as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_boarding_state(state: dict):
    try:
        with open(BOARDING_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def _parse_time_field(timestr: str):
    """Try to parse a provided time string into an ISO 8601 UTC-ish string for storage.
    Accepts ISO formats or 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DD HH:MM'. Returns string or raises ValueError.
    """
    if not timestr:
        raise ValueError('time required')
    # normalize space -> T
    s = timestr.strip()
    if ' ' in s and 'T' not in s:
        s = s.replace(' ', 'T')
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # last resort: try adding seconds
        try:
            dt = datetime.fromisoformat(s + ':00')
        except Exception:
            raise ValueError('invalid time format, use ISO 8601 or YYYY-MM-DD HH:MM')
    # If datetime is naive, assume local timezone then convert to UTC
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        try:
            dt = dt.replace(tzinfo=local_tz)
        except Exception:
            # fallback: assume UTC
            dt = dt.replace(tzinfo=timezone.utc)
    # convert to UTC and store as ISO with Z
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.isoformat().replace('+00:00', 'Z')


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

def save_passengers():
    with open(PASSENGER_FILE, "w") as file:
        json.dump(passengers, file, indent=4)

def find_duplicate(passport, flight):
    return any(p.get("passport") == passport and p.get("flight") == flight for p in passengers)

app = Flask(__name__, static_folder=FRONTEND_DIR)

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


@app.route('/api/bookings', methods=['GET'])
def api_bookings():
    """Return bookings: admin sees all, passenger sees only their own."""
    session = _require_session(request)
    if not session:
        return jsonify({'error': 'unauthorized'}), 401
    if session.get('role') == 'admin':
        # enrich with flight times
        flights = {f.get('flight'): f for f in _load_flights()}
        enriched = []
        for p in passengers:
            pe = p.copy()
            f = flights.get(pe.get('flight'))
            if f:
                pe['_flight_time'] = f.get('time')
            enriched.append(pe)
        return jsonify({'bookings': enriched}), 200
    # passenger
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
        flights = _load_flights()
        # enrich with passenger counts
        counts = {}
        for p in passengers:
            f = p.get('flight')
            if not f:
                continue
            counts[f] = counts.get(f, 0) + 1
        for fl in flights:
            flnum = fl.get('flight')
            fl['bookings'] = counts.get(flnum, 0)
        return jsonify({'flights': flights}), 200

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


@app.route('/api/request_code', methods=['POST'])
def api_request_code():
    """Request a one-time access code to be sent to the passenger's email on file.
    Body: { passport: str }
    """
    data = request.get_json() or {}
    passport = (data.get('passport') or '').strip()
    if not passport:
        return jsonify({'error': 'passport required'}), 400

    p = next((x for x in passengers if x.get('passport') == passport), None)
    if not p:
        return jsonify({'error': 'passenger not found'}), 404

    email = p.get('email')
    if not email:
        # No email on file; advise contacting an agent or use master password
        return jsonify({'error': 'no_email', 'detail': 'no email on file for this passenger; contact agent or provide master password'}), 400

    # generate and store code
    code, expires = _set_code_for_passport(passport)

    # send code by email (best effort)
    try:
        msg = EmailMessage()
        msg['Subject'] = f"Your access code for boarding pass"
        msg['From'] = os.getenv('SMTP_FROM') or os.getenv('SMTP_USER')
        msg['To'] = email
        body = f"Hello {p.get('name')},\n\nYour one-time access code is: {code}\nIt will expire at {expires} (UTC).\n\nIf you did not request this, contact support."
        msg.set_content(body)

        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT') or 0)
        use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')

        if not (smtp_host and smtp_port):
            # can't send, but code is still set; inform caller
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
                        ok = bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
                    except Exception:
                        ok = False
                else:
                    ok = (password == stored)
            except Exception:
                ok = False
            if ok:
                try:
                    admin_ttl = float(os.getenv('ADMIN_SESSION_TTL_SECONDS', '3600'))
                except Exception:
                    admin_ttl = 3600.0
                token, expires = _create_session('admin', None, ttl_seconds=admin_ttl)
                log_event({'type': 'login', 'role': 'admin', 'username': username, 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                return jsonify({'token': token, 'role': 'admin', 'expires': expires}), 200

        return jsonify({'error': 'invalid_credentials'}), 403

    return jsonify({'error': 'unknown_role'}), 400


@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.headers.get('X-SESSION') or request.cookies.get('session')
    if token:
        _delete_session(token)
    return jsonify({'status': 'ok'})


def _require_session(request, require_role=None):
    token = request.headers.get('X-SESSION') or request.cookies.get('session')
    entry = _get_session(token)
    if not entry:
        return None
    if require_role and entry.get('role') != require_role:
        return None
    return entry


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
    # Serve a simple server-rendered login page; show optional error message via query param
    err = request.args.get('error')
    msg = ''
    if err:
        msg = '<p style="color:crimson">Invalid credentials, please try again.</p>'
    html = f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Login</title><link rel="stylesheet" href="/style.css"></head>
<body><main class="container" style="max-width:420px;margin:4rem auto;padding:2rem;background:#fff;border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,0.08)">
<h2>Admin Login</h2>
{msg}
<form method="post" action="/admin/login">
<div style="margin:.5rem 0"><label>Username<br/><input name="username" required></label></div>
<div style="margin:.5rem 0"><label>Password<br/><input name="password" type="password" required></label></div>
<div style="margin-top:1rem"><button type="submit" class="btn primary">Sign in</button></div>
</form>
</main></body></html>'''
    return html


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
    width, height = 800, 400
    bg = Image.new('RGB', (width, height), color=(255,255,255))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(bg)
    # Try to load a default font; fallback to built-in
    try:
        font = ImageFont.truetype('arial.ttf', 24)
        font_small = ImageFont.truetype('arial.ttf', 18)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw text
    draw.text((24,24), f"Boarding Pass", fill=(11,116,222), font=font)
    draw.text((24,80), f"Name: {p.get('name')}", fill=(0,0,0), font=font_small)
    draw.text((24,120), f"Passport: {p.get('passport')}", fill=(0,0,0), font=font_small)
    draw.text((24,160), f"Flight: {p.get('flight')}", fill=(0,0,0), font=font_small)
    draw.text((24,200), f"Seat: {p.get('seat')}", fill=(0,0,0), font=font_small)

    # Generate QR code encoding a simple URL or payload
    qr_payload = f"pass:{p.get('passport')}|flight:{p.get('flight')}|seat:{p.get('seat')}"
    qr = qrcode.make(qr_payload).resize((200,200))
    bg.paste(qr, (width - 220, 80))
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
                RQ_QUEUE.enqueue('app.send_boarding_pass_email', passenger)
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
        return send_from_directory(FRONTEND_DIR, path)
    except Exception:
        return send_from_directory(FRONTEND_DIR, "index.html")


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


@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), path)

# Simple CORS for local development
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
# ...existing code...