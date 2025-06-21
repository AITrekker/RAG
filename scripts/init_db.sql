-- PostgreSQL initialization script for RAG platform
-- This script runs automatically when the container starts

-- Create main database if it doesn't exist
SELECT 'CREATE DATABASE rag_database'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'rag_database');

-- Connect to the main database
\c rag_database;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create basic schema structure for tenants
CREATE SCHEMA IF NOT EXISTS tenant_data;

-- Set timezone
SET timezone = 'UTC';

-- Create enum types
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sync_status') THEN
        CREATE TYPE sync_status AS ENUM ('pending', 'in_progress', 'completed', 'failed');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
        CREATE TYPE document_status AS ENUM ('uploaded', 'processing', 'indexed', 'failed');
    END IF;
END $$;

-- Initial tables will be created by Alembic migrations
-- This script just ensures basic database setup is ready

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON DATABASE rag_database TO rag_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO rag_user;
GRANT ALL PRIVILEGES ON SCHEMA tenant_data TO rag_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rag_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rag_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO rag_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_data GRANT ALL ON TABLES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_data GRANT ALL ON SEQUENCES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_data GRANT ALL ON FUNCTIONS TO rag_user; 