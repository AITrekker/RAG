import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SynchronizationService } from "@/src/services/api.generated";
import type { SyncTriggerRequest, ApiError, SyncResponse } from "@/src/services/api.generated";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { useTenant } from "@/contexts/TenantContext";
import { OpenAPI } from "@/src/services/api.generated/core/OpenAPI";
import { useState, useEffect } from "react";
import { RefreshCw, CheckCircle, XCircle, Clock, AlertCircle, FileText } from "lucide-react";

interface SyncStatus {
  latest_sync: {
    id: string | null;
    status: string | null;
    started_at: string | null;
    completed_at: string | null;
    files_processed: number;
    error_message: string | null;
  };
  file_status: {
    pending: number;
    processing: number;
    failed: number;
    total: number;
  };
}

interface SyncHistoryItem {
  id: string;
  operation_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  files_processed: number;
  files_added: number;
  files_updated: number;
  files_deleted: number;
  chunks_created: number;
  chunks_updated: number;
  chunks_deleted: number;
  error_message: string | null;
}

interface ChangeDetection {
  total_changes: number;
  new_files: number;
  updated_files: number;
  deleted_files: number;
  changes: Array<{
    change_type: string;
    file_path: string;
    file_id: string | null;
    old_hash: string | null;
    new_hash: string | null;
    file_size: number;
  }>;
}

