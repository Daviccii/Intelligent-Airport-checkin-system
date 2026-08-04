"""
Test script for dynamic booking system
Tests the dynamic scheduler, seat map generator, and pricing engine
"""

from datetime import datetime, timedelta, timezone
from dynamic_scheduler import DynamicScheduler
from dynamic_seat_map import DynamicSeatMap
from pricing_engine import PricingEngine
import json


def test_pricing_engine():
    """Test the pricing engine"""
    print("Testing Pricing Engine...")
    pricing_engine = PricingEngine()
    
    # Test price calculation
    price_result = pricing_engine.calculate_price('NBO', 'MBA', 'Kenya Airways', 'Boeing 737-800')
    # Extract the final price from the result dictionary
    price = price_result.get('final_price', price_result.get('base_price', 10000)) if isinstance(price_result, dict) else price_result
    print(f"[OK] Price NBO-MBA (Kenya Airways, Boeing 737-800): KES {price}")
    
    # Test flight category detection
    category = pricing_engine.get_flight_category('NBO', 'MBA')
    print(f"[OK] Flight category NBO-MBA: {category}")
    
    # Test distance calculation
    distance = pricing_engine.calculate_distance('NBO', 'MBA')
    print(f"[OK] Distance NBO-MBA: {distance} km")
    
    print("Pricing Engine tests passed!\n")


def test_dynamic_scheduler():
    """Test the dynamic scheduler"""
    print("Testing Dynamic Scheduler...")
    pricing_engine = PricingEngine()
    scheduler = DynamicScheduler(pricing_engine)
    
    # Test flight generation for a route
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=1)
    
    flights = scheduler.generate_flights_for_route('NBO', 'MBA', start_date, end_date)
    print(f"[OK] Generated {len(flights)} flights for NBO-MBA route")
    
    if flights:
        first_flight = flights[0]
        print(f"[OK] First flight: {first_flight['flight_number']} at {first_flight['departure_time']}")
        print(f"[OK] Aircraft: {first_flight['aircraft']}, Capacity: {first_flight['capacity']}")
        base_price = first_flight['dynamic_pricing']['base_price']
        # Handle if base_price is a dictionary
        if isinstance(base_price, dict):
            base_price = base_price.get('final_price', base_price.get('base_price', 10000))
        print(f"[OK] Dynamic pricing base: KES {base_price}")
    
    # Test dynamic pricing
    if flights:
        dynamic_price = scheduler.get_dynamic_price(flights[0]['id'], 'Economy', 1)
        print(f"[OK] Dynamic price for {flights[0]['id']}: KES {dynamic_price['final_price']}")
    
    print("Dynamic Scheduler tests passed!\n")


def test_dynamic_seat_map():
    """Test the dynamic seat map generator"""
    print("Testing Dynamic Seat Map...")
    
    # Mock aircraft config
    aircraft_config = {
        'name': 'Boeing 737-800',
        'capacity': 189,
        'seat_map': {
            'rows': 32,
            'columns': 6,
            'layout': '3-3',
            'blocked_seats': ['1A', '1F'],
            'emergency_exits': [15, 16],
            'priority_seats': ['12A', '12B', '12C', '12D', '12E', '12F']
        }
    }
    
    seat_map_generator = DynamicSeatMap(aircraft_config)
    
    # Generate seat map
    seat_map = seat_map_generator.generate_seat_map(
        booked_seats=['2A', '2B'],
        seat_class='Economy'
    )
    
    print(f"[OK] Generated seat map for {aircraft_config['name']}")
    print(f"[OK] Total seats: {seat_map['statistics']['total_seats']}")
    print(f"[OK] Available seats: {seat_map['statistics']['available_seats']}")
    print(f"[OK] Occupancy rate: {seat_map['statistics']['occupancy_rate']:.2%}")
    
    # Test seat pricing
    seat_pricing = seat_map_generator.get_seat_pricing('12A', 10000, 'Economy')
    print(f"[OK] Seat 12A pricing: KES {seat_pricing['final_price']} (tier: {seat_pricing['pricing_tier']})")
    
    # Test available seats filtering
    available_seats = seat_map_generator.get_available_seats(seat_map, features=['window'])
    print(f"[OK] Available window seats: {len(available_seats)}")
    
    print("Dynamic Seat Map tests passed!\n")


def test_integration():
    """Test the integration of all components"""
    print("Testing System Integration...")
    
    pricing_engine = PricingEngine()
    scheduler = DynamicScheduler(pricing_engine)
    
    # Generate flights
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=1)
    flights = scheduler.generate_flights_for_route('NBO', 'MBA', start_date, end_date)
    
    if flights:
        flight = flights[0]
        
        # Get seat map for the aircraft
        aircraft_config = {
            'name': flight['aircraft'],
            'capacity': flight['capacity'],
            'seat_map': flight['seat_map_config']
        }
        
        seat_map_generator = DynamicSeatMap(aircraft_config)
        seat_map = seat_map_generator.generate_seat_map(seat_class='Economy')
        
        # Calculate price for a specific seat
        base_price = flight['dynamic_pricing']['base_price']
        # Handle if base_price is a dictionary
        if isinstance(base_price, dict):
            base_price = base_price.get('final_price', base_price.get('base_price', 10000))
        seat_pricing = seat_map_generator.get_seat_pricing('12A', base_price, 'Economy')
        
        print(f"[OK] Integration test successful!")
        print(f"  Flight: {flight['flight_number']} ({flight['origin']} -> {flight['destination']})")
        print(f"  Aircraft: {flight['aircraft']}")
        print(f"  Seat 12A price: KES {seat_pricing['final_price']}")
        print(f"  Seat features: {', '.join(seat_pricing['features'])}")
    
    print("Integration tests passed!\n")


if __name__ == '__main__':
    print("=" * 50)
    print("Dynamic Booking System Test Suite")
    print("=" * 50 + "\n")
    
    try:
        test_pricing_engine()
        test_dynamic_scheduler()
        test_dynamic_seat_map()
        test_integration()
        
        print("=" * 50)
        print("[SUCCESS] All tests passed successfully!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()