import { Body, Controller, Get, Post } from '@nestjs/common';
import { SessionsService } from './sessions.service';

@Controller('sessions')
export class SessionsController {
  constructor(private readonly service: SessionsService) {}

  @Post()
  create(@Body() data: { position: { x: number; y: number; z: number }; timestamp: number }) {
    return this.service.save(data);
  }

  @Get()
  findAll() {
    return this.service.findAll();
  }
}
