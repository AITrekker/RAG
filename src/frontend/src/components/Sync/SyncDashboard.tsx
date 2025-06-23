import React, { useState, useEffect } from 'react';
import { api, SyncStatus } from '../../services/api';
import type { 
  DocumentInfo, 
  SyncConfig, 
  SyncMetrics, 
  SyncResponse, 
  SyncStatusResponse
} from '../../services/api';
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Badge } from "../ui/badge";
import {
  Zap,
  Pause,
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  FileText,
  Calendar,
  AlertCircle,
  Settings,
  TrendingUp
} from "lucide-react";

interface SyncOperation extends SyncResponse {} // Alias for clarity in this component
interface SyncStatusInfo extends SyncStatusResponse {} // Alias for clarity

interface DocumentsListProps {
  documents: DocumentInfo[];
  loading: boolean;
  onRefresh: () => void;
  onDeleteDocument: (documentId: string) => void;
  onClearAllDocuments: () => void;
}

const DocumentsList: React.FC<DocumentsListProps> = ({ documents, loading, onRefresh, onDeleteDocument, onClearAllDocuments }) => {
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

  const getStatusBadge = (status: string) => {
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

  if (loading) {
    return (
      <div className="flex justify-center items-center h-32">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        <span className="ml-2">Loading documents...</span>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-6xl mb-4">🗃️</div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Documents Found</h3>
        <p className="text-gray-500 mb-4">No documents have been indexed yet. Upload some documents and run a sync to get started.</p>
        <button 
          onClick={onRefresh}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          🔄 Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Indexed Documents ({documents.length})</h3>
        <div className="flex space-x-2">
          <button 
            onClick={onRefresh}
            className="px-3 py-1 border border-gray-300 rounded text-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            🔄 Refresh
          </button>
          {documents.length > 0 && (
            <button 
              onClick={() => {
                if (window.confirm(`Are you sure you want to delete ALL ${documents.length} documents? This action cannot be undone.`)) {
                  onClearAllDocuments();
                }
              }}
              className="px-3 py-1 border border-red-300 rounded text-sm text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            >
              🗑️ Clear All
            </button>
          )}
        </div>
      </div>
      
      <div className="grid gap-4">
        {documents.map((doc) => (
          <div key={doc.document_id} className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
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
                    {getStatusBadge(doc.status)}
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
              <div className="flex space-x-2">
                <button 
                  className="p-2 text-gray-400 hover:text-gray-600 focus:outline-none"
                  title="Download"
                >
                  ⬇️
                </button>
                <button 
                  onClick={() => onDeleteDocument(doc.document_id)}
                  className="p-2 text-red-400 hover:text-red-600 focus:outline-none"
                  title="Delete Document"
                >
                  🗑️
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const SyncDashboard: React.FC = () => {
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [syncHistory, setSyncHistory] = useState<SyncResponse[]>([]);
  const [syncMetrics, setSyncMetrics] = useState<SyncMetrics | null>(null);
  const [syncConfig, setSyncConfig] = useState<SyncConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState(7);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);

  const fetchStaticData = async () => {
    try {
      const [history, metrics, config] = await Promise.all([
        api.getSyncHistory(1, 50),
        api.getSyncMetrics(selectedPeriod),
        api.getSyncConfig(),
      ]);
      setSyncHistory(history.syncs);
      setSyncMetrics(metrics);
      setSyncConfig(config);
    } catch (error) {
      console.error('Failed to fetch static sync data:', error);
    }
  };

  const fetchDynamicData = async () => {
    try {
      setLoading(true);
      const [status, documentsRes] = await Promise.all([
        api.getSyncStatus(),
        api.getDocuments(1, 100), // Get first 100 documents
      ]);
      setSyncStatus(status);
      setDocuments(documentsRes.documents);
    } catch (error) {
      console.error('Failed to fetch dynamic sync data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStaticData();
    fetchDynamicData(); // Initial fetch
    const interval = setInterval(fetchDynamicData, 30000); // Refresh dynamic data every 30 seconds
    return () => clearInterval(interval);
  }, [selectedPeriod]);

  const refreshAllData = async () => {
    await Promise.all([fetchStaticData(), fetchDynamicData()]);
  };

  const triggerManualSync = async () => {
    setTriggering(true);
    try {
      const response = await fetch('/api/v1/sync/trigger', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ force_full_sync: false }),
      });
      
      if (response.ok) {
        await refreshAllData();
      } else {
        console.error('Failed to trigger sync');
      }
    } catch (error) {
      console.error('Error triggering sync:', error);
    } finally {
      setTriggering(false);
    }
  };

  const toggleAutoSync = async () => {
    if (!syncStatus) return;
    
    try {
      const endpoint = syncStatus.sync_enabled ? '/api/v1/sync/pause' : '/api/v1/sync/resume';
      const response = await fetch(endpoint, { method: 'POST' });
      
      if (response.ok) {
        await refreshAllData();
      }
    } catch (error) {
      console.error('Error toggling auto sync:', error);
    }
  };

  const getStatusBadge = (status: SyncStatus) => {
    switch (status) {
      case SyncStatus.RUNNING:
        return <Badge className="bg-blue-100 text-blue-800"><RefreshCw className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
      case SyncStatus.COMPLETED:
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" />Success</Badge>;
      case SyncStatus.FAILED:
        return <Badge className="bg-red-100 text-red-800"><XCircle className="w-3 h-3 mr-1" />Failed</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-800">{status}</Badge>;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  const handleDeleteDocument = async (documentId: string) => {
    try {
      await api.deleteDocument(documentId);
      await refreshAllData(); // Refresh the data
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document. Please try again.');
    }
  };

  const handleClearAllDocuments = async () => {
    try {
      await api.clearAllDocuments();
      await refreshAllData(); // Refresh the data
    } catch (error) {
      console.error('Failed to clear all documents:', error);
      alert('Failed to clear all documents. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Sync Dashboard</h1>
        <div className="flex space-x-2">
          <Button
            onClick={triggerManualSync}
            disabled={triggering}
            className="flex items-center space-x-2"
          >
            {triggering ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            <span>Trigger Sync</span>
          </Button>
          <Button
            onClick={toggleAutoSync}
            variant={syncStatus?.sync_enabled ? "destructive" : "default"}
            className="flex items-center space-x-2"
          >
            {syncStatus?.sync_enabled ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>{syncStatus?.sync_enabled ? 'Pause' : 'Resume'} Auto Sync</span>
          </Button>
        </div>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Sync Status</p>
                <p className="text-lg font-bold">
                  {syncStatus?.current_status ?? 'Unknown'}
                </p>
              </div>
              {syncStatus?.current_status === 'running' ? (
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
              ) : syncStatus?.last_sync_success === false ? (
                <XCircle className="w-8 h-8 text-red-500" />
              ) : (
                <CheckCircle className="w-8 h-8 text-green-500" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Last Sync</p>
                <p className="text-lg font-bold">
                  {syncStatus?.last_sync_time 
                    ? new Date(syncStatus.last_sync_time).toLocaleDateString()
                    : 'Never'
                  }
                </p>
              </div>
              <Clock className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Success Rate</p>
                <p className="text-lg font-bold">
                  {syncMetrics ? Math.round(syncMetrics.success_rate * 100) : 0}%
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Files Processed</p>
                <p className="text-lg font-bold">
                  {syncMetrics?.total_files_processed || 0}
                </p>
              </div>
              <FileText className="w-8 h-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="history" className="space-y-4">
        <TabsList>
          <TabsTrigger value="history">Sync History</TabsTrigger>
          <TabsTrigger value="metrics">Analytics</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>

        {/* Sync History Tab */}
        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Calendar className="w-5 h-5" />
                <span>Recent Sync Operations</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {syncHistory.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No sync history available</p>
                ) : (
                  syncHistory.map((event) => (
                    <div key={event.sync_id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center space-x-2">
                          {getStatusBadge(event.status as any)}
                          <span className="text-sm text-gray-500">
                            {new Date(event.started_at).toLocaleString()}
                          </span>
                        </div>
                        <span className="text-xs text-gray-400">{event.sync_id}</span>
                      </div>
                      
                      <p className="text-sm text-gray-700 mb-3">{`Processed ${event.successful_files}/${event.total_files} files.`}</p>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div className="text-center">
                          <p className="text-gray-500">Processed</p>
                          <p className="font-semibold">{event.processed_files}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Successful</p>
                          <p className="font-semibold text-green-600">{event.successful_files}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Failed</p>
                          <p className="font-semibold text-blue-600">{event.failed_files}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Chunks</p>
                          <p className="font-semibold text-red-600">{event.total_chunks}</p>
                        </div>
                      </div>
                      
                      {event.error_message && (
                        <div className="mt-3 p-2 bg-red-50 rounded-md">
                          <p className="text-sm text-red-700 flex items-center">
                            <AlertCircle className="w-4 h-4 mr-1" />
                            {event.error_message}
                          </p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="metrics" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Sync Analytics</h3>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(Number(e.target.value))}
              className="px-3 py-1 border rounded-md"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>

          {syncMetrics && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Sync Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between">
                    <span>Total Syncs:</span>
                    <span className="font-semibold">{syncMetrics.total_syncs}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Successful:</span>
                    <span className="font-semibold text-green-600">{syncMetrics.successful_syncs}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Failed:</span>
                    <span className="font-semibold text-red-600">{syncMetrics.failed_syncs}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Success Rate:</span>
                    <span className="font-semibold">{Math.round(syncMetrics.success_rate * 100)}%</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">File Operations</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between">
                    <span>Total Processed:</span>
                    <span className="font-semibold">{syncMetrics.total_files_processed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Added:</span>
                    <span className="font-semibold text-green-600">{syncMetrics.total_files_added}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Modified:</span>
                    <span className="font-semibold text-blue-600">{syncMetrics.total_files_modified}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Deleted:</span>
                    <span className="font-semibold text-red-600">{syncMetrics.total_files_deleted}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Performance</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between">
                    <span>Avg Sync Time:</span>
                    <span className="font-semibold">
                      {formatDuration(syncMetrics.average_sync_time_seconds)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Last Sync:</span>
                    <span className="font-semibold">
                      {syncMetrics.last_sync_time 
                        ? new Date(syncMetrics.last_sync_time).toLocaleDateString()
                        : 'Never'
                      }
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Configuration Tab */}
        <TabsContent value="config" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Settings className="w-5 h-5" />
                <span>Sync Configuration</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {syncConfig ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Auto Sync
                      </label>
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={syncConfig.auto_sync_enabled}
                          readOnly
                          className="rounded"
                        />
                        <span>{syncConfig.auto_sync_enabled ? 'Enabled' : 'Disabled'}</span>
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Sync Interval
                      </label>
                      <p className="text-sm text-gray-900">
                        Every {Math.floor(syncConfig.sync_interval_minutes / 60)} hours
                      </p>
                    </div>
                  </div>

                  {syncConfig.ignore_patterns.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Ignore Patterns
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {syncConfig.ignore_patterns.map((pattern, index) => (
                          <Badge key={index} variant="secondary">{pattern}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {syncConfig.webhooks.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Webhooks
                      </label>
                      <div className="space-y-2">
                        {syncConfig.webhooks.map((webhook, index) => (
                          <div key={index} className="p-3 border rounded-md">
                            <p className="font-medium">{webhook.url}</p>
                            <p className="text-sm text-gray-500">
                              Events: {webhook.events.join(', ')}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-gray-500">No configuration data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-4">
          <DocumentsList 
            documents={documents} 
            loading={loading} 
            onRefresh={refreshAllData}
            onDeleteDocument={handleDeleteDocument}
            onClearAllDocuments={handleClearAllDocuments}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SyncDashboard; 