import json
import random
from datetime import datetime, timedelta

# Load existing flights
with open('flights.json', 'r') as f:
    flights = json.load(f)

# Get the last flight ID number
flight_ids = [int(f['id'].split('_')[2]) for f in flights if '_' in f['id'] and len(f['id'].split('_')) > 2]
last_id = max(flight_ids) if flight_ids else 0

# Airlines and aircraft types
airlines = [
    {"name": "Kenya Airways", "code": "KQ"},
    {"name": "Ethiopian Airlines", "code": "ET"},
    {"name": "Emirates", "code": "EK"},
    {"name": "British Airways", "code": "BA"},
    {"name": "Air France", "code": "AF"},
    {"name": "KLM", "code": "KL"},
    {"name": "Lufthansa", "code": "LH"},
    {"name": "Turkish Airlines", "code": "TK"},
    {"name": "Qatar Airways", "code": "QR"},
    {"name": "South African Airways", "code": "SA"}
]

aircraft = [
    "Boeing 737-800", "Boeing 777-300ER", "Boeing 787-9", "Airbus A350-900",
    "Airbus A330-300", "Embraer E190", "Boeing 767-300ER", "Airbus A320"
]

# New routes to add (from Nairobi)
new_routes = [
    # International routes
    {"origin": "NBO", "destination": "LHR", "duration_hours": 9, "duration_minutes": 30},
    {"origin": "NBO", "destination": "CDG", "duration_hours": 9, "duration_minutes": 15},
    {"origin": "NBO", "destination": "FRA", "duration_hours": 8, "duration_minutes": 45},
    {"origin": "NBO", "destination": "AMS", "duration_hours": 9, "duration_minutes": 0},
    {"origin": "NBO", "destination": "JFK", "duration_hours": 14, "duration_minutes": 30},
    {"origin": "NBO", "destination": "ORD", "duration_hours": 15, "duration_minutes": 0},
    {"origin": "NBO", "destination": "DXB", "duration_hours": 4, "duration_minutes": 45},
    {"origin": "NBO", "destination": "AUH", "duration_hours": 4, "duration_minutes": 30},
    {"origin": "NBO", "destination": "DOH", "duration_hours": 5, "duration_minutes": 15},
    {"origin": "NBO", "destination": "IST", "duration_hours": 6, "duration_minutes": 30},
    {"origin": "NBO", "destination": "BOM", "duration_hours": 5, "duration_minutes": 45},
    {"origin": "NBO", "destination": "DEL", "duration_hours": 6, "duration_minutes": 15},
    {"origin": "NBO", "destination": "SIN", "duration_hours": 9, "duration_minutes": 30},
    {"origin": "NBO", "destination": "BKK", "duration_hours": 9, "duration_minutes": 45},
    {"origin": "NBO", "destination": "HKG", "duration_hours": 11, "duration_minutes": 0},
    {"origin": "NBO", "destination": "ICN", "duration_hours": 12, "duration_minutes": 30},
    {"origin": "NBO", "destination": "CPT", "duration_hours": 5, "duration_minutes": 0},
    {"origin": "NBO", "destination": "GRU", "duration_hours": 11, "duration_minutes": 45},
    {"origin": "NBO", "destination": "MEX", "duration_hours": 16, "duration_minutes": 30},

    # Regional routes
    {"origin": "NBO", "destination": "DAR", "duration_hours": 1, "duration_minutes": 45},
    {"origin": "NBO", "destination": "EBB", "duration_hours": 2, "duration_minutes": 0},
    {"origin": "NBO", "destination": "KGL", "duration_hours": 1, "duration_minutes": 30},
    {"origin": "NBO", "destination": "ZNZ", "duration_hours": 1, "duration_minutes": 15},
    {"origin": "NBO", "destination": "HRE", "duration_hours": 3, "duration_minutes": 0},
    {"origin": "NBO", "destination": "LUN", "duration_hours": 2, "duration_minutes": 45},
    {"origin": "NBO", "destination": "LLW", "duration_hours": 2, "duration_minutes": 30},
    {"origin": "NBO", "destination": "TNR", "duration_hours": 3, "duration_minutes": 45},
    {"origin": "NBO", "destination": "NLA", "duration_hours": 2, "duration_minutes": 15},

    # Return flights (reverse routes)
    {"origin": "LHR", "destination": "NBO", "duration_hours": 8, "duration_minutes": 45},
    {"origin": "CDG", "destination": "NBO", "duration_hours": 8, "duration_minutes": 30},
    {"origin": "FRA", "destination": "NBO", "duration_hours": 8, "duration_minutes": 0},
    {"origin": "AMS", "destination": "NBO", "duration_hours": 8, "duration_minutes": 15},
    {"origin": "JFK", "destination": "NBO", "duration_hours": 13, "duration_minutes": 45},
    {"origin": "ORD", "destination": "NBO", "duration_hours": 14, "duration_minutes": 15},
    {"origin": "DXB", "destination": "NBO", "duration_hours": 5, "duration_minutes": 0},
    {"origin": "AUH", "destination": "NBO", "duration_hours": 4, "duration_minutes": 45},
    {"origin": "DOH", "destination": "NBO", "duration_hours": 5, "duration_minutes": 30},
    {"origin": "IST", "destination": "NBO", "duration_hours": 6, "duration_minutes": 45},
    {"origin": "BOM", "destination": "NBO", "duration_hours": 6, "duration_minutes": 0},
    {"origin": "DEL", "destination": "NBO", "duration_hours": 6, "duration_minutes": 30},
    {"origin": "SIN", "destination": "NBO", "duration_hours": 8, "duration_minutes": 45},
    {"origin": "BKK", "destination": "NBO", "duration_hours": 9, "duration_minutes": 0},
    {"origin": "HKG", "destination": "NBO", "duration_hours": 10, "duration_minutes": 15},
    {"origin": "ICN", "destination": "NBO", "duration_hours": 11, "duration_minutes": 45},
    {"origin": "CPT", "destination": "NBO", "duration_hours": 5, "duration_minutes": 15},
    {"origin": "GRU", "destination": "NBO", "duration_hours": 11, "duration_minutes": 0},
    {"origin": "MEX", "destination": "NBO", "duration_hours": 15, "duration_minutes": 45},
]

