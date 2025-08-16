# RAG Architecture Implementation Notes
Based on "Building the Entire RAG Ecosystem" by Fareed Khan

## Overview
Complete RAG pipeline architecture for n8n + LangChain + React chat application with phased implementation approach.

## Core RAG Pipeline Components

### 1. INDEXING PHASE (Data Preparation)

#### Document Ingestion
- **Staging Area**: All documents reviewed before indexing (SAFETY FIRST)
- **Format Support**: PDF, TXT, MD, HTML, DOCX
- **Metadata Extraction**: Author, date, source, document type, tags

#### Chunking Strategies
**Phase 1: RecursiveCharacterTextSplitter**
```python
# Initial implementation
chunk_size = 1000
chunk_overlap = 200
separators = ["\n\n", "\n", ".", " ", ""]
```

**Phase 2: Semantic Chunking**
- Sentence-based splitting with semantic coherence
- Topic modeling for natural boundaries
- Preserve context with sliding windows

**Phase 3: Advanced Strategies**
- **Multi-Representation Indexing**: Summary + full text
- **RAPTOR**: Hierarchical summarization tree
- **ColBERT**: Token-level dense retrieval

#### Embedding Generation
- **Model**: OpenAI text-embedding-3-small (start)
- **Batch Processing**: 100 docs at a time
- **Caching**: Redis for temporary embeddings
- **Storage**: SQLite for permanent vectors

#### Vector Store Selection
**Phase 1: Chroma (Local)**
- Simple setup, good for prototyping
- Supports metadata filtering
- Built-in persistence

**Phase 2: Weaviate/Qdrant**
- Production-ready performance
- Advanced filtering capabilities
- Hybrid search support

### 2. RETRIEVAL PHASE (Query Processing)

#### Query Transformation Techniques

**Multi-Query Generation**
```python
# Generate 3-5 alternative queries
perspectives = [
    "technical explanation",
    "practical example",
    "conceptual overview"
]
```

**RAG-Fusion (Reciprocal Rank Fusion)**
- Run multiple queries in parallel
- Combine results using RRF scoring
- Weight by relevance and diversity

**Query Decomposition**
- Break complex queries into sub-questions
- Retrieve for each sub-question
- Synthesize comprehensive answer

**Step-Back Prompting**
- Abstract specific question to general concept
- Retrieve both specific and general context
- Provide broader understanding

**HyDE (Hypothetical Document Embeddings)**
- Generate hypothetical answer first
- Embed hypothetical answer
- Search for similar real documents

#### Routing Strategies

**Logical Routing**
```python
routing_rules = {
    "technical": "code_knowledge_base",
    "general": "documentation_base",
    "conversation": "chat_history"
}
```

**Semantic Routing**
- Embed query and route descriptions
- Cosine similarity for best match
- Threshold for multi-route activation

#### Query Construction
- **Text-to-SQL**: Natural language to database queries
- **Text-to-Cypher**: Graph database queries
- **Metadata Filtering**: Pre-filter by date, type, source

### 3. GENERATION PHASE (Response Creation)

#### Context Window Management
- **Max Context**: 4096 tokens (configurable)
- **Prioritization**: Most relevant chunks first
- **Truncation Strategy**: Keep beginning and end

#### Re-ranking Pipeline
1. **Initial Retrieval**: Top 20 candidates
2. **Cross-Encoder Reranking**: Reduce to top 5
3. **MMR (Maximum Marginal Relevance)**: Balance relevance + diversity
4. **Lost in the Middle Mitigation**: Place key info at start/end

#### Self-Correction Mechanisms

**CRAG (Corrective RAG)**
```python
confidence_threshold = 0.7
if retrieval_confidence < threshold:
    # Trigger web search or knowledge base expansion
    additional_context = web_search(query)
```

**Self-RAG**
- Generate multiple candidate answers
- Self-evaluate each answer
- Select best based on internal critique

#### Response Generation
- **Prompt Template**: Structured with context injection
- **Citation Tracking**: Link responses to source chunks
- **Streaming Support**: Token-by-token generation

## Phase 1 Integration Requirements

### Core Components Needed
1. **n8n Workflows**
   - Document upload trigger
   - Chunking workflow
   - Embedding generation flow
   - Query processing pipeline
   - Response generation flow

