import React, { useState, useEffect, useCallback } from 'react';
import { useTenant } from '../../contexts/TenantContext';
import { api, SyncStatus } from '../../services/api';
import type { SyncResponse, SyncStatusResponse, DocumentInfo } from '../../services/api';
import { Button } from "../ui/button";

const SyncStatusComponent: React.FC = () => {
  const { tenant } = useTenant();
  const [overallStatus, setOverallStatus] = useState<SyncStatusResponse | null>(null);
  const [activeSync, setActiveSync] = useState<SyncResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeTab, setActiveTab] = useState<'status' | 'documents'>('status');

  const primaryColor = tenant?.primaryColor || '#3B82F6';

  const getStatusIcon = (status?: SyncStatus) => {
    switch (status) {
      case SyncStatus.RUNNING:
        return (
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
        );
      case SyncStatus.COMPLETED:
        return (
          <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case SyncStatus.FAILED:
        return (
          <svg className="h-5 w-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      default:
        return (
          <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  const getStatusText = (status?: SyncStatus) => {
    switch (status) {
      case SyncStatus.RUNNING:
        return 'Syncing documents...';
      case SyncStatus.COMPLETED:
        return 'Sync completed';
      case SyncStatus.FAILED:
        return 'Sync failed';
      default:
        return 'Ready to sync';
    }
  };

  const getStatusColor = (status?: SyncStatus) => {
    switch (status) {
      case SyncStatus.RUNNING:
        return 'text-blue-600';
      case SyncStatus.COMPLETED:
        return 'text-green-600';
      case SyncStatus.FAILED:
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatLastSyncTime = (timestamp?: string) => {
    if (!timestamp) return 'Never';
    const lastSyncDate = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - lastSyncDate.getTime();
    const diffMins = Math.round(diffMs / 60000);
    const diffHours = Math.round(diffMs / 3600000);

    if (diffMins < 1) {
      return 'Just now';
    }
    if (diffMins < 60) {
      return `${diffMins} minutes ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hours ago`;
    } else {
      return lastSyncDate.toLocaleDateString();
    }
  };

  const fetchOverallStatus = useCallback(async () => {
    if (!tenant) return;
    try {
      const [statusData, documentsData] = await Promise.all([
        api.getSyncStatus(),
        api.getDocuments(1, 50)
      ]);
      setOverallStatus(statusData);
      setDocuments(documentsData.documents);
      if (statusData.current_status === SyncStatus.RUNNING && statusData.active_sync_id) {
        pollSyncStatus(statusData.active_sync_id);
      }
    } catch (err: any) {
      setError(err.error || 'Could not fetch sync status.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [tenant]);

  const pollSyncStatus = useCallback(async (syncId: string) => {
    let pollCount = 0;
    const maxPolls = 300; // Poll for a maximum of 10 minutes (300 * 2s)

    const poll = async () => {
      try {
        const status = await api.getSyncOperation(syncId);
        setActiveSync(status);
        
        if (status.status === SyncStatus.COMPLETED || status.status === SyncStatus.FAILED || pollCount >= maxPolls) {
          if (status.status === SyncStatus.FAILED) {
            setError(status.error_message || 'The sync operation failed.');
          }
          // Refresh overall status after polling finishes
          fetchOverallStatus();
          return;
        }
        
        pollCount++;
        setTimeout(poll, 2000);
      } catch (err) {
        setError('Failed to poll sync status.');
        console.error(err);
        // Refresh overall status to get out of a broken polling state
        fetchOverallStatus();
      }
    };
    
    setTimeout(poll, 2000); // Start polling after 2 seconds
  }, [fetchOverallStatus]);

  useEffect(() => {
    setIsLoading(true);
    fetchOverallStatus();
  }, [fetchOverallStatus]);

  const handleTriggerSync = async () => {
    if (activeSync?.status === SyncStatus.RUNNING || isTriggering) return;

    setIsTriggering(true);
    setError(null);
    try {
      const syncResponse = await api.triggerSync({ sync_type: 'manual' });
      setActiveSync(syncResponse);
      if (syncResponse.status === SyncStatus.RUNNING) {
        pollSyncStatus(syncResponse.sync_id);
      }
    } catch (err: any) {
      setError(err.error || 'Failed to trigger sync.');
      console.error(err);
    } finally {
      setIsTriggering(false);
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    if (!tenant) return;
    try {
      await api.deleteDocument(documentId);
      await fetchOverallStatus(); // Refresh the data
    } catch (error) {
      console.error('Failed to delete document:', error);
      setError('Failed to delete document.');
    }
  };

  const handleClearAll = async () => {
    if (!tenant) return;
    try {
      await api.clearAllDocuments();
      await fetchOverallStatus(); // Refresh the data
    } catch (error) {
      console.error('Failed to clear all documents:', error);
      setError('Failed to clear all documents.');
    }
  };

  if (isLoading) {
    return <div className="p-4 rounded-lg bg-white shadow-sm animate-pulse">Loading sync status...</div>;
  }

  if (error) {
    return <div className="p-4 rounded-lg bg-red-100 text-red-700 shadow-sm">{error}</div>;
  }

  if (!overallStatus) {
    return <div className="p-4 rounded-lg bg-white shadow-sm">Could not load sync status.</div>;
  }
  
  const isSyncing = activeSync?.status === SyncStatus.RUNNING || isTriggering;
  const currentStatus = (activeSync?.status ?? overallStatus?.current_status) as SyncStatus;
  
  return (
    <div className="p-6 max-w-4xl mx-auto bg-white rounded-xl shadow-lg">
      <div className="flex items-center justify-between mb-4 border-b pb-4">
        <h2 className="text-xl font-bold text-gray-800">Document Synchronization</h2>
        <Button
          onClick={handleTriggerSync}
          disabled={isSyncing}
          style={{ backgroundColor: isSyncing ? '#9CA3AF' : primaryColor }}
        >
          {isSyncing ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Syncing...
            </>
          ) : (
            'Sync Now'
          )}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            {getStatusIcon(currentStatus)}
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">Status</p>
              <p className={`text-lg font-semibold ${getStatusColor(currentStatus)}`}>
                {getStatusText(currentStatus)}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">Last Sync</p>
              <p className="text-lg font-semibold text-gray-600">
                {formatLastSyncTime(overallStatus.last_sync_time ?? undefined)}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-900">Files Processed</p>
              <p className="text-lg font-semibold text-gray-600">
                {activeSync ? `${activeSync.processed_files} / ${activeSync.total_files}` : `~${overallStatus.pending_changes} pending`}
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {activeSync?.status === SyncStatus.RUNNING && (
        <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
          <div 
            className="bg-blue-600 h-2.5 rounded-full" 
            style={{ width: `${(activeSync.processed_files / activeSync.total_files) * 100}%`, backgroundColor: primaryColor }}
          ></div>
        </div>
      )}

      <div>
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('status')}
              className={`${
                activeTab === 'status'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
              style={{
                borderColor: activeTab === 'status' ? primaryColor : 'transparent',
                color: activeTab === 'status' ? primaryColor : ''
              }}
            >
              Sync Details
            </button>
            <button
              onClick={() => setActiveTab('documents')}
              className={`${
                activeTab === 'documents'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
               style={{
                borderColor: activeTab === 'documents' ? primaryColor : 'transparent',
                color: activeTab === 'documents' ? primaryColor : ''
              }}
            >
              Indexed Documents ({documents.length})
            </button>
          </nav>
        </div>

        {activeTab === 'status' && (
          <div className="mt-4 text-sm text-gray-600">
            {activeSync ? (
              <ul>
                <li><strong>Sync ID:</strong> {activeSync.sync_id}</li>
                <li><strong>Status:</strong> {activeSync.status}</li>
                <li><strong>Started:</strong> {new Date(activeSync.started_at).toLocaleString()}</li>
                {activeSync.completed_at && <li><strong>Completed:</strong> {new Date(activeSync.completed_at).toLocaleString()}</li>}
                <li><strong>Files:</strong> {activeSync.processed_files}/{activeSync.total_files}</li>
                {activeSync.error_message && <li className="text-red-600"><strong>Error:</strong> {activeSync.error_message}</li>}
              </ul>
            ) : (
              <p>No active sync. Click "Sync Now" to start.</p>
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="mt-4">
            <div className="flex justify-between items-center mb-2">
              <p className="text-sm text-gray-600">A list of recently processed documents.</p>
              <div className="flex space-x-2">
                <button 
                  onClick={fetchOverallStatus}
                  className="px-3 py-1 border border-gray-300 rounded text-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Refresh List
                </button>
                <button 
                  onClick={handleClearAll}
                  className="px-3 py-1 border border-red-300 rounded text-sm text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  Clear All
                </button>
              </div>
            </div>
            <ul className="divide-y divide-gray-200">
              {documents.map((doc) => (
                <li key={doc.document_id} className="py-3 flex items-center justify-between">
                  <span className="text-sm text-gray-800">{doc.filename}</span>
                   <button 
                      onClick={() => handleDeleteDocument(doc.document_id)}
                      className="text-gray-400 hover:text-red-600"
                      title="Delete Document"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export { SyncStatusComponent as SyncStatus }; 