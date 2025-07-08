/**
 * Analytics API Service
 * Handles all analytics-related API calls with fallback to mock data
 */

// Mock data for development
const mockSummary = {
  tenant_id: "demo-tenant",
  today: {
    queries: 47,
    documents: 156,
    users: 12,
    avg_response_time: 850,
    success_rate: 94.2
  },
  all_time: {
    total_queries: 3247,
    total_documents: 156,
    success_rate: 91.8
  },
  recent_trend: [
    { date: "2025-07-01", queries: 35, success_rate: 92.1, avg_response_time: 920 },
    { date: "2025-07-02", queries: 42, success_rate: 94.3, avg_response_time: 780 },
    { date: "2025-07-03", queries: 38, success_rate: 91.2, avg_response_time: 890 },
    { date: "2025-07-04", queries: 51, success_rate: 95.1, avg_response_time: 720 },
    { date: "2025-07-05", queries: 44, success_rate: 93.8, avg_response_time: 810 },
    { date: "2025-07-06", queries: 39, success_rate: 92.7, avg_response_time: 870 },
    { date: "2025-07-07", queries: 47, success_rate: 94.2, avg_response_time: 850 }
  ]
};

const mockQueryHistory = [
  {
    id: "q1",
    query_text: "What are the key features of our new product?",
    response_type: "success",
    confidence_score: 0.92,
    response_time_ms: 750,
    sources_count: 3,
    created_at: "2025-07-07T15:30:00Z",
    user_id: "user1"
  },
  {
    id: "q2", 
    query_text: "How do we handle customer complaints?",
    response_type: "success",
    confidence_score: 0.88,
    response_time_ms: 920,
    sources_count: 2,
    created_at: "2025-07-07T15:15:00Z",
    user_id: "user2"
  },
  {
    id: "q3",
    query_text: "What is the pricing structure?",
    response_type: "no_answer",
    confidence_score: 0.45,
    response_time_ms: 1200,
    sources_count: 1,
    created_at: "2025-07-07T14:45:00Z",
    user_id: "user1"
  }
];

const mockDocumentUsage = [
  {
    file_id: "doc1",
    filename: "Product_Specifications_v2.pdf",
    access_count: 23,
    avg_relevance: 0.89,
    last_accessed: "2025-07-07T15:30:00Z"
  },
  {
    file_id: "doc2",
    filename: "Customer_Service_Guide.md",
    access_count: 18,
    avg_relevance: 0.92,
    last_accessed: "2025-07-07T14:20:00Z"
  },
  {
    file_id: "doc3",
    filename: "Company_Handbook.pdf", 
    access_count: 15,
    avg_relevance: 0.76,
    last_accessed: "2025-07-07T13:10:00Z"
  }
];

const mockPerformanceMetrics = {
  period: {
    start_date: "2025-06-07",
    end_date: "2025-07-07", 
    days: 30
  },
  metrics: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    total_queries: Math.floor(Math.random() * 50) + 20,
    success_rate: Math.random() * 20 + 80,
    avg_response_time: Math.random() * 500 + 500,
    avg_confidence: Math.random() * 0.3 + 0.7,
    unique_users: Math.floor(Math.random() * 15) + 5,
    documents: 156,
    storage_mb: 1247.5
  }))
};

export class AnalyticsApiService {
  private baseUrl: string;
  private apiKey: string;

  constructor(apiKey: string) {
    this.baseUrl = '/api/v1/analytics';
    this.apiKey = apiKey;
  }

  private async makeRequest(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'X-API-Key': this.apiKey,
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.warn(`Analytics API error for ${endpoint}:`, error);
      
      // Return mock data as fallback
      switch (endpoint) {
        case '/summary':
          return mockSummary;
        case '/queries/history?limit=20':
          return mockQueryHistory;
        case '/documents/usage':
          return mockDocumentUsage;
        default:
          if (endpoint.includes('/metrics/daily')) {
            return mockPerformanceMetrics;
          }
          throw error;
      }
    }
  }

  async getTenantSummary() {
    return this.makeRequest('/summary');
  }

  async getQueryHistory(limit: number = 20, offset: number = 0, userId?: string) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    
    if (userId) {
      params.append('user_id', userId);
    }

    return this.makeRequest(`/queries/history?${params}`);
  }

  async getDocumentUsage() {
    return this.makeRequest('/documents/usage');
  }

  async getPerformanceMetrics(days: number = 30) {
    return this.makeRequest(`/metrics/daily?days=${days}`);
  }

  async submitQueryFeedback(feedback: {
    query_log_id: string;
    rating: number;
    feedback_type?: string;
    feedback_text?: string;
    helpful?: boolean;
  }) {
    return this.makeRequest('/queries/feedback', {
      method: 'POST',
      body: JSON.stringify(feedback),
    });
  }

  async calculateMetrics(targetDate: string) {
    return this.makeRequest('/metrics/calculate', {
      method: 'POST',
      body: JSON.stringify({ target_date: targetDate }),
    });
  }
}

// Export a factory function
export const createAnalyticsApi = (apiKey: string) => {
  return new AnalyticsApiService(apiKey);
};