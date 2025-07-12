import { useState } from 'react';
import { useTenant } from './contexts/TenantContext';
import { MainLayout } from './components/Layout/MainLayout';
import { QueryInterface } from './components/Query/QueryInterface';
import { SyncDashboard } from './components/Sync/SyncDashboard';
import { Toaster } from "@/components/ui/toaster";
import './App.css';

type ActiveView = 'search' | 'sync';

function App() {
  const [activeView, setActiveView] = useState<ActiveView>('search');
  const { tenantApiKey, tenant, tenants, isLoading } = useTenant();

  const handleViewChange = (view: ActiveView) => {
    setActiveView(view);
  };

  // Show loading state while tenants are being loaded
  if (isLoading) {
    return (
      <>
        <MainLayout>
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading tenants...</p>
            </div>
          </div>
        </MainLayout>
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
          {tenants.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              <h3 className="text-lg font-medium mb-2">No Tenants Available</h3>
              <p>No tenants have been provisioned yet. Please contact your administrator.</p>
            </div>
          ) : tenant ? (
            renderContent()
          ) : (
            <div className="text-center text-gray-500 py-12">
              <h3 className="text-lg font-medium mb-2">No Tenant Selected</h3>
              <p>Please select a tenant from the dropdown to begin.</p>
            </div>
          )}
        </div>
      </MainLayout>
      <Toaster />
    </>
  );
}

export default App;
