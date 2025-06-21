import React, { useState, useEffect } from 'react';
import { useTenant } from '../../contexts/TenantContext';
import apiClient from '../../services/api';
import type { SyncResponse } from '../../services/api';

export interface SyncStatus {
  id: string;
  status: 'idle' | 'running' | 'completed' | 'error';
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
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({
    id: 'current',
    status: 'idle',
    lastSyncTime: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    documentsProcessed: 127,
    totalDocuments: 127
  });
  const [isTriggering, setIsTriggering] = useState(false);

  const primaryColor = tenant?.primaryColor || '#3B82F6';

  const getStatusIcon = (status: SyncStatus['status']) => {
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
      case 'error':
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

  const getStatusText = (status: SyncStatus['status']) => {
    switch (status) {
      case 'running':
        return 'Syncing documents...';
      case 'completed':
        return 'Sync completed successfully';
      case 'error':
        return 'Sync failed';
      default:
        return 'Ready to sync';
    }
  };

  const getStatusColor = (status: SyncStatus['status']) => {
    switch (status) {
      case 'running':
        return 'text-blue-600';
      case 'completed':
        return 'text-green-600';
      case 'error':
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

    if (diffMins < 60) {
      return `${diffMins} minutes ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hours ago`;
    } else {
      return `${diffDays} days ago`;
    }
  };

  const handleTriggerSync = async () => {
    if (syncStatus.status === 'running' || isTriggering) return;

    setIsTriggering(true);
    setSyncStatus(prev => ({
      ...prev,
      status: 'running',
      startTime: new Date().toISOString(),
      documentsProcessed: 0
    }));

    try {
      if (onTriggerSync) {
        await onTriggerSync();
      } else {
        // Use real API
        const syncResponse = await apiClient.triggerSync({
          sync_type: 'manual',
          force_full_sync: false
        });
        
        // Update status based on API response
        setSyncStatus(prev => ({
          ...prev,
          id: syncResponse.sync_id,
          status: syncResponse.status === 'running' ? 'running' : 'completed',
          startTime: syncResponse.started_at,
          endTime: syncResponse.completed_at,
          documentsProcessed: syncResponse.processed_files,
          totalDocuments: syncResponse.total_files
        }));
        
        // Poll for status updates if sync is running
        if (syncResponse.status === 'running') {
          pollSyncStatus(syncResponse.sync_id);
        }
      }
    } catch (error: any) {
      setSyncStatus(prev => ({
        ...prev,
        status: 'error',
        endTime: new Date().toISOString(),
        errorMessage: error.error || error.message || 'Sync failed'
      }));
    } finally {
      setIsTriggering(false);
    }
  };

  const pollSyncStatus = async (syncId: string) => {
    const maxPolls = 30; // 5 minutes max
    let pollCount = 0;
    
    const poll = async () => {
      try {
        const status = await apiClient.getSyncOperation(syncId);
        
        setSyncStatus(prev => ({
          ...prev,
          status: status.status === 'completed' ? 'completed' : 
                 status.status === 'failed' ? 'error' : 'running',
          endTime: status.completed_at,
          documentsProcessed: status.processed_files,
          totalDocuments: status.total_files,
          errorMessage: status.error_message
        }));
        
        if (status.status === 'completed' || status.status === 'failed' || pollCount >= maxPolls) {
          return;
        }
        
        pollCount++;
        setTimeout(poll, 10000); // Poll every 10 seconds
      } catch (error) {
        console.error('Failed to poll sync status:', error);
      }
    };
    
    setTimeout(poll, 2000); // Start polling after 2 seconds
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Document Sync Status</h2>
        <button
          onClick={handleTriggerSync}
          disabled={syncStatus.status === 'running' || isTriggering}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
          style={{
            backgroundColor: primaryColor
          }}
        >
          {syncStatus.status === 'running' ? (
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
          {getStatusIcon(syncStatus.status)}
          <span className={`font-medium ${getStatusColor(syncStatus.status)}`}>
            {getStatusText(syncStatus.status)}
          </span>
        </div>

        {/* Progress Bar */}
        {syncStatus.status === 'running' && syncStatus.totalDocuments && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Processing documents...</span>
              <span>{syncStatus.documentsProcessed || 0} / {syncStatus.totalDocuments}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ 
                  width: `${((syncStatus.documentsProcessed || 0) / syncStatus.totalDocuments) * 100}%`,
                  backgroundColor: primaryColor
                }}
              ></div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {syncStatus.status === 'error' && syncStatus.errorMessage && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-700">{syncStatus.errorMessage}</p>
          </div>
        )}

        {/* Sync Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
          <div className="text-center">
            <div className="text-2xl font-semibold text-gray-900">
              {syncStatus.documentsProcessed || 0}
            </div>
            <div className="text-sm text-gray-500">Documents Processed</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-semibold text-gray-900">
              {formatLastSyncTime(syncStatus.lastSyncTime)}
            </div>
            <div className="text-sm text-gray-500">Last Sync</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-semibold text-gray-900">
              {syncStatus.status === 'completed' ? '✓' : '—'}
            </div>
            <div className="text-sm text-gray-500">Status</div>
          </div>
        </div>

        {/* Next Scheduled Sync */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium text-gray-900">Automatic Sync</h4>
              <p className="text-sm text-gray-600">Next scheduled sync in ~22 hours</p>
            </div>
            <div className="text-sm text-gray-500">
              <svg className="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Every 24 hours
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}; 