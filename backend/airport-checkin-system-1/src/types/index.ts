export interface Passenger {
    id: number;
    name: string;
    flightId: number;
}

export interface Flight {
    id: number;
    flightNumber: string;
    destination: string;
}