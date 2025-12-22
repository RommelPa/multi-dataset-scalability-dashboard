
import { DatasetMetadata, Source, DatasetType, Fact, RealtimeEvent } from '../types';

class MockBackend {
  private datasets: DatasetMetadata[] = [
    {
      id: DatasetType.BALANCE,
      name: 'Balance de Energía',
      description: 'Monthly energy balance reporting by market segment (Regulated, Free, COES).',
      metrics: ['regulados', 'libres', 'coes', 'total'],
      grain: 'monthly'
    },
    {
      id: DatasetType.HIDROLOGIA,
      name: 'Hidrología',
      description: 'Daily tracking of reservoir volumes and river flows across the national network.',
      metrics: ['volumen', 'caudal'],
      grain: 'daily'
    }
  ];

  private sources: Source[] = [
    { source_id: 'central-sur-2024', dataset_id: DatasetType.BALANCE, file_name: 'balance_sur.xlsx', enabled: true, last_ingested: new Date().toISOString() },
    { source_id: 'reservoir-rimac', dataset_id: DatasetType.HIDROLOGIA, file_name: 'rimac_hydro.xlsx', enabled: true, last_ingested: new Date().toISOString() }
  ];

  private listeners: ((event: RealtimeEvent) => void)[] = [];

  getDatasets() {
    return this.datasets;
  }

  getSources() {
    return this.sources;
  }

  registerSource(source: Source) {
    this.sources.push(source);
    this.emit({
      type: 'DATASET_UPDATED',
      dataset_id: source.dataset_id,
      source_id: source.source_id,
      ts: new Date().toISOString(),
      message: `Source '${source.source_id}' registered successfully.`
    });
  }

  simulateIngestion(sourceId: string) {
    const source = this.sources.find(s => s.source_id === sourceId);
    if (!source) return;

    source.last_ingested = new Date().toISOString();
    
    // Simulate some logic...
    setTimeout(() => {
      this.emit({
        type: 'DATASET_UPDATED',
        dataset_id: source.dataset_id,
        source_id: source.source_id,
        ts: new Date().toISOString(),
        message: `ETL finished. Normalization successful for ${source.file_name}`
      });
    }, 1500);
  }

  subscribe(callback: (event: RealtimeEvent) => void) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }

  private emit(event: RealtimeEvent) {
    this.listeners.forEach(l => l(event));
  }

  // DATA FETCHING SIMULATION
  async getBalanceData(sourceId: string, year: number) {
    // Generate synthetic data
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic'];
    const baseReg = 50000 + Math.random() * 20000;
    const baseLib = 80000 + Math.random() * 30000;
    const baseCoes = 10000 + Math.random() * 10000;

    const regulados = months.map(() => baseReg + (Math.random() - 0.5) * 5000);
    const libres = months.map(() => baseLib + (Math.random() - 0.5) * 8000);
    const coes = months.map(() => baseCoes + (Math.random() - 0.5) * 2000);
    const total = months.map((_, i) => regulados[i] + libres[i] + coes[i]);

    return { months, regulados, libres, coes, total };
  }

  async getHydrologyData(sourceId: string, from: string, to: string) {
    // Generate daily time series
    const start = new Date(from);
    const end = new Date(to);
    const points = [];
    const curr = new Date(start);

    while (curr <= end) {
      points.push(curr.toISOString().split('T')[0]);
      curr.setDate(curr.getDate() + 1);
    }

    const volPoints = points.map(d => [d, 500 + Math.sin(points.indexOf(d) / 10) * 100 + Math.random() * 20]);
    const cauPoints = points.map(d => [d, 50 + Math.cos(points.indexOf(d) / 10) * 20 + Math.random() * 5]);

    return {
      volumen: { metric: 'volumen', unit: 'hm3', points: volPoints },
      caudal: { metric: 'caudal', unit: 'm3/s', points: cauPoints }
    };
  }
}

export const mockBackend = new MockBackend();
