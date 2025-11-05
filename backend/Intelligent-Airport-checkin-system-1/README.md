# Intelligent Airport Check-in System

## Overview
The Intelligent Airport Check-in System is a command-line application designed to streamline the passenger check-in process at airports. It allows for the registration of passengers, viewing of registered passengers, and management of passenger data through a JSON file.

## Features
- Register passengers with their name, passport/ID number, flight number, and automatically assigned seat number.
- View a list of all registered passengers along with their details.
- Data persistence through JSON file storage.

## Setup Instructions
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd Intelligent-Airport-checkin-system
   ```
3. Install the required dependencies:
   ```
   pip install -r backend/requirements.txt
   ```

## Usage
To run the application, execute the following command:
```
python backend/app.py
```
Follow the on-screen prompts to register passengers or view the list of registered passengers.

## Testing
Unit tests for the application can be found in the `backend/tests/test_app.py` file. To run the tests, use:
```
pytest backend/tests
```

## License
This project is licensed under the MIT License.