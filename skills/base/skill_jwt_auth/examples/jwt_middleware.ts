// JWT middleware — jsonwebtoken, Express/Node production pattern
import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

const SECRET = process.env.JWT_SECRET || 'change-me-in-production';

export interface AuthRequest extends Request {
  user?: { id: string; email: string; role?: string };
}

export function authMiddleware(req: AuthRequest, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }
  const token = header.split(' ')[1];
  try {
    const payload = jwt.verify(token, SECRET) as { sub: string; email: string; role?: string };
    req.user = { id: payload.sub, email: payload.email, role: payload.role };
    next();
  } catch {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}

export function createToken(payload: { sub: string; email: string; role?: string }): string {
  return jwt.sign(payload, SECRET, { expiresIn: '1h', algorithm: 'HS256' });
}
