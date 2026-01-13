#!/usr/bin/env python3
"""
Initialization script to register booking endpoints with the Flask app.
Run this after app.py is created but before app.run()
"""

def register_booking_apis(app, _require_session_func):
    """Register booking, check-in, and revenue endpoints."""
    from booking_endpoints import register_booking_endpoints
    register_booking_endpoints(app, _require_session_func)
    print("[INFO] Booking endpoints registered successfully")

if __name__ == '__main__':
    print("This module should be imported, not run directly")
