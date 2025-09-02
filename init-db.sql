-- ============================================================================
-- AI Enhanced PDF Scholar - PostgreSQL Initialization Script
-- ============================================================================

-- Create database if it doesn't exist (PostgreSQL doesn't support CREATE DATABASE IF NOT EXISTS)
-- The database is already created by the POSTGRES_DB environment variable

-- Connect to the database
\c ai_pdf_scholar;

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create basic schema for future use
CREATE SCHEMA IF NOT EXISTS ai_pdf_scholar;

-- Set default search path
ALTER DATABASE ai_pdf_scholar SET search_path TO ai_pdf_scholar, public;

-- Basic healthcheck function
CREATE OR REPLACE FUNCTION public.healthcheck()
RETURNS TEXT AS $$
BEGIN
    RETURN 'PostgreSQL is ready';
END;
$$ LANGUAGE plpgsql;

-- Create a simple test table to verify connection
CREATE TABLE IF NOT EXISTS public.connection_test (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'connected'
);

-- Insert a test record
INSERT INTO public.connection_test (status) VALUES ('initialized') ON CONFLICT DO NOTHING;

-- Grant permissions to the user
GRANT ALL PRIVILEGES ON DATABASE ai_pdf_scholar TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA ai_pdf_scholar TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Log initialization completion
DO $$
BEGIN
    RAISE NOTICE 'AI Enhanced PDF Scholar PostgreSQL database initialized successfully';
END $$;