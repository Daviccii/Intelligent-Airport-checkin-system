"""
Dynamic Seat Map Generator
Generates seat maps dynamically based on aircraft configuration and real-time availability
"""

from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime, timezone


class DynamicSeatMap:
    """
    Dynamic seat map system that:
    - Generates seat layouts based on aircraft configuration
    - Tracks real-time seat availability
    - Supports different seat classes and pricing tiers
    - Handles seat features (emergency exits, priority seats, etc.)
    """
    
    # Seat pricing tiers based on location and features
    SEAT_PRICING_TIERS = {
        'standard': 1.0,
        'priority': 1.3,
        'extra_legroom': 1.5,
        'emergency_exit': 1.2,
        'front_cabin': 1.4,
        'window': 1.1,
        'aisle': 1.05
    }
    
    # Seat class configurations
    SEAT_CLASS_CONFIGS = {
        'Economy': {
            'rows_per_class': 25,
            'starting_row': 2,
            'price_multiplier': 1.0
        },
        'Premium Economy': {
            'rows_per_class': 5,
            'starting_row': 2,
            'price_multiplier': 1.5
        },
        'Business': {
            'rows_per_class': 4,
            'starting_row': 1,
            'price_multiplier': 2.5
        },
        'First': {
            'rows_per_class': 2,
            'starting_row': 1,
            'price_multiplier': 4.0
        }
    }
    
    def __init__(self, aircraft_config: Dict):
        self.aircraft_config = aircraft_config
        self.seat_map_config = aircraft_config.get('seat_map', {})
        self.capacity = aircraft_config.get('capacity', 180)
    
    def generate_seat_map(
        self, 
        booked_seats: List[str] = None,
        blocked_seats: List[str] = None,
        seat_class: str = 'Economy'
    ) -> Dict:
        """
        Generate a complete seat map with availability status
        """
        if booked_seats is None:
            booked_seats = []
        if blocked_seats is None:
            blocked_seats = self.seat_map_config.get('blocked_seats', [])
        
        rows = self.seat_map_config.get('rows', 30)
        columns = self.seat_map_config.get('columns', 6)
        layout = self.seat_map_config.get('layout', '3-3')
        
        seat_map = {
            'aircraft': self.aircraft_config.get('name', 'Unknown'),
            'total_capacity': self.capacity,
            'rows': rows,
            'columns': columns,
            'layout': layout,
            'seat_class': seat_class,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'seats': [],
            'statistics': self._calculate_statistics(rows, columns, booked_seats, blocked_seats)
        }
        
        # Generate individual seats
        for row in range(1, rows + 1):
            for col in range(columns):
                seat_id = self._generate_seat_id(row, col)
                seat = self._create_seat(
                    seat_id, row, col, layout, booked_seats, blocked_seats, seat_class
                )
                seat_map['seats'].append(seat)
        
        return seat_map
    
    def _generate_seat_id(self, row: int, col: int) -> str:
        """Generate seat ID (e.g., '1A', '12B')"""
        column_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'K']
        if col < len(column_letters):
            return f"{row}{column_letters[col]}"
        return f"{row}{col}"
    
    def _create_seat(
        self, 
        seat_id: str, 
        row: int, 
        col: int, 
        layout: str,
        booked_seats: List[str],
        blocked_seats: List[str],
        seat_class: str
    ) -> Dict:
        """Create individual seat with properties and pricing"""
        is_booked = seat_id in booked_seats
        is_blocked = seat_id in blocked_seats
        is_available = not is_booked and not is_blocked
        
        # Determine seat features
        features = self._determine_seat_features(row, col, layout)
        
        # Calculate seat price multiplier
        price_multiplier = self._calculate_seat_price_multiplier(features, seat_class)
        
        return {
            'seat_id': seat_id,
            'row': row,
            'column': col,
            'is_available': is_available,
            'is_booked': is_booked,
            'is_blocked': is_blocked,
            'status': 'available' if is_available else ('booked' if is_booked else 'blocked'),
            'features': features,
            'pricing': {
                'tier': self._determine_pricing_tier(features),
                'multiplier': price_multiplier,
                'class_multiplier': self.SEAT_CLASS_CONFIGS.get(seat_class, {}).get('price_multiplier', 1.0)
            },
            'type': self._determine_seat_type(col, layout)
        }
    
    def _determine_seat_features(self, row: int, col: int, layout: str) -> List[str]:
        """Determine features based on seat position"""
        features = []
        
        # Emergency exit rows
        emergency_exits = self.seat_map_config.get('emergency_exits', [])
        if row in emergency_exits:
            features.append('emergency_exit')
            features.append('extra_legroom')
        
        # Priority seats
        priority_seats = self.seat_map_config.get('priority_seats', [])
        seat_id = self._generate_seat_id(row, col)
        if seat_id in priority_seats:
            features.append('priority')
        
        # Front cabin seats
        if row <= 2:
            features.append('front_cabin')
        
        # Window seats
        layout_parts = layout.split('-')
        if col == 0 or col == sum(len(part.strip().split()) for part in layout_parts) - 1:
            features.append('window')
        
        # Aisle seats
        current_col = 0
        for part in layout_parts:
            seats_in_section = len(part.strip().split())
            if col == current_col - 1 or col == current_col + seats_in_section:
                features.append('aisle')
            current_col += seats_in_section
        
        return features
    
    def _calculate_seat_price_multiplier(self, features: List[str], seat_class: str) -> float:
        """Calculate price multiplier based on features"""
        base_multiplier = 1.0
        
        for feature in features:
            if feature in self.SEAT_PRICING_TIERS:
                base_multiplier *= self.SEAT_PRICING_TIERS[feature]
        
        # Apply class multiplier
        class_multiplier = self.SEAT_CLASS_CONFIGS.get(seat_class, {}).get('price_multiplier', 1.0)
        
        return base_multiplier * class_multiplier
    
    def _determine_pricing_tier(self, features: List[str]) -> str:
        """Determine pricing tier based on features"""
        if 'priority' in features:
            return 'priority'
        elif 'extra_legroom' in features:
            return 'extra_legroom'
        elif 'emergency_exit' in features:
            return 'emergency_exit'
        elif 'front_cabin' in features:
            return 'front_cabin'
        elif 'window' in features:
            return 'window'
        elif 'aisle' in features:
            return 'aisle'
        else:
            return 'standard'
    
    def _determine_seat_type(self, col: int, layout: str) -> str:
        """Determine seat type (window, middle, aisle)"""
        layout_parts = layout.split('-')
        current_col = 0
        
        for part in layout_parts:
            seats_in_section = len(part.strip().split())
            if col == current_col:
                return 'window'
            elif col == current_col + seats_in_section - 1:
                return 'window'
            elif col == current_col - 1 or col == current_col + seats_in_section:
                return 'aisle'
            current_col += seats_in_section
        
        return 'middle'
    
    def _calculate_statistics(
        self, 
        rows: int, 
        columns: int, 
        booked_seats: List[str], 
        blocked_seats: List[str]
    ) -> Dict:
        """Calculate seat availability statistics"""
        total_seats = rows * columns
        available_seats = total_seats - len(booked_seats) - len(blocked_seats)
        
        return {
            'total_seats': total_seats,
            'available_seats': available_seats,
            'booked_seats': len(booked_seats),
            'blocked_seats': len(blocked_seats),
            'occupancy_rate': len(booked_seats) / total_seats if total_seats > 0 else 0,
            'availability_rate': available_seats / total_seats if total_seats > 0 else 0
        }
    
    def get_seat_pricing(
        self, 
        seat_id: str, 
        base_price: float, 
        seat_class: str = 'Economy'
    ) -> Dict:
        """
        Calculate pricing for a specific seat
        """
        # Parse seat ID to get row and column
        row = int(''.join(filter(str.isdigit, seat_id)))
        col_letter = ''.join(filter(str.isalpha, seat_id))
        col = ord(col_letter.upper()) - ord('A')
        
        layout = self.seat_map_config.get('layout', '3-3')
        features = self._determine_seat_features(row, col, layout)
        price_multiplier = self._calculate_seat_price_multiplier(features, seat_class)
        
        final_price = base_price * price_multiplier
        
        return {
            'seat_id': seat_id,
            'base_price': base_price,
            'features': features,
            'pricing_tier': self._determine_pricing_tier(features),
            'multiplier': price_multiplier,
            'final_price': final_price,
            'seat_class': seat_class,
            'calculated_at': datetime.now(timezone.utc).isoformat()
        }
    
    def update_seat_availability(
        self, 
        seat_map: Dict, 
        seat_id: str, 
        status: str
    ) -> Dict:
        """
        Update seat availability status
        """
        for seat in seat_map['seats']:
            if seat['seat_id'] == seat_id:
                seat['status'] = status
                seat['is_available'] = (status == 'available')
                seat['is_booked'] = (status == 'booked')
                seat['is_blocked'] = (status == 'blocked')
                break
        
        # Recalculate statistics
        booked = [s['seat_id'] for s in seat_map['seats'] if s['is_booked']]
        blocked = [s['seat_id'] for s in seat_map['seats'] if s['is_blocked']]
        seat_map['statistics'] = self._calculate_statistics(
            seat_map['rows'], 
            seat_map['columns'], 
            booked, 
            blocked
        )
        
        seat_map['updated_at'] = datetime.now(timezone.utc).isoformat()
        return seat_map
    
    def get_available_seats(
        self, 
        seat_map: Dict, 
        seat_class: str = None,
        features: List[str] = None
    ) -> List[Dict]:
        """
        Get available seats with optional filtering
        """
        available_seats = []
        
        for seat in seat_map['seats']:
            if not seat['is_available']:
                continue
            
            # Filter by seat class if specified
            if seat_class and seat_map.get('seat_class') != seat_class:
                continue
            
            # Filter by features if specified
            if features:
                if not all(feature in seat['features'] for feature in features):
                    continue
            
            available_seats.append(seat)
        
        return available_seats