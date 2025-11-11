export class FlightService {
    private flights: any[]; // Replace 'any' with a specific type or interface for flights

    constructor() {
        this.flights = [];
    }

    fetchFlightData(flightId: string) {
        // Logic to fetch flight data by flightId
        return this.flights.find(flight => flight.id === flightId);
    }

    updateFlightStatus(flightId: string, status: string) {
        // Logic to update the status of a flight
        const flight = this.flights.find(flight => flight.id === flightId);
        if (flight) {
            flight.status = status;
            return flight;
        }
        throw new Error('Flight not found');
    }

    listFlights() {
        // Logic to list all flights
        return this.flights;
    }

    addFlight(flight: any) { // Replace 'any' with a specific type or interface for flights
        this.flights.push(flight);
    }
}