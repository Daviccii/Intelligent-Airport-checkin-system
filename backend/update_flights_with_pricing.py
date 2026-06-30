"""
Update flights.json with realistic pricing using the new pricing engine
"""

import json
from datetime import datetime, timedelta, timezone
import random
import os
import sys

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from pricing_engine import pricing_engine

def update_flights_with_pricing():
    """Update flights.json with realistic pricing"""
    
    flights_file = os.path.join(os.path.dirname(__file__), 'flights.json')
    
    # Load existing flights
    with open(flights_file, 'r', encoding='utf-8') as f:
        flights = json.load(f)
    
    now = datetime.now(timezone.utc)
    
    # Airline options
    airlines = ['SmartFly', 'Kenya Airways', 'JamboJet', 'Ethiopian Airlines', 'RwandAir', 'Emirates', 'Qatar Airways']
    
    # Aircraft options
    aircraft_options = ['Boeing 737-800', 'Embraer E190', 'Boeing 787-8', 'Airbus A320']
    
    # Seat classes
    seat_classes = ['Economy', 'Premium Economy', 'Business']
    
    updated_flights = []
    flight_num = 500
    
    # Create routes covering domestic, regional, and international
    routes = [
        # Domestic Kenya routes
        ('NBO', 'MBA'), ('MBA', 'NBO'), ('NBO', 'KIS'), ('KIS', 'NBO'),
        ('NBO', 'EDL'), ('EDL', 'NBO'), ('MBA', 'KIS'), ('KIS', 'MBA'),
        ('NBO', 'WIL'), ('WIL', 'NBO'), ('MBA', 'EDL'), ('EDL', 'MBA'),
        
        # Regional East Africa routes
        ('NBO', 'EBB'), ('EBB', 'NBO'), ('NBO', 'JRO'), ('JRO', 'NBO'),
        ('NBO', 'DAR'), ('DAR', 'NBO'), ('NBO', 'ADD'), ('ADD', 'NBO'),
        ('NBO', 'KGL'), ('KGL', 'NBO'), ('MBA', 'EBB'), ('EBB', 'MBA'),
        ('NBO', 'JNB'), ('JNB', 'NBO'), ('NBO', 'CPT'), ('CPT', 'NBO'),
        
        # International routes
        ('NBO', 'LHR'), ('LHR', 'NBO'), ('NBO', 'CDG'), ('CDG', 'NBO'),
        ('NBO', 'DXB'), ('DXB', 'NBO'), ('NBO', 'AMS'), ('AMS', 'NBO'),
        ('NBO', 'FRA'), ('FRA', 'NBO'), ('NBO', 'JFK'), ('JFK', 'NBO'),
        ('NBO', 'SIN'), ('SIN', 'NBO'), ('NBO', 'SYD'), ('SYD', 'NBO'),
        ('NBO', 'BKK'), ('BKK', 'NBO'), ('NBO', 'HKG'), ('HKG', 'NBO'),
        ('NBO', 'LAX'), ('LAX', 'NBO'), ('NBO', 'ORD'), ('ORD', 'NBO'),
        ('NBO', 'ATL'), ('ATL', 'NBO'), ('NBO', 'DXB'), ('DXB', 'NBO')
    ]
    
    # Time slots for flights throughout the day
    time_slots = []
    for hour in range(6, 22):  # 6 AM to 10 PM
        for minute in [0, 30]:
            time_slots.append(now.replace(hour=hour, minute=minute, second=0, microsecond=0))
    
    # Status distribution
    statuses = ['scheduled', 'boarding', 'departed', 'arrived', 'delayed', 'cancelled']
    status_weights = [0.35, 0.15, 0.15, 0.15, 0.15, 0.05]
    
    # Create flights for each route at different times
    for origin, dest in routes:
        for i, departure_time in enumerate(time_slots[:5]):  # 5 flights per route
            # Calculate arrival time based on distance
            pricing = pricing_engine.calculate_price(origin, dest, 'SmartFly', 'Boeing 737-800', 'Economy')
            duration_hours = pricing['duration']
            arrival_time = departure_time + timedelta(hours=duration_hours)
            
            # Determine status based on time
            if departure_time < now - timedelta(hours=2):
                status = 'arrived'
            elif departure_time < now:
                status = 'departed'
            elif departure_time < now + timedelta(hours=1):
                status = 'boarding'
            else:
                status = random.choices(statuses, weights=status_weights)[0]
            
            # Add delays for some flights
            delay_minutes = 0
            if status == 'delayed':
                delay_minutes = random.choice([15, 30, 45, 60])
                actual_dep = departure_time + timedelta(minutes=delay_minutes)
                actual_arr = arrival_time + timedelta(minutes=delay_minutes)
            else:
                actual_dep = departure_time
                actual_arr = arrival_time
            
            # Select airline and aircraft
            airline = random.choice(airlines)
            aircraft = random.choice(aircraft_options)
            seat_class = random.choice(seat_classes)
            
            # Calculate pricing for this specific flight
            flight_pricing = pricing_engine.calculate_price(origin, dest, airline, aircraft, seat_class)
            
            # Calculate capacity based on aircraft
            capacity_map = {
                'Boeing 737-800': 160,
                'Embraer E190': 100,
                'Boeing 787-8': 250,
                'Airbus A320': 180
            }
            capacity = capacity_map.get(aircraft, 150)
            
            flight = {
                "id": f"FLT_PRICED{flight_num:04d}",
                "flight_number": f"KQ{flight_num}",
                "airline": airline,
                "aircraft": aircraft,
                "aircraft_type": aircraft if 'Boeing 787' in aircraft or 'Airbus A330' in aircraft else 'Narrow-body',
                "origin": origin,
                "destination": dest,
                "departure_time": actual_dep.isoformat(),
                "arrival_time": actual_arr.isoformat(),
                "capacity": capacity,
                "gate": random.choice(["A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2"]),
                "status": status,
                "checkin_enabled": status in ['scheduled', 'boarding'],
                "delay_minutes": delay_minutes,
                "blocked_seats": {},
                "booked_seats": random.randint(0, capacity // 2),
                "crew_count": random.randint(4, 10),
                "catering_required": random.choice([True, False]),
                "time": actual_dep.isoformat(),
                "arrival": actual_arr.isoformat(),
                # Pricing information
                "base_price": flight_pricing['base_price'],
                "adjusted_price": flight_pricing['adjusted_price'],
                "final_price": flight_pricing['final_price'],
                "airline_multiplier": flight_pricing['airline_multiplier'],
                "aircraft_multiplier": flight_pricing['aircraft_multiplier'],
                "class_multiplier": flight_pricing['class_multiplier'],
                "taxes_and_fees": flight_pricing['taxes_and_fees'],
                "flight_category": flight_pricing['flight_category'],
                "distance": flight_pricing['distance'],
                "duration": flight_pricing['duration'],
                "currency": flight_pricing['currency'],
                "seat_class": seat_class,
                "is_return": False
            }
            
            updated_flights.append(flight)
            flight_num += 1
    
    # Save updated flights
    with open(flights_file, 'w', encoding='utf-8') as f:
        json.dump(updated_flights, f, indent=2)
    
    print(f"Updated {len(updated_flights)} flights with realistic pricing")
    
    # Print pricing statistics
    print(f"\nPricing Statistics:")
    category_prices = {}
    for f in updated_flights:
        cat = f['flight_category']
        if cat not in category_prices:
            category_prices[cat] = []
        category_prices[cat].append(f['final_price'])
    
    for cat, prices in category_prices.items():
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        print(f"{cat}:")
        print(f"  Average: KES {avg_price:,.0f}")
        print(f"  Range: KES {min_price:,.0f} - KES {max_price:,.0f}")
        print(f"  Count: {len(prices)}")
    
    # Print airline distribution
    print(f"\nAirline Distribution:")
    airline_counts = {}
    for f in updated_flights:
        airline = f['airline']
        airline_counts[airline] = airline_counts.get(airline, 0) + 1
    
    for airline, count in airline_counts.items():
        print(f"  {airline}: {count} flights")
    
    return updated_flights

if __name__ == '__main__':
    update_flights_with_pricing()