2. **LangChain Integration**
   ```python
   from langchain.text_splitter import RecursiveCharacterTextSplitter
   from langchain.embeddings import OpenAIEmbeddings
   from langchain.vectorstores import Chroma
   from langchain.chains import RetrievalQA
   ```

3. **React Frontend**
   - Chat interface component
   - Document upload UI
   - Staging area review panel
   - Source citation display
   - Conversation history view

4. **Redis Cache Structure**
   ```javascript
   // Conversation memory
   conversation:{userId}:{sessionId} -> messages[]
   
   // Embedding cache
   embedding:{docHash} -> vector[]
   
   // Query cache
   query:{queryHash} -> results[]
   ```

5. **SQLite Schema**
   ```sql
   CREATE TABLE documents (
       id INTEGER PRIMARY KEY,
       content TEXT,
       metadata JSON,
       embedding BLOB,
       created_at TIMESTAMP
   );
   
   CREATE TABLE conversations (
       id INTEGER PRIMARY KEY,
       user_id TEXT,
       messages JSON,
       created_at TIMESTAMP
   );
   ```

### Safety & Validation

#### Prompt Injection Detection
```python
injection_patterns = [
    "ignore previous instructions",
    "system prompt",
    "[[INST]]",
    "###"
]
```

#### Content Validation
- Profanity filtering
- PII detection and masking
- Malware/script detection in uploads
- Rate limiting per user/session

### Evaluation Metrics

#### Retrieval Metrics
- **Context Precision**: Are retrieved docs relevant?
- **Context Recall**: Did we get all relevant docs?
- **Context Relevancy**: How much of context is useful?

#### Generation Metrics
- **Faithfulness**: Is answer grounded in context?
- **Answer Relevancy**: Does it answer the question?
- **Answer Correctness**: Is it factually accurate?

#### End-to-End Metrics
- **Latency**: Time from query to response
- **Token Efficiency**: Tokens used vs quality
- **User Satisfaction**: Feedback collection

## Implementation Roadmap

### Week 1: Foundation
- [ ] Set up n8n workflows for document ingestion
- [ ] Implement basic chunking with RecursiveCharacterTextSplitter
- [ ] Configure Chroma vector store
- [ ] Create staging area UI in React

### Week 2: Retrieval Pipeline
- [ ] Implement Multi-Query generation
- [ ] Add RAG-Fusion with RRF scoring
- [ ] Set up semantic routing
- [ ] Configure Redis caching layer

### Week 3: Generation & Safety
- [ ] Implement re-ranking pipeline
- [ ] Add CRAG confidence checking
- [ ] Set up prompt injection detection
- [ ] Create citation tracking system

### Week 4: Optimization & Evaluation
- [ ] Implement evaluation metrics dashboard
- [ ] Add query decomposition for complex queries
- [ ] Optimize chunk sizes based on metrics
- [ ] Performance tuning and caching

## Advanced Features (Phase 2)

### Graph-Enhanced RAG
- Knowledge graph construction
- Entity relationship extraction
- Graph traversal for context

### Multi-Modal RAG
- Image understanding and retrieval
- Table/chart extraction
- Video transcript processing

### Agentic RAG
- Tool use for dynamic retrieval
- Web search integration
- API calls for real-time data

### Long-Context Strategies
- Hierarchical indexing (RAPTOR)
- Sliding window attention
- Recursive summarization

## Configuration Templates

### n8n Workflow Config
```json
{
  "name": "RAG Document Processor",
  "nodes": [
    {
      "type": "webhook",
      "name": "Document Upload",
      "webhookPath": "rag-upload"
    },
    {
      "type": "function",
      "name": "Chunk Document",
      "code": "// Chunking logic here"
    },
    {
      "type": "http",
      "name": "Generate Embeddings",
      "url": "http://localhost:3000/api/embed"
    }
  ]
}
```

### LangChain Configuration
```python
# config.py
RAG_CONFIG = {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "embedding_model": "text-embedding-3-small",
    "llm_model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000,
    "retrieval_k": 5,
    "rerank_k": 3
}
```

