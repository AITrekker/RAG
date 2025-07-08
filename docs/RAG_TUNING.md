# RAG System Tuning Guide

**Complete guide to configuring and optimizing the RAG pipeline for your specific needs.**

## 🎯 Overview

The RAG system is designed for easy configuration and iterative tuning without code changes. All LLM settings, prompt templates, and response quality parameters can be adjusted through environment variables and configuration files.

## 📁 Configuration Files Structure

```
├── .env                                    # Main environment configuration
├── config/                                 # User-facing configuration directory
│   ├── README.md                          # Configuration guide
│   ├── rag_tuning.env                     # Sample RAG settings with documentation
│   ├── presets/                           # Pre-configured environment files
│   │   ├── production.env                 # Production-optimized settings
│   │   ├── development.env                # Development-friendly settings
│   │   └── testing.env                    # Fast testing configuration
│   └── prompts/                           # Prompt template definitions
│       ├── business.yaml                  # Business/professional templates
│       └── technical.yaml                 # Technical documentation templates
├── src/backend/config/                    # Backend configuration code
│   ├── settings.py                        # Settings schema and validation
│   ├── rag_prompts.py                     # Prompt template management
│   └── config_loader.py                  # Bridge between /config and backend
├── scripts/rag_config_manager.py          # Configuration management tool
└── docs/RAG_TUNING.md                     # This file
```

---

## 🚀 Quick Start

### **1. Apply Recommended Settings**
```bash
# Apply production preset (recommended for most use cases)
python scripts/rag_config_manager.py --apply-preset production

# Restart backend to apply changes
docker-compose restart backend

# Test the configuration
python demo_rag_queries.py --workflow --tenant tenant1
```

### **2. View Current Configuration**
```bash
# See all current RAG settings
python scripts/rag_config_manager.py --show-current

# List available presets
python scripts/rag_config_manager.py --list-presets
```

### **3. Test Changes Immediately**
```bash
# Test with a specific query
python scripts/rag_config_manager.py --test-query "What is the company's mission?"

# Run comprehensive demo
python demo_rag_queries.py --tenant tenant1 --query "Tell me about the financial performance"
```

---

## 🎛️ Configuration Categories

### **1. LLM Model Selection**
Controls which language model is used for answer generation.

| Setting | Options | Description | Impact |
|---------|---------|-------------|--------|
| `RAG_LLM_MODEL` | `distilgpt2`, `gpt2-medium`, `gpt2-large`, `gpt2-xl`, `microsoft/DialoGPT-medium` | Model size vs quality tradeoff | Larger = better quality, slower |

**Recommendations:**
- **Production**: `gpt2-medium` (345M params) - best balance
- **High Quality**: `gpt2-large` (774M params) - better responses
- **Fast/Demo**: `distilgpt2` (82M params) - quick but basic
- **Conversational**: `microsoft/DialoGPT-medium` - dialog optimized

### **2. Generation Quality Parameters**
Fine-tune how the LLM generates responses.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| `RAG_TEMPERATURE` | 0.1-1.0 | 0.3 | Lower = focused/deterministic, Higher = creative |
| `RAG_TOP_P` | 0.1-1.0 | 0.85 | Nucleus sampling - limits vocabulary diversity |
| `RAG_TOP_K` | 10-100 | 40 | Limits to top K most likely tokens |
| `RAG_REPETITION_PENALTY` | 1.0-2.0 | 1.3 | Prevents repetitive text |
| `RAG_MAX_NEW_TOKENS` | 50-500 | 200 | Maximum response length |

**Tuning Guidelines:**
- **More Focused**: Lower temperature (0.1-0.3), lower top-p (0.7-0.8)
- **More Creative**: Higher temperature (0.5-0.7), higher top-p (0.9-0.95)
- **Reduce Repetition**: Increase repetition penalty (1.3-1.5)
- **Longer Responses**: Increase max_new_tokens (250-400)

### **3. Retrieval Configuration**
Controls how documents are found and used for context.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| `RAG_MAX_SOURCES` | 3-10 | 5 | Number of documents to retrieve |
| `RAG_CONFIDENCE_THRESHOLD` | 0.1-0.9 | 0.3 | Minimum similarity score to include |
| `RAG_MAX_CONTEXT_LENGTH` | 1000-4000 | 2000 | Maximum characters in combined context |
| `RAG_SOURCE_PREVIEW_LENGTH` | 100-500 | 200 | Characters shown in source previews |

