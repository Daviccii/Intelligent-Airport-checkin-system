"""
Update flights.json with current dates and varied statuses for live monitoring
"""
import json
from datetime import datetime, timedelta, timezone
import random
import os

def update_flights_for_live_monitoring():
    """Update flights.json with current dates and realistic statuses"""
    
    flights_file = os.path.join(os.path.dirname(__file__), 'flights.json')
    
    # Load existing flights
    with open(flights_file, 'r', encoding='utf-8') as f:
        flights = json.load(f)
    
    now = datetime.now(timezone.utc)
    today = now.date()
    
    # Define time slots for today's flights
    time_slots = [
        (now + timedelta(hours=1), now + timedelta(hours=2)),      # 1 hour from now (incoming)
        (now + timedelta(hours=2), now + timedelta(hours=3)),      # 2 hours from now (outgoing)
        (now + timedelta(hours=3), now + timedelta(hours=4)),      # 3 hours from now (outgoing)
        (now + timedelta(hours=4), now + timedelta(hours=5)),      # 4 hours from now (outgoing)
        (now + timedelta(hours=5), now + timedelta(hours=6)),      # 5 hours from now (outgoing)
        (now - timedelta(hours=1), now),                         # 1 hour ago (arrived)
        (now - timedelta(hours=2), now - timedelta(hours=1)),     # 2 hours ago (arrived)
        (now + timedelta(hours=1.5), now + timedelta(hours=2.5)), # 1.5 hours from now (delayed)
        (now + timedelta(hours=2.5), now + timedelta(hours=3.5)), # 2.5 hours from now (delayed)
    ]
    
    # Status distribution
    statuses = ['scheduled', 'boarding', 'departed', 'arrived', 'delayed', 'cancelled']
    status_weights = [0.4, 0.15, 0.15, 0.15, 0.15, 0.05]
    
    # Routes
    routes = [
        ('NBO', 'MBA'), ('MBA', 'NBO'), ('NBO', 'KIS'), ('KIS', 'NBO'),
        ('NBO', 'EDL'), ('EDL', 'NBO'), ('NBO', 'JNB'), ('JNB', 'NBO'),
        ('NBO', 'EBB'), ('EBB', 'NBO'), ('NBO', 'DAR'), ('DAR', 'NBO'),
        ('NBO', 'ADD'), ('ADD', 'NBO'), ('NBO', 'LHR'), ('LHR', 'NBO')
    ]
    
    updated_flights = []
    flight_num = 500
    
    for i, (dep_time, arr_time) in enumerate(time_slots):
        # Create multiple flights per time slot
        for j in range(3):  # 3 flights per time slot
            origin, dest = routes[i % len(routes)]
            
            # Determine status based on time
            if dep_time < now:
                status = 'arrived'
            elif arr_time < now:
                status = 'departed'
            else:
                status = random.choices(statuses, weights=status_weights)[0]
            
            # Add some delays
            delay_minutes = 0
            if status == 'delayed':
                delay_minutes = random.choice([15, 30, 45, 60])
                actual_dep = dep_time + timedelta(minutes=delay_minutes)
                actual_arr = arr_time + timedelta(minutes=delay_minutes)
            else:
                actual_dep = dep_time
                actual_arr = arr_time
            
            flight = {
                "id": f"FLT_LIVE{i:03d}{j}",
                "flight_number": f"KQ{flight_num}",
                "airline": "Kenya Airways",
                "aircraft": random.choice(["Boeing 737-800", "Embraer E190", "Boeing 787-8"]),
                "aircraft_type": random.choice(["Narrow-body", "Narrow-body", "Wide-body"]),
                "origin": origin,
                "destination": dest,
                "departure_time": actual_dep.isoformat(),
                "arrival_time": actual_arr.isoformat(),
                "capacity": random.choice([100, 120, 150, 180]),
                "gate": random.choice(["A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2"]),
                "status": status,
                "checkin_enabled": status in ['scheduled', 'boarding'],
                "delay_minutes": delay_minutes,
                "blocked_seats": {},
                "booked_seats": random.randint(0, 50),
                "crew_count": random.randint(4, 8),
                "catering_required": random.choice([True, False]),
                "time": actual_dep.isoformat(),
                "arrival": actual_arr.isoformat()
            }
            
            updated_flights.append(flight)
            flight_num += 1
    
    # Save updated flights
    with open(flights_file, 'w', encoding='utf-8') as f:
        json.dump(updated_flights, f, indent=2)
    
    print(f"Updated {len(updated_flights)} flights with current dates and statuses")
    print(f"Flight status distribution:")
    status_counts = {}
    for f in updated_flights:
        status_counts[f['status']] = status_counts.get(f['status'], 0) + 1
    for status, count in status_counts.items():
        print(f"   {status}: {count}")
    
    print("Live monitoring ready!")
    
    return updated_flights

if __name__ == '__main__':
    update_flights_for_live_monitoring()