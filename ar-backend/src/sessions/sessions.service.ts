import { Injectable } from '@nestjs/common';

interface SessionData {
  position: { x: number; y: number; z: number };
  timestamp: number;
}

@Injectable()
export class SessionsService {
  private sessions: (SessionData & { id: number })[] = [];
  private nextId = 1;

  save(data: SessionData) {
    const entry = { id: this.nextId++, ...data };
    this.sessions.push(entry);
    return entry;
  }

  findAll() {
    return this.sessions;
  }
}
