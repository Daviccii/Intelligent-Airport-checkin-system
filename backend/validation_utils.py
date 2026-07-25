"""
Comprehensive validation utilities for SmartFly Intelligent Airport Check-In System.
Provides validation functions for all user input fields across the application.
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any


class ValidationError(Exception):
    """Custom exception for validation errors with user-friendly messages."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class ValidationUtils:
    """Centralized validation utilities for all user input fields."""
    
    # Regular expression patterns
    NAME_PATTERN = r"^[a-zA-Z\s\-']{2,50}$"
    EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    KENYAN_PHONE_PATTERN = r"^(?:254|\+254|0)?(7\d{8})$"
    INTERNATIONAL_PHONE_PATTERN = r"^\+?[1-9]\d{1,14}$"  # E.164
    PASSPORT_PATTERN = r"^[A-Z0-9]{6,12}$"
    KENYAN_ID_PATTERN = r"^\d{7,8}$"
    FLIGHT_NUMBER_PATTERN = r"^[A-Z]{2,3}\d{3,4}$"
    BOOKING_REF_PATTERN = r"^[A-Z0-9]{6}$"
    SEAT_PATTERN = r"^[A-Z][1-9]\d?$"
    
    @staticmethod
    def validate_name(name: str, field_name: str = "name") -> str:
        """
        Validate person names (letters, spaces, hyphens, apostrophes only).
        
        Args:
            name: The name to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized name
            
        Raises:
            ValidationError: If validation fails
        """
        if not name or not name.strip():
            raise ValidationError(field_name, "Name is required")
        
        name = name.strip()
        
        if len(name) < 2:
            raise ValidationError(field_name, "Name must be at least 2 characters long")
        
        if len(name) > 50:
            raise ValidationError(field_name, "Name must not exceed 50 characters")
        
        if not re.match(ValidationUtils.NAME_PATTERN, name):
            raise ValidationError(field_name, "Name can only contain letters, spaces, hyphens, and apostrophes")
        
        return name
    
    @staticmethod
    def validate_email(email: str, field_name: str = "email") -> str:
        """
        Validate email address format.
        
        Args:
            email: The email to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized email
            
        Raises:
            ValidationError: If validation fails
        """
        if not email or not email.strip():
            raise ValidationError(field_name, "Email is required")
        
        email = email.strip().lower()
        
        if len(email) > 100:
            raise ValidationError(field_name, "Email must not exceed 100 characters")
        
        if not re.match(ValidationUtils.EMAIL_PATTERN, email):
            raise ValidationError(field_name, "Invalid email format")
        
        return email
    
    @staticmethod
    def validate_phone(phone: str, is_kenyan: bool = True, field_name: str = "phone") -> str:
        """
        Validate phone number format (Kenyan or international).
        
        Args:
            phone: The phone number to validate
            is_kenyan: Whether to validate as Kenyan phone number
            field_name: Name of the field for error messages
            
        Returns:
            The validated and normalized phone number
            
        Raises:
            ValidationError: If validation fails
        """
        if not phone or not phone.strip():
            raise ValidationError(field_name, "Phone number is required")
        
        phone_cleaned = phone.strip().replace(" ", "")
        
        if is_kenyan:
            # Validate Kenyan phone number format
            match = re.match(ValidationUtils.KENYAN_PHONE_PATTERN, phone_cleaned)
            if not match:
                raise ValidationError(field_name, "Invalid Kenyan phone number format. Use format: +2547..., 2547... or 07...")
            # Normalize to +254 format
            phone = '+254' + match.group(1)
        else:
            # Validate international phone number
            if not re.match(ValidationUtils.INTERNATIONAL_PHONE_PATTERN, phone):
                raise ValidationError(field_name, "Invalid international phone number format")
        
        return phone
    
    @staticmethod
    def validate_passport(passport: str, field_name: str = "passport") -> str:
        """
        Validate passport number format.
        
        Args:
            passport: The passport number to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized passport number
            
        Raises:
            ValidationError: If validation fails
        """
        if not passport or not passport.strip():
            raise ValidationError(field_name, "Passport number is required")
        
        passport = passport.strip().upper()
        
        if len(passport) < 6 or len(passport) > 12:
            raise ValidationError(field_name, "Passport number must be 6-12 characters long")
        
        if not re.match(ValidationUtils.PASSPORT_PATTERN, passport):
            raise ValidationError(field_name, "Passport number can only contain letters and numbers")
        
        return passport
    
    @staticmethod
    def validate_national_id(id_number: str, field_name: str = "national_id") -> str:
        """
        Validate Kenyan national ID number format.
        
        Args:
            id_number: The national ID to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized national ID
            
        Raises:
            ValidationError: If validation fails
        """
        if not id_number or not id_number.strip():
            raise ValidationError(field_name, "National ID is required")
        
        id_number = id_number.strip()
        
        if not re.match(ValidationUtils.KENYAN_ID_PATTERN, id_number):
            raise ValidationError(field_name, "Invalid Kenyan national ID format. Must be 7-8 digits")
        
        return id_number
    
    @staticmethod
    def validate_flight_number(flight_number: str, field_name: str = "flight_number") -> str:
        """
        Validate flight number format (e.g., KQ123, BA4567).
        
        Args:
            flight_number: The flight number to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized flight number
            
        Raises:
            ValidationError: If validation fails
        """
        if not flight_number or not flight_number.strip():
            raise ValidationError(field_name, "Flight number is required")
        
        flight_number = flight_number.strip().upper()
        
        if not re.match(ValidationUtils.FLIGHT_NUMBER_PATTERN, flight_number):
            raise ValidationError(field_name, "Invalid flight number format. Use format: XX123 or XXX1234")
        
        return flight_number
    
    @staticmethod
    def validate_booking_reference(booking_ref: str, field_name: str = "booking_reference") -> str:
        """
        Validate booking reference format.
        
        Args:
            booking_ref: The booking reference to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized booking reference
            
        Raises:
            ValidationError: If validation fails
        """
        if not booking_ref or not booking_ref.strip():
            raise ValidationError(field_name, "Booking reference is required")
        
        booking_ref = booking_ref.strip().upper()
        
        if not re.match(ValidationUtils.BOOKING_REF_PATTERN, booking_ref):
            raise ValidationError(field_name, "Invalid booking reference format. Must be 6 alphanumeric characters")
        
        return booking_ref
    
    @staticmethod
    def validate_seat(seat: str, field_name: str = "seat") -> str:
        """
        Validate seat selection format (e.g., 1A, 12B, 5C).
        
        Args:
            seat: The seat to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized seat
            
        Raises:
            ValidationError: If validation fails
        """
        if not seat or not seat.strip():
            raise ValidationError(field_name, "Seat selection is required")
        
        seat = seat.strip().upper()
        
        if not re.match(ValidationUtils.SEAT_PATTERN, seat):
            raise ValidationError(field_name, "Invalid seat format. Use format: 1A, 12B, etc.")
        
        return seat
    
    @staticmethod
    def validate_date(date_str: str, date_format: str = "%Y-%m-%d", 
                     field_name: str = "date", allow_past: bool = False,
                     min_days_future: int = 0) -> str:
        """
        Validate date format and logical constraints.
        
        Args:
            date_str: The date string to validate
            date_format: Expected date format (default: YYYY-MM-DD)
            field_name: Name of the field for error messages
            allow_past: Whether to allow dates in the past
            min_days_future: Minimum number of days in the future required
            
        Returns:
            The validated date string
            
        Raises:
            ValidationError: If validation fails
        """
        if not date_str or not date_str.strip():
            raise ValidationError(field_name, "Date is required")
        
        date_str = date_str.strip()
        
        try:
            date_obj = datetime.strptime(date_str, date_format)
        except ValueError:
            raise ValidationError(field_name, f"Invalid date format. Expected format: {date_format}")
        
        today = datetime.now()

        # Check if date is in the past
        if not allow_past and date_obj.date() < today.date():
            raise ValidationError(field_name, "Date cannot be in the past")
        
        # Check minimum days in future
        if min_days_future > 0:
            min_date = today + timedelta(days=min_days_future)
            if date_obj < min_date:
                raise ValidationError(field_name, f"Date must be at least {min_days_future} days in the future")
        
        # Check if date is too far in the future (max 1 year)
        # This is more accurate than timedelta(days=365) as it handles leap years.
        max_date = today.replace(year=today.year + 1)
        if date_obj > max_date:
            raise ValidationError(field_name, "Date cannot be more than 1 year in the future")
        
        return date_str
    
    @staticmethod
    def validate_passenger_count(count: int, field_name: str = "passenger_count") -> int:
        """
        Validate passenger count.
        
        Args:
            count: The passenger count to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated passenger count
            
        Raises:
            ValidationError: If validation fails
        """
        if count is None:
            raise ValidationError(field_name, "Passenger count is required")
        
        try:
            count = int(count)
        except (ValueError, TypeError):
            raise ValidationError(field_name, "Passenger count must be a number")
        
        if count < 1:
            raise ValidationError(field_name, "At least 1 passenger is required")
        
        if count > 9:
            raise ValidationError(field_name, "Maximum 9 passengers allowed per booking")
        
        return count
    
    @staticmethod
    def validate_amount(amount: float, field_name: str = "amount", 
                        min_amount: float = 0.01, max_amount: float = 1000000.0) -> float:
        """
        Validate monetary amount.
        
        Args:
            amount: The amount to validate
            field_name: Name of the field for error messages
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount
            
        Returns:
            The validated amount
            
        Raises:
            ValidationError: If validation fails
        """
        if amount is None:
            raise ValidationError(field_name, "Amount is required")
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            raise ValidationError(field_name, "Amount must be a number")
        
        if amount < min_amount:
            raise ValidationError(field_name, f"Amount must be at least {min_amount}")
        
        if amount > max_amount:
            raise ValidationError(field_name, f"Amount cannot exceed {max_amount}")
        
        return round(amount, 2)
    
    @staticmethod
    def validate_password(password: str, field_name: str = "password", 
                         min_length: int = 8, require_special: bool = True) -> str:
        """
        Validate password strength.
        
        Args:
            password: The password to validate
            field_name: Name of the field for error messages
            min_length: Minimum password length
            require_special: Whether to require special characters
            
        Returns:
            The validated password
            
        Raises:
            ValidationError: If validation fails
        """
        if not password or not password.strip():
            raise ValidationError(field_name, "Password is required")
        
        password = password.strip()
        
        if len(password) < min_length:
            raise ValidationError(field_name, f"Password must be at least {min_length} characters long")
        
        if len(password) > 128:
            raise ValidationError(field_name, "Password must not exceed 128 characters")
        
        if require_special:
            # Check for at least one uppercase, one lowercase, one digit, and one special character
            if not re.search(r'[A-Z]', password):
                raise ValidationError(field_name, "Password must contain at least one uppercase letter")
            
            if not re.search(r'[a-z]', password):
                raise ValidationError(field_name, "Password must contain at least one lowercase letter")
            
            if not re.search(r'\d', password):
                raise ValidationError(field_name, "Password must contain at least one digit")
            
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise ValidationError(field_name, "Password must contain at least one special character")
        
        return password
    
    @staticmethod
    def validate_payment_method(payment_method: str, field_name: str = "payment_method") -> str:
        """
        Validate payment method.
        
        Args:
            payment_method: The payment method to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated payment method
            
        Raises:
            ValidationError: If validation fails
        """
        if not payment_method or not payment_method.strip():
            raise ValidationError(field_name, "Payment method is required")
        
        payment_method = payment_method.strip().lower()
        
        valid_methods = ['card', 'mpesa', 'bank_transfer', 'paypal', 'cash']
        if payment_method not in valid_methods:
            raise ValidationError(field_name, f"Invalid payment method. Must be one of: {', '.join(valid_methods)}")
        
        return payment_method
    
    @staticmethod
    def validate_airport_code(code: str, field_name: str = "airport_code") -> str:
        """
        Validate airport code format (IATA 3-letter code).
        
        Args:
            code: The airport code to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated airport code
            
        Raises:
            ValidationError: If validation fails
        """
        if not code or not code.strip():
            raise ValidationError(field_name, "Airport code is required")
        
        code = code.strip().upper()
        
        if len(code) != 3 or not code.isalpha():
            raise ValidationError(field_name, "Invalid airport code. Must be 3 letters")
        
        return code
    
    @staticmethod
    def validate_country_code(code: str, field_name: str = "country_code") -> str:
        """
        Validate country code (ISO 3166-1 alpha-2 or alpha-3).
        
        Args:
            code: The country code to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated country code
            
        Raises:
            ValidationError: If validation fails
        """
        if not code or not code.strip():
            raise ValidationError(field_name, "Country code is required")
        
        code = code.strip().upper()
        
        # Accept both 2-letter (ISO 3166-1 alpha-2) and 3-letter (ISO 3166-1 alpha-3) codes
        if not (len(code) == 2 and code.isalpha()) and not (len(code) == 3 and code.isalpha()):
            raise ValidationError(field_name, "Invalid country code. Must be 2 or 3 letters")
        
        return code
    
    @staticmethod
    def validate_class_of_service(service_class: str, field_name: str = "class") -> str:
        """
        Validate class of service.
        
        Args:
            service_class: The class of service to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated class of service
            
        Raises:
            ValidationError: If validation fails
        """
        if not service_class or not service_class.strip():
            raise ValidationError(field_name, "Class of service is required")
        
        service_class = service_class.strip().lower()
        
        valid_classes = ['economy', 'business', 'first', 'premium_economy']
        if service_class not in valid_classes:
            raise ValidationError(field_name, f"Invalid class of service. Must be one of: {', '.join(valid_classes)}")
        
        return service_class
    
    @staticmethod
    def validate_required_field(value: Any, field_name: str) -> Any:
        """
        Generic required field validation.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated value
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(field_name, f"{field_name.replace('_', ' ').title()} is required")
        
        return value


    @staticmethod
    def validate_date_of_birth(date_str: str, date_format: str = "%Y-%m-%d", 
                              field_name: str = "date_of_birth", min_age: int = 18) -> str:
        """
        Validate date of birth with age requirements.
        
        Args:
            date_str: The date string to validate
            date_format: Expected date format (default: YYYY-MM-DD)
            field_name: Name of the field for error messages
            min_age: Minimum age required (default: 18)
            
        Returns:
            The validated date string
            
        Raises:
            ValidationError: If validation fails
        """
        if not date_str or not date_str.strip():
            raise ValidationError(field_name, "Date of birth is required")
        
        date_str = date_str.strip()
        
        try:
            date_obj = datetime.strptime(date_str, date_format)
        except ValueError:
            raise ValidationError(field_name, f"Invalid date format. Expected format: {date_format}")
        
        today = datetime.now()

        # Check if date is in the future
        if date_obj > today:
            raise ValidationError(field_name, "Date of birth cannot be in the future")
        
        # Check minimum age requirement
        # This is more accurate than timedelta(days=365 * min_age) as it handles leap years.
        min_birth_date = today.replace(year=today.year - min_age)
        if date_obj > min_birth_date:
            raise ValidationError(field_name, f"Passenger must be at least {min_age} years old to make a booking")
        
        # Check if date is too far in the past (max 120 years)
        max_birth_date = today.replace(year=today.year - 120)
        if date_obj < max_birth_date:
            raise ValidationError(field_name, "Date of birth is invalid")
        
        return date_str
    
    @staticmethod
    def validate_passport_expiry(expiry_date: str, date_format: str = "%Y-%m-%d",
                               departure_date: str = None, field_name: str = "passport_expiry") -> str:
        """
        Validate passport expiry date with requirements.
        
        Args:
            expiry_date: The passport expiry date to validate
            date_format: Expected date format (default: YYYY-MM-DD)
            departure_date: The departure date to validate against (optional)
            field_name: Name of the field for error messages
            
        Returns:
            The validated expiry date string
            
        Raises:
            ValidationError: If validation fails
        """
        if not expiry_date or not expiry_date.strip():
            raise ValidationError(field_name, "Passport expiry date is required")
        
        expiry_date = expiry_date.strip()
        
        try:
            expiry_obj = datetime.strptime(expiry_date, date_format)
        except ValueError:
            raise ValidationError(field_name, f"Invalid date format. Expected format: {date_format}")
        
        today = datetime.now()

        # Check if expiry date is today or in the past
        if expiry_obj.date() <= today.date():
            raise ValidationError(field_name, "Passport cannot be expired. Expiry date must be in the future")
        
        # Check if expiry date is too far in the future (max 10 years)
        # This is more accurate than timedelta(days=365 * 10) as it handles leap years.
        max_expiry = today.replace(year=today.year + 10)
        if expiry_obj > max_expiry:
            raise ValidationError(field_name, "Passport expiry date cannot be more than 10 years in the future")
        
        # Check against departure date if provided
        if departure_date:
            try:
                departure_obj = datetime.strptime(departure_date, date_format)
                if expiry_obj <= departure_obj:
                    raise ValidationError(field_name, "Passport must be valid after departure date")
            except ValueError:
                # If departure date is invalid, don't fail on this check
                pass
        
        return expiry_date
    
    @staticmethod
    def validate_passport_issue_date(issue_date: str, date_format: str = "%Y-%m-%d",
                                   expiry_date: str = None, field_name: str = "passport_issue_date") -> str:
        """
        Validate passport issue date with requirements.
        
        Args:
            issue_date: The passport issue date to validate
            date_format: Expected date format (default: YYYY-MM-DD)
            expiry_date: The passport expiry date to validate against (optional)
            field_name: Name of the field for error messages
            
        Returns:
            The validated issue date string
            
        Raises:
            ValidationError: If validation fails
        """
        if not issue_date or not issue_date.strip():
            raise ValidationError(field_name, "Passport issue date is required")
        
        issue_date = issue_date.strip()
        
        try:
            issue_obj = datetime.strptime(issue_date, date_format)
        except ValueError:
            raise ValidationError(field_name, f"Invalid date format. Expected format: {date_format}")
        
        # Check if issue date is after today
        if issue_obj > datetime.now():
            raise ValidationError(field_name, "Passport issue date cannot be in the future")
        
        # Check against expiry date if provided
        if expiry_date:
            try:
                expiry_obj = datetime.strptime(expiry_date, date_format)
                if issue_obj >= expiry_obj:
                    raise ValidationError(field_name, "Passport issue date must be before expiry date")
            except ValueError:
                # If expiry date is invalid, don't fail on this check
                pass
        
        return issue_date
    
    @staticmethod
    def validate_card_number(card_number: str, field_name: str = "card_number") -> str:
        """
        Validate credit/debit card number using Luhn algorithm.
        
        Args:
            card_number: The card number to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized card number
            
        Raises:
            ValidationError: If validation fails
        """
        if not card_number or not card_number.strip():
            raise ValidationError(field_name, "Card number is required")
        
        card_number = card_number.strip().replace(' ', '').replace('-', '')
        
        # Check length (typically 13-19 digits)
        if len(card_number) < 13 or len(card_number) > 19:
            raise ValidationError(field_name, "Card number must be 13-19 digits long")
        
        # Check if all digits
        if not card_number.isdigit():
            raise ValidationError(field_name, "Card number can only contain digits")
        
        # Luhn algorithm validation
        def luhn_check(card_num):
            total = 0
            reverse_digits = card_num[::-1]
            for i, digit in enumerate(reverse_digits):
                n = int(digit)
                if i % 2 == 1:
                    n *= 2
                    if n > 9:
                        n -= 9
                total += n
            return total % 10 == 0
        
        if not luhn_check(card_number):
            raise ValidationError(field_name, "Invalid card number")
        
        return card_number
    
    @staticmethod
    def validate_card_holder(card_holder: str, field_name: str = "card_holder") -> str:
        """
        Validate card holder name.
        
        Args:
            card_holder: The card holder name to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated and sanitized card holder name
            
        Raises:
            ValidationError: If validation fails
        """
        if not card_holder or not card_holder.strip():
            raise ValidationError(field_name, "Card holder name is required")
        
        card_holder = card_holder.strip()
        
        if len(card_holder) < 2:
            raise ValidationError(field_name, "Card holder name must be at least 2 characters long")
        
        if len(card_holder) > 100:
            raise ValidationError(field_name, "Card holder name must not exceed 100 characters")
        
        # Allow letters, spaces, hyphens, apostrophes, and periods
        if not re.match(r"^[a-zA-Z\s\-'.]{2,100}$", card_holder):
            raise ValidationError(field_name, "Card holder name can only contain letters, spaces, hyphens, apostrophes, and periods")
        
        return card_holder
    
    @staticmethod
    def validate_cvv(cvv: str, field_name: str = "cvv") -> str:
        """
        Validate CVV/CVC code.
        
        Args:
            cvv: The CVV to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated CVV
            
        Raises:
            ValidationError: If validation fails
        """
        if not cvv or not cvv.strip():
            raise ValidationError(field_name, "CVV is required")
        
        cvv = cvv.strip()
        
        # CVV is typically 3 or 4 digits
        if not cvv.isdigit():
            raise ValidationError(field_name, "CVV can only contain digits")
        
        if len(cvv) < 3 or len(cvv) > 4:
            raise ValidationError(field_name, "CVV must be 3 or 4 digits")
        
        return cvv
    
    @staticmethod
    def validate_card_expiry(expiry_date: str, field_name: str = "card_expiry") -> str:
        """
        Validate card expiry date (MM/YY format).
        
        Args:
            expiry_date: The card expiry date to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated expiry date
            
        Raises:
            ValidationError: If validation fails
        """
        if not expiry_date or not expiry_date.strip():
            raise ValidationError(field_name, "Card expiry date is required")
        
        expiry_date = expiry_date.strip()
        
        # Validate format (MM/YY)
        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", expiry_date):
            raise ValidationError(field_name, "Invalid expiry date format. Use MM/YY")
        
        try:
            month, year = expiry_date.split('/')
            month = int(month)
            year = int('20' + year)  # Convert YY to 20YY
            
            # Create expiry date for the last day of the month
            if month == 12:
                expiry_obj = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                expiry_obj = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # Check if card is expired
            if expiry_obj < datetime.now():
                raise ValidationError(field_name, "Card has expired")
            
            # Check if expiry date is too far in the future (max 20 years)
            max_expiry = datetime.now() + timedelta(days=365 * 20)
            if expiry_obj > max_expiry:
                raise ValidationError(field_name, "Card expiry date cannot be more than 20 years in the future")
            
        except ValueError:
            raise ValidationError(field_name, "Invalid expiry date")
        
        return expiry_date
    
    @staticmethod
    def validate_flight_route(origin: str, destination: str, 
                            field_name: str = "route") -> Tuple[str, str]:
        """
        Validate flight route (origin and destination cannot be the same).
        
        Args:
            origin: The origin airport code
            destination: The destination airport code
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (validated_origin, validated_destination)
            
        Raises:
            ValidationError: If validation fails
        """
        origin = ValidationUtils.validate_airport_code(origin, f"{field_name}_origin")
        destination = ValidationUtils.validate_airport_code(destination, f"{field_name}_destination")
        
        if origin == destination:
            raise ValidationError(field_name, "Origin and destination airports cannot be the same")
        
        return origin, destination
    
    @staticmethod
    def validate_return_date(departure_date: str, return_date: str,
                            date_format: str = "%Y-%m-%d",
                            field_name: str = "return_date") -> str:
        """
        Validate return date (must be after departure date).
        
        Args:
            departure_date: The departure date
            return_date: The return date to validate
            date_format: Expected date format (default: YYYY-MM-DD)
            field_name: Name of the field for error messages
            
        Returns:
            The validated return date string
            
        Raises:
            ValidationError: If validation fails
        """
        if not return_date or not return_date.strip():
            raise ValidationError(field_name, "Return date is required")
        
        return_date = return_date.strip()
        
        try:
            return_obj = datetime.strptime(return_date, date_format)
            departure_obj = datetime.strptime(departure_date, date_format)
        except ValueError:
            raise ValidationError(field_name, f"Invalid date format. Expected format: {date_format}")
        
        # Check if return date is before or same as departure date
        if return_obj <= departure_obj:
            raise ValidationError(field_name, "Return date must be after departure date")
        
        # Check if return date is too far in the future (max 1 year from departure)
        max_return = departure_obj + timedelta(days=365)
        if return_obj > max_return:
            raise ValidationError(field_name, "Return date cannot be more than 1 year after departure date")
        
        return return_date
    
    @staticmethod
    def validate_gender(gender: str, field_name: str = "gender") -> str:
        """
        Validate gender field.
        
        Args:
            gender: The gender to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated gender
            
        Raises:
            ValidationError: If validation fails
        """
        if not gender or not gender.strip():
            raise ValidationError(field_name, "Gender is required")
        
        gender = gender.strip().lower()
        
        valid_genders = ['male', 'female', 'other', 'prefer_not_to_say']
        if gender not in valid_genders:
            raise ValidationError(field_name, f"Invalid gender. Must be one of: {', '.join(valid_genders)}")
        
        return gender


def validate_form_data(data: Dict[str, Any], validation_rules: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """
    Validate form data against a set of validation rules.
    
    Args:
        data: Dictionary of form data
        validation_rules: Dictionary mapping field names to validation functions and parameters
        
    Returns:
        Tuple of (is_valid, errors_dict)
    
    Example:
        rules = {
            'name': {'validator': 'validate_name', 'field_name': 'Full Name'},
            'email': {'validator': 'validate_email', 'field_name': 'Email Address'},
            'phone': {'validator': 'validate_phone', 'field_name': 'Phone Number', 'is_kenyan': True}
        }
        is_valid, errors = validate_form_data(form_data, rules)
    """
    errors = {}
    validator = ValidationUtils()
    
    for field_name, rule in validation_rules.items():
        field_value = data.get(field_name)
        validator_name = rule.get('validator')
        field_display_name = rule.get('field_name', field_name)
        validator_params = {k: v for k, v in rule.items() if k not in ['validator', 'field_name']}
        
        if field_value is None and rule.get('required', True):
            errors[field_name] = f"{field_display_name} is required"
            continue
        
        if field_value is not None and field_value != '':
            try:
                validator_func = getattr(validator, validator_name)
                validator_func(field_value, field_name=field_display_name, **validator_params)
            except ValidationError as e:
                errors[field_name] = e.message
            except AttributeError:
                errors[field_name] = f"Unknown validator: {validator_name}"
    
    return len(errors) == 0, errors