export const SyncDashboard = () => {
  const { tenant, tenantApiKey } = useTenant();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isPolling, setIsPolling] = useState(false);

  // Custom API calls for endpoints not in generated service
  const fetchSyncStatus = async (): Promise<SyncStatus> => {
    const response = await fetch(`${OpenAPI.BASE}/api/v1/sync/status`, {
      headers: {
        'X-API-Key': tenantApiKey!,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to fetch sync status');
    return response.json();
  };

  const fetchSyncHistory = async (): Promise<{ history: SyncHistoryItem[] }> => {
    const response = await fetch(`${OpenAPI.BASE}/api/v1/sync/history?limit=10`, {
      headers: {
        'X-API-Key': tenantApiKey!,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to fetch sync history');
    return response.json();
  };

  const fetchChangeDetection = async (): Promise<ChangeDetection> => {
    const response = await fetch(`${OpenAPI.BASE}/api/v1/sync/detect-changes`, {
      method: 'POST',
      headers: {
        'X-API-Key': tenantApiKey!,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to detect changes');
    return response.json();
  };

  // Queries for sync data
  const { data: syncStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['syncStatus', tenant],
    queryFn: fetchSyncStatus,
    enabled: !!tenant && !!tenantApiKey,
    refetchInterval: isPolling ? 2000 : false,
  });

  const { data: syncHistory } = useQuery({
    queryKey: ['syncHistory', tenant],
    queryFn: fetchSyncHistory,
    enabled: !!tenant && !!tenantApiKey,
  });

  const { data: changeDetection, refetch: refetchChanges } = useQuery({
    queryKey: ['changeDetection', tenant],
    queryFn: fetchChangeDetection,
    enabled: false, // Only fetch on demand
  });

  const syncMutation = useMutation<SyncResponse, ApiError, SyncTriggerRequest>({
    mutationFn: (params) =>
      SynchronizationService.triggerManualSyncApiV1SyncTriggerPost(params),
    onSuccess: (data) => {
      toast({
        title: "Sync Started",
        description: `Sync operation (ID: ${data.sync_id}) has been initiated.`,
      });
      setIsPolling(true);
      queryClient.invalidateQueries({ queryKey: ["auditEvents"] });
      queryClient.invalidateQueries({ queryKey: ["syncStatus"] });
      queryClient.invalidateQueries({ queryKey: ["syncHistory"] });
    },
    onError: (error) => {
      toast({
        title: "Sync Failed",
        description: error.message || "An unexpected error occurred.",
        variant: "destructive",
      });
    },
  });

  // Stop polling when sync completes
  useEffect(() => {
    if (syncStatus?.latest_sync?.status && 
        ['completed', 'failed'].includes(syncStatus.latest_sync.status)) {
      setIsPolling(false);
    }
  }, [syncStatus?.latest_sync?.status]);

  const handleSync = (forceFull: boolean) => {
    syncMutation.mutate({ force_full_sync: forceFull });
  };

  const handlePreviewChanges = () => {
    refetchChanges();
  };

  const getStatusColor = (status: string | null) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'running': return 'text-blue-600';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-500';
    }
  };

  const getStatusIcon = (status: string | null) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'running': return <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-600" />;
      default: return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Sync Management</h2>
        <p className="text-gray-600 mb-4">
          Manage file synchronization and view sync status for the current tenant.
        </p>
      </div>

      {/* Sync Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            Sync Controls
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button
              onClick={() => handleSync(false)}
              disabled={syncMutation.isPending || !tenant || !tenantApiKey}
              className="flex items-center gap-2"
            >
              {syncMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              {syncMutation.isPending ? "Syncing..." : "Trigger Delta Sync"}
            </Button>
            <Button
              onClick={() => handleSync(true)}
              disabled={syncMutation.isPending || !tenant || !tenantApiKey}
              variant="outline"
              className="flex items-center gap-2"
            >
              {syncMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              {syncMutation.isPending ? "Syncing..." : "Force Full Sync"}
            </Button>
            <Button
              onClick={handlePreviewChanges}
              disabled={!tenant || !tenantApiKey}
              variant="secondary"
              className="flex items-center gap-2"
            >
              <FileText className="w-4 h-4" />
              Preview Changes
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Current Status */}
      {syncStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getStatusIcon(syncStatus.latest_sync?.status)}
              Current Sync Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-semibold mb-2">Latest Sync Operation</h4>
                {syncStatus.latest_sync?.id ? (
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <Badge 
                        variant={syncStatus.latest_sync.status === 'completed' ? 'default' : 
                                syncStatus.latest_sync.status === 'failed' ? 'destructive' : 'secondary'}
                        className="flex items-center gap-1"
                      >
                        {getStatusIcon(syncStatus.latest_sync.status)}
                        {syncStatus.latest_sync.status || 'Unknown'}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Started:</span>
                      <span className="text-sm">{formatDateTime(syncStatus.latest_sync.started_at)}</span>
                    </div>
                    {syncStatus.latest_sync.completed_at && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Completed:</span>
                        <span className="text-sm">{formatDateTime(syncStatus.latest_sync.completed_at)}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-600">Files Processed:</span>
                      <span className="text-sm">{syncStatus.latest_sync.files_processed}</span>
                    </div>
                    {syncStatus.latest_sync.error_message && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                        <strong>Error:</strong> {syncStatus.latest_sync.error_message}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-gray-500">No sync operations yet</p>
                )}
              </div>
              
              <div>
                <h4 className="font-semibold mb-2">File Status</h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Pending:</span>
                    <Badge variant="secondary">{syncStatus.file_status.pending}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Processing:</span>
                    <Badge variant="secondary">{syncStatus.file_status.processing}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Failed:</span>
                    <Badge variant={syncStatus.file_status.failed > 0 ? 'destructive' : 'secondary'}>
                      {syncStatus.file_status.failed}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total:</span>
                    <Badge variant="outline">{syncStatus.file_status.total}</Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Change Detection Preview */}
      {changeDetection && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Detected Changes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {changeDetection.total_changes > 0 ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{changeDetection.new_files}</div>
                    <div className="text-sm text-gray-600">New Files</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{changeDetection.updated_files}</div>
                    <div className="text-sm text-gray-600">Updated</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">{changeDetection.deleted_files}</div>
                    <div className="text-sm text-gray-600">Deleted</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-700">{changeDetection.total_changes}</div>
                    <div className="text-sm text-gray-600">Total Changes</div>
                  </div>
                </div>
                
                {changeDetection.changes.length > 0 && (
                  <div>
                    <h5 className="font-semibold mb-2">Change Details</h5>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {changeDetection.changes.slice(0, 10).map((change, index) => (
                        <div key={index} className="flex items-center gap-2 text-sm p-2 bg-gray-50 rounded">
                          <Badge 
                            variant={change.change_type === 'created' ? 'default' : 
                                    change.change_type === 'updated' ? 'secondary' : 'destructive'}
                          >
                            {change.change_type}
                          </Badge>
                          <span className="flex-1 truncate">{change.file_path}</span>
                          {change.file_size && (
                            <span className="text-gray-500">{(change.file_size / 1024).toFixed(1)}KB</span>
                          )}
                        </div>
                      ))}
                      {changeDetection.changes.length > 10 && (
                        <div className="text-sm text-gray-500 text-center">
                          ... and {changeDetection.changes.length - 10} more changes
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-4">
                <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                <p>No changes detected. All files are up to date.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Sync History */}
      {syncHistory && syncHistory.history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Recent Sync History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {syncHistory.history.map((item) => (
                <div key={item.id} className="border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(item.status)}
                      <span className="font-medium">{item.operation_type}</span>
                      <Badge 
                        variant={item.status === 'completed' ? 'default' : 
                                item.status === 'failed' ? 'destructive' : 'secondary'}
                      >
                        {item.status}
                      </Badge>
                    </div>
                    <span className="text-sm text-gray-500">
                      {formatDateTime(item.started_at)}
                    </span>
                  </div>
                  
                  <div className="space-y-3">
                    {/* File Operations Metrics */}
                    <div>
                      <h5 className="font-semibold text-sm text-gray-700 mb-1 flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        File Operations
                      </h5>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                        <div>
                          <span className="text-gray-600">Processed:</span>
                          <span className="ml-1 font-medium">{item.files_processed}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Added:</span>
                          <span className="ml-1 font-medium text-green-600">{item.files_added}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Updated:</span>
                          <span className="ml-1 font-medium text-blue-600">{item.files_updated}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Deleted:</span>
                          <span className="ml-1 font-medium text-red-600">{item.files_deleted}</span>
                        </div>
                      </div>
                    </div>

                    {/* Embedding Operations Metrics */}
                    <div>
                      <h5 className="font-semibold text-sm text-gray-700 mb-1 flex items-center gap-1">
                        <RefreshCw className="w-3 h-3" />
                        Embedding Operations
                      </h5>
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <span className="text-gray-600">Created:</span>
                          <span className="ml-1 font-medium text-green-600">{item.chunks_created}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Updated:</span>
                          <span className="ml-1 font-medium text-blue-600">{item.chunks_updated}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Deleted:</span>
                          <span className="ml-1 font-medium text-red-600">{item.chunks_deleted}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {item.error_message && (
                    <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                      <strong>Error:</strong> {item.error_message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SyncDashboard; 