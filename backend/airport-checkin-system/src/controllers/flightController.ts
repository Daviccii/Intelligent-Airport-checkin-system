import { Request, Response } from 'express';
import { FlightService } from '../services/flightService';

export class FlightController {
    private flightService: FlightService;

    constructor() {
        this.flightService = new FlightService();
    }

    public async getFlightDetails(req: Request, res: Response): Promise<void> {
        const flightId = req.params.id;
        try {
            const flightDetails = await this.flightService.fetchFlightInfo(flightId);
            res.status(200).json(flightDetails);
        } catch (error) {
            res.status(500).json({ message: 'Error fetching flight details', error });
        }
    }

    public async listFlights(req: Request, res: Response): Promise<void> {
        try {
            const flights = await this.flightService.listAllFlights();
            res.status(200).json(flights);
        } catch (error) {
            res.status(500).json({ message: 'Error listing flights', error });
        }
    }
}