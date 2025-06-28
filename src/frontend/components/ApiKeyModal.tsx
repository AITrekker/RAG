import { useState } from 'react';
import { useTenant } from '@/contexts/TenantContext';
import { Button } from '@/components/ui/button';
import { TenantSelector } from '@/components/TenantSelector';
import { useToast } from '@/components/ui/use-toast';
import { useMutation } from '@tanstack/react-query';
import { TenantsService } from '@/src/services/api.generated/services/TenantsService';
import type { ApiError } from '@/src/services/api.generated/core/ApiError';

export const ApiKeyModal: React.FC = () => {
  const { setApiKey, tenant } = useTenant();
  const [localApiKey, setLocalApiKey] = useState('');
  const { toast } = useToast();

  const createKeyMutation = useMutation({
    mutationFn: (tenantId: string) => TenantsService.createApiKeyApiV1TenantsApiKeyPost({
        tenant_id: tenantId
    }),
    onSuccess: (data) => {
      setLocalApiKey(data.api_key);
      toast({
        title: "API Key Generated",
        description: "Your new API key has been created and populated below.",
      });
    },
    onError: (error: ApiError) => {
        toast({
            title: "Failed to Generate Key",
            description: error.body?.detail || error.message,
            variant: "destructive",
        })
    }
  })

  const handleSave = () => {
    if (localApiKey.trim()) {
      setApiKey(localApiKey.trim());
    }
  };

  const handleGenerateKey = () => {
    if(tenant) {
        createKeyMutation.mutate(tenant);
    }
  }

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <h2 className="text-2xl font-bold mb-4">Configuration Required</h2>
        <p className="text-gray-600 mb-6">
          Please select your tenant and provide your API key. If you don't have a key, you can generate one.
        </p>
        <div className="space-y-4">
          <TenantSelector />
          <div>
            <label htmlFor="api-key-input" className="block text-sm font-medium text-gray-700">
              API Key
            </label>
            <div className="flex items-center space-x-2 mt-1">
                <input
                type="password"
                id="api-key-input"
                value={localApiKey}
                onChange={(e) => setLocalApiKey(e.target.value)}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                placeholder="Enter your API key or generate one"
                />
                <Button variant="outline" onClick={handleGenerateKey} disabled={!tenant || createKeyMutation.isPending}>
                    {createKeyMutation.isPending ? "Generating..." : "Generate"}
                </Button>
            </div>
          </div>
        </div>
        <div className="mt-8 flex justify-end">
          <Button
            onClick={handleSave}
            disabled={!tenant || !localApiKey.trim()}
          >
            Save and Continue
          </Button>
        </div>
      </div>
    </div>
  );
}; 