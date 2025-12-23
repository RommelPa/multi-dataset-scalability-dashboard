
export enum DatasetType {
  BALANCE = 'balance',
  HIDROLOGIA = 'hidrologia'
}

export interface DatasetMetadata {
  id: DatasetType;
  name: string;
  description: string;
  metrics: string[];
  grain: 'monthly' | 'daily';
}

export interface Source {
  source_id: string;
  dataset_id: DatasetType;
  file_name: string;
  enabled: boolean;
  last_ingested?: string;
}

export interface Fact {
  dataset_id: string;
  source_id: string;
  date: string; // ISO YYYY-MM-DD
  metric: string;
  value: number;
  unit: string;
  updated_at: string;
}

export interface ETLRun {
  id: string;
  dataset_id: string;
  source_id: string;
  ran_at: string;
  status: 'SUCCESS' | 'ERROR' | 'WARNING';
  parser_name: string;
  message: string;
  warnings?: string[];
}

export interface RealtimeEvent {
  type: 'DATASET_UPDATED' | 'ETL_ERROR';
  dataset_id: DatasetType | 'balance';
  source_id: string;
  ts?: string;
  year?: number;
  warnings?: string[];
  message?: string;
}

export interface BalanceEnergyPoint {
  year: number;
  month: string;
  period: string;
  label: string;
  regulados_mwh: number;
  libres_mwh: number;
  coes_mwh: number;
  perdidas_mwh: number;
  servicios_aux_mwh: number;
  venta_energia_mwh: number;
  total_mercados_mwh: number;
}

export interface BalanceSalesPoint {
  year: number;
  month: string;
  period: string;
  label: string;
  regulados: number;
  libres: number;
  coes_spot: number;
  otros: number;
  total: number;
}

export interface BalanceOverviewResponse {
  years: number[];
  last_year: number | null;
  last_month: string | null;
  source_id: string;
  energy_points: BalanceEnergyPoint[];
  sales_points: BalanceSalesPoint[];
  warnings?: string[];
}
