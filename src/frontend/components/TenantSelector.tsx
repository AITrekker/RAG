import React from 'react';
import { useTenant } from '@/contexts/TenantContext';

export const TenantSelector: React.FC = () => {
  const { tenant, tenants, selectTenant, isLoading } = useTenant();

  const handleTenantChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    selectTenant(event.target.value);
  };

  if (isLoading && tenants.length === 0) {
    return <div>Loading tenants...</div>;
  }

  return (
    <div className="flex items-center">
      <label htmlFor="tenant-select" className="text-sm font-medium text-gray-700 mr-2">Tenant:</label>
      <select
        id="tenant-select"
        value={tenant || ''}
        onChange={handleTenantChange}
        className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
        disabled={isLoading}
      >
        <option value="" disabled>-- Select a Tenant --</option>
        {tenants.map((t) => (
          <option key={t.tenant_id} value={t.tenant_id}>
            {t.tenant_id}
          </option>
        ))}
      </select>
    </div>
  );
}; 