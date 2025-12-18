#!/usr/bin/env python3
"""
Simulate active user sessions for the SmartFly dashboard
This creates realistic session data in sessions.json
"""

import json
import random
from datetime import datetime, timedelta

# Load users from users.json
try:
    with open('users.json', 'r') as f:
        users_data = json.load(f)
except:
    users_data = {}

# Create active sessions (10-20 random users)
sessions = {}
current_time = datetime.utcnow()

actions = [
    'Logged in',
    'Viewing bookings',
    'Searching flights',
    'Processing payment',
    'Checking in',
    'Updating profile',
    'Booking flight',
    'Adding baggage',
    'Viewing dashboard',
    'Managing account'
]

# Select 15 random users to have active sessions
user_items = list(users_data.items())
if len(user_items) > 0:
    selected_users = random.sample(user_items, min(15, len(user_items)))
    
    for i, (username, user_info) in enumerate(selected_users):
        session_id = f"sess_{i+1:04d}"
        
        # Random activity time within last 15 minutes
        minutes_ago = random.randint(0, 15)
        last_activity = (current_time - timedelta(minutes=minutes_ago)).isoformat() + 'Z'
        created_minutes_ago = minutes_ago + random.randint(5, 30)
        created_at = (current_time - timedelta(minutes=created_minutes_ago)).isoformat() + 'Z'
        
        # Determine user type
        membership = user_info.get('membership_tier', 'local')
        if membership in ['platinum', 'gold']:
            role = 'premium'
        else:
            role = 'user'
        
        # Some users are admins
        if i < 2:
            role = 'admin'
        
        sessions[session_id] = {
            'user_id': user_info.get('user_id', f'user_{i}'),
            'username': username,
            'user_name': user_info.get('full_name', username),
            'email': user_info.get('email', ''),
            'role': role,
            'membership_tier': membership,
            'last_activity': last_activity,
            'last_action': random.choice(actions),
            'created_at': created_at,
            'ip_address': f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

# Save sessions to file
with open('sessions.json', 'w') as f:
    json.dump(sessions, f, indent=2)

print(f"✅ Created {len(sessions)} active user sessions")
print(f"   - Admin users: {sum(1 for s in sessions.values() if s['role'] == 'admin')}")
print(f"   - Premium users: {sum(1 for s in sessions.values() if s['role'] == 'premium')}")
print(f"   - Regular users: {sum(1 for s in sessions.values() if s['role'] == 'user')}")
print(f"\n💡 Sessions saved to sessions.json")
print(f"   Restart the Flask server to see active users in the dashboard!")
