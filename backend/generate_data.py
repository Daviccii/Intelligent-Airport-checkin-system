#!/usr/bin/env python3
"""
Data Generator for SmartFly Airlines System
Generates realistic data for:
- 200 Passengers
- 150 Users with membership tiers (local, gold, silver, platinum)
- 30+ Flights across multiple routes
"""

import json
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

# Common flight routes
ROUTES = [
    ("JFK", "LHR"), ("LAX", "CDG"), ("ORD", "LHR"), ("DFW", "CDG"),
    ("SFO", "NRT"), ("MIA", "MAD"), ("BOS", "LHR"), ("LAS", "CDG"),
    ("DEN", "AMS"), ("ATL", "LHR"), ("PHX", "MAD"), ("SEA", "NRT"),
    ("NYC", "LON"), ("LON", "NYC"), ("LAX", "NYC"), ("NYC", "LAX"),
    ("SFO", "LAX"), ("LAX", "HNL"), ("MIA", "CUN"), ("LAS", "LAX"),
    ("DEN", "LAX"), ("ORD", "LAX"), ("BOS", "MIA"), ("ATL", "MIA")
]

AIRLINES = [
    "United Airlines", "American Airlines", "Delta Airlines", "Southwest Airlines",
    "JetBlue Airways", "Alaska Airlines", "Spirit Airlines", "Frontier Airlines",
    "British Airways", "Lufthansa", "Air France", "KLM", "Iberia", "Ryanair",
    "Turkish Airlines", "Emirates", "Qatar Airways", "Singapore Airlines"
]

AIRCRAFT = [
    "Boeing 737", "Boeing 777", "Airbus A320", "Airbus A350", "Airbus A380",
    "Embraer E195", "Bombardier CRJ900", "Boeing 787", "Airbus A330", "Boeing 767"
]

MEMBERSHIP_TIERS = ["local", "gold", "silver", "platinum"]

def generate_passengers(count=200):
    """Generate realistic passenger data"""
    passengers = []
    flights = list(range(1, 35))  # Reference flight indices
    
    for i in range(count):
        passenger = {
            "id": f"PAX{i+1:04d}",
            "name": fake.name(),
            "passport": fake.bothify(text="??###???").upper(),
            "flight": f"FL{random.choice(flights):02d}",
            "seat": random.randint(1, 180),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
            "nationality": fake.country(),
            "checked_in": random.choice([True, False]),
            "boarding_time": (datetime.utcnow() + timedelta(hours=random.randint(1, 12))).isoformat() + "Z",
            "ticket_number": fake.bothify(text="UA####???###").upper(),
            "baggage_count": random.randint(1, 3),
            "seat_class": random.choice(["economy", "business", "first"]),
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat() + "Z"
        }
        passengers.append(passenger)
    
    return passengers

def generate_users(count=150):
    """Generate registered users with membership tiers"""
    users = {}
    membership_counts = {
        "local": int(count * 0.40),      # 40% local members
        "gold": int(count * 0.25),       # 25% gold
        "silver": int(count * 0.20),     # 20% silver
        "platinum": int(count * 0.15)    # 15% platinum
    }
    
    user_id = 1
    
    for tier, tier_count in membership_counts.items():
        for i in range(tier_count):
            username = fake.user_name()
            user_email = fake.email()
            
            users[username] = {
                "user_id": f"USR{user_id:04d}",
                "email": user_email,
                "full_name": fake.name(),
                "membership_tier": tier,
                "membership_joined": (datetime.utcnow() - timedelta(days=random.randint(1, 365))).isoformat() + "Z",
                "phone": fake.phone_number(),
                "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
                "nationality": fake.country(),
                "country": fake.country(),
                "city": fake.city(),
                "address": fake.address().replace("\n", ", "),
                "passport_number": fake.bothify(text="??###???").upper(),
                "password_hash": "$2b$12$abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "frequent_flyer_number": fake.bothify(text="FF####???###").upper(),
                "total_flights": random.randint(0, 150),
                "loyalty_points": random.randint(0, 50000),
                "preferred_airline": random.choice(AIRLINES),
                "preferred_seat": random.choice(["window", "aisle", "middle"]),
                "meal_preference": random.choice(["vegetarian", "vegan", "halal", "kosher", "regular"]),
                "special_requests": random.choice([None, "Extra legroom", "Wheelchair assistance", "Unaccompanied minor"]),
                "account_status": "active",
                "email_verified": True,
                "phone_verified": True,
                "two_factor_enabled": random.choice([True, False]),
                "newsletter_subscription": random.choice([True, False]),
                "last_login": (datetime.utcnow() - timedelta(hours=random.randint(1, 168))).isoformat() + "Z",
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 365))).isoformat() + "Z",
                "updated_at": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat() + "Z"
            }
            
            user_id += 1
    
    return users