### React Component Structure
```javascript
// ChatInterface.jsx
components/
  ├── Chat/
  │   ├── MessageList.jsx
  │   ├── InputBox.jsx
  │   └── SourceCitations.jsx
  ├── Documents/
  │   ├── UploadZone.jsx
  │   ├── StagingArea.jsx
  │   └── DocumentList.jsx
  └── Metrics/
      ├── EvaluationDashboard.jsx
      └── PerformanceMonitor.jsx
```

## Testing Strategy

### Unit Tests
- Chunking accuracy
- Embedding generation
- Query transformation
- Reranking logic

### Integration Tests
- End-to-end query flow
- Document ingestion pipeline
- Cache hit/miss scenarios
- Error handling

### Performance Tests
- Latency under load
- Concurrent user handling
- Large document processing
- Cache effectiveness

## Monitoring & Observability

### Key Metrics to Track
- Query latency (p50, p95, p99)
- Retrieval accuracy scores
- Cache hit rates
- Token usage per query
- Error rates by component

### Logging Strategy
```python
logger.info("Query processed", {
    "query_id": query_id,
    "latency_ms": latency,
    "chunks_retrieved": len(chunks),
    "confidence_score": confidence,
    "cache_hit": cache_hit
})
```

## Document Safety Checkpoint System

### Security Tag Categories
```javascript
const SECURITY_TAGS = {
  PROMPT_INJECTION: {
    severity: 'HIGH',
    description: 'Potential prompt injection attempt detected',
    patterns: ['ignore previous', 'forget instructions', 'system prompt'],
    autoDetect: true,
    confidence: 0.85
  },
  PII_DETECTED: {
    severity: 'MEDIUM', 
    description: 'Personal identifiable information found',
    patterns: ['SSN patterns', 'email addresses', 'phone numbers'],
    autoDetect: true,
    confidence: 0.92
  },
  CONTENT_SECURITY: {
    severity: 'LOW',
    description: 'Content requires review for appropriateness',
    patterns: ['suspicious links', 'malformed data', 'encoding issues'],
    autoDetect: false,
    confidence: 0.60
  },
  MALICIOUS_CODE: {
    severity: 'CRITICAL',
    description: 'Potential malicious code or scripts detected',
    patterns: ['script tags', 'eval statements', 'system commands'],
    autoDetect: true,
    confidence: 0.95
  },
  DOCUMENT_STRUCTURE: {
    severity: 'LOW',
    description: 'Document structure anomalies detected',
    patterns: ['unusual formatting', 'hidden characters', 'encoding mismatches'],
    autoDetect: true,
    confidence: 0.75
  },
  ADVERSARIAL_CONTENT: {
    severity: 'HIGH',
    description: 'Content designed to manipulate model behavior',
    patterns: ['repetitive tokens', 'gradient attacks', 'backdoor triggers'],
    autoDetect: false,
    confidence: 0.70
  }
}
```

### Redis Queue Structure
```javascript
// Document Processing Queue Schema
const REDIS_QUEUES = {
  // Incoming documents awaiting safety review
  'docs:staging': {
    structure: 'list',
    data: {
      docId: 'uuid',
      content: 'string',
      source: 'url|file|api',
      timestamp: 'iso_datetime',
      priority: 'low|medium|high|critical',
      autoFlags: ['array_of_detected_tags'],
      confidence_scores: 'object'
    }
  },
  
  // Documents approved for processing
  'docs:approved': {
    structure: 'list', 
    data: {
      docId: 'uuid',
      reviewedBy: 'user_id',
      approvedTags: ['array'],
      notes: 'string',
      timestamp: 'iso_datetime'
    }
  },
  
  // Documents rejected or flagged
  'docs:rejected': {
    structure: 'list',
    data: {
      docId: 'uuid',
      rejectionReason: 'string',
      flaggedTags: ['array'],
      reviewNotes: 'string',
      timestamp: 'iso_datetime'
    }
  },
  
  // Pattern learning training data
  'patterns:training': {
    structure: 'hash',
    data: {
      pattern_id: {
        content_snippet: 'string',
        human_decision: 'approve|reject',
        confidence_level: 'float',
        tag_applied: 'string',
        context: 'object'
      }
    }
  },
  
  // Real-time review notifications
  'notifications:review': {
    structure: 'pubsub',
    channels: ['new_document', 'priority_alert', 'batch_complete']
  }
}
```

