// Next.js 14 App Router — API route handler production pattern
import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';

const CreateSchema = z.object({
  name:  z.string().min(1),
  email: z.string().email(),
});

// GET /api/items
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const page  = Number(searchParams.get('page'))  || 1;
    const limit = Number(searchParams.get('limit')) || 20;
    // const items = await db.item.findMany({ skip: (page-1)*limit, take: limit });
    return NextResponse.json({ data: [], page, limit });
  } catch (err) {
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}

// POST /api/items
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const data = CreateSchema.parse(body);
    // const item = await db.item.create({ data });
    return NextResponse.json(data, { status: 201 });
  } catch (err) {
    if (err instanceof z.ZodError) {
      return NextResponse.json({ error: err.errors }, { status: 400 });
    }
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
