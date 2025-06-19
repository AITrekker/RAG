# Docker Configuration for Enterprise RAG Pipeline

This directory contains all Docker-related configuration files for the Enterprise RAG Pipeline.

## Files Overview

- `Dockerfile` - Main application container with GPU support
- `docker-compose.yml` - Multi-container orchestration
- `entrypoint.sh` - Container startup script
- `env.example` - Environment variables template

## Quick Start

1. **Prerequisites**
   - Docker Engine 20.10+
   - Docker Compose 2.0+
   - NVIDIA Container Toolkit (for GPU support)
   - NVIDIA GPU drivers

2. **Setup Environment**
   ```bash
   # Copy environment template
   cp docker/env.example .env
   
   # Edit .env with your settings
   nano .env
   ```

3. **Start Services**
   ```bash
   # Build and start all services
   docker-compose -f docker/docker-compose.yml up --build
   
   # Or run in background
   docker-compose -f docker/docker-compose.yml up -d --build
   ```

4. **Access Services**
   - Main Application: http://localhost:8000
   - Vector Store API: http://localhost:8001
   - Database: localhost:5432

## Container Architecture

### Main Application Container (`hr-rag-app`)
- **Base Image**: `nvidia/cuda:11.8-devel-ubuntu22.04`
- **Purpose**: Runs the Enterprise RAG Pipeline application
- **GPU Support**: Uses NVIDIA runtime for embedding generation
- **Ports**: 8000 (FastAPI)
- **Volumes**: 
  - Source code (read-only)
  - Data directories (master/sync folders)
  - Application data (SQLite, logs)

### Database Container (`database`)
- **Base Image**: `postgres:15`
- **Purpose**: Stores metadata, file tracking, and sync status
- **Ports**: 5432
- **Volumes**: Persistent database storage

### Vector Store Container (`vector-store`)
- **Base Image**: `chromadb/chroma:latest`
- **Purpose**: Stores and retrieves vector embeddings
- **Ports**: 8001 (mapped from internal 8000)
- **Volumes**: Persistent vector data storage

## Volume Configuration

### Named Volumes (Managed by Docker)
- `enterprise_rag_data` - Application data and SQLite database
- `enterprise_rag_logs` - Application logs
- `enterprise_rag_db_data` - PostgreSQL database files
- `enterprise_rag_vector_data` - ChromaDB vector storage

### Bind Mounts (Host Directories)
- `./data/master` → `/app/data/master` - File drop location
- `./data/sync` → `/app/data/sync` - Processed files

## Environment Variables

Key environment variables (see `env.example` for complete list):

- `DATABASE_URL` - Database connection string
- `MASTER_FOLDER_PATH` - Override master folder location
- `SYNC_FOLDER_PATH` - Override sync folder location
- `CUDA_VISIBLE_DEVICES` - GPU device selection
- `LOG_LEVEL` - Logging verbosity

## GPU Support

### Requirements
- NVIDIA GPU with compute capability 6.0+
- NVIDIA Container Toolkit installed
- Proper GPU drivers

### Configuration
The application automatically detects GPU availability and falls back to CPU if needed.

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Health Checks

All containers include health checks:
- **App**: HTTP health endpoint
- **Database**: PostgreSQL connection test
- **Vector Store**: ChromaDB heartbeat API

## Development vs Production

### Development Mode
- Uses SQLite database
- Source code mounted as volume for hot reload
- Debug logging enabled

### Production Mode
- Uses PostgreSQL database
- Source code copied into container
- Optimized logging configuration

Switch modes by updating `DATABASE_URL` in environment variables.

## Troubleshooting

### GPU Issues
```bash
# Check GPU availability in container
docker exec hr-rag-pipeline nvidia-smi

# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi
```

### Permission Issues
```bash
# Fix volume permissions
sudo chown -R $USER:$USER ./data/
```

### Container Logs
```bash
# View application logs
docker logs hr-rag-pipeline

# View all service logs
docker-compose -f docker/docker-compose.yml logs
```

### Reset Everything
```bash
# Stop and remove all containers and volumes
docker-compose -f docker/docker-compose.yml down -v

# Remove images
docker rmi $(docker images "hr-rag*" -q)
```

## Performance Tuning

### GPU Memory
Adjust in environment:
```env
MAX_GPU_MEMORY_GB=10
```

### Resource Limits
Configure in docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      memory: 8G
      cpus: '4.0'
```

## Security Notes

- Change default passwords in production
- Use secrets management for sensitive environment variables
- Configure firewall rules for exposed ports
- Enable container security scanning 