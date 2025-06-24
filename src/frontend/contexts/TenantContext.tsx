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

// Define our available tenants
const availableTenants: TenantConfig[] = [
  {
    id: 'tenant1',
    name: 'InnovateCorp (Large Corp)',
    primaryColor: '#1E3A8A', // Dark Blue
    secondaryColor: '#1D4ED8',
    welcomeMessage: 'Welcome to InnovateCorp. Efficiency and excellence are our driving principles.'
  },
  {
    id: 'tenant2',
    name: 'QuantumLeap (Mid-Size)',
    primaryColor: '#047857', // Emerald
    secondaryColor: '#059669',
    welcomeMessage: 'QuantumLeap is growing fast. Let\'s find what you need to succeed.'
  },
  {
    id: 'tenant3',
    name: 'AgileSphere (Startup)',
    primaryColor: '#9D174D', // Fuchsia
    secondaryColor: '#BE185D',
    welcomeMessage: 'AgileSphere moves quickly. Search our knowledge base to keep up!'
  }
];

interface TenantContextType {
  tenant: TenantConfig | null;
  setTenantById: (tenantId: string) => void;
  availableTenants: TenantConfig[];
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
    // Load tenant configuration from localStorage or set a default
    const loadTenantConfig = () => {
      try {
        const storedTenantId = localStorage.getItem('tenant-id');
        const currentTenant = availableTenants.find(t => t.id === storedTenantId);

        if (currentTenant) {
          setTenant(currentTenant);
        } else {
          // Set tenant1 as the default
          setTenant(availableTenants[0]);
          localStorage.setItem('tenant-id', availableTenants[0].id);
        }
      } catch (error) {
        console.error('Failed to load tenant configuration:', error);
        // Fallback to default if error
        setTenant(availableTenants[0]);
      } finally {
        setIsLoading(false);
      }
    };

    loadTenantConfig();
  }, []);

  const setTenantById = (tenantId: string) => {
    const newTenant = availableTenants.find(t => t.id === tenantId);
    if (newTenant) {
      setTenant(newTenant);
      localStorage.setItem('tenant-id', newTenant.id);
    } else {
      console.warn(`Tenant with id "${tenantId}" not found.`);
    }
  };

  const value = {
    tenant,
    setTenantById,
    availableTenants,
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