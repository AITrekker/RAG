import { describe, it, expect, beforeAll } from 'vitest';
import { HealthService, OpenAPI } from '@/services/api.generated/index';

// Set the base URL for the API tests
beforeAll(() => {
  OpenAPI.BASE = 'http://localhost:8000';
});

describe('API Integration Tests', () => {

  it('should successfully call the health check endpoint', async () => {
    // Act: Call the health check endpoint
    const response = await HealthService.getApiV1Health();

    // Assert: Check for a successful response and valid data
    expect(response).toBeDefined();
    expect(response.status).toBe('ok');
  });

  it('should successfully call the detailed health check endpoint', async () => {
    // Act: Call the detailed health check endpoint
    const response = await HealthService.getApiV1HealthDetailed();

    // Assert: Check for a successful response and the expected structure
    expect(response).toBeDefined();
    expect(response.database).toBeDefined();
    expect(response.database.status).toBe('ok');
    expect(response.vector_store).toBeDefined();
    // The vector store might be 'unhealthy' if not configured, so we just check for presence
    expect(response.vector_store.status).toBeDefined();
  });

}); 