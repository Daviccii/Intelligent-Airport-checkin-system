import express from 'express';
import { createConnection } from 'typeorm';
import { routes } from './routes';
import { dbConfig } from './db';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use('/api', routes);

createConnection(dbConfig)
    .then(() => {
        app.listen(PORT, () => {
            console.log(`Server is running on http://localhost:${PORT}`);
        });
    })
    .catch(error => {
        console.error('Database connection failed:', error);
    });