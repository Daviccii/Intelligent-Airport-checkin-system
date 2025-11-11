import { Router } from 'express';
import CheckinController from '../controllers/checkinController';
import FlightController from '../controllers/flightController';

const router = Router();
const checkinController = new CheckinController();
const flightController = new FlightController();

// Check-in routes
router.post('/checkin', checkinController.checkIn);
router.get('/checkin/status/:id', checkinController.getCheckinStatus);

// Flight routes
router.get('/flights', flightController.listFlights);
router.get('/flights/:id', flightController.getFlightDetails);

export default router;