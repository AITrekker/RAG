import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { OpenAPI } from '@/src/services/api.generated/core/OpenAPI';
import { TenantsService } from '@/src/services/api.generated/services/TenantsService';
import type { TenantResponse } from '@/src/services/api.generated/models/TenantResponse';
import type { ApiError } from '@/src/services/api.generated/core/ApiError';

// Set the base URL for the API client
OpenAPI.BASE = "http://localhost:8000";

interface TenantContextType {
  tenant: string | null;
  tenants: TenantResponse[];
  selectTenant: (tenantId: string) => void;
  apiKey: string | null;
  setApiKey: (key: string) => void;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const TenantProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [tenant, setTenant] = useState<string | null>(() => localStorage.getItem('tenantId'));
  
  // Auto-load admin API key from environment, fallback to localStorage
  const getInitialApiKey = () => {
    const envAdminKey = import.meta.env.VITE_ADMIN_API_KEY;
    if (envAdminKey && envAdminKey !== 'your_admin_api_key_here') {
      return envAdminKey;
    }
    return localStorage.getItem('apiKey');
  };
  
  const [apiKey, setApiKey] = useState<string | null>(getInitialApiKey);
  const queryClient = useQueryClient();

  const { data: tenants = [], isLoading } = useQuery<TenantResponse[], ApiError>({
    queryKey: ['tenants'],
    queryFn: async () => {
      // Use the working auth/tenants endpoint instead of the generated client
      const response = await fetch(`${OpenAPI.BASE}/api/v1/auth/tenants`, {
        headers: {
          'X-API-Key': apiKey!,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    },
    enabled: !!apiKey, // Only run query when API key is available
  });

  useEffect(() => {
    if (apiKey) {
      OpenAPI.HEADERS = { 'X-API-Key': apiKey };
      localStorage.setItem('apiKey', apiKey);
    } else {
      OpenAPI.HEADERS = {};
      localStorage.removeItem('apiKey');
    }
    // Invalidate tenants query when API key changes to refetch with new credentials
    queryClient.invalidateQueries({ queryKey: ['tenants'] });
  }, [apiKey, queryClient]);

  const selectTenant = useCallback((tenantId: string) => {
    setTenant(tenantId);
    localStorage.setItem('tenantId', tenantId);
  }, []);

  const handleSetApiKey = useCallback((key: string) => {
    setApiKey(key);
  }, []);

  return (
    <TenantContext.Provider value={{ tenant, tenants, selectTenant, apiKey, setApiKey: handleSetApiKey, isLoading }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = (): TenantContextType => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
}; 