### React Review Interface
```jsx
const DocumentReviewPanel = ({ document, onApprove, onReject }) => {
  const [selectedTags, setSelectedTags] = useState(document.autoFlags || []);
  const [notes, setNotes] = useState('');
  const [reviewDecision, setReviewDecision] = useState(null);
  
  const handleTagToggle = (tagKey) => {
    setSelectedTags(prev => 
      prev.includes(tagKey) 
        ? prev.filter(t => t !== tagKey)
        : [...prev, tagKey]
    );
  };
  
  const submitReview = (decision) => {
    const reviewData = {
      docId: document.docId,
      decision,
      tags: selectedTags,
      notes,
      confidence: calculateConfidence(selectedTags),
      timestamp: new Date().toISOString()
    };
    
    if (decision === 'approve') {
      onApprove(reviewData);
    } else {
      onReject(reviewData);
    }
  };
  
  return (
    <div className="review-panel">
      <DocumentPreview 
        content={document.content} 
        highlightSuspicious={true}
        autoFlags={document.autoFlags}
      />
      
      <SecurityTagGrid>
        {Object.entries(SECURITY_TAGS).map(([key, tag]) => (
          <TagButton
            key={key}
            tag={tag}
            selected={selectedTags.includes(key)}
            autoDetected={document.autoFlags?.includes(key)}
            confidence={document.confidence_scores?.[key]}
            onClick={() => handleTagToggle(key)}
          />
        ))}
      </SecurityTagGrid>
      
      <PatternLearningIndicator 
        document={document}
        selectedTags={selectedTags}
      />
      
      <NotesSection 
        value={notes} 
        onChange={setNotes}
        placeholder="Document review notes, concerns, or observations..."
      />
      
      <ActionButtons>
        <ApproveButton 
          onClick={() => submitReview('approve')}
          disabled={selectedTags.length === 0}
        />
        <RejectButton 
          onClick={() => submitReview('reject')}
          danger={selectedTags.some(t => SECURITY_TAGS[t].severity === 'CRITICAL')}
        />
        <FlagForLaterButton 
          onClick={() => submitReview('flag')}
        />
      </ActionButtons>
    </div>
  );
};

const TagButton = ({ tag, selected, autoDetected, confidence, onClick }) => (
  <button 
    className={`tag-btn ${selected ? 'selected' : ''} ${autoDetected ? 'auto-detected' : ''}`}
    onClick={onClick}
    data-severity={tag.severity}
  >
    {tag.description}
    {autoDetected && <ConfidenceBadge value={confidence} />}
    {tag.severity === 'CRITICAL' && <WarningIcon />}
  </button>
);
```

### N8N Workflow Integration
```json
{
  "name": "Document Safety Pipeline",
  "nodes": [
    {
      "type": "webhook",
      "name": "Document Upload",
      "webhookPath": "document-upload",
      "httpMethod": "POST"
    },
    {
      "type": "function",
      "name": "Security Scan",
      "code": `
        // Auto-detect security patterns
        const content = items[0].json.content;
        const autoFlags = [];
        const confidenceScores = {};
        
        for (const [tagKey, tag] of Object.entries(SECURITY_TAGS)) {
          if (tag.autoDetect) {
            const detected = scanForPatterns(content, tag.patterns);
            if (detected.found) {
              autoFlags.push(tagKey);
              confidenceScores[tagKey] = detected.confidence;
            }
          }
        }
        
        return {
          ...items[0].json,
          autoFlags,
          confidence_scores: confidenceScores,
          requiresReview: autoFlags.length > 0 || content.length > 10000
        };
      `
    },
    {
      "type": "switch",
      "name": "Route Based on Risk",
      "rules": [
        {
          "condition": "{{ $json.requiresReview }}",
          "output": "staging_queue"
        },
        {
          "condition": "{{ !$json.requiresReview }}",
          "output": "auto_approve"
        }
      ]
    },
    {
      "type": "redis",
      "name": "Queue for Review",
      "operation": "lpush",
      "key": "docs:staging",
      "value": "{{ JSON.stringify($json) }}"
    },
    {
      "type": "function",
      "name": "Auto Approve Low Risk",
      "code": `
        // Automatically approve low-risk documents
        return {
          ...items[0].json,
          reviewedBy: 'auto_system',
          approvedTags: [],
          timestamp: new Date().toISOString()
        };
      `
    },
    {
      "type": "redis",
      "name": "Queue Approved",
      "operation": "lpush", 
      "key": "docs:approved",
      "value": "{{ JSON.stringify($json) }}"
    }
  ]
}
```

