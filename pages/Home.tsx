
import React, { useState, useEffect } from 'react';
import { DatasetMetadata, Source, DatasetType } from '../types';
import { fetchDatasets, fetchSources, registerSource } from '../services/api';

export const Home: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [ds, sc] = await Promise.all([fetchDatasets(), fetchSources()]);
        setDatasets(ds);
        setSources(sc);
      } catch (err) {
        console.error(err);
        setError('No se pudieron cargar los metadatos iniciales');
      }
    };
    load();
  }, []);

  const handleRegisterSource = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const formData = new FormData(e.currentTarget);
    const newSource: Partial<Source> = {
      source_id: formData.get('source_id') as string,
      dataset_id: formData.get('dataset_id') as DatasetType,
      file_name: formData.get('file_name') as string,
      enabled: true
    };
    try {
      await registerSource(newSource as Source);
      const sc = await fetchSources();
      setSources(sc);
      setIsRegistering(false);
    } catch (err) {
      console.error(err);
      setError('No se pudo registrar la fuente');
    }
  };

  const triggerIngestion = (sourceId: string) => {
    // ETL se dispara automáticamente al guardar el Excel en la carpeta data/
    alert(`Para re-ingestar '${sourceId}', guarda el Excel actualizado en la carpeta /backend/data.`);
  };

  return (
    <div className="space-y-8">
      <section>
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Dataset Registry</h1>
            <p className="text-slate-500 mt-2">Manage your data sources and monitor ingestion pipelines.</p>
          </div>
          <button 
            onClick={() => setIsRegistering(!isRegistering)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
            Register Source
          </button>
        </div>

        {isRegistering && (
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-8 animate-in fade-in slide-in-from-top-4">
            <h2 className="text-lg font-bold mb-4">New Source Registration</h2>
            <form onSubmit={handleRegisterSource} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 uppercase">Dataset Type</label>
                <select name="dataset_id" className="w-full border border-slate-300 rounded-md p-2 text-sm">
                  {datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 uppercase">Source ID (Unique)</label>
                <input required name="source_id" type="text" placeholder="e.g. lima-plant-01" className="w-full border border-slate-300 rounded-md p-2 text-sm" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 uppercase">Excel Filename</label>
                <input required name="file_name" type="text" placeholder="balance_2024.xlsx" className="w-full border border-slate-300 rounded-md p-2 text-sm" />
              </div>
              <div className="flex gap-2">
                <button type="submit" className="flex-1 bg-indigo-600 text-white p-2 rounded-md font-medium text-sm">Save</button>
                <button type="button" onClick={() => setIsRegistering(false)} className="px-4 py-2 border border-slate-300 rounded-md text-sm">Cancel</button>
              </div>
            </form>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {datasets.map(dataset => (
            <div key={dataset.id} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-4">
                <div className={`p-2 rounded-lg ${dataset.id === DatasetType.BALANCE ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'}`}>
                  {dataset.id === DatasetType.BALANCE ? (
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  ) : (
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                  )}
                </div>
                <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{dataset.grain}</span>
              </div>
              <h3 className="text-xl font-bold text-slate-900">{dataset.name}</h3>
              <p className="text-slate-500 text-sm mt-2 line-clamp-2">{dataset.description}</p>
              <div className="mt-4 pt-4 border-t border-slate-100 flex gap-2 flex-wrap">
                {dataset.metrics.map(m => (
                  <span key={m} className="px-2 py-1 bg-slate-100 text-slate-600 rounded text-[10px] font-bold uppercase">{m}</span>
                ))}
              </div>
              <a href={`#/dashboard/${dataset.id}`} className="mt-6 block w-full text-center py-2 border border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-semibold text-sm">
                View Dashboard
              </a>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-slate-900 mb-6">Active Sources</h2>
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Source ID</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Dataset</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Last Ingested</th>
                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sources.map(source => (
                <tr key={source.source_id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 font-medium text-slate-900">{source.source_id}</td>
                  <td className="px-6 py-4 text-sm text-slate-500">{source.dataset_id}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${source.enabled ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-800'}`}>
                      {source.enabled ? 'Connected' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">
                    {source.last_ingested ? new Date(source.last_ingested).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-6 py-4">
                    <button 
                      onClick={() => triggerIngestion(source.source_id)}
                      className="text-indigo-600 hover:text-indigo-900 text-sm font-semibold flex items-center gap-1 group"
                    >
                      <svg className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                      Re-ingest
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