# Generate flights for the next 30 days
base_date = datetime(2026, 1, 18)  # Current date + 1 day
gates = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3"]

new_flights = []
for i in range(30):  # 30 days
    current_date = base_date + timedelta(days=i)

    for route in new_routes:
        # Add 1-2 flights per route per day
        num_flights = random.randint(1, 2)

        for j in range(num_flights):
            last_id += 1
            flight_id = f"FLT_INT{last_id:03d}"

            # Random departure time between 6 AM and 10 PM
            hour = random.randint(6, 22)
            minute = random.choice([0, 15, 30, 45])
            departure_time = current_date.replace(hour=hour, minute=minute)

            # Calculate arrival time
            arrival_time = departure_time + timedelta(
                hours=route["duration_hours"],
                minutes=route["duration_minutes"]
            )

            # Select airline (prefer Kenya Airways for routes from NBO)
            if route["origin"] == "NBO":
                airline = random.choice([airlines[0]] + airlines)  # Bias towards Kenya Airways
            else:
                airline = random.choice(airlines)

            flight_number = f"{airline['code']}{random.randint(100, 999)}"

            flight = {
                "id": flight_id,
                "flight_number": flight_number,
                "airline": airline["name"],
                "aircraft": random.choice(aircraft),
                "origin": route["origin"],
                "destination": route["destination"],
                "departure_time": departure_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "arrival_time": arrival_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "capacity": random.choice([150, 200, 250, 300, 350]),
                "gate": random.choice(gates),
                "status": "scheduled",
                "checkin_enabled": True,
                "delay_minutes": 0,
                "blocked_seats": {},
                "booked_seats": 0,
                "crew_count": random.randint(4, 12),
                "catering_required": True,
                "time": departure_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "arrival": arrival_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }

            new_flights.append(flight)

# Add new flights to existing flights
all_flights = flights + new_flights

# Save updated flights
with open('flights.json', 'w') as f:
    json.dump(all_flights, f, indent=2)

print(f"Added {len(new_flights)} new flights")
print(f"Total flights: {len(all_flights)}")

# Analyze new routes
routes = {}
for f in all_flights:
    key = f['origin'] + '-' + f['destination']
    if key not in routes:
        routes[key] = {'count': 0, 'dates': set()}
    routes[key]['count'] += 1
    routes[key]['dates'].add(f['departure_time'].split('T')[0])

print("\nUpdated Routes:")
for route, data in sorted(routes.items()):
    dates = sorted(data['dates'])
    print(f'{route}: {data["count"]} flights')