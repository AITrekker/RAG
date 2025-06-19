# Docker Setup for Enterprise RAG Pipeline

## System Requirements

- Docker Engine 24.0.0+
- Docker Compose v2.20.0+
- NVIDIA Container Toolkit (for GPU support)
- 16GB RAM minimum (32GB recommended)
- 100GB disk space minimum
- NVIDIA GPU with 8GB VRAM (for optimal performance)

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/rag.git
   cd rag
   ```

2. Copy and configure environment variables:
   ```bash
   cp docker/.env.example docker/.env
   # Edit docker/.env with your settings
   ```

3. Start the services:
   ```bash
   cd docker
   docker compose up -d
   ```

4. Verify the deployment:
   ```bash
   docker compose ps
   ```

## Service Architecture

The system consists of the following containers:

1. `rag-app`: Main application container
   - Python FastAPI backend
   - React frontend
   - GPU-accelerated inference
   - Resource monitoring

2. `rag-db`: PostgreSQL database
   - Document metadata
   - User data
   - System metrics
   - Backup management

3. `rag-vector`: Vector store (pgvector)
   - Document embeddings
   - Semantic search
   - Index management

4. `rag-monitoring`: Monitoring stack
   - Prometheus metrics
   - Grafana dashboards
   - Alert management

## Configuration

### Environment Variables

Key environment variables in `.env`:

```env
# App Configuration
RAG_ENV=production
LOG_LEVEL=INFO
DEBUG=0

# Database
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=rag_db
POSTGRES_HOST=rag-db

# Vector Store
VECTOR_STORE_URL=postgresql://rag_user:your_secure_password@rag-vector:5432/vector_db

# GPU Settings
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Resource Limits
APP_MEMORY_LIMIT=16g
DB_MEMORY_LIMIT=8g
VECTOR_MEMORY_LIMIT=8g
```

### Volume Configuration

Persistent data is stored in Docker volumes:

- `rag-db-data`: Database files
- `rag-vector-data`: Vector store data
- `rag-app-data`: Application data
- `rag-monitoring-data`: Monitoring data

## Health Checks

The system implements the following health checks:

1. Application Health:
   ```bash
   curl http://localhost:8000/health
   ```

2. Database Health:
   ```bash
   docker compose exec rag-db pg_isready
   ```

3. Vector Store Health:
   ```bash
   docker compose exec rag-vector pg_isready
   ```

## Troubleshooting

Common issues and solutions:

1. Container fails to start:
   ```bash
   docker compose logs [service-name]
   ```

2. Out of memory:
   - Check resource usage: `docker stats`
   - Adjust memory limits in `.env`
   - Consider scaling horizontally

3. GPU not detected:
   - Verify NVIDIA drivers: `nvidia-smi`
   - Check NVIDIA Container Toolkit: `nvidia-container-cli info`
   - Ensure GPU support in Docker: `docker info | grep -i gpu`

4. Database connection issues:
   - Check network: `docker network inspect rag_network`
   - Verify credentials in `.env`
   - Check logs: `docker compose logs rag-db`

## Maintenance

### Backup Procedures

1. Database backup:
   ```bash
   docker compose exec rag-db pg_dump -U rag_user rag_db > backup.sql
   ```

2. Vector store backup:
   ```bash
   docker compose exec rag-vector pg_dump -U rag_user vector_db > vector_backup.sql
   ```

3. Application data backup:
   ```bash
   docker compose exec rag-app tar czf /backup/app_data.tar.gz /app/data
   ```

### Monitoring

1. Access Grafana:
   ```
   http://localhost:3000
   ```

2. View Prometheus metrics:
   ```
   http://localhost:9090
   ```

3. Check container metrics:
   ```bash
   docker stats
   ```

## Security Best Practices

1. Use strong passwords in `.env`
2. Keep Docker and dependencies updated
3. Implement network segmentation
4. Enable Docker content trust
5. Use non-root users in containers
6. Regular security audits
7. Monitor container logs

## Performance Tuning

1. Database optimization:
   - Adjust `postgresql.conf`
   - Optimize indexes
   - Configure connection pooling

2. Vector store tuning:
   - Optimize index parameters
   - Configure batch sizes
   - Adjust search parameters

3. Application settings:
   - Configure worker processes
   - Optimize batch processing
   - Tune caching parameters

## Scaling Guidelines

1. Vertical scaling:
   - Increase container resources
   - Optimize resource allocation
   - Monitor resource usage

2. Horizontal scaling:
   - Add read replicas
   - Implement load balancing
   - Configure service discovery

## Support and Resources

- [Docker Documentation](https://docs.docker.com/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/) 