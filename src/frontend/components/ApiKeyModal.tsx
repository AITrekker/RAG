import { useState } from 'react';
import { useTenant } from '@/contexts/TenantContext';
import { Button } from '@/components/ui/button';
import { TenantSelector } from '@/components/TenantSelector';
import { useToast } from '@/components/ui/use-toast';
import { useMutation } from '@tanstack/react-query';
import { TenantsService } from '@/src/services/api.generated/services/TenantsService';
import type { ApiError } from '@/src/services/api.generated/core/ApiError';

export const ApiKeyModal: React.FC = () => {
  const { tenant, tenantKeys } = useTenant();
  const { toast } = useToast();

  const handleContinue = () => {
    if (!tenant) {
      toast({
        title: "No Tenant Selected",
        description: "Please select a tenant to continue.",
        variant: "destructive",
      });
      return;
    }
    
    const tenantKey = tenantKeys[tenant];
    if (!tenantKey) {
      toast({
        title: "No API Key Found",
        description: `No API key found for tenant: ${tenant}`,
        variant: "destructive",
      });
      return;
    }
    
    // Keys are automatically loaded and set by TenantContext
    toast({
      title: "Authentication Ready",
      description: `Connected to ${tenant}`,
    });
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <h2 className="text-2xl font-bold mb-4">Select Tenant</h2>
        <p className="text-gray-600 mb-6">
          Please select your tenant to continue. API keys are automatically loaded for each tenant.
        </p>
        <div className="space-y-4">
          <TenantSelector />
          
          {tenant && tenantKeys[tenant] && (
            <div className="bg-green-50 border border-green-200 rounded-md p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-green-800">
                    API Key Ready
                  </p>
                  <p className="text-sm text-green-600">
                    {tenantKeys[tenant].description}
                  </p>
                </div>
              </div>
            </div>
          )}
          
          {tenant && !tenantKeys[tenant] && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-red-800">
                    No API Key Found
                  </p>
                  <p className="text-sm text-red-600">
                    No API key available for tenant: {tenant}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="mt-8 flex justify-end">
          <Button
            onClick={handleContinue}
            disabled={!tenant || !tenantKeys[tenant]}
          >
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}; 