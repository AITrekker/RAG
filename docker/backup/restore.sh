#!/bin/bash

# Configuration
BACKUP_DIR="/backup"
LOG_FILE="${BACKUP_DIR}/restore_$(date +%Y%m%d_%H%M%S).log"

# Start logging
exec 1> >(tee -a "${LOG_FILE}")
exec 2>&1

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if a command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        log "SUCCESS: $1"
    else
        log "ERROR: $1"
        exit 1
    fi
}

# Check if backup date is provided
if [ -z "$1" ]; then
    log "ERROR: Backup date not provided"
    log "Usage: $0 YYYYMMDD_HHMMSS"
    exit 1
fi

BACKUP_DATE=$1
log "Starting restore from backup date: ${BACKUP_DATE}"

# Verify backup files exist
log "Verifying backup files..."
required_files=(
    "database_${BACKUP_DATE}.sql"
    "vector_store_${BACKUP_DATE}.sql"
    "app_data_${BACKUP_DATE}.tar.gz"
    "docker-compose_${BACKUP_DATE}.yml"
    "env_${BACKUP_DATE}"
    "manifest_${BACKUP_DATE}.txt"
)

for file in "${required_files[@]}"; do
    if [ ! -f "${BACKUP_DIR}/${file}" ]; then
        log "ERROR: Required backup file not found: ${file}"
        exit 1
    fi
done

# Check backup success flag
if [ ! -f "${BACKUP_DIR}/backup_${BACKUP_DATE}.success" ]; then
    log "ERROR: Backup success flag not found. This backup may be incomplete."
    exit 1
fi

# Stop services
log "Stopping services..."
docker compose down
check_status "Service shutdown"

# Restore configuration
log "Restoring configuration..."
cp "${BACKUP_DIR}/docker-compose_${BACKUP_DATE}.yml" docker-compose.yml
cp "${BACKUP_DIR}/env_${BACKUP_DATE}" .env
check_status "Configuration restore"

# Start database and vector store services
log "Starting database and vector store services..."
docker compose up -d rag-db rag-vector
check_status "Database and vector store startup"

# Wait for services to be ready
log "Waiting for services to be ready..."
sleep 30

# Restore database
log "Restoring database..."
docker compose exec -T rag-db psql -U rag_user -d rag_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
check_status "Database schema reset"
cat "${BACKUP_DIR}/database_${BACKUP_DATE}.sql" | docker compose exec -T rag-db psql -U rag_user -d rag_db
check_status "Database restore"

# Restore vector store
log "Restoring vector store..."
docker compose exec -T rag-vector psql -U rag_user -d vector_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
check_status "Vector store schema reset"
cat "${BACKUP_DIR}/vector_store_${BACKUP_DATE}.sql" | docker compose exec -T rag-vector psql -U rag_user -d vector_db
check_status "Vector store restore"

# Stop services before restoring application data
log "Stopping services for application data restore..."
docker compose down
check_status "Service shutdown"

# Restore application data
log "Restoring application data..."
docker compose up -d rag-app
check_status "Application container startup"
cat "${BACKUP_DIR}/app_data_${BACKUP_DATE}.tar.gz" | docker compose exec -T rag-app tar xzf - -C /
check_status "Application data restore"

# Start all services
log "Starting all services..."
docker compose down
docker compose up -d
check_status "Service startup"

# Verify restore
log "Verifying restore..."

# Check database
log "Checking database..."
docker compose exec rag-db pg_isready
check_status "Database connectivity check"

# Check vector store
log "Checking vector store..."
docker compose exec rag-vector pg_isready
check_status "Vector store connectivity check"

# Check application
log "Checking application..."
curl -f http://localhost:8000/health
check_status "Application health check"

log "Restore completed successfully at $(date)"

# Create restore success flag
touch "${BACKUP_DIR}/restore_${BACKUP_DATE}_$(date +%Y%m%d_%H%M%S).success"

exit 0 