**Optimization Tips:**
- **More Context**: Increase max_sources (7-10) and context_length (3000+)
- **Higher Quality**: Increase confidence_threshold (0.5-0.7)
- **Faster Retrieval**: Reduce max_sources (3-5)

### **4. Response Quality Controls**
Fine-tune the final response formatting and quality.

| Setting | Default | Description |
|---------|---------|-------------|
| `RAG_MAX_SENTENCES` | 4 | Maximum sentences in final response |
| `RAG_MIN_SENTENCE_LENGTH` | 10 | Minimum characters per sentence |
| `RAG_REMOVE_PROMPT_ARTIFACTS` | true | Clean up prompt remnants |
| `RAG_ENSURE_PUNCTUATION` | true | Add proper sentence endings |

---

## 🎯 Pre-configured Presets

Use these tested configurations for different scenarios:

### **Production (Recommended)**
```bash
python scripts/rag_config_manager.py --apply-preset production
```
- **Model**: gpt2-medium (345M parameters)
- **Temperature**: 0.3 (focused but not rigid)
- **Use Case**: Production deployments, enterprise use
- **Quality**: High | **Speed**: Good | **Reliability**: Excellent

### **Development**
```bash
python scripts/rag_config_manager.py --apply-preset development
```
- **Model**: gpt2-medium (345M parameters)
- **Temperature**: 0.4 (slightly more creative for experimentation)
- **Use Case**: Development, testing, iteration
- **Quality**: High | **Speed**: Good | **Flexibility**: High

### **Testing**
```bash
python scripts/rag_config_manager.py --apply-preset testing
```
- **Model**: distilgpt2 (82M parameters)
- **Temperature**: 0.3 (consistent for testing)
- **Use Case**: Automated testing, CI/CD
- **Quality**: Basic | **Speed**: Very Fast | **Deterministic**: High

### **Legacy Presets** (Available for compatibility)

#### **High Quality**
```bash
python scripts/rag_config_manager.py --apply-preset high-quality
```
- **Model**: gpt2-large (774M parameters)
- **Use Case**: Critical documents, reports, analysis
- **Quality**: Excellent | **Speed**: Slower

#### **Fast Response**
```bash
python scripts/rag_config_manager.py --apply-preset fast
```
- **Model**: distilgpt2 (82M parameters)
- **Use Case**: Demos, quick testing, resource-constrained
- **Quality**: Basic | **Speed**: Very Fast

---

## 📝 Prompt Template System with Hot-Reloading

The RAG system supports **hot-reloadable prompt templates** - you can edit templates and see changes immediately without restarting the backend!

### **Available Templates**

| Template | Description | Best For | Source |
|----------|-------------|----------|---------|
| `professional` | Business-focused, professional language | General enterprise use | 🔄 External |
| `conversational` | Casual, friendly tone | Customer support | 🔄 External |
| `technical` | Detailed technical documentation style | Engineering docs | 🔄 External |
| `executive` | Concise executive summary format | C-level reports | 🔄 External |
| `qa` | Simple question-answer format | FAQ systems | 📝 Built-in |
| `fallback` | Minimal prompt for basic responses | Error handling | 📝 Built-in |

**Legend:**
- 🔄 **External**: Loaded from `/config/prompts/` YAML files (hot-reloadable)
- 📝 **Built-in**: Hardcoded fallback templates

### **🔄 Hot-Reloading Features**

#### **Automatic Template Reloading**
- **File Watching**: Checks for changes every 2 seconds when templates are accessed
- **Zero Downtime**: Templates update without affecting running queries
- **Automatic Detection**: No manual commands needed (but available)
- **Graceful Fallback**: Uses built-in templates if external files have errors

#### **Manual Template Management**
```bash
# Reload all templates immediately
python scripts/rag_config_manager.py --reload-templates

# List all available templates
python scripts/rag_config_manager.py --list-templates

# Test a specific template
python scripts/rag_config_manager.py --test-template professional

# View reload status in config overview
python scripts/rag_config_manager.py --show-current
```

