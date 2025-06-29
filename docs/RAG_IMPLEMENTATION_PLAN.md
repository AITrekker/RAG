# RAG Implementation Plan

## Executive Summary

Build a modular RAG (Retrieval-Augmented Generation) system on top of the multi-format embedding infrastructure. Focus on modularity for both production integration and component-level testing using test tenants.

## Current State Analysis

### What We Have
- ✅ Multi-format document processing (TXT, PDF, HTML)
- ✅ Hybrid PostgreSQL + Qdrant storage
- ✅ Embedding generation with sentence-transformers
- ✅ Test tenant isolation
- ✅ Delta sync pipeline

### What We Need
- ❌ Query processing and validation
- ❌ Vector similarity search
- ❌ Context retrieval and ranking
- ❌ LLM integration for answer generation
- ❌ Response formatting and citations
- ❌ Quality testing framework

## Architecture Design

### Modular RAG Components

```
src/backend/services/rag/
├── __init__.py
├── base.py                    # Abstract interfaces
├── query_processor.py         # Query analysis and validation
├── retriever.py              # Vector search and context retrieval
├── context_ranker.py         # Relevance scoring and ranking
├── answer_generator.py       # LLM integration
├── response_formatter.py     # Citation and formatting
└── rag_pipeline.py           # Orchestration
```

### Core Interfaces

```python
# base.py
@dataclass
class Query:
    text: str
    tenant_id: UUID
    user_id: Optional[UUID]
    filters: Dict[str, Any]
    max_results: int = 10
    min_score: float = 0.7

@dataclass 
class RetrievedChunk:
    chunk_id: UUID
    content: str
    file_id: UUID
    filename: str
    score: float
    metadata: Dict[str, Any]

@dataclass
class RAGContext:
    chunks: List[RetrievedChunk]
    total_chunks: int
    search_query: str
    filters_applied: Dict[str, Any]

@dataclass
class RAGResponse:
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    context_used: List[str]
    processing_time: float
    metadata: Dict[str, Any]
```

### Component Breakdown

#### 1. Query Processor
```python
class QueryProcessor:
    """Analyzes and preprocesses user queries."""
    
    def process_query(self, raw_query: str, tenant_id: UUID) -> Query:
        """Clean, validate, and enhance query."""
        pass
    
    def extract_filters(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """Extract file type, date, or other filters from query."""
        pass
    
    def expand_query(self, query: str) -> List[str]:
        """Generate query variations for better retrieval."""
        pass
```

#### 2. Vector Retriever
```python
class VectorRetriever:
    """Handles vector similarity search in Qdrant."""
    
    def search(self, query: Query) -> List[RetrievedChunk]:
        """Perform vector search with filters."""
        pass
    
    def hybrid_search(self, query: Query) -> List[RetrievedChunk]:
        """Combine vector + keyword search."""
        pass
    
    def search_with_rerank(self, query: Query) -> List[RetrievedChunk]:
        """Search with secondary ranking."""
        pass
```

#### 3. Context Ranker
```python
class ContextRanker:
    """Ranks and filters retrieved chunks."""
    
    def rank_by_relevance(self, chunks: List[RetrievedChunk], query: str) -> List[RetrievedChunk]:
        """Rank chunks by relevance to query."""
        pass
    
    def filter_duplicates(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Remove near-duplicate content."""
        pass
    
    def apply_diversity(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Ensure source diversity."""
        pass
```

#### 4. Answer Generator
```python
class AnswerGenerator:
    """Generates answers using LLM."""
    
    def generate_answer(self, context: RAGContext, query: str) -> str:
        """Generate answer from context."""
        pass
    
    def generate_with_citations(self, context: RAGContext, query: str) -> Tuple[str, List[Dict]]:
        """Generate answer with source citations."""
        pass
    
    def stream_answer(self, context: RAGContext, query: str) -> Iterator[str]:
        """Stream answer generation."""
        pass
```

