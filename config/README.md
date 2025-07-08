# RAG Configuration Directory

This directory contains user-facing configuration files for the RAG system.

## 📁 Directory Structure

```
/config/
├── README.md                    # This file
├── rag_tuning.env              # Sample configuration with documentation
├── delta_sync.yaml             # Delta sync configuration
├── presets/                    # Pre-configured environment files
│   ├── production.env          # Production-optimized settings
│   ├── development.env         # Development-friendly settings  
│   └── testing.env             # Fast testing configuration
└── prompts/                    # Prompt template definitions
    ├── business.yaml           # Business/professional templates
    └── technical.yaml          # Technical documentation templates
```

## 🎯 Usage

### **Apply Configuration Presets**
```bash
# Copy a preset to your .env file
cp config/presets/production.env .env

# Or append to existing .env
cat config/presets/development.env >> .env

# Apply using the config manager
python scripts/rag_config_manager.py --apply-preset production
```

### **Environment-Specific Setup**
```bash
# Development environment
cp config/presets/development.env .env.development
ln -sf .env.development .env

# Production environment  
cp config/presets/production.env .env.production
ln -sf .env.production .env

# Testing environment
cp config/presets/testing.env .env.testing
ln -sf .env.testing .env
```

## 📋 Configuration Files

### **Presets**
- **`production.env`**: Optimized for reliability and consistency
- **`development.env`**: Balanced for iteration and testing  
- **`testing.env`**: Fast, minimal configuration for automated tests

### **Prompt Templates**
- **`business.yaml`**: Professional, executive, conversational templates
- **`technical.yaml`**: Technical documentation, API reference, troubleshooting

## 🔧 Configuration Management

### **Using the Config Manager**
```bash
# View current configuration
python scripts/rag_config_manager.py --show-current

# Apply preset
python scripts/rag_config_manager.py --apply-preset production

# Test configuration
python scripts/rag_config_manager.py --test-query "What is the company mission?"
```

### **Manual Configuration**
1. Copy a preset: `cp config/presets/production.env .env`
2. Edit settings: `nano .env`
3. Restart backend: `docker-compose restart backend`
4. Test: `python demo_rag_queries.py --workflow`

## 🎛️ Key Configuration Categories

### **LLM Model Settings**
- Model selection (distilgpt2, gpt2-medium, gpt2-large)
- Generation parameters (temperature, top-p, top-k)
- Response length and quality controls

### **Retrieval Configuration**  
- Number of source documents
- Confidence thresholds
- Context length limits

### **Response Quality**
- Sentence limits and formatting
- Prompt artifact removal
- Punctuation and grammar enforcement

## 🚀 Best Practices

1. **Start with presets** - Use tested configurations as starting points
2. **Environment-specific configs** - Different settings for dev/test/prod
3. **Version control** - Track configuration changes
4. **Testing** - Validate changes before production deployment
5. **Documentation** - Document custom configurations and their purposes

## 🔗 Related Files

- **Settings Schema**: `/src/backend/config/settings.py`
- **Prompt Management**: `/src/backend/config/rag_prompts.py`  
- **Config Manager**: `/scripts/rag_config_manager.py`
- **Documentation**: `/docs/RAG_TUNING.md`