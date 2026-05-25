// Express.js app with proper middleware setup — production pattern
import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import 'dotenv/config';

export function createApp(): Application {
  const app = express();

  // Security & parsing
  app.use(helmet());
  app.use(cors({ origin: process.env.CORS_ORIGIN || '*', credentials: true }));
  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true }));

  // Health check
  app.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // 404 handler
  app.use((_req: Request, res: Response) => {
    res.status(404).json({ error: 'Not found' });
  });

  // Global error handler
  app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error(err.stack);
    res.status(500).json({ error: process.env.NODE_ENV === 'production' ? 'Internal error' : err.message });
  });

  return app;
}

// src/index.ts entry point pattern:
// import { createApp } from './app';
// const app = createApp();
// const PORT = Number(process.env.PORT) || 3000;
// app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