#### 5. RAG Pipeline
```python
class RAGPipeline:
    """Orchestrates the complete RAG workflow."""
    
    def __init__(self, 
                 query_processor: QueryProcessor,
                 retriever: VectorRetriever, 
                 ranker: ContextRanker,
                 generator: AnswerGenerator,
                 formatter: ResponseFormatter):
        pass
    
    def process_query(self, raw_query: str, tenant_id: UUID) -> RAGResponse:
        """Complete RAG pipeline."""
        pass
    
    def process_query_async(self, raw_query: str, tenant_id: UUID) -> AsyncIterator[str]:
        """Streaming RAG pipeline."""
        pass
```

## Implementation Plan

### Phase 1: Core Retrieval (Week 1)
- [ ] Implement base interfaces and data classes
- [ ] Build QueryProcessor with basic cleaning/validation
- [ ] Create VectorRetriever with Qdrant integration
- [ ] Add basic context ranking
- [ ] Test with existing embedded documents

### Phase 2: Answer Generation (Week 2)  
- [ ] Integrate LLM for answer generation (start with local models)
- [ ] Implement response formatting with citations
- [ ] Build RAGPipeline orchestration
- [ ] Add streaming support for real-time responses

### Phase 3: Quality & Testing (Week 3)
- [ ] Build comprehensive test suite
- [ ] Implement quality metrics (relevance, accuracy)
- [ ] Add performance benchmarking
- [ ] Create test data sets for validation

### Phase 4: Advanced Features (Week 4)
- [ ] Hybrid search (vector + keyword)
- [ ] Query expansion and reformulation
- [ ] Context window optimization
- [ ] Multi-turn conversation support

## Testing Strategy

### Test Data Structure
```
tests/rag_tests/
├── test_data/
│   ├── queries/
│   │   ├── simple_queries.json
│   │   ├── complex_queries.json
│   │   └── edge_cases.json
│   ├── expected_responses/
│   │   ├── qa_pairs.json
│   │   └── benchmarks.json
│   └── documents/
│       ├── test_company_docs/
│       ├── technical_docs/
│       └── mixed_content/
├── unit_tests/
│   ├── test_query_processor.py
│   ├── test_retriever.py
│   ├── test_ranker.py
│   ├── test_generator.py
│   └── test_pipeline.py
├── integration_tests/
│   ├── test_end_to_end.py
│   ├── test_performance.py
│   └── test_quality_metrics.py
└── benchmark_tests/
    ├── test_retrieval_accuracy.py
    ├── test_answer_quality.py
    └── test_citation_accuracy.py
```

### Test Tenant Strategy
```python
# Use dedicated test tenant for RAG testing
RAG_TEST_TENANT_ID = "rag-test-00000000-0000-0000-0000-000000000000"
RAG_TEST_COLLECTION = f"tenant_{RAG_TEST_TENANT_ID}_documents"

# Test data categories
TEST_SCENARIOS = {
    "factual_qa": "Direct factual questions",
    "conceptual": "Conceptual understanding",
    "multi_document": "Cross-document reasoning", 
    "ambiguous": "Ambiguous or unclear queries",
    "edge_cases": "Empty results, long queries, special chars"
}
```

### Quality Metrics Framework
```python
class RAGQualityMetrics:
    """Framework for evaluating RAG quality."""
    
    def evaluate_retrieval_accuracy(self, queries: List[str], expected_docs: List[List[str]]) -> float:
        """Measure retrieval precision/recall."""
        pass
    
    def evaluate_answer_relevance(self, qa_pairs: List[Tuple[str, str, str]]) -> float:
        """Measure answer relevance to question."""
        pass
    
    def evaluate_citation_accuracy(self, responses: List[RAGResponse]) -> float:
        """Measure citation accuracy."""
        pass
    
    def evaluate_response_time(self, queries: List[str]) -> Dict[str, float]:
        """Measure performance metrics."""
        pass
```

### Automated Test Suite
```python
# scripts/test_rag_quality.py
class RAGQualityTestSuite:
    """Comprehensive RAG quality testing."""
    
    async def run_daily_tests(self) -> Dict[str, Any]:
        """Run daily quality checks."""
        return {
            "retrieval_accuracy": await self.test_retrieval_accuracy(),
            "answer_quality": await self.test_answer_quality(),
            "citation_accuracy": await self.test_citation_accuracy(),
            "performance_benchmarks": await self.test_performance(),
            "edge_case_handling": await self.test_edge_cases()
        }
    
    async def test_retrieval_accuracy(self) -> Dict[str, float]:
        """Test retrieval system accuracy."""
        # Load test queries with known relevant documents
        # Measure precision@k, recall@k, MRR
        pass
    
    async def test_answer_quality(self) -> Dict[str, float]:
        """Test answer generation quality.""" 
        # Load Q&A pairs
        # Measure semantic similarity, factual accuracy
        pass
```

