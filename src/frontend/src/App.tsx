import React, { useState } from 'react';
import { TenantProvider } from './contexts/TenantContext';
import { MainLayout } from './components/Layout/MainLayout';
import { QueryInterface } from './components/Query/QueryInterface';
import { SyncStatus } from './components/Sync/SyncStatus';
import { usePerformanceMonitoring } from './hooks/usePerformanceMonitoring';
import './App.css';

type ActiveView = 'search' | 'sync' | 'help';

function App() {
  const [activeView, setActiveView] = useState<ActiveView>('search');
  const { measureInteraction } = usePerformanceMonitoring();

  const handleViewChange = async (view: ActiveView) => {
    await measureInteraction(`navigation-${view}`, async () => {
      setActiveView(view);
    });
  };

  const renderContent = () => {
    switch (activeView) {
      case 'search':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                Search Your Documents
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Ask questions about your company documents and get instant, accurate answers with source citations.
              </p>
            </div>
            <QueryInterface />
          </div>
        );
      case 'sync':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                Document Synchronization
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Monitor and manage document synchronization status and trigger manual syncs when needed.
              </p>
            </div>
            <SyncStatus />
          </div>
        );
      case 'help':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                Help & Documentation
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Learn how to use the Enterprise RAG Platform effectively.
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Getting Started</h3>
                  <ul className="space-y-2 text-gray-600">
                    <li>• Upload your documents to the designated folder</li>
                    <li>• Wait for automatic synchronization (every 24 hours)</li>
                    <li>• Or trigger manual sync from the Sync Status page</li>
                    <li>• Start asking questions about your documents</li>
                  </ul>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Tips for Better Results</h3>
                  <ul className="space-y-2 text-gray-600">
                    <li>• Be specific in your questions</li>
                    <li>• Use natural language</li>
                    <li>• Reference document types when relevant</li>
                    <li>• Check source citations for accuracy</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <TenantProvider>
      <MainLayout>
        {/* Navigation Tabs */}
        <div className="mb-8">
          <nav className="flex space-x-8" aria-label="Tabs">
            {[
              { id: 'search', name: 'Search', icon: '🔍' },
              { id: 'sync', name: 'Sync Status', icon: '🔄' },
              { id: 'help', name: 'Help', icon: '❓' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleViewChange(tab.id as ActiveView)}
                className={`${
                  activeView === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm transition-colors`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        {renderContent()}
      </MainLayout>
    </TenantProvider>
  );
}

export default App;
