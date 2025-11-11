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
        await db.passenger.bulkCreate(passengers);
        await db.flight.bulkCreate(flights);
        console.log('Database seeded successfully!');
    } catch (error) {
        console.error('Error seeding database:', error);
    }
};

seedDatabase();