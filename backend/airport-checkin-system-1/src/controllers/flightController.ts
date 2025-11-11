export class FlightController {
    constructor(private flightService: FlightService) {}

    async getFlightDetails(req, res) {
        const flightId = req.params.id;
        try {
            const flightDetails = await this.flightService.fetchFlightData(flightId);
            res.status(200).json(flightDetails);
        } catch (error) {
            res.status(500).json({ message: 'Error fetching flight details', error });
        }
    }

    async listFlights(req, res) {
        try {
            const flights = await this.flightService.getAllFlights();
            res.status(200).json(flights);
        } catch (error) {
            res.status(500).json({ message: 'Error listing flights', error });
        }
    }
}