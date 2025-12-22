
import React from 'react';
import { RealtimeEvent } from '../types';

interface LayoutProps {
  children: React.ReactNode;
  notifications: RealtimeEvent[];
}

export const Layout: React.FC<LayoutProps> = ({ children, notifications }) => {
  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-indigo-900 text-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <a href="#/" className="text-xl font-bold tracking-tight">ScalabilityPlatform<span className="text-indigo-400">.v3</span></a>
            <nav className="hidden md:flex gap-6 text-sm font-medium">
              <a href="#/" className="hover:text-indigo-200 transition-colors">Registry</a>
              <a href="#/dashboard/balance" className="hover:text-indigo-200 transition-colors">Energy Balance</a>
              <a href="#/dashboard/hidrologia" className="hover:text-indigo-200 transition-colors">Hydrology</a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div className="relative group">
              <button className="p-2 rounded-full hover:bg-indigo-800 transition-colors relative">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                {notifications.length > 0 && <span className="absolute top-1 right-1 w-3 h-3 bg-red-500 border-2 border-indigo-900 rounded-full"></span>}
              </button>
              {/* Notifications Dropdown */}
              <div className="absolute right-0 top-full mt-2 w-80 bg-white text-slate-900 rounded-lg shadow-xl border border-slate-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pointer-events-none group-hover:pointer-events-auto overflow-hidden">
                <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 font-semibold text-xs uppercase tracking-wider text-slate-500">
                  Live Events (SSE)
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-slate-400 text-sm">No new events</div>
                  ) : (
                    notifications.map((n, i) => (
                      <div key={i} className={`px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 ${n.type === 'ETL_ERROR' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-green-500'}`}>
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-bold text-sm">{n.type}</span>
                          <span className="text-[10px] text-slate-400">{new Date(n.ts || Date.now()).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-xs text-slate-600 truncate">Source: {n.source_id}</p>
                        {n.message && <p className="text-xs text-slate-500 mt-1">{n.message}</p>}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
            <div className="h-8 w-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold text-xs">AD</div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
        {children}
      </main>

      <footer className="bg-white border-t border-slate-200 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center text-slate-400 text-sm">
          <div>© 2024 Multi-Dataset Scalability MVP. Architected for Performance.</div>
          <div className="flex gap-4 mt-4 md:mt-0">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500"></span> Backend Online</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500"></span> SSE Active</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