#### **API-Based Template Management**
```bash
# List all templates
curl "http://localhost:8000/api/v1/templates/" \
  -H "X-API-Key: YOUR_KEY"

# Get specific template
curl "http://localhost:8000/api/v1/templates/professional" \
  -H "X-API-Key: YOUR_KEY"

# Force reload all templates
curl -X POST "http://localhost:8000/api/v1/templates/reload" \
  -H "X-API-Key: YOUR_KEY"

# Check reload status
curl "http://localhost:8000/api/v1/templates/status/reload" \
  -H "X-API-Key: YOUR_KEY"

# Validate template formatting
curl -X POST "http://localhost:8000/api/v1/templates/validate/professional" \
  -H "X-API-Key: YOUR_KEY"
```

### **📁 Template File Structure**

Templates are stored in YAML format in `/config/prompts/`:

```yaml
# /config/prompts/business.yaml
professional:
  name: "Professional Business Assistant"
  description: "Professional business language for enterprise use"
  template: |
    You are a professional AI assistant providing accurate information based on company documents.

    CONTEXT FROM COMPANY DOCUMENTS:
    {context}

    USER QUESTION: {query}

    INSTRUCTIONS:
    - Provide a clear, well-structured answer based ONLY on the context above
    - Use professional language and complete sentences
    - If information is missing from the context, state this clearly
    - Cite specific sources when making claims

    PROFESSIONAL ANSWER:

executive:
  name: "Executive Summary Style"
  description: "Concise executive summary format"
  template: |
    You are an executive assistant providing concise, business-focused answers.

    BUSINESS CONTEXT:
    {context}

    EXECUTIVE QUESTION: {query}

    DIRECTIVE:
    - Provide a concise, business-focused answer
    - Highlight key metrics, outcomes, and strategic implications
    - Use professional business language
    - Focus on actionable insights

    EXECUTIVE SUMMARY:
```

### **🔧 Creating Custom Templates**

#### **Method 1: Edit YAML Files (Recommended)**
```bash
# 1. Edit template files
nano config/prompts/business.yaml

# 2. Add your custom template
custom_domain:
  name: "Custom Domain Expert"
  description: "Specialized assistant for your domain"
  template: |
    You are a specialized expert in [YOUR DOMAIN].
    
    DOMAIN KNOWLEDGE:
    {context}
    
    EXPERT QUESTION: {query}
    
    EXPERT RESPONSE:

# 3. Templates reload automatically in 2-3 seconds!
# 4. Test immediately
python scripts/rag_config_manager.py --test-template custom_domain
```

#### **Method 2: Create New Template Category**
```bash
# Create new template file
nano config/prompts/custom_category.yaml

# Add templates for your specific use case
support_agent:
  name: "Customer Support Agent"
  description: "Friendly customer support responses"
  template: |
    You are a helpful customer support representative.
    
    KNOWLEDGE BASE:
    {context}
    
    CUSTOMER QUESTION: {query}
    
    HELPFUL RESPONSE:

sales_assistant:
  name: "Sales Assistant"
  description: "Sales-focused responses with product benefits"
  template: |
    You are a knowledgeable sales assistant.
    
    PRODUCT INFORMATION:
    {context}
    
    SALES INQUIRY: {query}
    
    SALES RESPONSE:
```

### **🧪 Testing Template Changes**

#### **Real-Time Template Testing**
```bash
# 1. Create test template
python scripts/test_hot_reload.py --create-test-template

# 2. Run comprehensive hot-reload demo
python scripts/test_hot_reload.py --demo

# 3. Edit config/prompts/test_templates.yaml while demo runs
# 4. Watch automatic reloading in action!

# 5. Test specific templates
python scripts/rag_config_manager.py --test-template test_basic
```

#### **API Testing Workflow**
```bash
# Test template via API without restart
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "query": "What is the company mission?",
    "prompt_template": "professional"
  }'

# Change template in YAML file, then test again
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "query": "What is the company mission?", 
    "prompt_template": "executive"
  }'
```

### **📊 Template Performance Optimization**

#### **Template Loading Statistics**
```bash
# Check template reload status
python scripts/rag_config_manager.py --show-current

# Output includes:
# 🔄 Hot-Reload Status:
#    Enabled: True
#    Check Interval: 2.0s
#    External Templates: 6
#    External Names: professional, executive, technical, conversational
```

#### **Disable Hot-Reload for Production**
```python
# In production, disable hot-reload for performance
rag_prompts = RAGPromptManager(enable_hot_reload=False)

# Or via API
curl -X POST "http://localhost:8000/api/v1/templates/status/reload/disable" \
  -H "X-API-Key: YOUR_KEY"
```

