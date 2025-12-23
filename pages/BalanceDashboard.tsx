import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from 'recharts';
import { ChartCard } from '../components/ChartCard';
import {
  BalanceEnergyPoint,
  BalanceOverviewResponse,
  BalanceSalesPoint,
  DatasetType,
  Source,
} from '../types';
import { fetchBalanceOverview, fetchSources, subscribeToEvents } from '../services/api';

const MONTH_ORDER = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic'];

const ENERGY_COLORS = {
  regulados: '#1d4ed8',
  libres: '#f97316',
  coes: '#10b981',
  total: '#cbd5e1',
};

const STACKED_COLORS = {
  regulados: '#ef4444',
  libres: '#22c55e',
  coes: '#2563eb',
  total: '#0d9488',
};

const SALES_COLORS = {
  regulados: '#16a34a',
  libres: '#ef4444',
  coes: '#facc15',
  otros: '#8b5cf6',
  total: '#e2e8f0',
};

type EnergyRow = BalanceEnergyPoint & {
  regulados: number;
  libres: number;
  coes: number;
  perdidas: number;
  servicios_aux: number;
  ventaEnergia: number;
  totalMercados: number;
};

type SalesRow = BalanceSalesPoint;

const monthIndex = (month: string) => MONTH_ORDER.indexOf(month);

