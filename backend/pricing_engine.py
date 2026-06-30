"""
Pricing Engine for SmartFly Airlines
Handles domestic/international detection, airline-based pricing, and location-based fare calculations
"""

import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class PricingEngine:
    """
    Comprehensive pricing system for airline operations
    - Detects domestic vs international flights
    - Calculates prices based on distance and airline
    - Handles Kenya-specific pricing rules
    """
    
    # Kenya domestic airports (Jomo Kenyatta and major airports)
    KENYA_AIRPORTS = {
        'NBO': 'Jomo Kenyatta International Airport',
        'MBA': 'Moi International Airport',
        'KIS': 'Kisumu International Airport',
        'EDL': 'Eldoret International Airport',
        'WIL': 'Wilson Airport',
        'LLK': 'Lokichoggio Airport',
        'GMV': 'Garissa Airport',
        'KEY': 'Keekorok Airport',
        'LOK': 'Lodwar Airport',
        'MSU': 'Manda Airport',
        'NYK': 'Nanyuki Airport',
        'VKG': 'Vipingo Airport',
        'RRG': 'Rongai Airport',
        'MUT': 'Mutomo Airport',
        'JKU': 'Jomo Kenyatta University Airport'
    }
    
    # East African airports (treated as regional domestic)
    EAST_AFRICAN_AIRPORTS = {
        'EBB': 'Entebbe International Airport',
        'JRO': 'Kilimanjaro International Airport',
        'DAR': 'Julius Nyerere International Airport',
        'ADD': 'Addis Ababa Bole International Airport',
        'KGL': 'Kigali International Airport',
        'MPM': 'Maputo International Airport',
        'LLW': 'Kamuzu International Airport',
        'HRE': 'Robert Gabriel Mugabe International Airport',
        'LUN': 'Kenneth Kaunda International Airport',
        'DZA': 'Ambouli International Airport'
    }
    
    # Airport coordinates (latitude, longitude) for distance calculation
    AIRPORT_COORDINATES = {
        # Kenya airports
        'NBO': (-1.3192, 36.9278),
        'MBA': (-4.0348, 39.5942),
        'KIS': (-0.0841, 34.6829),
        'EDL': (0.4511, 35.2364),
        'WIL': (-1.3211, 36.8165),
        'LLK': (4.2075, 35.8167),
        'GMV': (-0.4833, 39.6333),
        'KEY': (-1.8917, 35.0083),
        'LOK': (3.1333, 35.6167),
        'MSU': (-2.2667, 40.9833),
        'NYK': (0.0167, 37.0667),
        'VKG': (-3.7833, 39.9167),
        'RRG': (-2.3833, 37.6667),
        'MUT': (-1.7667, 38.0333),
        'JKU': (-1.1167, 37.0167),
        
        # East African airports
        'EBB': (0.0424, 32.4435),
        'JRO': (-3.4272, 37.0744),
        'DAR': (-6.8781, 39.2026),
        'ADD': (8.9779, 38.7993),
        'KGL': (-1.9686, 30.1395),
        'MPM': (-25.9208, 32.5726),
        'LLW': (-13.7895, 33.2740),
        'HRE': (-17.9318, 31.0928),
        'LUN': (-15.3308, 28.4527),
        'DZA': (11.5250, 42.8380),
        
        # International airports
        'JFK': (40.6413, -73.7781),
        'LHR': (51.4700, -0.4543),
        'CDG': (49.0097, 2.5479),
        'DXB': (25.2532, 55.3657),
        'AMS': (52.3105, 4.7683),
        'FRA': (50.0379, 8.5622),
        'SIN': (1.3644, 103.9915),
        'SYD': (-33.9399, 151.1753),
        'JNB': (-26.1367, 28.2411),
        'CPT': (-33.9715, 18.6021),
        'ORD': (41.9742, -87.9073),
        'LAX': (33.9416, -118.4085),
        'SFO': (37.6213, -122.3790),
        'ATL': (33.6407, -84.4277),
        'MIA': (25.7959, -80.2870),
        'BOS': (42.3656, -71.0096),
        'SEA': (47.4502, -122.3088),
        'DFW': (32.8998, -97.0403),
        'DEN': (39.8561, -104.6737),
        'LAS': (36.0840, -115.1537),
        'PHX': (33.4373, -112.0078),
        'IAD': (38.9531, -77.4565),
        'EWR': (40.6895, -74.1745),
        'BKK': (13.6900, 100.7501),
        'HKG': (22.3080, 113.9185),
        'NRT': (35.7720, 140.3929),
        'ICN': (37.4602, 126.6407),
        'PVG': (31.1979, 121.3363),
        'PEK': (40.0799, 116.6031)
    }
    
    # Airline pricing multipliers (based on service level and operating costs)
    AIRLINE_MULTIPLIERS = {
        'Kenya Airways': 1.0,  # Premium carrier
        'SmartFly': 0.85,  # Budget-friendly main carrier
        'JamboJet': 0.75,  # Low-cost carrier
        'Fly540': 0.80,  # Regional carrier
        'Precision Air': 0.90,  # Regional premium
        'Ethiopian Airlines': 0.95,  # Major international
        'RwandAir': 0.88,  # Regional premium
        'South African Airways': 0.92,  # Regional premium
        'Emirates': 1.2,  # International premium
        'Qatar Airways': 1.15,  # International premium
        'Turkish Airlines': 1.1,  # International premium
        'KLM': 1.05,  # International premium
        'British Airways': 1.1,  # International premium
        'Lufthansa': 1.1,  # International premium
        'Air France': 1.05,  # International premium
        'Qantas': 1.15,  # International premium
        'Singapore Airlines': 1.2,  # International premium
        'Cathay Pacific': 1.15,  # International premium
        'ANA': 1.1,  # International premium
        'JAL': 1.1,  # International premium
        'Delta': 1.05,  # International major
        'United': 1.05,  # International major
        'American Airlines': 1.05,  # International major
    }
    
    # Aircraft type pricing (fuel efficiency and capacity)
    AIRCRAFT_PRICING = {
        'Boeing 737-800': 1.0,
        'Boeing 737-300F': 0.95,
        'Boeing 787-8': 1.2,
        'Embraer E190': 0.85,
        'Airbus A320': 0.95,
        'Airbus A330': 1.15,
        'Airbus A380': 1.3,
        'Bombardier CRJ': 0.8,
        'ATR 72': 0.75
    }
    
    # Base pricing (in KES)
    BASE_PRICES = {
        'domestic_short': 8000,      # < 1 hour
        'domestic_medium': 12000,    # 1-2 hours
        'domestic_long': 18000,      # > 2 hours
        'regional_short': 25000,    # East Africa < 3 hours
        'regional_medium': 35000,   # East Africa 3-5 hours
        'regional_long': 45000,     # East Africa > 5 hours
        'international_short': 65000,   # < 6 hours
        'international_medium': 85000,  # 6-10 hours
        'international_long': 120000,   # > 10 hours
        'international_ultra': 180000   # > 15 hours
    }
    
    def __init__(self):
        self.current_location = 'NBO'  # Default to Nairobi as main hub
    
    def set_current_location(self, airport_code: str):
        """Set the current location for pricing calculations"""
        self.current_location = airport_code
    
    def is_domestic_flight(self, origin: str, destination: str) -> bool:
        """
        Determine if a flight is domestic (within Kenya)
        """
        return (origin in self.KENYA_AIRPORTS and destination in self.KENYA_AIRPORTS)
    
    def is_regional_flight(self, origin: str, destination: str) -> bool:
        """
        Determine if a flight is regional (East Africa)
        """
        all_east_african = {**self.KENYA_AIRPORTS, **self.EAST_AFRICAN_AIRPORTS}
        return (origin in all_east_african and destination in all_east_african)
    
    def is_international_flight(self, origin: str, destination: str) -> bool:
        """
        Determine if a flight is international (outside East Africa)
        """
        return not self.is_regional_flight(origin, destination)
    
    def get_flight_category(self, origin: str, destination: str) -> str:
        """
        Get flight category: domestic, regional, or international
        """
        if self.is_domestic_flight(origin, destination):
            return 'domestic'
        elif self.is_regional_flight(origin, destination):
            return 'regional'
        else:
            return 'international'
    
    def calculate_distance(self, origin: str, destination: str) -> float:
        """
        Calculate distance between two airports using Haversine formula
        Returns distance in kilometers
        """
        if origin not in self.AIRPORT_COORDINATES or destination not in self.AIRPORT_COORDINATES:
            # Default to estimated distance if coordinates not available
            return 500
        
        lat1, lon1 = self.AIRPORT_COORDINATES[origin]
        lat2, lon2 = self.AIRPORT_COORDINATES[destination]
        
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c
        
        return distance
    
    def calculate_flight_duration(self, distance: float, aircraft_type: str = 'Boeing 737-800') -> float:
        """
        Estimate flight duration in hours based on distance and aircraft type
        """
        # Average speeds by aircraft type (km/h)
        aircraft_speeds = {
            'Boeing 737-800': 800,
            'Boeing 737-300F': 750,
            'Boeing 787-8': 900,
            'Embraer E190': 700,
            'Airbus A320': 820,
            'Airbus A330': 880,
            'Airbus A380': 900,
            'Bombardier CRJ': 650,
            'ATR 72': 500
        }
        
        speed = aircraft_speeds.get(aircraft_type, 800)
        
        # Add takeoff/landing time (30 minutes total)
        cruise_time = distance / speed
        total_time = cruise_time + 0.5
        
        return total_time
    
    def get_base_price(self, distance: float, flight_category: str, duration: float) -> float:
        """
        Get base price based on distance, category, and duration
        """
        if flight_category == 'domestic':
            if duration < 1:
                return self.BASE_PRICES['domestic_short']
            elif duration < 2:
                return self.BASE_PRICES['domestic_medium']
            else:
                return self.BASE_PRICES['domestic_long']
        
        elif flight_category == 'regional':
            if duration < 3:
                return self.BASE_PRICES['regional_short']
            elif duration < 5:
                return self.BASE_PRICES['regional_medium']
            else:
                return self.BASE_PRICES['regional_long']
        
        else:  # international
            if duration < 6:
                return self.BASE_PRICES['international_short']
            elif duration < 10:
                return self.BASE_PRICES['international_medium']
            elif duration < 15:
                return self.BASE_PRICES['international_long']
            else:
                return self.BASE_PRICES['international_ultra']
    
    def calculate_price(self, origin: str, destination: str, airline: str = 'SmartFly', 
                      aircraft: str = 'Boeing 737-800', seat_class: str = 'Economy',
                      is_return: bool = False) -> Dict:
        """
        Calculate comprehensive pricing for a flight
        
        Returns dict with:
        - base_price: Base fare
        - final_price: Final price after all adjustments
        - airline_multiplier: Airline pricing factor
        - aircraft_multiplier: Aircraft pricing factor
        - class_multiplier: Seat class pricing factor
        - taxes_and_fees: Additional charges
        - flight_category: domestic/regional/international
        - distance: Distance in km
        - duration: Flight duration in hours
        - currency: KES
        """
        
        # Calculate distance and duration
        distance = self.calculate_distance(origin, destination)
        duration = self.calculate_flight_duration(distance, aircraft)
        
        # Determine flight category
        flight_category = self.get_flight_category(origin, destination)
        
        # Get base price
        base_price = self.get_base_price(distance, flight_category, duration)
        
        # Apply airline multiplier
        airline_multiplier = self.AIRLINE_MULTIPLIERS.get(airline, 1.0)
        
        # Apply aircraft multiplier
        aircraft_multiplier = self.AIRCRAFT_PRICING.get(aircraft, 1.0)
        
        # Apply seat class multiplier
        class_multipliers = {
            'Economy': 1.0,
            'Premium Economy': 1.5,
            'Business': 2.5,
            'First Class': 4.0
        }
        class_multiplier = class_multipliers.get(seat_class, 1.0)
        
        # Calculate adjusted base price
        adjusted_price = base_price * airline_multiplier * aircraft_multiplier * class_multiplier
        
        # Calculate taxes and fees (Kenya-specific)
        taxes_and_fees = self.calculate_taxes_and_fees(adjusted_price, flight_category, is_return)
        
        # Final price
        final_price = adjusted_price + taxes_and_fees
        
        # Round to nearest 100
        final_price = round(final_price / 100) * 100
        
        return {
            'base_price': base_price,
            'adjusted_price': adjusted_price,
            'final_price': final_price,
            'airline_multiplier': airline_multiplier,
            'aircraft_multiplier': aircraft_multiplier,
            'class_multiplier': class_multiplier,
            'taxes_and_fees': taxes_and_fees,
            'flight_category': flight_category,
            'distance': round(distance, 2),
            'duration': round(duration, 2),
            'currency': 'KES',
            'origin': origin,
            'destination': destination,
            'airline': airline,
            'aircraft': aircraft,
            'seat_class': seat_class,
            'is_return': is_return
        }
    
    def calculate_taxes_and_fees(self, price: float, flight_category: str, is_return: bool = False) -> float:
        """
        Calculate Kenya-specific taxes and fees
        """
        taxes = 0.0
        
        # Passenger Service Charge (PSC)
        if flight_category == 'domestic':
            psc = 500  # KES
        elif flight_category == 'regional':
            psc = 1500  # KES
        else:  # international
            psc = 3500  # KES
        
        taxes += psc
        
        # Airport Tax (JKIA departure tax)
        if flight_category == 'domestic':
            airport_tax = 200  # KES
        elif flight_category == 'regional':
            airport_tax = 500  # KES
        else:  # international
            airport_tax = 2000  # KES
        
        taxes += airport_tax
        
        # Value Added Tax (VAT) - 16% in Kenya
        vat = price * 0.16
        taxes += vat
        
        # Fuel surcharge (variable by distance)
        if flight_category == 'international':
            fuel_surcharge = 3000  # KES
            taxes += fuel_surcharge
        
        # Insurance surcharge
        insurance = 300  # KES
        taxes += insurance
        
        return taxes
    
    def get_price_breakdown(self, origin: str, destination: str, airline: str = 'SmartFly',
                          aircraft: str = 'Boeing 737-800', seat_class: str = 'Economy',
                          is_return: bool = False) -> Dict:
        """
        Get detailed price breakdown for display
        """
        pricing = self.calculate_price(origin, destination, airline, aircraft, seat_class, is_return)
        
        breakdown = {
            'Base Fare': pricing['base_price'],
            'Airline Adjustment': pricing['adjusted_price'] - pricing['base_price'],
            'Seat Class Premium': pricing['adjusted_price'] * (pricing['class_multiplier'] - 1),
            'Taxes & Fees': pricing['taxes_and_fees'],
            'Total': pricing['final_price'],
            'Currency': 'KES',
            'Flight Details': {
                'Category': pricing['flight_category'],
                'Distance': f"{pricing['distance']} km",
                'Duration': f"{pricing['duration']} hours",
                'Airline': airline,
                'Aircraft': aircraft
            }
        }
        
        return breakdown
    
    def get_route_recommendations(self, origin: str, budget: float, 
                               preferred_category: str = 'any') -> List[Dict]:
        """
        Get flight recommendations based on budget and preferences
        """
        recommendations = []
        
        # Popular destinations from origin
        if origin == 'NBO':
            destinations = ['MBA', 'KIS', 'EDL', 'JNB', 'ADD', 'LHR', 'DXB', 'AMS']
        else:
            destinations = ['NBO', 'MBA', 'KIS', 'JNB', 'ADD', 'LHR']
        
        for dest in destinations:
            for airline in ['SmartFly', 'Kenya Airways', 'JamboJet']:
                for seat_class in ['Economy', 'Business']:
                    pricing = self.calculate_price(origin, dest, airline, 'Boeing 737-800', seat_class)
                    
                    if pricing['final_price'] <= budget:
                        if preferred_category == 'any' or pricing['flight_category'] == preferred_category:
                            recommendations.append({
                                'destination': dest,
                                'airline': airline,
                                'seat_class': seat_class,
                                'price': pricing['final_price'],
                                'category': pricing['flight_category'],
                                'duration': pricing['duration']
                            })
        
        # Sort by price
        recommendations.sort(key=lambda x: x['price'])
        
        return recommendations[:10]  # Return top 10


# Global pricing engine instance
pricing_engine = PricingEngine()