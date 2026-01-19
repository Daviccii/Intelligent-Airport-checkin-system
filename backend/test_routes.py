#!/usr/bin/env python3
import json

# Load flights
with open('flights.json', 'r') as f:
    flights = json.load(f)

# Check specific route
origin = 'NBO'
destination = 'DXB'
date = '2026-01-16'

matching = [f for f in flights 
           if f['origin'] == origin 
           and f['destination'] == destination 
           and f['departure_time'].startswith(date)]

print(f"\n=== Flight Check: {origin} → {destination} on {date} ===")
print(f"Found {len(matching)} flight(s)")

if matching:
    for f in matching:
        print(f"\n  Flight: {f['flight_number']}")
        print(f"    Time: {f['departure_time']}")
        print(f"    Airline: {f['airline']}")
        print(f"    Aircraft: {f['aircraft']}")

# Check all routes and dates
print(f"\n=== All Available Routes ===")
routes = {}
for f in flights:
    date = f['departure_time'].split('T')[0]
    key = f"{f['origin']}-{f['destination']}"
    if key not in routes:
        routes[key] = {'count': 0, 'dates': set()}
    routes[key]['count'] += 1
    routes[key]['dates'].add(date)

for route in sorted(routes.keys()):
    info = routes[route]
    dates_str = ', '.join(sorted(info['dates']))
    print(f"{route}: {info['count']} flights on {dates_str}")
