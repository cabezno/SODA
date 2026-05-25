// Express REST router — full CRUD pattern with error handling
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';

const router = Router();

// Input validation schema
const CreateItemSchema = z.object({
  name:        z.string().min(1).max(255),
  description: z.string().optional(),
  price:       z.number().positive().optional(),
});

// GET /items
router.get('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const page  = Number(req.query.page)  || 1;
    const limit = Number(req.query.limit) || 20;
    // Replace with your service call:
    // const items = await itemService.findAll({ page, limit });
    res.json({ data: [], page, limit, total: 0 });
  } catch (err) { next(err); }
});

// GET /items/:id
router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    // const item = await itemService.findById(req.params.id);
    // if (!item) return res.status(404).json({ error: 'Not found' });
    res.json({ id: req.params.id });
  } catch (err) { next(err); }
});

// POST /items
router.post('/', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const body = CreateItemSchema.parse(req.body);
    // const item = await itemService.create(body);
    res.status(201).json(body);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    next(err);
  }
});

// DELETE /items/:id
router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    // await itemService.delete(req.params.id);
    res.status(204).send();
  } catch (err) { next(err); }
});

export default router;