### Pattern Learning & Automation
```javascript
// Training Data Collection
const collectTrainingData = (reviewDecision) => {
  const trainingEntry = {
    pattern_id: generateUUID(),
    content_snippet: extractRelevantSnippet(reviewDecision.content),
    human_decision: reviewDecision.decision,
    confidence_level: reviewDecision.confidence,
    tag_applied: reviewDecision.tags.join(','),
    context: {
      document_type: reviewDecision.source,
      reviewer_id: reviewDecision.reviewedBy,
      review_time_seconds: reviewDecision.reviewDuration,
      similar_patterns: findSimilarPatterns(reviewDecision.content)
    }
  };
  
  // Store in Redis for ML training pipeline
  redis.hset('patterns:training', trainingEntry.pattern_id, JSON.stringify(trainingEntry));
  
  // Trigger model retraining if enough new data
  const trainingDataCount = redis.hlen('patterns:training');
  if (trainingDataCount % 100 === 0) {
    triggerModelRetraining();
  }
};

// Confidence Score Calculation
const calculateConfidence = (selectedTags, documentContext) => {
  let baseConfidence = 0.5;
  
  // Increase confidence for multiple consistent flags
  if (selectedTags.length > 1) {
    baseConfidence += 0.2;
  }
  
  // Increase confidence for high-severity tags
  const criticalTags = selectedTags.filter(tag => 
    SECURITY_TAGS[tag].severity === 'CRITICAL'
  );
  baseConfidence += criticalTags.length * 0.3;
  
  // Historical accuracy adjustment
  const reviewerAccuracy = getReviewerAccuracy(documentContext.reviewedBy);
  baseConfidence *= reviewerAccuracy;
  
  return Math.min(baseConfidence, 1.0);
};

// Auto-Escalation Rules
const checkAutoEscalation = (document) => {
  const escalationRules = [
    {
      condition: document.autoFlags.includes('MALICIOUS_CODE'),
      action: 'immediate_quarantine',
      notify: ['security_team', 'admin']
    },
    {
      condition: document.confidence_scores.PROMPT_INJECTION > 0.9,
      action: 'priority_review',
      notify: ['senior_reviewer']
    },
    {
      condition: document.source === 'external_api' && document.autoFlags.length > 2,
      action: 'enhanced_review',
      notify: ['api_security_team']
    }
  ];
  
  escalationRules.forEach(rule => {
    if (rule.condition) {
      executeEscalationAction(rule.action, document);
      notifyTeams(rule.notify, document);
    }
  });
};
```

## Security Considerations

### Data Protection
- Encrypt embeddings at rest
- Secure API endpoints
- User authentication/authorization
- Rate limiting and throttling

### Privacy
- PII detection and masking
- Data retention policies
- User consent for data usage
- Right to deletion support

## Optimization Tips

### Performance
- Batch embedding generation
- Implement aggressive caching
- Use streaming for long responses
- Optimize chunk sizes for model

### Cost
- Cache common queries
- Use smaller embedding models where possible
- Implement query deduplication
- Monitor and limit token usage

### Quality
- Regular evaluation metric reviews
- A/B testing for improvements
- User feedback integration
- Continuous retraining pipeline

## Next Steps

1. **Immediate Actions**
   - Set up development environment
   - Install required dependencies
   - Create project structure
   - Initialize n8n workflows

2. **Short-term Goals**
   - Implement Phase 1 core components
   - Set up evaluation framework
   - Create basic UI
   - Deploy staging environment

3. **Long-term Vision**
   - Scale to production
   - Add advanced RAG features
   - Implement multi-modal support
   - Build knowledge graph integration

## Resources & References

- [LangChain RAG Documentation](https://python.langchain.com/docs/use_cases/question_answering)
- [n8n Workflow Examples](https://n8n.io/workflows)
- [Chroma Vector Store](https://docs.trychroma.com)
- [Redis Integration Notes](./redis_integration_discovery.md)
- Original Article: "Building the Entire RAG Ecosystem" by Fareed Khan