import { Passenger } from '../src/models/passenger';
import { Flight } from '../src/models/flight';
import { db } from '../src/db/index';

const seedDatabase = async () => {
    const passengers: Passenger[] = [
        { id: 1, name: 'John Doe', flightId: 101 },
        { id: 2, name: 'Jane Smith', flightId: 102 },
        { id: 3, name: 'Alice Johnson', flightId: 103 },
    ];

    const flights: Flight[] = [
        { id: 101, flightNumber: 'AA123', destination: 'New York' },
        { id: 102, flightNumber: 'BA456', destination: 'London' },
        { id: 103, flightNumber: 'CA789', destination: 'Tokyo' },
    ];

    try {
        await db.connect();

        await db.query('DELETE FROM passengers');
        await db.query('DELETE FROM flights');

        for (const passenger of passengers) {
            await db.query('INSERT INTO passengers (id, name, flightId) VALUES ($1, $2, $3)', [passenger.id, passenger.name, passenger.flightId]);
        }

        for (const flight of flights) {
            await db.query('INSERT INTO flights (id, flightNumber, destination) VALUES ($1, $2, $3)', [flight.id, flight.flightNumber, flight.destination]);
        }

        console.log('Database seeded successfully');
    } catch (error) {
        console.error('Error seeding database:', error);
    } finally {
        await db.disconnect();
    }
};

seedDatabase();