import React, { useState, useEffect } from 'react';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { 
  Calendar,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Play,
  Pause,
  Settings,
  RefreshCw,
  TrendingUp,
  FileText,
  Zap
} from 'lucide-react';

interface SyncEvent {
  sync_run_id: string;
  timestamp: string;
  status: 'SUCCESS' | 'FAILURE' | 'IN_PROGRESS';
  event_type: string;
  message: string;
  files_processed: number;
  files_added: number;
  files_modified: number;
  files_deleted: number;
  error_count: number;
}

interface SyncStatus {
  tenant_id: string;
  sync_enabled: boolean;
  last_sync_time: string | null;
  last_sync_success: boolean | null;
  sync_interval_minutes: number;
  file_watcher_active: boolean;
  pending_changes: number;
  current_status: string;
}

interface SyncMetrics {
  period_days: number;
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  success_rate: number;
  total_files_processed: number;
  total_files_added: number;
  total_files_modified: number;
  total_files_deleted: number;
  average_sync_time_seconds: number | null;
  last_sync_time: string | null;
}

interface SyncConfig {
  auto_sync_enabled: boolean;
  sync_interval_minutes: number;
  ignore_patterns: string[];
  webhooks: Array<{
    url: string;
    events: string[];
    timeout: number;
    retry_count: number;
  }>;
}

const SyncDashboard: React.FC = () => {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncHistory, setSyncHistory] = useState<SyncEvent[]>([]);
  const [syncMetrics, setSyncMetrics] = useState<SyncMetrics | null>(null);
  const [syncConfig, setSyncConfig] = useState<SyncConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState(7);

  useEffect(() => {
    fetchSyncData();
    const interval = setInterval(fetchSyncData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [selectedPeriod]);

  const fetchSyncData = async () => {
    try {
      const [statusRes, historyRes, metricsRes, configRes] = await Promise.all([
        fetch('/api/v1/sync/status'),
        fetch('/api/v1/sync/history?limit=50'),
        fetch(`/api/v1/sync/metrics?days=${selectedPeriod}`),
        fetch('/api/v1/sync/config')
      ]);

      const [status, history, metrics, config] = await Promise.all([
        statusRes.json(),
        historyRes.json(),
        metricsRes.json(),
        configRes.json()
      ]);

      setSyncStatus(status);
      setSyncHistory(history);
      setSyncMetrics(metrics);
      setSyncConfig(config);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch sync data:', error);
      setLoading(false);
    }
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
        await fetchSyncData();
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
        await fetchSyncData();
      }
    } catch (error) {
      console.error('Error toggling auto sync:', error);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" />Success</Badge>;
      case 'FAILURE':
        return <Badge className="bg-red-100 text-red-800"><XCircle className="w-3 h-3 mr-1" />Failed</Badge>;
      case 'IN_PROGRESS':
        return <Badge className="bg-blue-100 text-blue-800"><RefreshCw className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
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
                  {syncStatus?.sync_enabled ? 'Enabled' : 'Disabled'}
                </p>
              </div>
              {syncStatus?.sync_enabled ? (
                <CheckCircle className="w-8 h-8 text-green-500" />
              ) : (
                <Pause className="w-8 h-8 text-gray-400" />
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
                    <div key={event.sync_run_id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center space-x-2">
                          {getStatusBadge(event.status)}
                          <span className="text-sm text-gray-500">
                            {new Date(event.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <span className="text-xs text-gray-400">{event.sync_run_id}</span>
                      </div>
                      
                      <p className="text-sm text-gray-700 mb-3">{event.message}</p>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div className="text-center">
                          <p className="text-gray-500">Processed</p>
                          <p className="font-semibold">{event.files_processed}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Added</p>
                          <p className="font-semibold text-green-600">{event.files_added}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Modified</p>
                          <p className="font-semibold text-blue-600">{event.files_modified}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-gray-500">Deleted</p>
                          <p className="font-semibold text-red-600">{event.files_deleted}</p>
                        </div>
                      </div>
                      
                      {event.error_count > 0 && (
                        <div className="mt-3 p-2 bg-red-50 rounded-md">
                          <p className="text-sm text-red-700 flex items-center">
                            <AlertCircle className="w-4 h-4 mr-1" />
                            {event.error_count} error(s) occurred during sync
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
      </Tabs>
    </div>
  );
};

export default SyncDashboard; 