#!/bin/bash

# Configuration
BACKUP_DIR="/backup"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${BACKUP_DIR}/backup_${DATE}.log"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Start logging
exec 1> >(tee -a "${LOG_FILE}")
exec 2>&1

echo "Starting backup at $(date)"

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

# Backup database
log "Starting database backup..."
docker compose exec -T rag-db pg_dump -U rag_user rag_db > "${BACKUP_DIR}/database_${DATE}.sql"
check_status "Database backup"

# Backup vector store
log "Starting vector store backup..."
docker compose exec -T rag-vector pg_dump -U rag_user vector_db > "${BACKUP_DIR}/vector_store_${DATE}.sql"
check_status "Vector store backup"

# Backup application data
log "Starting application data backup..."
docker compose exec -T rag-app tar czf - /app/data > "${BACKUP_DIR}/app_data_${DATE}.tar.gz"
check_status "Application data backup"

# Backup configuration
log "Starting configuration backup..."
cp docker-compose.yml "${BACKUP_DIR}/docker-compose_${DATE}.yml"
cp .env "${BACKUP_DIR}/env_${DATE}"
check_status "Configuration backup"

# Create backup manifest
log "Creating backup manifest..."
cat > "${BACKUP_DIR}/manifest_${DATE}.txt" << EOF
Backup Date: $(date)
Components:
- Database: database_${DATE}.sql
- Vector Store: vector_store_${DATE}.sql
- Application Data: app_data_${DATE}.tar.gz
- Configuration:
  - docker-compose_${DATE}.yml
  - env_${DATE}
EOF
check_status "Backup manifest creation"

# Clean up old backups
log "Cleaning up old backups..."
find "${BACKUP_DIR}" -type f -mtime +${RETENTION_DAYS} -delete
check_status "Old backup cleanup"

# Calculate backup size
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Total backup size: ${TOTAL_SIZE}"

# Verify backups
log "Verifying backups..."

# Check database backup
if [ -s "${BACKUP_DIR}/database_${DATE}.sql" ]; then
    log "Database backup verified"
else
    log "ERROR: Database backup verification failed"
    exit 1
fi

# Check vector store backup
if [ -s "${BACKUP_DIR}/vector_store_${DATE}.sql" ]; then
    log "Vector store backup verified"
else
    log "ERROR: Vector store backup verification failed"
    exit 1
fi

# Check application data backup
if [ -s "${BACKUP_DIR}/app_data_${DATE}.tar.gz" ]; then
    log "Application data backup verified"
else
    log "ERROR: Application data backup verification failed"
    exit 1
fi

# Check configuration backups
if [ -s "${BACKUP_DIR}/docker-compose_${DATE}.yml" ] && [ -s "${BACKUP_DIR}/env_${DATE}" ]; then
    log "Configuration backup verified"
else
    log "ERROR: Configuration backup verification failed"
    exit 1
fi

log "Backup completed successfully at $(date)"

# Create success flag file
touch "${BACKUP_DIR}/backup_${DATE}.success"

exit 0 