### **🎯 Template Best Practices**

#### **1. Template Design Guidelines**
- **Variable Placeholders**: Always use `{query}` and `{context}`
- **Clear Instructions**: Provide specific guidance for AI behavior
- **Consistent Formatting**: Use similar structure across templates
- **Error Handling**: Include fallback instructions for missing context

#### **2. Hot-Reload Workflow**
```bash
# Recommended development workflow:
# 1. Start with existing template
cp config/prompts/business.yaml config/prompts/my_templates.yaml

# 2. Edit and test iteratively
nano config/prompts/my_templates.yaml
python scripts/rag_config_manager.py --test-template my_custom

# 3. Test with real queries
python demo_rag_queries.py --query "test question"

# 4. Validate before production
curl -X POST "http://localhost:8000/api/v1/templates/validate/my_custom" \
  -H "X-API-Key: YOUR_KEY"
```

#### **3. Template Categories**
- **business.yaml**: Professional, executive, conversational templates
- **technical.yaml**: Technical documentation, API reference, troubleshooting
- **custom_domain.yaml**: Your specific domain templates
- **experimental.yaml**: Test templates for iteration

### **⚡ What Still Requires Restart**

**🔄 Hot-Reloadable (No restart needed):**
- ✅ Prompt template content and structure
- ✅ Template descriptions and names
- ✅ New template files and categories
- ✅ Template validation and formatting

**🔒 Restart Required:**
- ❌ LLM model selection (gpt2-medium → gpt2-large)
- ❌ Generation parameters (temperature, top-p, top-k)
- ❌ Model device allocation (CPU → GPU)
- ❌ Environment variables in `.env` file

**Bottom Line**: You can now iterate on prompt templates as fast as you can edit YAML files!

### **🚀 Quick Template Commands**

```bash
# === Template Management ===
python scripts/rag_config_manager.py --list-templates           # List all templates
python scripts/rag_config_manager.py --reload-templates         # Force reload
python scripts/rag_config_manager.py --test-template NAME       # Test template

# === Hot-Reload Testing ===
python scripts/test_hot_reload.py --demo                        # Full demo
python scripts/test_hot_reload.py --create-test-template        # Create test file

# === API Template Management ===
curl "http://localhost:8000/api/v1/templates/" -H "X-API-Key: KEY"                    # List
curl -X POST "http://localhost:8000/api/v1/templates/reload" -H "X-API-Key: KEY"      # Reload
curl "http://localhost:8000/api/v1/templates/status/reload" -H "X-API-Key: KEY"       # Status
```

---

## 🔧 Configuration Management

### **Using the Config Manager Script**

#### **View Current Settings**
```bash
python scripts/rag_config_manager.py --show-current
```
Shows all current RAG parameters, prompt templates, and model settings.

#### **Apply Presets**
```bash
# List available presets
python scripts/rag_config_manager.py --list-presets

# Apply a specific preset
python scripts/rag_config_manager.py --apply-preset high-quality

# Always restart backend after changes
docker-compose restart backend
```

#### **Test Configurations**
```bash
# Test with default tenant
python scripts/rag_config_manager.py --test-query "What is the company's mission?"

# Test with specific tenant key
python scripts/rag_config_manager.py --test-query "Tell me about financial performance" --tenant-key YOUR_API_KEY
```

#### **Export/Import Configurations**
```bash
# Export current config for backup
python scripts/rag_config_manager.py --export backup_config.json

# Benchmark all presets
python scripts/rag_config_manager.py --benchmark
```

### **Manual Configuration**

#### **Edit .env File Directly**
```bash
# Copy sample configuration
cp config/rag_tuning.env .env.rag_sample

# Add to your main .env file
cat .env.rag_sample >> .env

# Edit specific settings
nano .env
```

#### **Environment Variables**
```bash
# Core quality settings
RAG_LLM_MODEL=gpt2-medium
RAG_TEMPERATURE=0.3
RAG_TOP_P=0.85
RAG_MAX_NEW_TOKENS=200

# Retrieval settings
RAG_MAX_SOURCES=5
RAG_CONFIDENCE_THRESHOLD=0.3

# Response formatting
RAG_MAX_SENTENCES=4
RAG_REMOVE_PROMPT_ARTIFACTS=true
```

