import React, { useState, useEffect, useCallback } from 'react';
import { useTenant } from '../../contexts/TenantContext';
import { api } from '../../services/api';
import type { SyncResponse } from '../../services/api';

type SyncStatusType = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface SyncStatus {
  id: string;
  status: SyncStatusType;
  startTime?: string;
  endTime?: string;
  documentsProcessed?: number;
  totalDocuments?: number;
  errorMessage?: string;
  lastSyncTime?: string;
}

interface SyncStatusProps {
  onTriggerSync?: () => Promise<void>;
}

interface DocumentInfo {
  document_id: string;
  filename: string;
  upload_timestamp: string;
  file_size: number;
  status: string;
  chunks_count: number;
  content_type?: string;
  metadata: {
    document_type?: string;
    file_hash?: string;
    file_path?: string;
    embedding_model?: string;
    processed_at?: string;
    error_message?: string;
  };
}

export const SyncStatus: React.FC<SyncStatusProps> = ({ onTriggerSync }) => {
  const { tenant } = useTenant();
  const [syncStatus, setSyncStatus] = useState<SyncResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeTab, setActiveTab] = useState<'status' | 'documents'>('status');

  const primaryColor = tenant?.primaryColor || '#3B82F6';

  const getStatusIcon = (status: SyncStatusType) => {
    switch (status) {
      case 'running':
        return (
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
        );
      case 'completed':
        return (
          <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'failed':
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

  const getStatusText = (status: SyncStatusType) => {
    switch (status) {
      case 'running':
        return 'Syncing documents...';
      case 'completed':
        return 'Sync completed successfully';
      case 'failed':
        return 'Sync failed';
      default:
        return 'Ready to sync';
    }
  };

  const getStatusColor = (status: SyncStatusType) => {
    switch (status) {
      case 'running':
        return 'text-blue-600';
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatLastSyncTime = (timestamp?: string) => {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) {
        return 'Just now';
    }
    if (diffMins < 60) {
      return `${diffMins} minutes ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hours ago`;
    } else {
      return `${diffDays} days ago`;
    }
  };

  const pollSyncStatus = useCallback(async (syncId: string) => {
    const maxPolls = 30; // 5 minutes max
    let pollCount = 0;
    
    const poll = async () => {
      try {
        const status = await api.getSyncOperation(syncId);
        setSyncStatus(status);
        
        if (status.status === 'completed' || status.status === 'failed' || pollCount >= maxPolls) {
          if (status.status === 'failed') {
            setError(status.error_message || 'The sync operation failed.');
          }
          return;
        }
        
        pollCount++;
        setTimeout(poll, 10000); // Poll every 10 seconds
      } catch (err: any) {
        setError(err.error || 'Failed to poll sync status.');
        console.error('Failed to poll sync status:', err);
      }
    };
    
    setTimeout(poll, 2000); // Start polling after 2 seconds
  }, []);

  const fetchSyncStatus = useCallback(async () => {
    if (!tenant) return;
    setIsLoading(true);
    setError(null);
    try {
      const [syncData, documentsData] = await Promise.all([
        api.getSyncStatus(),
        api.getDocuments(1, 50) // Get first 50 documents
      ]);
      
      setSyncStatus(syncData);
      setDocuments(documentsData.documents);
      
      if (syncData.status === 'running') {
        pollSyncStatus(syncData.sync_id);
      }
    } catch (err: any) {
      setError(err.error || 'Could not fetch sync status.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [tenant, pollSyncStatus]);

  useEffect(() => {
    fetchSyncStatus();
  }, [fetchSyncStatus]);

  const handleTriggerSync = async () => {
    if (syncStatus?.status === 'running' || isTriggering) return;

    setIsTriggering(true);
    setError(null);
    try {
      const syncResponse = await api.triggerSync({ sync_type: 'manual' });
      setSyncStatus(syncResponse);
      if (syncResponse.status === 'running') {
        pollSyncStatus(syncResponse.sync_id);
      }
    } catch (err: any) {
      setError(err.error || 'Failed to trigger sync.');
      console.error(err);
    } finally {
      setIsTriggering(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getDocumentStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">✓ Processed</span>;
      case 'failed':
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">✗ Failed</span>;
      case 'processing':
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">⟳ Processing</span>;
      case 'pending':
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">⏳ Pending</span>;
      default:
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>;
    }
  };

  const getFileIcon = (contentType?: string) => {
    if (!contentType) return '📄';
    if (contentType.includes('pdf')) return '📕';
    if (contentType.includes('word') || contentType.includes('document')) return '📘';
    if (contentType.includes('text')) return '📝';
    return '📄';
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-sm text-gray-600">Loading Sync Status...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex">
          <button
            onClick={() => setActiveTab('status')}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'status'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Sync Status
          </button>
          <button
            onClick={() => setActiveTab('documents')}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'documents'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Documents ({documents.length})
          </button>
        </nav>
      </div>

      <div className="p-6">
        {activeTab === 'status' ? (
          // Existing sync status content
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900">Document Sync Status</h2>
              <button
                onClick={handleTriggerSync}
                disabled={syncStatus?.status === 'running' || isTriggering}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
                style={{ backgroundColor: primaryColor }}
              >
                {syncStatus?.status === 'running' ? (
                  <div className="flex items-center space-x-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Syncing...</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <span>⚡</span>
                    <span>Sync Now</span>
                  </div>
                )}
              </button>
            </div>
            
            {/* Status cards and existing sync status UI */}
            {syncStatus && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center">
                    {getStatusIcon(syncStatus.status)}
                    <div className="ml-3">
                      <p className="text-sm font-medium text-gray-900">Status</p>
                      <p className={`text-lg font-semibold ${getStatusColor(syncStatus.status)}`}>
                        {getStatusText(syncStatus.status)}
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
                        {formatLastSyncTime(syncStatus.completed_at || syncStatus.started_at)}
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
                        {syncStatus.processed_files || 0} / {syncStatus.total_files || 0}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          // Documents list
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold text-gray-900">Indexed Documents</h2>
              <button 
                onClick={fetchSyncStatus}
                className="px-3 py-1 border border-gray-300 rounded text-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                🔄 Refresh
              </button>
            </div>

            {documents.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">🗃️</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Documents Found</h3>
                <p className="text-gray-500 mb-4">No documents have been indexed yet. Upload some documents and run a sync to get started.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {documents.map((doc) => (
                  <div key={doc.document_id} className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3 flex-1">
                        <span className="text-2xl">{getFileIcon(doc.content_type)}</span>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-gray-900 truncate">{doc.filename}</h4>
                          <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                            <span>{formatFileSize(doc.file_size)}</span>
                            <span>{formatDate(doc.upload_timestamp)}</span>
                            {doc.metadata.embedding_model && (
                              <span className="flex items-center">
                                🧠 {doc.metadata.embedding_model}
                              </span>
                            )}
                          </div>
                          <div className="mt-2 flex items-center space-x-4">
                            {getDocumentStatusBadge(doc.status)}
                            {doc.chunks_count > 0 && (
                              <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800 border">
                                {doc.chunks_count} chunks
                              </span>
                            )}
                            {doc.metadata.processed_at && (
                              <span className="text-xs text-gray-400">
                                Processed: {formatDate(doc.metadata.processed_at)}
                              </span>
                            )}
                          </div>
                          {doc.metadata.error_message && (
                            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                              ⚠️ {doc.metadata.error_message}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Sync Error</h3>
                <p className="mt-1 text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}; 