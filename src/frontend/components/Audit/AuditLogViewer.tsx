import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AuditService } from '@/src/services/api.generated';
import type { SyncEventResponse, ApiError } from '@/src/services/api.generated';
import { useTenant } from '@/contexts/TenantContext';

export const AuditLogViewer: React.FC = () => {
  const { tenant } = useTenant();

  const { data: events, isLoading, error } = useQuery<SyncEventResponse[], ApiError>({
    queryKey: ['auditEvents', tenant],
    queryFn: () => AuditService.getAuditEventsApiV1AuditEventsGet(500),
    enabled: !!tenant,
  });

  const formattedEvents = useMemo(() => {
    return events?.map(event => ({
      ...event,
      created_at: new Date(event.created_at).toLocaleString(),
    })).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()) || [];
  }, [events]);

  if (isLoading) return <div className="p-4">Loading audit logs...</div>;
  if (error) return <div className="p-4 text-red-500">Error loading audit logs: {error.body?.detail || error.message}</div>;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Audit Log</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr className="bg-gray-100">
              <th className="py-2 px-4 border-b text-left">Timestamp</th>
              <th className="py-2 px-4 border-b text-left">Event Type</th>
              <th className="py-2 px-4 border-b text-left">Status</th>
              <th className="py-2 px-4 border-b text-left">Message</th>
              <th className="py-2 px-4 border-b text-left">Sync Run ID</th>
            </tr>
          </thead>
          <tbody>
            {formattedEvents.map((event) => (
              <tr key={event.id} className="hover:bg-gray-50">
                <td className="py-2 px-4 border-b">{event.created_at}</td>
                <td className="py-2 px-4 border-b">{event.event_type}</td>
                <td className="py-2 px-4 border-b">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        event.status === 'SUCCESS' ? 'bg-green-100 text-green-800' :
                        event.status === 'FAILURE' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                        {event.status}
                    </span>
                </td>
                <td className="py-2 px-4 border-b">{event.message}</td>
                <td className="py-2 px-4 border-b font-mono text-xs">{event.sync_run_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AuditLogViewer;