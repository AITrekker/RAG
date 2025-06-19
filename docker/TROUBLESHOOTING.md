# Enterprise RAG Pipeline Troubleshooting Guide

## Quick Reference

### Common Commands
```bash
# View container status
docker compose ps

# View container logs
docker compose logs [service-name]

# Check resource usage
docker stats

# Restart service
docker compose restart [service-name]

# Rebuild and restart service
docker compose up -d --build [service-name]
```

## Common Issues and Solutions

### 1. Container Startup Issues

#### Container Fails to Start
```bash
# Check container logs
docker compose logs [service-name]

# Verify environment variables
docker compose config

# Check disk space
df -h

# Check Docker daemon
systemctl status docker
```

**Solution:**
1. Verify environment variables in `.env`
2. Check for port conflicts
3. Ensure sufficient disk space
4. Validate Docker daemon status

#### Permission Issues
```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./data/
sudo chmod -R 755 ./data/

# Check SELinux context
ls -Z ./data/
```

**Solution:**
1. Set correct ownership
2. Update file permissions
3. Configure SELinux context
4. Verify Docker user mapping

### 2. Database Issues

#### Connection Failures
```bash
# Check database logs
docker compose logs rag-db

# Test connection
docker compose exec rag-db pg_isready

# Check network
docker network inspect rag_network
```

**Solution:**
1. Verify credentials in `.env`
2. Check network connectivity
3. Validate database initialization
4. Review connection limits

#### Performance Issues
```bash
# Check active connections
docker compose exec rag-db psql -U rag_user -c 'SELECT count(*) FROM pg_stat_activity;'

# Monitor query performance
docker compose exec rag-db psql -U rag_user -c 'SELECT * FROM pg_stat_activity WHERE state != 'idle';'
```

**Solution:**
1. Optimize connection pooling
2. Review query patterns
3. Adjust resource limits
4. Configure PostgreSQL parameters

### 3. Vector Store Issues

#### Search Performance
```bash
# Monitor vector store metrics
curl http://localhost:8001/metrics

# Check index status
docker compose exec rag-vector psql -U rag_user -c '\di+'
```

**Solution:**
1. Verify index configuration
2. Optimize batch sizes
3. Adjust search parameters
4. Monitor resource usage

#### Index Corruption
```bash
# Backup data
docker compose exec rag-vector pg_dump -U rag_user vector_db > backup.sql

# Rebuild index
docker compose exec rag-vector psql -U rag_user -c 'REINDEX DATABASE vector_db;'
```

**Solution:**
1. Create backup
2. Rebuild indices
3. Verify data integrity
4. Monitor rebuild progress

### 4. GPU Issues

#### GPU Not Detected
```bash
# Check NVIDIA drivers
nvidia-smi

# Verify NVIDIA Container Toolkit
nvidia-container-cli info

# Check Docker GPU support
docker info | grep -i gpu
```

**Solution:**
1. Update NVIDIA drivers
2. Reinstall NVIDIA Container Toolkit
3. Configure Docker GPU runtime
4. Verify hardware compatibility

#### GPU Memory Issues
```bash
# Monitor GPU usage
nvidia-smi -l 1

# Check container GPU stats
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}"
```

**Solution:**
1. Adjust memory limits
2. Optimize batch sizes
3. Configure GPU memory growth
4. Monitor memory usage

### 5. Monitoring Issues

#### Prometheus Connectivity
```bash
# Check Prometheus status
curl http://localhost:9090/-/healthy

# Verify targets
curl http://localhost:9090/api/v1/targets
```

**Solution:**
1. Verify endpoint configuration
2. Check network connectivity
3. Review authentication settings
4. Validate scrape configs

#### Grafana Dashboard Issues
```bash
# Check Grafana logs
docker compose logs rag-monitoring

# Verify datasource
curl http://localhost:3000/api/health
```

**Solution:**
1. Check datasource configuration
2. Verify dashboard permissions
3. Review panel queries
4. Update dashboard settings

### 6. Resource Issues

#### Memory Exhaustion
```bash
# Check memory usage
docker stats

# Monitor system memory
free -m

# Check swap usage
swapon -s
```

**Solution:**
1. Adjust container limits
2. Optimize memory usage
3. Configure swap space
4. Monitor memory patterns

#### Disk Space Issues
```bash
# Check disk usage
df -h

# Find large files
du -h --max-depth=1 /var/lib/docker/

# Clean up unused resources
docker system prune -a
```

**Solution:**
1. Clean up old containers
2. Remove unused images
3. Configure log rotation
4. Monitor disk usage

### 7. Backup and Recovery

#### Backup Failures
```bash
# Check backup logs
docker compose logs rag-backup

# Verify backup location
ls -l /path/to/backups

# Test backup script
./backup.sh --dry-run
```

**Solution:**
1. Verify backup permissions
2. Check storage space
3. Review backup configuration
4. Test backup procedures

#### Recovery Issues
```bash
# Verify backup integrity
pg_restore --list backup.sql

# Test restore procedure
pg_restore --dry-run backup.sql
```

**Solution:**
1. Validate backup files
2. Check restore permissions
3. Review recovery procedure
4. Test restore process

## Preventive Measures

### 1. Regular Maintenance
- Schedule regular backups
- Monitor resource usage
- Update dependencies
- Review logs regularly

### 2. Monitoring Setup
- Configure alerting thresholds
- Set up log aggregation
- Monitor performance metrics
- Track error rates

### 3. Documentation
- Keep runbooks updated
- Document configuration changes
- Record incident responses
- Update contact information

## Support Resources

### Documentation
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [Prometheus Documentation](https://prometheus.io/docs/)

### Support Channels
- GitHub Issues
- Docker Forums
- PostgreSQL Mailing Lists
- NVIDIA Developer Forums

### Emergency Contacts
- System Administrator: [Contact Info]
- Database Administrator: [Contact Info]
- Security Team: [Contact Info]
- Vendor Support: [Contact Info] 