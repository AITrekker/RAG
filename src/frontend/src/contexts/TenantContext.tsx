import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

export interface TenantConfig {
  id: string;
  name: string;
  logo?: string;
  primaryColor?: string;
  secondaryColor?: string;
  welcomeMessage?: string;
}

interface TenantContextType {
  tenant: TenantConfig | null;
  setTenant: (tenant: TenantConfig | null) => void;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

interface TenantProviderProps {
  children: ReactNode;
}

export const TenantProvider: React.FC<TenantProviderProps> = ({ children }) => {
  const [tenant, setTenant] = useState<TenantConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load tenant configuration from localStorage or API
    const loadTenantConfig = async () => {
      try {
        // Try to get tenant from localStorage first
        const storedTenant = localStorage.getItem('tenant-config');
        if (storedTenant) {
          setTenant(JSON.parse(storedTenant));
        } else {
          // Default tenant configuration for development
          const defaultTenant: TenantConfig = {
            id: 'default',
            name: 'Enterprise RAG Platform',
            primaryColor: '#3B82F6',
            secondaryColor: '#1E40AF',
            welcomeMessage: 'Welcome to the Enterprise RAG Platform'
          };
          setTenant(defaultTenant);
          localStorage.setItem('tenant-config', JSON.stringify(defaultTenant));
        }
      } catch (error) {
        console.error('Failed to load tenant configuration:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadTenantConfig();
  }, []);

  const value = {
    tenant,
    setTenant: (newTenant: TenantConfig | null) => {
      setTenant(newTenant);
      if (newTenant) {
        localStorage.setItem('tenant-config', JSON.stringify(newTenant));
      } else {
        localStorage.removeItem('tenant-config');
      }
    },
    isLoading
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = (): TenantContextType => {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
}; 