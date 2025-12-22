
import React, { useState, useEffect } from 'react';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { BalanceDashboard } from './pages/BalanceDashboard';
import { HydrologyDashboard } from './pages/HydrologyDashboard';
import { DatasetType, RealtimeEvent } from './types';
import { mockBackend } from './services/mockBackend';

const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>(window.location.hash || '#/');
  const [notifications, setNotifications] = useState<RealtimeEvent[]>([]);

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentPath(window.location.hash || '#/');
    };
    window.addEventListener('hashchange', handleHashChange);
    
    // Subscribe to SSE events (simulated)
    const unsubscribe = mockBackend.subscribe((event) => {
      setNotifications((prev) => [event, ...prev].slice(0, 5));
      // In a real app, this would trigger a re-fetch of data if on the relevant dashboard
    });

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
      unsubscribe();
    };
  }, []);

  const renderContent = () => {
    if (currentPath.startsWith('#/dashboard/balance')) return <BalanceDashboard />;
    if (currentPath.startsWith('#/dashboard/hidrologia')) return <HydrologyDashboard />;
    return <Home />;
  };

  return (
    <Layout notifications={notifications}>
      {renderContent()}
    </Layout>
  );
};

export default App;
