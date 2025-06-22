import React from 'react';
import { useTenant } from '../contexts/TenantContext';

export const TenantSelector: React.FC = () => {
  const { tenant, setTenantById, availableTenants, isLoading } = useTenant();

  const handleTenantChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setTenantById(event.target.value);
    // Optionally, reload the page to ensure all components refresh with the new tenant context
    window.location.reload();
  };

  if (isLoading || !tenant) {
    return null; // Or a loading skeleton
  }

  return (
    <div className="flex items-center">
      <label htmlFor="tenant-select" className="sr-only">Select Tenant</label>
      <select
        id="tenant-select"
        value={tenant.id}
        onChange={handleTenantChange}
        className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
      >
        {availableTenants.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
    </div>
  );
}; 