---

## 🧪 Testing and Optimization Workflow

### **1. Establish Baseline**
```bash
# Start with production preset
python scripts/rag_config_manager.py --apply-preset production
docker-compose restart backend

# Test with standard queries
python demo_rag_queries.py --workflow --tenant tenant1
```

### **2. Test Different Scenarios**
```bash
# Test various query types
python scripts/rag_config_manager.py --test-query "What is the company's mission?"         # General
python scripts/rag_config_manager.py --test-query "What are the technical requirements?"  # Technical
python scripts/rag_config_manager.py --test-query "What are the financial results?"       # Specific
python scripts/rag_config_manager.py --test-query "How do I use the system?"             # Procedural
```

### **3. Iterate on Quality**
```bash
# If responses are too generic/unfocused
RAG_TEMPERATURE=0.2        # Make more focused
RAG_TOP_K=30              # Limit vocabulary
RAG_REPETITION_PENALTY=1.4 # Reduce repetition

# If responses are too rigid/robotic
RAG_TEMPERATURE=0.4        # Add creativity
RAG_TOP_P=0.9             # Allow more vocabulary

# If responses are too short
RAG_MAX_NEW_TOKENS=250     # Allow longer responses
RAG_MAX_SENTENCES=6        # More sentences

# If responses use irrelevant sources
RAG_CONFIDENCE_THRESHOLD=0.5  # Higher quality threshold
RAG_MAX_SOURCES=3             # Fewer, better sources
```

### **4. Performance vs Quality Tradeoffs**

#### **Optimize for Speed**
```bash
RAG_LLM_MODEL=distilgpt2      # Fastest model
RAG_MAX_NEW_TOKENS=150        # Shorter responses
RAG_MAX_SOURCES=3             # Less retrieval
RAG_ENABLE_QUANTIZATION=true  # Model compression
```

#### **Optimize for Quality**
```bash
RAG_LLM_MODEL=gpt2-large      # Best model
RAG_TEMPERATURE=0.2           # Very focused
RAG_MAX_SOURCES=7             # More context
RAG_MAX_NEW_TOKENS=300        # Detailed responses
```

---

## 📊 Performance Monitoring

### **Response Quality Metrics**
Monitor these aspects of generated responses:

1. **Relevance**: Do responses address the specific question?
2. **Accuracy**: Are facts correct based on source documents?
3. **Completeness**: Are responses comprehensive enough?
4. **Coherence**: Do responses flow logically?
5. **Professional Tone**: Is language appropriate for business use?

### **Technical Performance Metrics**
```bash
# Check response times in API calls
curl -w "@curl-format.txt" -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Monitor in demo script
python demo_rag_queries.py --tenant tenant1 --query "test"
# Look for "Processing time: X.XXXs" in output
```

### **Model Loading Times**
- **distilgpt2**: ~5-10 seconds initial load
- **gpt2-medium**: ~15-30 seconds initial load  
- **gpt2-large**: ~45-90 seconds initial load

---

## 🎯 Use Case Specific Configurations

### **Customer Support**
```bash
# Friendly, helpful responses
RAG_LLM_MODEL=microsoft/DialoGPT-medium
RAG_TEMPERATURE=0.4
RAG_MAX_SOURCES=5
# Use "conversational" prompt template
```

### **Technical Documentation**
```bash
# Precise, detailed responses
RAG_LLM_MODEL=gpt2-medium
RAG_TEMPERATURE=0.2
RAG_MAX_NEW_TOKENS=300
RAG_MAX_SOURCES=7
# Use "technical" prompt template
```

### **Executive Reporting**
```bash
# Concise, business-focused
RAG_LLM_MODEL=gpt2-medium
RAG_TEMPERATURE=0.25
RAG_MAX_SENTENCES=3
RAG_MAX_SOURCES=5
# Use "executive" prompt template
```

### **Research/Analysis**
```bash
# Comprehensive, high-quality
RAG_LLM_MODEL=gpt2-large
RAG_TEMPERATURE=0.3
RAG_MAX_NEW_TOKENS=400
RAG_MAX_SOURCES=8
RAG_CONFIDENCE_THRESHOLD=0.4
# Use "professional" prompt template
```

---

## 🚨 Troubleshooting

### **Common Issues and Solutions**

