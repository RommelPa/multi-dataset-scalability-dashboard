
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChartCard } from '../components/ChartCard';
import { fetchBalance, fetchBalanceYears, fetchSources, subscribeToEvents } from '../services/api';
import { DatasetType, Source } from '../types';

declare const echarts: any;

export const BalanceDashboard: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totals, setTotals] = useState<{regulados: number; libres: number; coes: number; total: number}>({regulados: 0, libres: 0, coes: 0, total: 0});

  const mainChartRef = useRef<HTMLDivElement>(null);
  const donutChartRef = useRef<HTMLDivElement>(null);

  const refreshYears = useCallback(async () => {
    try {
      const availableYears = await fetchBalanceYears();
      setYears(availableYears);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBalance(year);
      const totalRegulados = data.regulados.reduce((a, b) => a + b, 0);
      const totalLibres = data.libres.reduce((a, b) => a + b, 0);
      const totalCoes = data.coes.reduce((a, b) => a + b, 0);
      const summaryTotals = {
        regulados: totalRegulados / 1000,
        libres: totalLibres / 1000,
        coes: totalCoes / 1000,
        total: (totalRegulados + totalLibres + totalCoes) / 1000,
      };
      setTotals(summaryTotals);
      
      if (mainChartRef.current) {
        const chart = echarts.getInstanceByDom(mainChartRef.current) || echarts.init(mainChartRef.current);
        chart.setOption({
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['Regulados', 'Libres', 'COES', 'Total'], bottom: 0 },
          grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
          xAxis: { type: 'category', data: data.months },
          yAxis: { type: 'value', name: 'GWh' },
          series: [
            { name: 'Regulados', type: 'bar', stack: 'total', color: '#6366f1', data: data.regulados.map(v => v/1000) },
            { name: 'Libres', type: 'bar', stack: 'total', color: '#f59e0b', data: data.libres.map(v => v/1000) },
            { name: 'COES', type: 'bar', stack: 'total', color: '#10b981', data: data.coes.map(v => v/1000) },
            { name: 'Total', type: 'line', color: '#ef4444', data: data.total.map(v => v/1000), smooth: true }
          ]
        });
      }
  
      if (donutChartRef.current) {
        const chart = echarts.getInstanceByDom(donutChartRef.current) || echarts.init(donutChartRef.current);
        chart.setOption({
          tooltip: { trigger: 'item', formatter: '{b}: {c} GWh ({d}%)' },
          legend: { orient: 'vertical', left: 'left', textStyle: { fontSize: 10 } },
          series: [{
            name: 'Acumulado Anual',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
            label: { show: false },
            data: [
              { value: summaryTotals.regulados.toFixed(1), name: 'Regulados', itemStyle: { color: '#6366f1' } },
              { value: summaryTotals.libres.toFixed(1), name: 'Libres', itemStyle: { color: '#f59e0b' } },
              { value: summaryTotals.coes.toFixed(1), name: 'COES', itemStyle: { color: '#10b981' } }
            ]
          }]
        });
      }
    } catch (err) {
      console.error(err);
      setError('No se pudo obtener los datos del año seleccionado');
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    const load = async () => {
      try {
        const [apiSources, availableYears] = await Promise.all([fetchSources(), fetchBalanceYears()]);
        const balanceSources = apiSources.filter(src => src.dataset_id === DatasetType.BALANCE);
        setSources(balanceSources);
        if (balanceSources.length > 0) {
          setSelectedSource(balanceSources[0].source_id);
        } else {
          setSelectedSource('balance-xlsx');
        }
        setYears(availableYears);
        if (availableYears.length > 0) {
          setYear(availableYears[availableYears.length - 1]);
        }
      } catch (err) {
        console.error(err);
        setError('No se pudo cargar configuración inicial');
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (!selectedSource) return;
    refreshData();
  }, [selectedSource, year]);

  useEffect(() => {
    const unsubscribe = subscribeToEvents((event) => {
      if (event.type === 'DATASET_UPDATED' && event.dataset_id === DatasetType.BALANCE) {
        refreshData();
        refreshYears();
      }
    });
    return () => unsubscribe();
  }, [refreshData, refreshYears]);

  const handleExport = (ref: React.RefObject<HTMLDivElement>, name: string) => {
    if (!ref.current) return;
    const chart = echarts.getInstanceByDom(ref.current);
    if (!chart) return;
    const url = chart.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
    const link = document.createElement('a');
    link.download = `${name}-${selectedSource}-${year}.png`;
    link.href = url;
    link.click();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-orange-100 text-orange-600 rounded-lg">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Balance de Energía</h1>
            <p className="text-xs text-slate-500 uppercase font-semibold">GWh Multi-Market Analytics</p>
          </div>
        </div>
        <div className="flex gap-3">
          <select 
            value={selectedSource} 
            onChange={(e) => setSelectedSource(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          >
            {sources.length === 0 && <option value="balance-xlsx">balance-xlsx</option>}
            {sources.map(s => <option key={s.source_id} value={s.source_id}>{s.source_id}</option>)}
          </select>
          <select 
            value={year} 
            onChange={(e) => setYear(Number(e.target.value))}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          >
            {(years.length === 0 ? [year] : years).map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button 
            onClick={refreshData}
            className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="Refresh"
          >
            <svg className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCard 
            title="Evolución Mensual de Ventas" 
            onExport={() => handleExport(mainChartRef, 'balance-monthly')}
          >
            <div ref={mainChartRef} className="w-full h-[400px]"></div>
          </ChartCard>
        </div>
        <div>
          <ChartCard 
            title="Distribución Acumulada" 
            onExport={() => handleExport(donutChartRef, 'balance-donut')}
          >
            <div ref={donutChartRef} className="w-full h-[400px]"></div>
          </ChartCard>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <SummaryItem label="Regulados" color="indigo" unit="GWh" value={totals.regulados} />
        <SummaryItem label="Libres" color="amber" unit="GWh" value={totals.libres} />
        <SummaryItem label="COES" color="emerald" unit="GWh" value={totals.coes} />
        <SummaryItem label="Total" color="red" unit="GWh" value={totals.total} />
      </div>
    </div>
  );
};

const SummaryItem: React.FC<{label: string, color: string, value: number, unit: string}> = ({label, color, value, unit}) => (
  <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
    <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">{label}</div>
    <div className="flex items-baseline gap-2">
      <span className={`text-2xl font-black text-${color}-600`}>{value.toLocaleString()}</span>
      <span className="text-xs text-slate-400 font-medium">{unit}</span>
    </div>
    <div className="mt-4 flex items-center gap-1 text-[10px]">
      <span className="text-green-500 font-bold">▲ 4.2%</span>
      <span className="text-slate-300">vs prev period</span>
    </div>
  </div>
);
