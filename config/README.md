# Configuration Directory

This directory contains configuration files and templates for the RAG system.

## Files

- **`delta_sync.yaml`** - Delta sync configuration
- **`rag_tuning.env`** - Sample environment configuration with documentation
- **`presets/`** - Pre-configured environment files for different deployments
- **`prompts/`** - Prompt template definitions

## Usage

```bash
# Copy a preset to your .env file
cp config/presets/production.env .env

# Apply configuration
docker-compose restart backend
```

See [docs/GUIDE.md](../docs/GUIDE.md) for complete configuration documentation.