import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  FileText, 
  Clock, 
  Brain,
  Target,
  Activity,
  Download,
  RefreshCw,
  Calendar,
  Search,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Zap
} from 'lucide-react';

import { StatsCard } from '../ui/stats-card';
import { AnimatedTabs, AnimatedTabContent } from '../ui/animated-tabs';
import { LoadingSpinner, ProgressBar } from '../ui/loading-states';
import { AnimatedButton } from '../ui/animated-button';
import { useTenant } from '../../contexts/TenantContext';
import { createAnalyticsApi } from '../../services/analytics-api';

// =============================================
// TYPES & INTERFACES
// =============================================

interface TenantSummary {
  tenant_id: string;
  today: {
    queries: number;
    documents: number;
    users: number;
    avg_response_time: number;
    success_rate: number;
  };
  all_time: {
    total_queries: number;
    total_documents: number;
    success_rate: number;
  };
  recent_trend: Array<{
    date: string;
    queries: number;
    success_rate: number;
    avg_response_time: number;
  }>;
}

interface QueryHistory {
  id: string;
  query_text: string;
  response_type: string;
  confidence_score: number | null;
  response_time_ms: number;
  sources_count: number;
  created_at: string;
  user_id: string | null;
}

interface DocumentUsage {
  file_id: string;
  filename: string;
  access_count: number;
  avg_relevance: number;
  last_accessed: string | null;
}

interface PerformanceMetrics {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  metrics: Array<{
    date: string;
    total_queries: number;
    success_rate: number;
    avg_response_time: number;
    avg_confidence: number;
    unique_users: number;
    documents: number;
    storage_mb: number;
  }>;
}

// =============================================
// MAIN DASHBOARD COMPONENT
// =============================================

