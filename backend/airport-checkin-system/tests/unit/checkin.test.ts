import { CheckinController } from '../../src/controllers/checkinController';
import { CheckinService } from '../../src/services/checkinService';

describe('CheckinController', () => {
    let checkinController: CheckinController;
    let checkinService: CheckinService;

    beforeEach(() => {
        checkinService = new CheckinService();
        checkinController = new CheckinController(checkinService);
    });

    describe('checkInPassenger', () => {
        it('should successfully check in a passenger', async () => {
            const passengerData = { id: '1', name: 'John Doe', flightId: 'FL123' };
            jest.spyOn(checkinService, 'processCheckIn').mockResolvedValue(passengerData);

            const result = await checkinController.checkInPassenger(passengerData);
            expect(result).toEqual(passengerData);
        });

        it('should throw an error if check-in fails', async () => {
            const passengerData = { id: '1', name: 'John Doe', flightId: 'FL123' };
            jest.spyOn(checkinService, 'processCheckIn').mockRejectedValue(new Error('Check-in failed'));

            await expect(checkinController.checkInPassenger(passengerData)).rejects.toThrow('Check-in failed');
        });
    });

    describe('getCheckInStatus', () => {
        it('should return check-in status for a passenger', async () => {
            const passengerId = '1';
            const status = { passengerId, checkedIn: true };
            jest.spyOn(checkinService, 'validatePassenger').mockResolvedValue(status);

            const result = await checkinController.getCheckInStatus(passengerId);
            expect(result).toEqual(status);
        });

        it('should throw an error if passenger is not found', async () => {
            const passengerId = '1';
            jest.spyOn(checkinService, 'validatePassenger').mockRejectedValue(new Error('Passenger not found'));

            await expect(checkinController.getCheckInStatus(passengerId)).rejects.toThrow('Passenger not found');
        });
    });
});