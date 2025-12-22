
import React from 'react';

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
  onExport?: () => void;
}

export const ChartCard: React.FC<ChartCardProps> = ({ title, children, onExport }) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-full">
      <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-tight">{title}</h3>
        {onExport && (
          <button 
            onClick={onExport}
            className="text-slate-400 hover:text-indigo-600 transition-colors p-1"
            title="Export PNG"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        )}
      </div>
      <div className="p-6 flex-1">
        {children}
      </div>
    </div>
  );
};