export const AnalyticsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [summary, setSummary] = useState<TenantSummary | null>(null);
  const [queryHistory, setQueryHistory] = useState<QueryHistory[]>([]);
  const [documentUsage, setDocumentUsage] = useState<DocumentUsage[]>([]);
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [timeRange, setTimeRange] = useState(30);
  const { apiKey, tenant } = useTenant();

  // =============================================
  // DATA FETCHING
  // =============================================

  const fetchAnalytics = async (showLoader = true) => {
    if (!apiKey) return;
    
    if (showLoader) setLoading(true);
    setRefreshing(!showLoader);
    
    try {
      const analyticsApi = createAnalyticsApi(apiKey);

      // Fetch all analytics data in parallel
      const [summaryData, historyData, usageData, performanceData] = await Promise.all([
        analyticsApi.getTenantSummary(),
        analyticsApi.getQueryHistory(20),
        analyticsApi.getDocumentUsage(),
        analyticsApi.getPerformanceMetrics(timeRange)
      ]);

      setSummary(summaryData);
      setQueryHistory(historyData);
      setDocumentUsage(usageData);
      setPerformance(performanceData);

    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [apiKey, timeRange]);

  // =============================================
  // OVERVIEW TAB
  // =============================================

  const renderOverview = () => (
    <motion.div
      key="overview"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-8"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Analytics Overview</h2>
          <p className="text-gray-600 mt-1">Comprehensive insights for {tenant || 'your tenant'}</p>
        </div>
        <div className="flex items-center gap-3">
          <select 
            value={timeRange} 
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <AnimatedButton
            variant="outline"
            size="sm"
            icon={<RefreshCw size={16} />}
            onClick={() => fetchAnalytics(false)}
            loading={refreshing}
            animation="rotate"
          >
            Refresh
          </AnimatedButton>
        </div>
      </div>

      {/* Summary Stats */}
      {summary && (
        <motion.div 
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <StatsCard
            title="Total Queries"
            value={summary.all_time.total_queries}
            change={{ 
              value: summary.today.queries, 
              type: summary.today.queries > 0 ? "increase" : "neutral",
              label: "today"
            }}
            icon={<MessageSquare size={24} />}
            color="blue"
            trend={summary.recent_trend.map(d => d.queries)}
          />
          <StatsCard
            title="Success Rate"
            value={`${Math.round(summary.all_time.success_rate)}%`}
            change={{ 
              value: Math.round(summary.today.success_rate), 
              type: summary.today.success_rate >= 80 ? "increase" : "decrease",
              label: "today"
            }}
            icon={<Target size={24} />}
            color="green"
            trend={summary.recent_trend.map(d => d.success_rate)}
          />
          <StatsCard
            title="Total Documents"
            value={summary.all_time.total_documents}
            change={{ 
              value: summary.today.documents, 
              type: "neutral",
              label: "indexed"
            }}
            icon={<FileText size={24} />}
            color="purple"
          />
          <StatsCard
            title="Avg Response Time"
            value={`${Math.round(summary.today.avg_response_time || 0)}ms`}
            change={{ 
              value: Math.round(summary.today.avg_response_time || 0), 
              type: summary.today.avg_response_time < 1000 ? "increase" : "decrease",
              label: "current"
            }}
            icon={<Zap size={24} />}
            color="orange"
            trend={summary.recent_trend.map(d => d.avg_response_time)}
          />
        </motion.div>
      )}

      {/* Performance Chart */}
      {performance && (
        <motion.div
          className="bg-white rounded-xl shadow-lg p-6 border border-gray-200"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <TrendingUp className="text-blue-500" size={24} />
              Performance Trends
            </h3>
            <div className="text-sm text-gray-500">
              {performance.period.start_date} to {performance.period.end_date}
            </div>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold mb-3">Query Volume</h4>
              <div className="space-y-2">
                {performance.metrics.slice(-7).map((metric, idx) => (
                  <div key={metric.date} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      {new Date(metric.date).toLocaleDateString()}
                    </span>
                    <div className="flex items-center gap-2">
                      <ProgressBar
                        progress={Math.min((metric.total_queries / 100) * 100, 100)}
                        variant="gradient"
                        color="blue"
                        className="w-24"
                      />
                      <span className="text-sm font-medium w-8">
                        {metric.total_queries}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            <div>
              <h4 className="font-semibold mb-3">Success Rate</h4>
              <div className="space-y-2">
                {performance.metrics.slice(-7).map((metric, idx) => (
                  <div key={metric.date} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      {new Date(metric.date).toLocaleDateString()}
                    </span>
                    <div className="flex items-center gap-2">
                      <ProgressBar
                        progress={metric.success_rate}
                        variant="gradient"
                        color={metric.success_rate >= 80 ? "green" : "orange"}
                        className="w-24"
                      />
                      <span className="text-sm font-medium w-12">
                        {Math.round(metric.success_rate)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  );

  // =============================================
  // QUERIES TAB
  // =============================================

  const renderQueries = () => (
    <motion.div
      key="queries"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Query Analytics</h2>
        <AnimatedButton
          variant="outline"
          icon={<Download size={16} />}
          onClick={() => console.log('Export queries')}
        >
          Export Data
        </AnimatedButton>
      </div>

      {/* Recent Queries */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Search className="text-blue-500" size={20} />
            Recent Queries
          </h3>
        </div>
        <div className="divide-y divide-gray-200">
          {queryHistory.slice(0, 10).map((query) => (
            <motion.div
              key={query.id}
              className="p-4 hover:bg-gray-50 transition-colors"
              whileHover={{ x: 4 }}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900 mb-1">
                    {query.query_text.length > 100 
                      ? `${query.query_text.substring(0, 100)}...` 
                      : query.query_text
                    }
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>
                      {new Date(query.created_at).toLocaleString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {query.response_time_ms}ms
                    </span>
                    <span className="flex items-center gap-1">
                      <FileText size={12} />
                      {query.sources_count} sources
                    </span>
                    {query.confidence_score && (
                      <span className="flex items-center gap-1">
                        <Brain size={12} />
                        {Math.round(query.confidence_score * 100)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="ml-4">
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    query.response_type === 'success' 
                      ? 'bg-green-100 text-green-800'
                      : query.response_type === 'no_answer'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {query.response_type}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );

  // =============================================
  // DOCUMENTS TAB
  // =============================================

  const renderDocuments = () => (
    <motion.div
      key="documents"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <h2 className="text-2xl font-bold text-gray-900">Document Analytics</h2>

      {/* Document Usage */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <FileText className="text-purple-500" size={20} />
            Most Accessed Documents
          </h3>
        </div>
        <div className="divide-y divide-gray-200">
          {documentUsage.slice(0, 10).map((doc, idx) => (
            <motion.div
              key={doc.file_id}
              className="p-4 hover:bg-gray-50 transition-colors"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="font-medium text-gray-900 mb-1">
                    {doc.filename}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Activity size={12} />
                      {doc.access_count} accesses
                    </span>
                    <span className="flex items-center gap-1">
                      <Target size={12} />
                      {Math.round(doc.avg_relevance * 100)}% relevance
                    </span>
                    {doc.last_accessed && (
                      <span>
                        Last: {new Date(doc.last_accessed).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="ml-4 text-right">
                  <div className="text-lg font-bold text-blue-600">
                    #{idx + 1}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );

  // =============================================
  // TAB CONFIGURATION
  // =============================================

  const tabs = [
    { 
      id: 'overview', 
      label: 'Overview', 
      icon: <BarChart3 size={18} />, 
      color: 'from-blue-500 to-blue-600' 
    },
    { 
      id: 'queries', 
      label: 'Queries', 
      icon: <Search size={18} />, 
      color: 'from-green-500 to-green-600',
      badge: queryHistory.length 
    },
    { 
      id: 'documents', 
      label: 'Documents', 
      icon: <FileText size={18} />, 
      color: 'from-purple-500 to-purple-600',
      badge: documentUsage.length
    },
    { 
      id: 'users', 
      label: 'Users', 
      icon: <Users size={18} />, 
      color: 'from-orange-500 to-orange-600',
      badge: 'Soon'
    }
  ];

  // =============================================
  // LOADING STATE
  // =============================================

  if (loading) {
    return (
      <div className="min-h-[600px] flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="xl" variant="orbit" color="blue" className="mb-4" />
          <p className="text-gray-600">Loading analytics data...</p>
        </div>
      </div>
    );
  }

  // =============================================
  // MAIN RENDER
  // =============================================

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div 
        className="flex items-center gap-4"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="w-16 h-16 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-xl">
          <BarChart3 className="text-white" size={32} />
        </div>
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
            Analytics Dashboard
          </h1>
          <p className="text-lg text-gray-500 mt-1">
            Real-time insights and performance metrics
          </p>
        </div>
      </motion.div>

      {/* Navigation */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <AnimatedTabs
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          variant="pills"
          staggerDelay={0.05}
          className="justify-center"
        />
      </motion.div>

      {/* Content */}
      <AnimatedTabContent
        activeTab={activeTab}
        animation="slide"
        direction="right"
        className="min-h-[600px]"
      >
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'queries' && renderQueries()}
        {activeTab === 'documents' && renderDocuments()}
        {activeTab === 'users' && (
          <div className="text-center py-20">
            <Users className="mx-auto text-gray-400 mb-4" size={64} />
            <h3 className="text-xl font-semibold text-gray-600 mb-2">User Analytics Coming Soon</h3>
            <p className="text-gray-500">Advanced user behavior and engagement metrics</p>
          </div>
        )}
      </AnimatedTabContent>
    </div>
  );
};