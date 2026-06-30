"""
M-Pesa Integration Module for SmartFly Airlines
Supports STK Push, C2B, and B2C transactions
"""

import os
import requests
import base64
import json
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MpesaIntegration:
    """
    M-Pesa Daraja API Integration Class
    Handles STK Push, C2B, and B2C transactions
    """
    
    def __init__(self):
        # M-Pesa API Configuration
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
        self.passkey = os.getenv('MPESA_PASSKEY')
        self.environment = os.getenv('MPESA_ENVIRONMENT', 'sandbox')  # sandbox or production
        self.shortcode = os.getenv('MPESA_SHORTCODE')
        self.head_office = os.getenv('MPESA_HEAD_OFFICE')
        self.initiator_username = os.getenv('MPESA_INITIATOR_USERNAME')
        self.initiator_password = os.getenv('MPESA_INITIATOR_PASSWORD')
        self.security_credential = os.getenv('MPESA_SECURITY_CREDENTIAL')
        self.business_shortcode = os.getenv('MPESA_BUSINESS_SHORTCODE')
        self.paybill_number = os.getenv('MPESA_PAYBILL_NUMBER')
        
        # API URLs based on environment
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke/mpesa/'
            self.auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        else:
            self.base_url = 'https://api.safaricom.co.ke/mpesa/'
            self.auth_url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        
        self.access_token = None
        self.token_expiry = None
    
    def generate_access_token(self):
        """Generate OAuth access token for M-Pesa API"""
        try:
            # Create basic auth string
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(self.auth_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                # Token expires in 1 hour (3600 seconds)
                self.token_expiry = datetime.now() + timedelta(seconds=3590)
                logger.info("M-Pesa access token generated successfully")
                return True
            else:
                logger.error(f"Failed to generate access token: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating access token: {str(e)}")
            return False
    
    def is_token_valid(self):
        """Check if current access token is still valid"""
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry
    
    def get_access_token(self):
        """Get valid access token, generating new one if needed"""
        if not self.is_token_valid():
            if not self.generate_access_token():
                return None
        return self.access_token
    
    def stk_push_payment(self, phone_number, amount, callback_url, account_reference, transaction_desc):
        """
        Initiate STK Push payment (Lipa na M-Pesa)
        
        Args:
            phone_number: Customer phone number (format: 2547XXXXXXXXX)
            amount: Amount to charge
            callback_url: URL to receive payment notification
            account_reference: Unique reference for the transaction
            transaction_desc: Description of the transaction
        
        Returns:
            dict: Response from M-Pesa API
        """
        try:
            token = self.get_access_token()
            if not token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            # Generate password for the request
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self._generate_stk_password(timestamp)
            
            # Prepare request payload
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': amount,
                'PartyA': phone_number,
                'PartyB': self.shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"STK Push initiated successfully: {result}")
                return {'success': True, 'data': result}
            else:
                logger.error(f"STK Push failed: {response.text}")
                return {'success': False, 'message': response.text}
                
        except Exception as e:
            logger.error(f"Error in STK Push: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def c2b_register_url(self, validation_url, confirmation_url, response_type):
        """
        Register C2B callback URLs with M-Pesa
        
        Args:
            validation_url: URL for validation requests
            confirmation_url: URL for confirmation requests
            response_type: Response type (Completed, Cancelled)
        
        Returns:
            dict: Response from M-Pesa API
        """
        try:
            token = self.get_access_token()
            if not token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            payload = {
                'ShortCode': self.shortcode,
                'ResponseType': response_type,
                'ConfirmationURL': confirmation_url,
                'ValidationURL': validation_url
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}c2b/v1/registerurl"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"C2B URL registered successfully: {result}")
                return {'success': True, 'data': result}
            else:
                logger.error(f"C2B URL registration failed: {response.text}")
                return {'success': False, 'message': response.text}
                
        except Exception as e:
            logger.error(f"Error registering C2B URL: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def b2c_payment(self, phone_number, amount, command_id, remarks, occasion, recipient_type):
        """
        Initiate B2C payment (Business to Customer) for refunds/payouts
        
        args:
            phone_number: Recipient phone number
            amount: Amount to send
            command_id: 'SalaryPayment', 'BusinessPayment', 'PromotionPayment', etc.
            remarks: Description of the payment
            occasion: Optional occasion for the payment
            recipient_type: 'MSISDN' (for phone numbers)
        
        Returns:
            dict: Response from M-Pesa API
        """
        try:
            token = self.get_access_token()
            if not token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            # Generate security credential
            security_credential = self._generate_security_credential()
            
            # Prepare request payload
            payload = {
                'InitiatorName': self.initiator_username,
                'SecurityCredential': security_credential,
                'CommandID': command_id,
                'Amount': amount,
                'PartyA': self.business_shortcode,
                'PartyB': phone_number,
                'Remarks': remarks,
                'QueueTimeOutURL': os.getenv('MPESA_QUEUE_TIMEOUT_URL'),
                'ResultURL': os.getenv('MPESA_B2C_RESULT_URL'),
                'Occasion': occasion,
                'RecipientType': recipient_type
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}b2c/v1/paymentrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"B2C payment initiated successfully: {result}")
                return {'success': True, 'data': result}
            else:
                logger.error(f"B2C payment failed: {response.text}")
                return {'success': False, 'message': response.text}
                
        except Exception as e:
            logger.error(f"Error in B2C payment: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _generate_stk_password(self, timestamp):
        """Generate encrypted password for STK Push requests"""
        try:
            # Combine shortcode, passkey, and timestamp
            data = f"{self.shortcode}{self.passkey}{timestamp}"
            
            # Base64 encode the data (simplified approach)
            password = base64.b64encode(data.encode('utf-8')).decode('ascii')
            
            return password
            
        except Exception as e:
            logger.error(f"Error generating STK password: {str(e)}")
            return None
    
    def _generate_security_credential(self):
        """Generate security credential for B2C requests"""
        try:
            # Use the security credential directly (base64 encoded)
            # This should be pre-generated from the Daraja portal
            return self.security_credential
                
        except Exception as e:
            logger.error(f"Error generating security credential: {str(e)}")
            return self.security_credential


class SMSIntegration:
    """
    SMS Integration for payment confirmations
    Supports multiple SMS providers (Africa's Talking, Twilio, etc.)
    """
    
    def __init__(self):
        # SMS Provider Configuration
        self.provider = os.getenv('SMS_PROVIDER', 'africastalking')  # africastalking, twilio, safaricom
        self.api_key = os.getenv('SMS_API_KEY')
        self.username = os.getenv('SMS_USERNAME')
        self.sender_id = os.getenv('SMS_SENDER_ID', 'SmartFly')
        
        # Africa's Talking Configuration
        self.africastalking_url = 'https://api.africastalking.com/version1/messaging'
        
        # Twilio Configuration
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_from_number = os.getenv('TWILIO_FROM_NUMBER')
        
        # M-Pesa SMS Configuration (for Safaricom)
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
        self.environment = os.getenv('MPESA_ENVIRONMENT', 'sandbox')
        
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke/mpesa/'
            self.auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        else:
            self.base_url = 'https://api.safaricom.co.ke/mpesa/'
            self.auth_url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        
        self.access_token = None
        self.token_expiry = None
    
    def generate_access_token(self):
        """Generate OAuth access token for M-Pesa SMS API"""
        try:
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(self.auth_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                self.token_expiry = datetime.now() + timedelta(seconds=3590)
                logger.info("M-Pesa SMS access token generated successfully")
                return True
            else:
                logger.error(f"Failed to generate SMS access token: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating SMS access token: {str(e)}")
            return False
    
    def is_token_valid(self):
        """Check if current access token is still valid"""
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry
    
    def get_access_token(self):
        """Get valid access token, generating new one if needed"""
        if not self.is_token_valid():
            if not self.generate_access_token():
                return None
        return self.access_token
    
    def send_payment_confirmation(self, phone_number, amount, transaction_id, booking_reference, flight_details):
        """
        Send SMS payment confirmation to customer
        
        Args:
            phone_number: Customer phone number
            amount: Amount paid
            transaction_id: M-Pesa transaction ID
            booking_reference: Booking reference number
            flight_details: Flight information (dict with route, date, time)
        
        Returns:
            dict: Response from SMS provider
        """
        try:
            message = self._format_payment_message(amount, transaction_id, booking_reference, flight_details)
            
            if self.provider == 'africastalking':
                return self._send_africastalking_sms(phone_number, message)
            elif self.provider == 'twilio':
                return self._send_twilio_sms(phone_number, message)
            elif self.provider == 'safaricom':
                return self._send_safaricom_sms(phone_number, message)
            else:
                logger.error(f"Unsupported SMS provider: {self.provider}")
                return {'success': False, 'message': 'Unsupported SMS provider'}
                
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {'success': False, message: str(e)}
    
    def _format_payment_message(self, amount, transaction_id, booking_reference, flight_details):
        """Format payment confirmation message"""
        try:
            flight_info = f"{flight_details.get('route', 'NBO-JKQ')} on {flight_details.get('date', 'TBD')} at {flight_details.get('time', 'TBD')}"
            
            message = (
                f"SmartFly: Payment of Ksh {amount:,} confirmed.\n"
                f"Transaction ID: {transaction_id}\n"
                f"Booking Ref: {booking_reference}\n"
                f"Flight: {flight_info}\n"
                f"Thank you for choosing SmartFly!"
            )
            return message
            
        except Exception as e:
            logger.error(f"Error formatting SMS message: {str(e)}")
            return "SmartFly: Payment confirmed. Thank you for choosing SmartFly!"
    
    def _send_africastalking_sms(self, phone_number, message):
        """Send SMS using Africa's Talking API"""
        try:
            payload = {
                'username': self.username,
                'to': phone_number,
                'message': message,
                'from': self.sender_id
            }
            
            headers = {
                'apiKey': self.api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(self.africastalking_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"SMS sent successfully via Africa's Talking: {result}")
                return {'success': True, 'data': result}
            else:
                logger.error(f"SMS sending failed: {response.text}")
                return {'success': False, 'message': response.text}
                
        except Exception as e:
            logger.error(f"Error sending Africa's Talking SMS: {str(e)}")
            return {'success': False, message: str(e)}
    
    def _send_twilio_sms(self, phone_number, message):
        """Send SMS using Twilio API"""
        try:
            from twilio.rest import Client
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            message = client.messages.create(
                body=message,
                from_=self.twilio_from_number,
                to=phone_number
            )
            
            logger.info(f"SMS sent successfully via Twilio: {message.sid}")
            return {'success': True, 'data': {'message_id': message.sid}}
            
        except Exception as e:
            logger.error(f"Error sending Twilio SMS: {str(e)}")
            return {'success': False, message: str(e)}
    
    def _send_safaricom_sms(self, phone_number, message):
        """Send SMS using Safaricom SMS API"""
        try:
            token = self.get_access_token()
            if not token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            payload = {
                'OutboundSMSRequest': {
                    'ClientCtx': {
                        'Rem': 'SmartFly Payment Confirmation',
                        'LinkId': 'PAYCONF' + datetime.now().strftime('%Y%m%d%H%M%S')
                    },
                    'Destinations': [
                        {
                            'MSISDN': phone_number,
                            'Message': message
                        }
                    ]
                }
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}mpesa/outbound/v1/send"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"SMS sent successfully via Safaricom: {result}")
                return {'success': True, 'data': result}
            else:
                logger.error(f"SMS sending failed: {response.text}")
                return {'success': False, 'message': response.text}
                
        except Exception as e:
            logger.error(f"Error sending Safaricom SMS: {str(e)}")
            return {'success': False, message: str(e)}


class EmailIntegration:
    """
    Email Integration for check-in reminders
    Uses SMTP for sending emails
    """
    
    def __init__(self):
        # Email Configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        
        # Safely convert SMTP_PORT to int
        smtp_port_str = os.getenv('SMTP_PORT', '587')
        try:
            self.smtp_port = int(smtp_port_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid SMTP_PORT value: {smtp_port_str}, using default 587")
            self.smtp_port = 587
        
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@smartfly.com')
        self.from_name = os.getenv('FROM_NAME', 'SmartFly Airlines')
    
    def send_checkin_reminder(self, recipient_email, passenger_name, flight_number, flight_date, flight_time, departure_gate):
        """
        Send check-in reminder email to passenger
        
        Args:
            recipient_email: Passenger email address
            passenger_name: Passenger name
            flight_number: Flight number
            flight_date: Flight date
            flight_time: Flight time
            departure_gate: Departure gate number
        
        Returns:
            dict: Response indicating success/failure
        """
        try:
            subject = f"Check-in Reminder: {flight_number} - {passenger_name}"
            
            # Create HTML email body
            body = self._format_checkin_reminder_email(
                passenger_name, flight_number, flight_date, flight_time, departure_gate
            )
            
            # Create message
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = recipient_email
            msg.set_content(body, subtype='html')
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Check-in reminder email sent to {recipient_email}")
            return {'success': True, 'message': 'Email sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {'success': False, message: str(e)}
    
    def _format_checkin_reminder_email(self, passenger_name, flight_number, flight_date, flight_time, departure_gate):
        """Format check-in reminder email HTML body"""
        try:
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #0066cc 0%, #0052a3 100%);
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background: #fff;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .flight-details {{
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                    .flight-info {{
                        display: flex;
                        justify-content: space-between;
                        margin: 10px 0;
                        padding: 10px 0;
                        border-bottom: 1px solid #e9ecef;
                    }}
                    .flight-info:last-child {{
                        border-bottom: none;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 12px 24px;
                        background: #0066cc;
                        color: white;
                        text-decoration: none;
                        border-radius: 5px;
                        margin-top: 20px;
                    }}
                    .footer {{
                        text-align: center;
                        padding: 20px;
                        color: #6c757d;
                        font-size: 12px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✈️ SmartFly Airlines</h1>
                        <p>Check-in Reminder</p>
                    </div>
                    <div class="content">
                        <h2>Dear {passenger_name},</h2>
                        <p>This is a friendly reminder to check in for your upcoming flight:</p>
                        
                        <div class="flight-details">
                            <div class="flight-info">
                                <strong>Flight Number:</strong>
                                <span>{flight_number}</span>
                            </div>
                            <div class="flight-info">
                                <strong>Flight Date:</strong>
                                <span>{flight_date}</span>
                            </div>
                            <div class="flight-info">
                                <strong>Flight Time:</strong>
                                <span>{flight_time}</span>
                            </div>
                            <div class="flight-info">
                                <strong>Departure Gate:</strong>
                                <span>{departure_gate}</span>
                            </div>
                        </div>
                        
                        <p>Check-in opens 24 hours before departure. We recommend checking in online to save time at the airport.</p>
                        
                        <a href="https://smartfly.com/checkin" class="btn">Check In Now</a>
                        
                        <p>If you have any questions, please contact our customer service team.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 SmartFly Airlines. All rights reserved.</p>
                        <p>This is an automated email, please do not reply.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            return html_body
            
        except Exception as e:
            logger.error(f"Error formatting email: {str(e)}")
            return f"<p>Dear {passenger_name},</p><p>This is a reminder to check in for flight {flight_number} on {flight_date} at {flight_time}.</p><p>Gate: {departure_gate}</p>"


# Initialize integration classes with error handling
try:
    mpesa_integration = MpesaIntegration()
except Exception as e:
    logger.error(f"Failed to initialize M-Pesa integration: {str(e)}")
    mpesa_integration = None

try:
    sms_integration = SMSIntegration()
except Exception as e:
    logger.error(f"Failed to initialize SMS integration: {str(e)}")
    sms_integration = None

try:
    email_integration = EmailIntegration()
except Exception as e:
    logger.error(f"Failed to initialize Email integration: {str(e)}")
    email_integration = None