## LLM Integration Options

### Option 1: Local Models (Recommended for start)
```python
# Use Hugging Face transformers for local deployment
SUPPORTED_MODELS = {
    "microsoft/DialoGPT-medium": "Conversational",
    "google/flan-t5-large": "Instruction following", 
    "microsoft/GRIN-MoE": "Efficient reasoning"
}
```

### Option 2: API-based Models
```python
# For production deployment
API_MODELS = {
    "openai": "gpt-3.5-turbo",
    "anthropic": "claude-3-haiku",
    "google": "gemini-pro"
}
```

### Option 3: Hybrid Approach
```python
# Local for testing, API for production
class LLMProvider:
    def __init__(self, mode: str = "local"):
        if mode == "local":
            self.generator = LocalLLMGenerator()
        else:
            self.generator = APILLMGenerator()
```

## RAG Pipeline Example

### Complete Flow
```python
async def example_rag_query():
    # 1. Query Processing
    raw_query = "What is our work from home policy?"
    query = query_processor.process_query(raw_query, tenant_id)
    
    # 2. Vector Retrieval 
    chunks = await retriever.search(query)
    
    # 3. Context Ranking
    ranked_chunks = ranker.rank_by_relevance(chunks, query.text)
    context = RAGContext(chunks=ranked_chunks[:5], ...)
    
    # 4. Answer Generation
    answer, sources = generator.generate_with_citations(context, query.text)
    
    # 5. Response Formatting
    response = formatter.format_response(answer, sources, context)
    
    return response
```

### Expected Output
```json
{
    "answer": "According to the Employee Handbook, our work from home policy allows employees to work remotely up to 3 days per week with manager approval. This flexible arrangement supports work-life balance while maintaining team collaboration.",
    "sources": [
        {
            "filename": "test_page.html", 
            "chunk_index": 0,
            "relevance_score": 0.95,
            "excerpt": "work from home up to 3 days per week with manager approval"
        }
    ],
    "confidence": 0.92,
    "processing_time": 1.2
}
```

## Success Metrics

### Functionality Metrics
- **Retrieval Accuracy**: >85% relevant chunks in top-5 results
- **Answer Quality**: >80% factually correct responses
- **Citation Accuracy**: >95% accurate source attribution

### Performance Metrics  
- **Query Response Time**: <3 seconds end-to-end
- **Retrieval Time**: <500ms for vector search
- **Generation Time**: <2 seconds for answer

### Quality Metrics
- **Relevance Score**: >0.8 average relevance
- **User Satisfaction**: Measured via feedback system
- **Coverage**: >90% questions get meaningful answers

## Risk Mitigation

### Technical Risks
1. **LLM Hallucination**: Implement citation verification
2. **Poor Retrieval**: Build comprehensive test suite  
3. **Performance Issues**: Profile and optimize each component
4. **Context Window Limits**: Implement smart context truncation

### Operational Risks
1. **Test Data Quality**: Curate high-quality test datasets
2. **Model Dependency**: Support multiple LLM backends
3. **Tenant Isolation**: Ensure proper access controls
4. **Scalability**: Design for multi-tenant scaling

## Next Steps for Approval

### Key Decisions Needed:

1. **LLM Strategy**: Start with local models or API-based?
2. **Testing Depth**: How comprehensive should the quality framework be?
3. **Performance Targets**: Are the proposed metrics acceptable?
4. **Implementation Timeline**: 4-week phased approach or faster iteration?
5. **Integration Points**: Should RAG service be standalone or integrated into existing rag_service.py?

### Implementation Priority:
1. **High**: Core retrieval and basic answer generation
2. **Medium**: Quality testing framework
3. **Low**: Advanced features (streaming, multi-turn)

This plan provides a complete, modular RAG system that builds on our embedding infrastructure while maintaining testability and production readiness.