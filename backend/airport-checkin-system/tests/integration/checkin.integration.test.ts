import request from 'supertest';
import { app } from '../../src/server'; // Adjust the import based on your server setup
import { createPassenger, createFlight } from '../helpers/testHelpers'; // Assuming you have helper functions for test setup

describe('Check-in Integration Tests', () => {
    let passengerId;
    let flightId;

    beforeAll(async () => {
        // Create a flight and a passenger for testing
        flightId = await createFlight({ flightNumber: 'AA123', destination: 'New York' });
        passengerId = await createPassenger({ name: 'John Doe', flightId });
    });

    afterAll(async () => {
        // Clean up test data
        await request(app).delete(`/api/passengers/${passengerId}`);
        await request(app).delete(`/api/flights/${flightId}`);
    });

    it('should check in a passenger successfully', async () => {
        const response = await request(app)
            .post('/api/checkin')
            .send({ passengerId });

        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('message', 'Check-in successful');
    });

    it('should return check-in status for a passenger', async () => {
        await request(app).post('/api/checkin').send({ passengerId });

        const response = await request(app)
            .get(`/api/checkin/status/${passengerId}`);

        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('status', 'Checked In');
    });
});