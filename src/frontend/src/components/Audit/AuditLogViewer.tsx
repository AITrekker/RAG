import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../../services/api';
import { useTenant } from '../../contexts/TenantContext';

interface AuditEvent {
  id: string;
  sync_run_id: string;
  timestamp: string;
  event_type: string;
  status: 'SUCCESS' | 'FAILURE' | 'IN_PROGRESS';
  message: string;
  event_metadata: {
    file_path?: string;
    error?: string;
  };
}

export const AuditLogViewer: React.FC = () => {
  const { tenant } = useTenant();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    const fetchEvents = async () => {
      if (!tenant) return;
      setIsLoading(true);
      setError(null);
      try {
        const response = await api.getAuditEvents(page, 50);
        setEvents(response.events as AuditEvent[]);
        setTotalPages(Math.ceil(response.total_count / 50));
      } catch (err: any) {
        setError(err.error || 'Failed to fetch audit logs.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEvents();
  }, [tenant, page]);

  const groupedEvents = useMemo(() => {
    const groups: { [key: string]: AuditEvent[] } = {};
    events.forEach(event => {
      if (!groups[event.sync_run_id]) {
        groups[event.sync_run_id] = [];
      }
      groups[event.sync_run_id].push(event);
    });
    return Object.values(groups).sort((a, b) => 
      new Date(b[0].timestamp).getTime() - new Date(a[0].timestamp).getTime()
    );
  }, [events]);

  if (isLoading) {
    return <div className="text-center p-8">Loading audit logs...</div>;
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-md">{error}</div>;
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Sync Audit Logs</h2>
      <div className="space-y-6">
        {groupedEvents.map((group, index) => {
          const runStart = group.find(e => e.event_type === 'SYNC_RUN_START');
          return (
            <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-50 p-3 border-b border-gray-200">
                <h3 className="font-semibold text-gray-800">
                  Sync Run: {group[0].sync_run_id}
                </h3>
                <p className="text-sm text-gray-500">
                  Started at: {runStart ? new Date(runStart.timestamp).toLocaleString() : 'N/A'}
                </p>
              </div>
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Event</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {group.map(event => (
                    <tr key={event.id}>
                      <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{new Date(event.timestamp).toLocaleTimeString()}</td>
                      <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-800">{event.event_type}</td>
                      <td className="px-4 py-2 whitespace-nowrap text-sm">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          event.status === 'SUCCESS' ? 'bg-green-100 text-green-800' : 
                          event.status === 'FAILURE' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {event.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-700 break-all">{event.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </div>
  );
}; 