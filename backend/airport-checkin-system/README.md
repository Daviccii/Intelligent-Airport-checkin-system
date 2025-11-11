# Airport Check-In System

This project is an airport check-in system that allows passengers to check in for their flights and manage flight-related operations. 

## Features

- **Passenger Check-In**: Passengers can check in for their flights and get their check-in status.
- **Flight Management**: Manage flight details and list available flights.
- **Database Integration**: Connects to a database to store and retrieve passenger and flight information.

## Project Structure

```
airport-checkin-system
├── src
│   ├── server.ts
│   ├── controllers
│   ├── services
│   ├── models
│   ├── routes
│   ├── db
│   └── types
├── scripts
├── tests
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd airport-checkin-system
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Set up the environment variables**:
   Copy `.env.example` to `.env` and fill in the required values.

4. **Run database migrations**:
   Ensure your database is running and execute the migration script to create necessary tables.

5. **Start the application**:
   ```bash
   npm start
   ```

## Usage

- To check in a passenger, send a request to the check-in endpoint with the necessary passenger details.
- To get flight details, use the flight management endpoint.

## Testing

Run unit and integration tests to ensure the functionality works as expected:
```bash
npm test
```

## License

This project is licensed under the MIT License.