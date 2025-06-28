import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SynchronizationService } from "@/src/services/api.generated";
import type { SyncTriggerRequest, ApiError, SyncResponse } from "@/src/services/api.generated";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { useTenant } from "@/contexts/TenantContext";

export const SyncDashboard = () => {
  const { tenant } = useTenant();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const syncMutation = useMutation<SyncResponse, ApiError, SyncTriggerRequest>({
    mutationFn: (params) =>
      SynchronizationService.triggerManualSyncApiV1SyncTriggerPost(params),
    onSuccess: (data) => {
      toast({
        title: "Sync Started",
        description: `Sync operation (ID: ${data.sync_id}) has been initiated.`,
      });
      queryClient.invalidateQueries({ queryKey: ["auditEvents"] });
    },
    onError: (error) => {
      toast({
        title: "Sync Failed",
        description: error.message || "An unexpected error occurred.",
        variant: "destructive",
      });
    },
  });

  const handleSync = (forceFull: boolean) => {
    syncMutation.mutate({ force_full_sync: forceFull });
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Sync Controls</h2>
      <div className="flex gap-4">
        <Button
          onClick={() => handleSync(false)}
          disabled={syncMutation.isPending || !tenant}
        >
          {syncMutation.isPending ? "Syncing..." : "Trigger Delta Sync"}
        </Button>
        <Button
          onClick={() => handleSync(true)}
          disabled={syncMutation.isPending || !tenant}
          variant="outline"
        >
          {syncMutation.isPending ? "Syncing..." : "Force Full Sync"}
        </Button>
      </div>
    </div>
  );
};

export default SyncDashboard; 