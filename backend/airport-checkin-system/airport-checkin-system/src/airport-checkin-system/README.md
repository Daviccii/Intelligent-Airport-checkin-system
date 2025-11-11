# Airport Check-In System

This project is an airport check-in system that allows passengers to check in for their flights, manage flight information, and handle related operations.

## Features

- **Passenger Check-In**: Passengers can check in for their flights and receive their check-in status.
- **Flight Management**: Manage flight details, including fetching flight information and updating flight statuses.
- **Database Integration**: Connects to a database to store and retrieve passenger and flight data.
- **Testing**: Includes unit and integration tests to ensure the system works as expected.

## Project Structure

```
airport-checkin-system
├── src
│   ├── index.ts               # Main entry point of the application
│   ├── server.ts              # Sets up the Express server
│   ├── controllers            # Contains controllers for handling requests
│   │   ├── checkinController.ts
│   │   └── flightController.ts
│   ├── services               # Contains business logic for the application
│   │   ├── checkinService.ts
│   │   └── flightService.ts
│   ├── models                 # Defines data models
│   │   ├── passenger.ts
│   │   └── flight.ts
│   ├── routes                 # Sets up application routes
│   │   └── index.ts
│   ├── db                    # Database connection and migrations
│   │   ├── index.ts
│   │   └── migrations
│   │       └── 001_create_tables.sql
│   └── types                  # TypeScript interfaces
│       └── index.ts
├── scripts                    # Scripts for seeding the database
│   └── seed.ts
├── tests                      # Contains unit and integration tests
│   ├── unit
│   │   └── checkin.test.ts
│   └── integration
│       └── checkin.integration.test.ts
├── Dockerfile                 # Docker configuration for the application
├── docker-compose.yml         # Docker Compose configuration
├── package.json               # npm configuration file
├── tsconfig.json              # TypeScript configuration file
└── README.md                  # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd airport-checkin-system
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Set up the database:
   - Update the database configuration in `src/db/index.ts`.
   - Run the migrations to create necessary tables:
     ```
     # Assuming you have a SQL client set up
     psql -U <username> -d <database> -f src/db/migrations/001_create_tables.sql
     ```

4. Start the application:
   ```
   npm start
   ```

5. Run tests:
   ```
   npm test
   ```

## Usage

- Access the API endpoints for check-in and flight management through the configured server URL.
- Refer to the controller files for specific endpoint details and request/response formats.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.