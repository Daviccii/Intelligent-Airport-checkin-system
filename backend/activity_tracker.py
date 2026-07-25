"""
Activity Tracker - Records all user actions (bookings, payments, check-ins)
for admin dashboard monitoring
"""

import json
import os
from datetime import datetime
from pathlib import Path

ACTIVITY_LOG_FILE = Path(__file__).parent / 'activity_log.json'

def log_activity(activity_type, data):
    """Log user activity to JSON file
    
    Args:
        activity_type: 'booking', 'payment', 'checkin', 'flight_status'
        data: dict with activity details
    """
    try:
        # Load existing activities
        activities = []
        if ACTIVITY_LOG_FILE.exists():
            with open(ACTIVITY_LOG_FILE, 'r') as f:
                content = f.read()
                if content.strip():
                    activities = json.loads(content)
        
        # Add new activity
        new_activity = {
            'id': len(activities) + 1,
            'type': activity_type,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        activities.append(new_activity)
        
        # Keep only last 1000 activities
        activities = activities[-1000:]
        
        # Save to file
        with open(ACTIVITY_LOG_FILE, 'w') as f:
            json.dump(activities, f, indent=2)
        
        return new_activity
    except Exception as e:
        print(f"Error logging activity: {e}")
        return None

def get_activities(activity_type=None, limit=100):
    """Retrieve activities from log
    
    Args:
        activity_type: Filter by type (optional)
        limit: Max number of activities to return
    
    Returns:
        List of activities
    """
    try:
        if not ACTIVITY_LOG_FILE.exists():
            return []
        
        with open(ACTIVITY_LOG_FILE, 'r') as f:
            content = f.read()
            if not content.strip():
                return []
            activities = json.loads(content)
        
        if activity_type:
            activities = [a for a in activities if a['type'] == activity_type]
        
        # Return most recent first
        return activities[-limit:][::-1]
    except Exception as e:
        print(f"Error retrieving activities: {e}")
        return []

def get_bookings_log():
    """Get all booking activities"""
    return get_activities('booking', limit=500)

def get_checkins_log():
    """Get all check-in activities"""
    return get_activities('checkin', limit=500)

def get_payments_log():
    """Get all payment activities"""
    return get_activities('payment', limit=500)

def get_bookings_log():
    """Get all booking activities"""
    return get_activities('booking', limit=500)

def save_activities(activities):
    """Save activities to file"""
    try:
        with open(ACTIVITY_LOG_FILE, 'w') as f:
            json.dump(activities, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving activities: {e}")
        return False

def clear_activities():
    """Clear all activities"""
    if ACTIVITY_LOG_FILE.exists():
        ACTIVITY_LOG_FILE.unlink()
