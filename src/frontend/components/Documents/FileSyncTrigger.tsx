import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { SyncService } from '@/src/services/api.generated';
import type { ApiError } from '@/src/services/api.generated';
import { useTenant } from '@/contexts/TenantContext';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { RefreshCw, FolderSync, Info } from 'lucide-react';

export const FileSyncTrigger: React.FC = () => {
  const { tenant } = useTenant();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const syncMutation = useMutation<any, ApiError, void>({
    mutationFn: () => SyncService.triggerSyncApiV1SyncTriggerPost(),
    onSuccess: (data) => {
      toast({
        title: "Sync Completed",
        description: "File synchronization has been triggered successfully.",
      });
      // Invalidate files query to refresh the list
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
    onError: (error: ApiError) => {
      toast({
        title: "Sync Failed",
        description: error.body?.detail || error.message || "An unexpected error occurred.",
        variant: "destructive",
      });
    },
  });

  const handleSync = () => {
    if (!tenant) {
      toast({
        title: "No Tenant Selected",
        description: "Please select a tenant before triggering sync.",
        variant: "destructive",
      });
      return;
    }
    syncMutation.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <FolderSync className="h-5 w-5" />
          <span>File Synchronization</span>
        </CardTitle>
        <CardDescription>
          Sync files from the tenant's upload folder into the RAG system using delta sync.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start space-x-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-medium">How to add files:</p>
            <p className="mt-1">
              Place files in: <code className="bg-blue-100 px-1 rounded text-xs">./data/uploads/{tenant?.id || '{tenant-id}'}/</code>
            </p>
            <p className="mt-1 text-blue-600">
              Then click the sync button below to process them into the system.
            </p>
          </div>
        </div>

        <Button 
          onClick={handleSync}
          disabled={!tenant || syncMutation.isPending}
          className="w-full"
          size="lg"
        >
          {syncMutation.isPending ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              Syncing Files...
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4 mr-2" />
              Trigger Delta Sync
            </>
          )}
        </Button>

        <div className="text-xs text-gray-500 space-y-1">
          <p>• Delta sync only processes new or changed files</p>
          <p>• Supported formats: PDF, DOCX, TXT, HTML, MD</p>
          <p>• Files are automatically chunked and embedded</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default FileSyncTrigger;