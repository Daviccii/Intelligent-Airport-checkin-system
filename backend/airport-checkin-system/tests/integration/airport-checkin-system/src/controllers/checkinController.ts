class CheckinController {
    constructor(private checkinService: CheckinService) {}

    async checkIn(req: Request, res: Response): Promise<Response> {
        try {
            const { passengerId, flightId } = req.body;
            const result = await this.checkinService.processCheckin(passengerId, flightId);
            return res.status(200).json(result);
        } catch (error) {
            return res.status(500).json({ message: error.message });
        }
    }

    async getCheckinStatus(req: Request, res: Response): Promise<Response> {
        try {
            const { passengerId } = req.params;
            const status = await this.checkinService.validateCheckin(passengerId);
            return res.status(200).json(status);
        } catch (error) {
            return res.status(500).json({ message: error.message });
        }
    }
}

export default CheckinController;