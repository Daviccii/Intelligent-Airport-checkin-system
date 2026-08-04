"""
One-time migration: rebuild passengers.json from bookings.json.

Why this exists
----------------
The in-memory `passengers` list in app.py was never being reloaded from
passengers.json on startup, so every server restart silently dropped all
existing passengers. The next booking made after a restart would then
overwrite passengers.json with just that one new record (see save_passengers()
in app.py, which dumps the whole in-memory list). That's why passengers.json
ended up with only a single stray entry despite bookings.json holding the
real, complete history.

bookings.json was never affected by this bug (_load_bookings()/_save_bookings()
always read/write the full file, no in-memory cache) so it remains the
complete, trustworthy source of truth for what bookings actually happened.

What this script does
----------------------
- READS bookings.json only. Never writes to it, never modifies it.
- WRITES a rebuilt passengers.json only. No other file is touched.
- Does not touch admin_users.json, staff.json, sessions.json, flights.json,
  or any application code beyond what's already been fixed in app.py.

Each booking becomes one passenger/check-in record, using the exact same
shape the live /api/bookings handler already produces for new bookings
(see the `passenger_record` block in app.py), so nothing about the schema
changes for any code that reads `passengers` afterward.

checked_in is set to False for every backfilled record. bookings.json has
no check-in field, so there's no way to know which of these passengers may
have actually checked in before the data was lost to the restart bug — that
information doesn't exist anywhere. Passengers will simply need to be
checked in again if that state mattered.

Run this once, in the same directory as app.py (so BASE_DIR-relative paths
resolve correctly), then restart the server.
"""
import json
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BOOKINGS_FILE = os.path.join(BASE_DIR, 'bookings.json')
PASSENGER_FILE = os.path.join(BASE_DIR, 'passengers.json')


def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f'Could not read {path}: {e}')
    return default


def _booking_name(b):
    name = (b.get('name') or b.get('passenger_name') or '').strip()
    if name:
        return name
    plist = b.get('passengers')
    if isinstance(plist, list) and plist:
        first = plist[0]
        if isinstance(first, str):
            return first.strip()
    return ''


def _booking_flight(b):
    return (b.get('flight') or b.get('flight_number') or 'N/A')


def _booking_amount(b):
    amount = b.get('amount')
    if amount is None:
        amount = b.get('total_amount')
    try:
        return float(amount) if amount is not None else 0
    except (TypeError, ValueError):
        return 0


def _booking_ref(b):
    return (b.get('booking_ref') or b.get('id') or
            b.get('booking_reference') or b.get('booking_id') or '')


def build_passengers_from_bookings(bookings):
    passengers = []
    seat_counters = {}  # per-flight incrementing seat, same logic app.py uses

    for b in bookings:
        name = _booking_name(b)
        flight = _booking_flight(b)
        if not name:
            # Nothing usable to show a staff member; skip rather than
            # inventing a placeholder passenger.
            continue

        seat_counters[flight] = seat_counters.get(flight, 0) + 1
        passport = (b.get('passport') or '').strip() or _booking_ref(b)

        record = {
            'name': name,
            'passport': passport,
            'flight': flight,
            'seat': seat_counters[flight],
            'email': b.get('email'),
            'phone': b.get('phone'),
            'payment_method': b.get('payment_method'),
            'currency': b.get('currency'),
            'amount': _booking_amount(b),
            'checked_in': False,
        }
        passengers.append(record)

    return passengers


def main():
    bookings = _load_json(BOOKINGS_FILE, [])
    if not bookings:
        print(f'No bookings found at {BOOKINGS_FILE}; nothing to do.')
        return

    existing = _load_json(PASSENGER_FILE, [])
    print(f'Read {len(bookings)} bookings from {BOOKINGS_FILE}')
    print(f'Existing passengers.json currently has {len(existing)} record(s) — will be replaced')

    rebuilt = build_passengers_from_bookings(bookings)

    backup_path = PASSENGER_FILE + '.bak'
    if os.path.exists(PASSENGER_FILE):
        with open(PASSENGER_FILE, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        print(f'Backed up existing passengers.json to {backup_path}')

    with open(PASSENGER_FILE, 'w', encoding='utf-8') as f:
        json.dump(rebuilt, f, indent=4)

    print(f'Wrote {len(rebuilt)} passenger records to {PASSENGER_FILE}')
    print('Restart the server so the fixed startup loader picks this up.')


if __name__ == '__main__':
    main()