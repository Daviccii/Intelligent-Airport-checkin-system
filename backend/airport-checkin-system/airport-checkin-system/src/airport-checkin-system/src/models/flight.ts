export interface Flight {
    id: number;
    flightNumber: string;
    destination: string;
    departureTime: Date;
    arrivalTime: Date;
    status: string;
}