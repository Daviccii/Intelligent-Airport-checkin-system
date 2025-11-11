import { CheckinController } from '../../src/controllers/checkinController';
import { CheckinService } from '../../src/services/checkinService';

describe('CheckinController', () => {
    let checkinController: CheckinController;
    let checkinService: CheckinService;

    beforeEach(() => {
        checkinService = new CheckinService();
        checkinController = new CheckinController(checkinService);
    });

    describe('checkIn', () => {
        it('should successfully check in a passenger', async () => {
            const mockRequest = {
                body: {
                    passengerId: '123',
                    flightId: '456'
                }
            } as any;

            const mockResponse = {
                status: jest.fn().mockReturnThis(),
                json: jest.fn()
            };

            jest.spyOn(checkinService, 'processCheckin').mockResolvedValue(true);

            await checkinController.checkIn(mockRequest, mockResponse);

            expect(mockResponse.status).toHaveBeenCalledWith(200);
            expect(mockResponse.json).toHaveBeenCalledWith({ message: 'Check-in successful' });
        });

        it('should return an error if check-in fails', async () => {
            const mockRequest = {
                body: {
                    passengerId: '123',
                    flightId: '456'
                }
            } as any;

            const mockResponse = {
                status: jest.fn().mockReturnThis(),
                json: jest.fn()
            };

            jest.spyOn(checkinService, 'processCheckin').mockResolvedValue(false);

            await checkinController.checkIn(mockRequest, mockResponse);

            expect(mockResponse.status).toHaveBeenCalledWith(400);
            expect(mockResponse.json).toHaveBeenCalledWith({ message: 'Check-in failed' });
        });
    });

    describe('getCheckinStatus', () => {
        it('should return check-in status for a passenger', async () => {
            const mockRequest = {
                params: {
                    passengerId: '123'
                }
            } as any;

            const mockResponse = {
                status: jest.fn().mockReturnThis(),
                json: jest.fn()
            };

            jest.spyOn(checkinService, 'validateCheckin').mockResolvedValue({ checkedIn: true });

            await checkinController.getCheckinStatus(mockRequest, mockResponse);

            expect(mockResponse.status).toHaveBeenCalledWith(200);
            expect(mockResponse.json).toHaveBeenCalledWith({ checkedIn: true });
        });

        it('should return an error if passenger not found', async () => {
            const mockRequest = {
                params: {
                    passengerId: '999'
                }
            } as any;

            const mockResponse = {
                status: jest.fn().mockReturnThis(),
                json: jest.fn()
            };

            jest.spyOn(checkinService, 'validateCheckin').mockResolvedValue(null);

            await checkinController.getCheckinStatus(mockRequest, mockResponse);

            expect(mockResponse.status).toHaveBeenCalledWith(404);
            expect(mockResponse.json).toHaveBeenCalledWith({ message: 'Passenger not found' });
        });
    });
});