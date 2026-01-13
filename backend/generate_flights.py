import json
from datetime import datetime, timedelta
import random

# Load existing flights
with open('flights.json', 'r', encoding='utf-8-sig') as f:
    existing_flights = json.load(f)

print(f'Current flights: {len(existing_flights)}')

# Popular routes with return flights
routes = [
    ('NBO', 'LHR', 'Kenya Airways', 'KQ', 8.5),
    ('LHR', 'NBO', 'Kenya Airways', 'KQ', 8.5),
    ('NBO', 'DXB', 'Emirates', 'EK', 4.5),
    ('DXB', 'NBO', 'Emirates', 'EK', 4.5),
    ('NBO', 'JNB', 'Kenya Airways', 'KQ', 4),
    ('JNB', 'NBO', 'Kenya Airways', 'KQ', 4),
    ('NBO', 'ADD', 'Ethiopian Airlines', 'ET', 2),
    ('ADD', 'NBO', 'Ethiopian Airlines', 'ET', 2),
    ('LHR', 'JFK', 'British Airways', 'BA', 8),
    ('JFK', 'LHR', 'British Airways', 'BA', 7),
    ('LHR', 'CDG', 'British Airways', 'BA', 1.5),
    ('CDG', 'LHR', 'Air France', 'AF', 1.5),
    ('DXB', 'LHR', 'Emirates', 'EK', 7),
    ('LHR', 'DXB', 'Emirates', 'EK', 7),
    ('DXB', 'JFK', 'Emirates', 'EK', 14),
    ('JFK', 'DXB', 'Emirates', 'EK', 13),
    ('JFK', 'LAX', 'American Airlines', 'AA', 6),
    ('LAX', 'JFK', 'Delta Air Lines', 'DL', 5.5),
    ('LAX', 'NRT', 'Japan Airlines', 'JL', 11),
    ('NRT', 'LAX', 'Japan Airlines', 'JL', 10),
    ('CDG', 'FRA', 'Air France', 'AF', 1.5),
    ('FRA', 'CDG', 'Lufthansa', 'LH', 1.5),
    ('FRA', 'MUC', 'Lufthansa', 'LH', 1),
    ('MUC', 'FRA', 'Lufthansa', 'LH', 1),
    ('AMS', 'LHR', 'KLM', 'KL', 1.5),
    ('LHR', 'AMS', 'British Airways', 'BA', 1.5),
    ('SIN', 'DXB', 'Singapore Airlines', 'SQ', 7),
    ('DXB', 'SIN', 'Emirates', 'EK', 7),
    ('SYD', 'SIN', 'Qantas', 'QF', 8),
    ('SIN', 'SYD', 'Singapore Airlines', 'SQ', 8),
    ('JNB', 'CPT', 'South African Airways', 'SA', 2),
    ('CPT', 'JNB', 'South African Airways', 'SA', 2),
    ('NRT', 'SIN', 'Singapore Airlines', 'SQ', 7),
    ('SIN', 'NRT', 'Singapore Airlines', 'SQ', 7),
    ('ADD', 'DXB', 'Ethiopian Airlines', 'ET', 3),
    ('DXB', 'ADD', 'Emirates', 'EK', 3),
]

aircraft_types = ['Boeing 787 Dreamliner', 'Boeing 777', 'Airbus A350', 'Airbus A380', 'Boeing 737', 'Airbus A320']

new_flights = []
flight_counter = len(existing_flights) + 1

# Generate flights for next 45 days (Jan 13 - Feb 26, 2026)
start_date = datetime(2026, 1, 13)

for days_ahead in range(45):
    current_date = start_date + timedelta(days=days_ahead)
    
    # Add 1-2 flights per route per day
    for origin, dest, airline, code, duration in routes:
        num_flights = random.randint(1, 2)
        
        for _ in range(num_flights):
            hour = random.choice([6, 8, 10, 12, 14, 16, 18, 20, 22])
            minute = random.choice([0, 15, 30, 45])
            
            departure = current_date.replace(hour=hour, minute=minute, second=0)
            arrival = departure + timedelta(hours=duration)
            
            capacity = random.choice([180, 220, 250, 300, 380])
            booked = random.randint(int(capacity * 0.2), int(capacity * 0.6))
            
            flight = {
                'id': f'FLT{flight_counter:03d}',
                'flight_number': f'{code}{100 + flight_counter}',
                'airline': airline,
                'aircraft': random.choice(aircraft_types),
                'origin': origin,
                'destination': dest,
                'departure_time': departure.isoformat() + 'Z',
                'arrival_time': arrival.isoformat() + 'Z',
                'capacity': capacity,
                'gate': f'{random.choice(["A", "B", "C", "D", "K", "J"])}{random.randint(1, 20)}',
                'status': 'scheduled',
                'checkin_enabled': True,
                'delay_minutes': 0,
                'blocked_seats': [],
                'booked_seats': booked,
                'crew_count': random.randint(6, 14),
                'catering_required': True,
                'time': departure.isoformat() + 'Z',
                'arrival': arrival.isoformat() + 'Z'
            }
            
            new_flights.append(flight)
            flight_counter += 1

all_flights = existing_flights + new_flights

with open('flights.json', 'w', encoding='utf-8') as f:
    json.dump(all_flights, f, indent=2, ensure_ascii=False)

print(f'Added {len(new_flights)} new flights')
print(f'Total flights: {len(all_flights)}')
print(f'Date range: {start_date.date()} to {(start_date + timedelta(days=44)).date()}')
print(f'Total routes: {len(routes)}')
print('\nSample routes added:')
for i, (origin, dest, airline, code, duration) in enumerate(routes[:10]):
    print(f'  {origin} → {dest} ({airline})')
