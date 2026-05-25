// NestJS module + controller + service — production pattern
import { Module, Controller, Get, Post, Body, Param,
         Injectable, NotFoundException, HttpCode } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

// ── Service ──────────────────────────────────────────────────────────────────
@Injectable()
export class ItemService {
  constructor(
    @InjectRepository(ItemEntity)
    private readonly repo: Repository<ItemEntity>,
  ) {}

  findAll() { return this.repo.find(); }

  async findOne(id: string) {
    const item = await this.repo.findOneBy({ id });
    if (!item) throw new NotFoundException(`Item ${id} not found`);
    return item;
  }

  create(dto: CreateItemDto) {
    const item = this.repo.create(dto);
    return this.repo.save(item);
  }
}

// ── Controller ───────────────────────────────────────────────────────────────
@Controller('items')
export class ItemController {
  constructor(private readonly service: ItemService) {}

  @Get()       getAll()                     { return this.service.findAll(); }
  @Get(':id')  getOne(@Param('id') id: string) { return this.service.findOne(id); }

  @Post()
  @HttpCode(201)
  create(@Body() dto: CreateItemDto)        { return this.service.create(dto); }
}

// ── Module ───────────────────────────────────────────────────────────────────
@Module({
  imports:     [TypeOrmModule.forFeature([ItemEntity])],
  controllers: [ItemController],
  providers:   [ItemService],
  exports:     [ItemService],
})
export class ItemModule {}
