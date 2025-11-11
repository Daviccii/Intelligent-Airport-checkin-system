import { Router } from 'express';
import CheckinController from '../controllers/checkinController';
import FlightController from '../controllers/flightController';

const router = Router();
const checkinController = new CheckinController();
const flightController = new FlightController();

router.post('/checkin', checkinController.checkInPassenger.bind(checkinController));
router.get('/checkin/status', checkinController.getCheckInStatus.bind(checkinController));
router.get('/flights', flightController.listFlights.bind(flightController));
router.get('/flights/:id', flightController.getFlightDetails.bind(flightController));

export default router;