#### **Responses are too generic/unfocused**
```bash
# Lower temperature for more focused responses
RAG_TEMPERATURE=0.2

# Increase confidence threshold for better sources
RAG_CONFIDENCE_THRESHOLD=0.5

# Use fewer, higher quality sources
RAG_MAX_SOURCES=3
```

#### **Responses are too repetitive**
```bash
# Increase repetition penalty
RAG_REPETITION_PENALTY=1.4

# Add vocabulary diversity
RAG_TOP_K=50
RAG_TOP_P=0.9
```

#### **Responses are too short**
```bash
# Allow longer generation
RAG_MAX_NEW_TOKENS=250

# Allow more sentences
RAG_MAX_SENTENCES=6

# Provide more context
RAG_MAX_SOURCES=7
RAG_MAX_CONTEXT_LENGTH=3000
```

#### **Responses contain prompt artifacts**
```bash
# Ensure cleaning is enabled
RAG_REMOVE_PROMPT_ARTIFACTS=true

# Try different prompt template
# Use "qa" or "conversational" template
```

#### **Poor source relevance**
```bash
# Increase confidence threshold
RAG_CONFIDENCE_THRESHOLD=0.6

# Improve embedding model (in settings.py)
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2

# Reduce context noise
RAG_MAX_SOURCES=3
```

#### **Slow response times**
```bash
# Use faster model
RAG_LLM_MODEL=distilgpt2

# Reduce response length
RAG_MAX_NEW_TOKENS=150

# Enable quantization
RAG_ENABLE_QUANTIZATION=true

# Reduce retrieval overhead
RAG_MAX_SOURCES=3
```

### **Backend Issues**

#### **Model Loading Errors**
```bash
# Check model cache
ls -la cache/transformers/

# Clear cache if corrupted
rm -rf cache/transformers/

# Check available disk space
df -h

# Restart with logs
docker-compose restart backend
docker-compose logs -f backend
```

#### **Configuration Not Applied**
```bash
# Verify .env file changes
cat .env | grep RAG_

# Restart backend (required for config changes)
docker-compose restart backend

# Check if environment loaded
python -c "from src.backend.config.settings import get_settings; print(get_settings().rag_llm_model)"
```

---

## 📚 Advanced Configuration

### **Custom Embedding Models**
Edit `src/backend/config/settings.py`:
```python
# Higher quality embeddings (slower)
embedding_model: str = Field(
    default="sentence-transformers/all-mpnet-base-v2", 
    env="EMBEDDING_MODEL"
)

# Faster embeddings  
embedding_model: str = Field(
    default="sentence-transformers/all-MiniLM-L6-v2", 
    env="EMBEDDING_MODEL"
)
```

### **Custom LLM Models**
Add support for other models in `src/backend/services/rag_service.py`:
```python
# Example: Add support for Llama models
if "llama" in model_name.lower():
    # Special initialization for Llama models
    pass
```

### **A/B Testing Configuration**
Create multiple configuration files for testing:
```bash
# Create test configurations
cp .env .env.config_a
cp .env .env.config_b

# Modify settings in each file
# Switch between configurations
cp .env.config_a .env && docker-compose restart backend
```

### **Production Optimizations**
```bash
# Production settings for scale
RAG_LLM_MODEL=gpt2-medium           # Balanced performance
RAG_ENABLE_QUANTIZATION=true       # Memory efficiency
RAG_MAX_NEW_TOKENS=200              # Consistent response length
RAG_TEMPERATURE=0.3                 # Deterministic but natural
RAG_MAX_SOURCES=5                   # Optimal context/speed balance
RAG_CONFIDENCE_THRESHOLD=0.4        # High quality sources only

# Cache settings
RAG_CACHE_DIR=/app/cache/models     # Persistent model cache
```

---

## 🎓 Best Practices

### **1. Start with Presets**
- Always begin with a tested preset
- Use `production` for general purposes
- Only customize after understanding baseline performance

### **2. Iterative Tuning**
- Change one parameter at a time
- Test with consistent queries
- Document what works for your use case

### **3. Quality vs Performance**
- Higher quality models are slower
- Find the minimum quality threshold for your needs
- Consider different configs for different query types

### **4. Context Quality**
- Good retrieval is more important than advanced LLM settings
- Tune confidence thresholds before generation parameters
- Monitor source relevance regularly

