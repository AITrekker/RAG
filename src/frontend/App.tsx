import { useState } from 'react';
import { useTenant } from './contexts/TenantContext';
import { MainLayout } from './components/Layout/MainLayout';
import { QueryInterface } from './components/Query/QueryInterface';
import { AuditLogViewer } from './components/Audit/AuditLogViewer';
import { ApiKeyModal } from './components/ApiKeyModal';
import { SyncDashboard } from './components/Sync/SyncDashboard';
import { Toaster } from "@/components/ui/toaster";
import './App.css';

type ActiveView = 'search' | 'sync' | 'audit';

function App() {
  const [activeView, setActiveView] = useState<ActiveView>('search');
  const { apiKey, tenant } = useTenant();

  const handleViewChange = (view: ActiveView) => {
    setActiveView(view);
  };

  // If there's no API key, force the user to configure one.
  if (!apiKey) {
    return (
      <>
        <ApiKeyModal />
        <Toaster />
      </>
    );
  }

  const renderContent = () => {
    switch (activeView) {
      case 'search':
        return <QueryInterface />;
      case 'sync':
        return <SyncDashboard />;
      case 'audit':
        return <AuditLogViewer />;
      default:
        return null;
    }
  };

  return (
    <>
      <MainLayout>
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-800">RAG Platform</h1>
          <p className="text-lg text-gray-500 mt-2">
            Selected Tenant: <span className="font-semibold text-blue-600">{tenant || 'None'}</span>
          </p>
        </div>
        <div className="mb-8">
          <nav className="flex space-x-1" aria-label="Tabs">
            {[
              { id: 'search', name: 'Search' },
              { id: 'sync', name: 'Sync' },
              { id: 'audit', name: 'Audit Log' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleViewChange(tab.id as ActiveView)}
                className={`
                  ${activeView === tab.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'}
                  px-3 py-2 font-medium text-sm rounded-md transition-colors
                `}
                disabled={!tenant}
              >
                {tab.name}
              </button>
            ))}
          </nav>
        </div>
        <div className="bg-white rounded-lg shadow-md p-6 min-h-[400px]">
          {tenant ? renderContent() : <div className="text-center text-gray-500">Please select a tenant to begin.</div>}
        </div>
      </MainLayout>
      <Toaster />
    </>
  );
}

export default App;
