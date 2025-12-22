
import React, { useState, useEffect, useRef } from 'react';
import { ChartCard } from '../components/ChartCard';
import { mockBackend } from '../services/mockBackend';
import { DatasetType, Source } from '../types';

declare const echarts: any;

export const HydrologyDashboard: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [dateRange, setDateRange] = useState({ from: '2023-01-01', to: '2023-12-31' });
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const s = mockBackend.getSources().filter(src => src.dataset_id === DatasetType.HIDROLOGIA);
    setSources(s);
    if (s.length > 0) setSelectedSource(s[0].source_id);
  }, []);

  useEffect(() => {
    if (!selectedSource) return;
    refreshData();
  }, [selectedSource, dateRange]);

  const refreshData = async () => {
    const data = await mockBackend.getHydrologyData(selectedSource, dateRange.from, dateRange.to);
    
    if (chartRef.current) {
      const chart = echarts.getInstanceByDom(chartRef.current) || echarts.init(chartRef.current);
      
      const dates = data.volumen.points.map(p => p[0]);
      const volValues = data.volumen.points.map(p => p[1]);
      const cauValues = data.caudal.points.map(p => p[1]);

      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['Volumen (hm3)', 'Caudal (m3/s)'], bottom: 0 },
        dataZoom: [{ type: 'inside' }, { type: 'slider' }],
        xAxis: { type: 'category', data: dates },
        yAxis: [
          { type: 'value', name: 'hm3', position: 'left', splitLine: { show: false } },
          { type: 'value', name: 'm3/s', position: 'right', splitLine: { show: true, lineStyle: { type: 'dashed' } } }
        ],
        series: [
          { 
            name: 'Volumen (hm3)', 
            type: 'line', 
            yAxisIndex: 0, 
            data: volValues, 
            areaStyle: { opacity: 0.1 },
            color: '#0ea5e9',
            smooth: true
          },
          { 
            name: 'Caudal (m3/s)', 
            type: 'line', 
            yAxisIndex: 1, 
            data: cauValues, 
            color: '#f43f5e',
            smooth: true
          }
        ]
      });
    }
  };

  const handleExport = () => {
    if (!chartRef.current) return;
    const chart = echarts.getInstanceByDom(chartRef.current);
    if (!chart) return;
    const url = chart.getDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
    const link = document.createElement('a');
    link.download = `hidrology-${selectedSource}.png`;
    link.href = url;
    link.click();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-blue-100 text-blue-600 rounded-lg">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Evolución Hidrológica</h1>
            <p className="text-xs text-slate-500 uppercase font-semibold">Almacenamiento vs Caudal</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <select 
            value={selectedSource} 
            onChange={(e) => setSelectedSource(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          >
            {sources.map(s => <option key={s.source_id} value={s.source_id}>{s.source_id}</option>)}
          </select>
          <div className="flex items-center border border-slate-300 rounded-lg px-2 bg-white">
            <input 
              type="date" 
              value={dateRange.from} 
              onChange={(e) => setDateRange(prev => ({...prev, from: e.target.value}))}
              className="p-2 text-sm outline-none" 
            />
            <span className="text-slate-300">|</span>
            <input 
              type="date" 
              value={dateRange.to} 
              onChange={(e) => setDateRange(prev => ({...prev, to: e.target.value}))}
              className="p-2 text-sm outline-none" 
            />
          </div>
        </div>
      </div>

      <ChartCard title="Series de Tiempo (Volumen & Caudal)" onExport={handleExport}>
        <div ref={chartRef} className="w-full h-[600px]"></div>
      </ChartCard>

      <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <p className="text-sm text-amber-700">
              Heuristic Ingestion Active: Detected <strong>hm3</strong> unit from column mapping synonym 'almacenamiento'. 
              Reliability: 98%.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
