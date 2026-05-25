// TypeScript service class — dependency injection pattern
import { Injectable } from '@nestjs/common';  // or remove decorator for plain TS

export interface CreateItemDto { name: string; description?: string; price?: number; }
export interface UpdateItemDto extends Partial<CreateItemDto> {}
export interface Item extends Required<CreateItemDto> { id: string; createdAt: Date; }

@Injectable()
export class ItemService {
  private items: Map<string, Item> = new Map();

  async findAll(): Promise<Item[]> {
    return Array.from(this.items.values());
  }

  async findById(id: string): Promise<Item | null> {
    return this.items.get(id) ?? null;
  }

  async create(dto: CreateItemDto): Promise<Item> {
    const item: Item = {
      id:          crypto.randomUUID(),
      name:        dto.name,
      description: dto.description ?? '',
      price:       dto.price       ?? 0,
      createdAt:   new Date(),
    };
    this.items.set(item.id, item);
    return item;
  }

  async update(id: string, dto: UpdateItemDto): Promise<Item | null> {
    const existing = this.items.get(id);
    if (!existing) return null;
    const updated = { ...existing, ...dto };
    this.items.set(id, updated);
    return updated;
  }

  async delete(id: string): Promise<boolean> {
    return this.items.delete(id);
  }
}
