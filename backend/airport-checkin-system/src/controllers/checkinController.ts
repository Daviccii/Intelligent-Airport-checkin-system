class CheckinController {
    checkInPassenger(req, res) {
        // Logic for checking in a passenger
        res.send("Passenger checked in successfully.");
    }

    getCheckInStatus(req, res) {
        // Logic for getting the check-in status of a passenger
        res.send("Check-in status retrieved successfully.");
    }
}

export default CheckinController;