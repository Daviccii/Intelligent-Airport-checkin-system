export class Passenger {
    id: number;
    name: string;
    flightId: number;

    constructor(id: number, name: string, flightId: number) {
        this.id = id;
        this.name = name;
        this.flightId = flightId;
    }
}