const formatNumber = (value: number, decimals = 1) =>
  value.toLocaleString('es-PE', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const BalanceDashboard: React.FC = () => {
  const [overview, setOverview] = useState<BalanceOverviewResponse | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('balance-xlsx');
  const [selectedMonthKey, setSelectedMonthKey] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sourceList, data] = await Promise.all([fetchSources(), fetchBalanceOverview()]);
      const balanceSources = sourceList.filter((s) => s.dataset_id === DatasetType.BALANCE);
      setSources(balanceSources);
      setSelectedSource(balanceSources[0]?.source_id || data.source_id || 'balance-xlsx');
      setOverview(data);
      if (data.last_year && data.last_month) {
        const monthIdx = monthIndex(data.last_month);
        setSelectedMonthKey(`${data.last_year}-${String(monthIdx + 1).padStart(2, '0')}`);
      }
    } catch (err) {
      console.error(err);
      setError('No se pudo cargar el balance de energía');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeToEvents((event) => {
      if (event.dataset_id === DatasetType.BALANCE) {
        loadData();
      }
    });
    return () => unsubscribe();
  }, []);

  const energyData: EnergyRow[] = useMemo(() => {
    if (!overview) return [];
    const sorted = [...overview.energy_points].sort((a, b) => {
      if (a.year === b.year) return monthIndex(a.month) - monthIndex(b.month);
      return a.year - b.year;
    });
    return sorted.map((row) => ({
      ...row,
      regulados: row.regulados_mwh / 1000,
      libres: row.libres_mwh / 1000,
      coes: row.coes_mwh / 1000,
      perdidas: row.perdidas_mwh / 1000,
      servicios_aux: row.servicios_aux_mwh / 1000,
      ventaEnergia: row.venta_energia_mwh / 1000,
      totalMercados: row.total_mercados_mwh / 1000,
    }));
  }, [overview]);

  const salesData: SalesRow[] = useMemo(() => {
    if (!overview) return [];
    const sorted = [...overview.sales_points].sort((a, b) => {
      if (a.year === b.year) return monthIndex(a.month) - monthIndex(b.month);
      return a.year - b.year;
    });
    return sorted;
  }, [overview]);

  const donutPoint = useMemo(() => {
    if (!overview || !selectedMonthKey) return null;
    const point = energyData.find((p) => p.period === selectedMonthKey);
    return point || null;
  }, [energyData, overview, selectedMonthKey]);

  const donutOptions = useMemo(() => {
    if (!overview) return [];
    return energyData
      .filter((p) => p.year === overview.last_year)
      .map((p) => ({ key: p.period, label: `${p.month}-${p.year}` }));
  }, [energyData, overview]);

  const totalVentaEnergia = useMemo(() => energyData.reduce((sum, row) => sum + row.ventaEnergia, 0), [energyData]);
  const totalMercados = useMemo(() => energyData.reduce((sum, row) => sum + row.totalMercados, 0), [energyData]);

  const renderEnergyTable = () => (
    <div className="overflow-x-auto mt-4">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-2 py-1 text-left text-slate-600">Mes</th>
            <th className="px-2 py-1 text-left">Regulados</th>
            <th className="px-2 py-1 text-left">Libres</th>
            <th className="px-2 py-1 text-left">COES-SPOT</th>
            <th className="px-2 py-1 text-left">Total mercados</th>
          </tr>
        </thead>
        <tbody>
          {energyData.map((row) => (
            <tr key={row.period} className="border-b border-slate-100">
              <td className="px-2 py-1 font-semibold text-slate-700">{row.label}</td>
              <td className="px-2 py-1">{formatNumber(row.regulados)}</td>
              <td className="px-2 py-1">{formatNumber(row.libres)}</td>
              <td className="px-2 py-1">{formatNumber(row.coes)}</td>
              <td className="px-2 py-1 font-semibold">{formatNumber(row.totalMercados)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderStackedTable = () => (
    <div className="overflow-x-auto mt-4">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-2 py-1 text-left text-slate-600">Mes</th>
            <th className="px-2 py-1 text-left">Mercado Regulado</th>
            <th className="px-2 py-1 text-left">Mercado Libre</th>
            <th className="px-2 py-1 text-left">Mercado Spot-COES</th>
            <th className="px-2 py-1 text-left">Total</th>
          </tr>
        </thead>
        <tbody>
          {energyData.map((row) => (
            <tr key={row.period} className="border-b border-slate-100">
              <td className="px-2 py-1 font-semibold text-slate-700">{row.label}</td>
              <td className="px-2 py-1">{formatNumber(row.regulados)}</td>
              <td className="px-2 py-1">{formatNumber(row.libres)}</td>
              <td className="px-2 py-1">{formatNumber(row.coes)}</td>
              <td className="px-2 py-1 font-semibold">{formatNumber(row.totalMercados)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderSalesTable = () => (
    <div className="overflow-x-auto mt-4">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-2 py-1 text-left text-slate-600">Mes</th>
            <th className="px-2 py-1 text-left">Regulados</th>
            <th className="px-2 py-1 text-left">Libres</th>
            <th className="px-2 py-1 text-left">COES-SPOT</th>
            <th className="px-2 py-1 text-left">Otros</th>
            <th className="px-2 py-1 text-left">Total</th>
          </tr>
        </thead>
        <tbody>
          {salesData.map((row) => (
            <tr key={row.period} className="border-b border-slate-100">
              <td className="px-2 py-1 font-semibold text-slate-700">{row.label}</td>
              <td className="px-2 py-1">{formatNumber(row.regulados, 2)}</td>
              <td className="px-2 py-1">{formatNumber(row.libres, 2)}</td>
              <td className="px-2 py-1">{formatNumber(row.coes_spot, 2)}</td>
              <td className="px-2 py-1">{formatNumber(row.otros, 2)}</td>
              <td className="px-2 py-1 font-semibold">{formatNumber(row.total, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-orange-100 text-orange-600 rounded-lg">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Balance de Energía</h1>
            <p className="text-xs text-slate-500 uppercase font-semibold">GWh por mercados (2016-2025)</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <label className="text-xs text-slate-500 font-semibold">Fuente</label>
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          >
            {(sources.length === 0 ? [{ source_id: selectedSource }] : sources).map((s) => (
              <option key={s.source_id} value={s.source_id}>{s.source_id}</option>
            ))}
          </select>
          <div className="text-xs text-slate-400">{loading ? 'Actualizando…' : 'Actualizado'}</div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold text-slate-400 uppercase">Venta de Energía oficial</div>
          <div className="text-3xl font-black text-slate-800 mt-2">{formatNumber(totalVentaEnergia, 1)} GWh</div>
          <p className="text-xs text-slate-500 mt-1">VentaEnergía = A emp. Distribuidoras + A clientes Libres</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold text-slate-400 uppercase">Total mercados (Reg+Lib+COES)</div>
          <div className="text-3xl font-black text-slate-800 mt-2">{formatNumber(totalMercados, 1)} GWh</div>
          <p className="text-xs text-slate-500 mt-1">Usado en los gráficos apilados con línea y barras con TOTAL de fondo</p>
        </div>
      </div>

      <ChartCard title="Ventas de energía por mercados (GWh)">
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={energyData} barCategoryGap="25%" barGap={-12}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" />
              <YAxis tickFormatter={(v) => `${v}`} label={{ value: 'GWh', angle: -90, position: 'insideLeft' }} />
              <Tooltip
                formatter={(value: number) => `${formatNumber(value as number)} GWh`}
                labelFormatter={(label) => `Mes: ${label}`}
              />
              <Legend />
              <Bar dataKey="totalMercados" name="TOTAL" fill={ENERGY_COLORS.total} barSize={38} radius={[6, 6, 0, 0]} />
              <Bar dataKey="regulados" name="REGULADOS" stackId="markets" fill={ENERGY_COLORS.regulados} barSize={24} radius={[6, 6, 0, 0]} />
              <Bar dataKey="libres" name="LIBRES" stackId="markets" fill={ENERGY_COLORS.libres} barSize={24} radius={[6, 6, 0, 0]} />
              <Bar dataKey="coes" name="COES-SPOT" stackId="markets" fill={ENERGY_COLORS.coes} barSize={24} radius={[6, 6, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        {renderEnergyTable()}
      </ChartCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Balance de Energía (MWh) - Donut por mes">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2 items-center">
              <label className="text-xs font-semibold text-slate-500">Mes:</label>
              <select
                value={selectedMonthKey}
                onChange={(e) => setSelectedMonthKey(e.target.value)}
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                {donutOptions.map((opt) => (
                  <option key={opt.key} value={opt.key}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div className="h-[320px]">
              {donutPoint ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip formatter={(value: number) => `${formatNumber(value as number, 0)} MWh`} />
                    <Pie
                      data={[
                        { name: 'Mercado Regulado', value: donutPoint.regulados_mwh },
                        { name: 'Mercado Libre', value: donutPoint.libres_mwh },
                        { name: 'COES', value: donutPoint.coes_mwh },
                        { name: 'Pérdidas', value: donutPoint.perdidas_mwh },
                        { name: 'Servicios Auxiliares', value: donutPoint.servicios_aux_mwh },
                      ]}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={70}
                      outerRadius={110}
                      label={(entry) => {
                        const total =
                          donutPoint.regulados_mwh +
                          donutPoint.libres_mwh +
                          donutPoint.coes_mwh +
                          donutPoint.perdidas_mwh +
                          donutPoint.servicios_aux_mwh;
                        const pct = total ? Math.round((entry.value / total) * 100) : 0;
                        return `${entry.name}; ${formatNumber(entry.value, 0)}; ${pct}%`;
                      }}
                      labelLine={false}
                    >
                      <Cell fill={ENERGY_COLORS.regulados} />
                      <Cell fill={ENERGY_COLORS.libres} />
                      <Cell fill={ENERGY_COLORS.coes} />
                      <Cell fill="#94a3b8" />
                      <Cell fill="#8b5cf6" />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 text-sm">Sin datos para el mes seleccionado</div>
              )}
            </div>
          </div>
        </ChartCard>

        <ChartCard title="Ventas de energía (GWh) - Barras apiladas + línea Total">
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={energyData} barCategoryGap="40%">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" />
                <YAxis tickFormatter={(v) => `${v}`} label={{ value: 'GWh', angle: -90, position: 'insideLeft' }} />
                <Tooltip formatter={(value: number) => `${formatNumber(value as number)} GWh`} />
                <Legend />
                <Bar dataKey="regulados" name="Mercado Regulado" stackId="stacked" fill={STACKED_COLORS.regulados} radius={[6, 6, 0, 0]} />
                <Bar dataKey="libres" name="Mercado Libre" stackId="stacked" fill={STACKED_COLORS.libres} radius={[6, 6, 0, 0]} />
                <Bar dataKey="coes" name="Mercado Spot-COES" stackId="stacked" fill={STACKED_COLORS.coes} radius={[6, 6, 0, 0]} />
                <Line type="monotone" dataKey="totalMercados" name="Total mercados" stroke={STACKED_COLORS.total} strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {renderStackedTable()}
        </ChartCard>
      </div>

      <ChartCard title="Ventas de energía (Millones S/)">
        {salesData.length === 0 ? (
          <div className="text-slate-500 text-sm">No se detectó tabla en soles en el Excel.</div>
        ) : (
          <>
            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={salesData} barCategoryGap="25%" barGap={-12}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" />
                  <YAxis tickFormatter={(v) => `${v}`} label={{ value: 'Millones S/ ', angle: -90, position: 'insideLeft' }} />
                  <Tooltip formatter={(value: number) => `${formatNumber(value as number, 2)} MM S/`} />
                  <Legend />
                  <Bar dataKey="total" name="TOTAL" fill={SALES_COLORS.total} barSize={38} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="regulados" name="REGULADOS" stackId="sales" fill={SALES_COLORS.regulados} barSize={24} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="libres" name="LIBRES" stackId="sales" fill={SALES_COLORS.libres} barSize={24} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="coes_spot" name="COES-SPOT" stackId="sales" fill={SALES_COLORS.coes} barSize={24} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="otros" name="OTROS" stackId="sales" fill={SALES_COLORS.otros} barSize={24} radius={[6, 6, 0, 0]} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            {renderSalesTable()}
          </>
        )}
      </ChartCard>

      {overview?.warnings && overview.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-lg">
          <div className="font-semibold mb-1">Advertencias del parser</div>
          <ul className="list-disc list-inside text-sm space-y-1">
            {overview.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export { BalanceDashboard };