def generate_flights(count=35):
    """Generate flight data with realistic information"""
    flights = []
    base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(count):
        origin, destination = random.choice(ROUTES)
        
        # Flight time with gaps (not all at same time)
        flight_time = base_time + timedelta(days=random.randint(0, 14), hours=random.randint(0, 23), minutes=random.choice([0, 15, 30, 45]))
        
        # Estimate arrival based on route distance (simplified)
        distance = random.randint(2, 12)  # Hours of flight
        arrival_time = flight_time + timedelta(hours=distance)
        
        flight = {
            "id": f"FLT{i+1:03d}",
            "flight_number": f"{random.choice(['UA', 'AA', 'DL', 'SW', 'B6', 'AS', 'F9', 'NK'])}{random.randint(1000, 9999)}",
            "airline": random.choice(AIRLINES),
            "aircraft": random.choice(AIRCRAFT),
            "origin": origin,
            "destination": destination,
            "departure_time": flight_time.isoformat() + "Z",
            "arrival_time": arrival_time.isoformat() + "Z",
            "capacity": random.choice([150, 180, 200, 220, 250, 350, 400]),
            "gate": f"{random.choice(['A', 'B', 'C', 'D', 'E'])}{random.randint(1, 15)}",
            "status": random.choice(["scheduled", "boarding", "delayed", "departed", "arrived"]),
            "checkin_enabled": random.choice([True, True, True, False]),
            "delay_minutes": random.randint(0, 120) if random.choice([True, False, False]) else 0,
            "blocked_seats": [random.randint(1, 180) for _ in range(random.randint(0, 10))],
            "booked_seats": random.randint(50, 200),
            "crew_count": random.randint(6, 12),
            "catering_required": True,
            "ground_equipment": ["tug", "stairs", "belt_loader"],
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 60))).isoformat() + "Z",
            "updated_at": (datetime.utcnow() - timedelta(hours=random.randint(0, 24))).isoformat() + "Z"
        }
        flights.append(flight)
    
    return flights

def main():
    """Generate all data files"""
    
    print("🚀 Generating SmartFly Airlines System Data...")
    print("-" * 60)
    
    # Generate passengers
    print("✈️  Generating 200 passengers...")
    passengers = generate_passengers(200)
    with open("passengers.json", "w") as f:
        json.dump(passengers, f, indent=2)
    print(f"   ✅ Created {len(passengers)} passenger records")
    
    # Generate users
    print("\n👥 Generating 150 registered users...")
    users = generate_users(150)
    
    # Separate users into different files
    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)
    
    # Also create admin_users.json with some users as admins
    admin_users = {}
    admin_list = list(users.items())[:10]  # First 10 users are admins
    for username, user_data in admin_list:
        admin_users[username] = {
            "password_hash": "$2b$12$abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "role": "admin",
            "permissions": ["manage_flights", "manage_passengers", "manage_users", "view_reports"],
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
    
    with open("admin_users.json", "w") as f:
        json.dump(admin_users, f, indent=2)
    
    print(f"   ✅ Created {len(users)} user accounts")
    print(f"      - Local Members: {sum(1 for u in users.values() if u['membership_tier'] == 'local')}")
    print(f"      - Gold Members: {sum(1 for u in users.values() if u['membership_tier'] == 'gold')}")
    print(f"      - Silver Members: {sum(1 for u in users.values() if u['membership_tier'] == 'silver')}")
    print(f"      - Platinum Members: {sum(1 for u in users.values() if u['membership_tier'] == 'platinum')}")
    print(f"      - Admin Users: {len(admin_users)}")
    
    # Generate flights
    print("\n🛫 Generating 35 flights...")
    flights = generate_flights(35)
    with open("flights.json", "w") as f:
        json.dump(flights, f, indent=2)
    print(f"   ✅ Created {len(flights)} flight records")
    
    # Generate bookings from passengers
    print("\n📋 Generating bookings from passenger data...")
    bookings = []
    for i, passenger in enumerate(passengers[:150]):  # Create bookings for most passengers
        booking = {
            "booking_id": f"BK{i+1:05d}",
            "passenger_id": passenger.get("id", f"PAX{i+1:04d}"),
            "passenger_name": passenger["name"],
            "email": passenger["email"],
            "flight_number": passenger["flight"],
            "origin": random.choice(ROUTES)[0],
            "destination": random.choice(ROUTES)[1],
            "departure_date": (datetime.utcnow() + timedelta(days=random.randint(1, 30))).isoformat() + "Z",
            "seat_assignment": passenger["seat"],
            "seat_class": passenger.get("seat_class", "economy"),
            "booking_reference": fake.bothify(text="????###").upper(),
            "total_amount": random.uniform(150, 2000),
            "currency": "USD",
            "payment_status": random.choice(["confirmed", "pending", "completed"]),
            "payment_method": random.choice(["credit_card", "debit_card", "paypal", "bank_transfer"]),
            "booking_status": random.choice(["confirmed", "pending", "cancelled"]),
            "passengers": [passenger["name"]],
            "special_requests": passenger.get("special_requests"),
            "baggage_allowance": random.randint(1, 3),
            "insurance_selected": random.choice([True, False]),
            "booking_date": (datetime.utcnow() - timedelta(days=random.randint(1, 60))).isoformat() + "Z",
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 60))).isoformat() + "Z"
        }
        bookings.append(booking)
    
    with open("bookings.json", "w") as f:
        json.dump(bookings, f, indent=2)
    print(f"   ✅ Created {len(bookings)} booking records")
    
    print("\n" + "=" * 60)
    print("✅ DATA GENERATION COMPLETE!")
    print("=" * 60)
    print("\nFiles created:")
    print("  📄 passengers.json - 200 passenger records")
    print("  📄 users.json - 150 registered user accounts")
    print("  📄 admin_users.json - 10 admin accounts")
    print("  📄 flights.json - 35 flight schedules")
    print("  📄 bookings.json - 150 booking records")
    print("\nSystem is now active with:")
    print(f"  ✈️  200 Passengers")
    print(f"  👥 150 Registered Users (40% local, 25% gold, 20% silver, 15% platinum)")
    print(f"  🛫 35 Flights across multiple routes")
    print(f"  📋 150 Bookings")
    print("\nYou can now:")
    print("  1. Start the backend: py app.py")
    print("  2. Open http://127.0.0.1:5000 to see flights in dropdown")
    print("  3. Admin dashboard will show all metrics populated")
    print("=" * 60)

if __name__ == "__main__":
    main()
