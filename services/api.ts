import { DatasetType, RealtimeEvent, Source } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

type EventListener = (event: RealtimeEvent) => void;
let eventSource: EventSource | null = null;
const listeners = new Set<EventListener>();

function ensureEventSource() {
  if (eventSource) return;
  eventSource = new EventSource(`${API_BASE}/api/events`);
  eventSource.onmessage = (ev) => {
    try {
      const payload = JSON.parse(ev.data) as RealtimeEvent;
      listeners.forEach((listener) => listener(payload));
    } catch (err) {
      console.error('Error parsing SSE payload', err);
    }
  };
  eventSource.onerror = () => {
    console.warn('SSE connection error, attempting to reconnect...');
  };
}

export function subscribeToEvents(listener: EventListener) {
  listeners.add(listener);
  ensureEventSource();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}

export async function fetchDatasets() {
  // Static metadata for now; could be expanded from backend
  return [
    {
      id: DatasetType.BALANCE,
      name: 'Balance de Energía',
      description: 'Ingesta mensual por segmento (Regulados, Libres, COES).',
      metrics: ['regulados', 'libres', 'coes', 'total'],
      grain: 'monthly' as const,
    },
    {
      id: DatasetType.HIDROLOGIA,
      name: 'Hidrología',
      description: 'Flujos y volúmenes de embalses.',
      metrics: ['volumen', 'caudal'],
      grain: 'daily' as const,
    },
  ];
}

export async function fetchSources(): Promise<Source[]> {
  const resp = await fetch(`${API_BASE}/api/sources`);
  if (!resp.ok) throw new Error('No se pudieron obtener las fuentes');
  const data = await resp.json();
  return data.sources || [];
}

export async function registerSource(newSource: Source): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(newSource),
  });
  if (!resp.ok) {
    throw new Error('No se pudo registrar la fuente');
  }
}

export async function fetchBalanceYears(): Promise<number[]> {
  const resp = await fetch(`${API_BASE}/api/balance/years`);
  if (!resp.ok) throw new Error('No se pudieron obtener los años');
  const data = await resp.json();
  return data.years || [];
}

export interface BalanceResponse {
  months: string[];
  regulados: number[];
  libres: number[];
  coes: number[];
  total: number[];
  source_id: string;
  year: number;
  warnings?: string[];
}

export async function fetchBalance(year: number): Promise<BalanceResponse> {
  const resp = await fetch(`${API_BASE}/api/balance/${year}`);
  if (!resp.ok) throw new Error(`No se pudo obtener balance ${year}`);
  return resp.json();
}
