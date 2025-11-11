export class Flight {
    id: number;
    flightNumber: string;
    destination: string;

    constructor(id: number, flightNumber: string, destination: string) {
        this.id = id;
        this.flightNumber = flightNumber;
        this.destination = destination;
    }
}