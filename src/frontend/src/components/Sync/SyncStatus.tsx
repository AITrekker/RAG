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

export const SyncStatus: React.FC<SyncStatusProps> = ({ onTriggerSync }) => {
  const { tenant } = useTenant();
  const [syncStatus, setSyncStatus] = useState<SyncResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const status = await api.getSyncStatus();
      setSyncStatus(status);
      if (status.status === 'running') {
        pollSyncStatus(status.sync_id);
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

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-sm text-gray-600">Loading Sync Status...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
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
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Sync Now</span>
            </div>
          )}
        </button>
      </div>

      {/* Current Status */}
      <div className="space-y-4">
        <div className="flex items-center space-x-3">
          {getStatusIcon(syncStatus?.status || 'idle')}
          <span className={`font-medium ${getStatusColor(syncStatus?.status || 'idle')}`}>
            {getStatusText(syncStatus?.status || 'idle')}
          </span>
        </div>

        {/* Progress Bar */}
        {syncStatus?.status === 'running' && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Processing documents...</span>
              <span>{syncStatus.processed_files} / {syncStatus.total_files}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ 
                  width: `${(syncStatus.processed_files / syncStatus.total_files) * 100}%`,
                  backgroundColor: primaryColor
                }}
              ></div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Sync Statistics */}
        {syncStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-200 mt-6">
            <div className="text-center">
              <p className="text-sm text-gray-500">Status</p>
              <p className="text-md font-semibold text-gray-800">{syncStatus.status}</p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-500">Files Processed</p>
              <p className="text-md font-semibold text-gray-800">{syncStatus.successful_files} / {syncStatus.total_files}</p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-500">Last Run</p>
              <p className="text-md font-semibold text-gray-800">{formatLastSyncTime(syncStatus.completed_at || syncStatus.started_at)}</p>
            </div>
             <div className="text-center">
              <p className="text-sm text-gray-500">Duration</p>
              <p className="text-md font-semibold text-gray-800">{syncStatus.processing_time ? `${syncStatus.processing_time.toFixed(2)}s` : 'N/A'}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}; 