### **5. Prompt Engineering**
- Choose appropriate prompt templates
- Test templates with your specific document types
- Create custom templates for specialized domains

### **6. Production Deployment**
- Use quantization for memory efficiency
- Set reasonable token limits
- Monitor response times and quality metrics
- Have fallback configurations ready

---

## 📝 Configuration Reference

### **Complete Environment Variables List**

```bash
# === LLM Model Configuration ===
RAG_LLM_MODEL=gpt2-medium                    # Model selection
RAG_MAX_LENGTH=512                           # Total sequence length
RAG_MAX_NEW_TOKENS=200                       # New tokens to generate
RAG_TEMPERATURE=0.3                          # Generation randomness (0.1-1.0)
RAG_TOP_P=0.85                              # Nucleus sampling (0.1-1.0)
RAG_TOP_K=40                                # Vocabulary limit (10-100)
RAG_REPETITION_PENALTY=1.3                  # Repetition control (1.0-2.0)
RAG_EARLY_STOPPING=true                     # Stop at natural completion
RAG_DO_SAMPLE=true                          # Use sampling vs greedy
RAG_ENABLE_QUANTIZATION=true                # Model compression
RAG_CACHE_DIR=./cache/transformers          # Model cache location

# === Retrieval Configuration ===
RAG_MAX_SOURCES=5                           # Source documents (3-10)
RAG_CONFIDENCE_THRESHOLD=0.3                # Minimum similarity (0.1-0.9)
RAG_MAX_CONTEXT_LENGTH=2000                 # Context character limit
RAG_SOURCE_PREVIEW_LENGTH=200               # Preview length

# === Response Quality ===
RAG_MAX_SENTENCES=4                         # Sentence limit
RAG_MIN_SENTENCE_LENGTH=10                  # Minimum sentence chars
RAG_REMOVE_PROMPT_ARTIFACTS=true            # Clean responses
RAG_ENSURE_PUNCTUATION=true                 # Add punctuation

# === Embedding Model ===
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu                        # cpu or cuda
EMBEDDING_BATCH_SIZE=32                     # Batch processing

# === Document Processing ===
CHUNK_SIZE=512                              # Document chunk size
CHUNK_OVERLAP=50                            # Chunk overlap chars
```

### **Preset Configurations**

#### **Balanced (Recommended)**
```bash
RAG_LLM_MODEL=gpt2-medium
RAG_TEMPERATURE=0.3
RAG_MAX_NEW_TOKENS=200
RAG_MAX_SOURCES=5
RAG_TOP_P=0.85
RAG_TOP_K=40
RAG_REPETITION_PENALTY=1.3
```

#### **High Quality**
```bash
RAG_LLM_MODEL=gpt2-large
RAG_TEMPERATURE=0.2
RAG_MAX_NEW_TOKENS=250
RAG_MAX_SOURCES=7
RAG_TOP_P=0.8
RAG_TOP_K=30
RAG_REPETITION_PENALTY=1.4
```

#### **Fast Response**
```bash
RAG_LLM_MODEL=distilgpt2
RAG_TEMPERATURE=0.4
RAG_MAX_NEW_TOKENS=150
RAG_MAX_SOURCES=3
RAG_TOP_P=0.9
RAG_TOP_K=50
```

---

## 🔗 Quick Reference Commands

```bash
# === Configuration Management ===
python scripts/rag_config_manager.py --show-current           # View settings
python scripts/rag_config_manager.py --list-presets           # List presets
python scripts/rag_config_manager.py --apply-preset production  # Apply preset
python scripts/rag_config_manager.py --export config.json     # Export config

# === Testing ===
python scripts/rag_config_manager.py --test-query "question"         # Test query
python demo_rag_queries.py --workflow --tenant tenant1               # Full demo
python demo_rag_queries.py --query "question" --tenant tenant1       # Single query

# === Backend Management ===
docker-compose restart backend                               # Apply config changes
docker-compose logs -f backend                              # Monitor logs
docker-compose ps                                           # Check status

# === Debugging ===
curl http://localhost:8000/api/v1/health/                   # Health check
cat .env | grep RAG_                                        # View RAG settings
ls -la cache/transformers/                                  # Check model cache
```

---

This comprehensive guide covers everything needed to tune and optimize your RAG system. Start with the presets, test with your specific use cases, and iterate based on quality and performance requirements.