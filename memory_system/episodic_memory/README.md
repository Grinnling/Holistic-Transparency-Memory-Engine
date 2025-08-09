# Episodic Memory Service

## Overview
The Episodic Memory Service is a core component of the memory heat map system, providing long-term storage and retrieval of conversation episodes. It archives conversations from working memory, enables full-text search, and maintains rich metadata for each interaction.

## Architecture

### System Components
```
┌─────────────────┐
│   Test Client   │
│  (port 8005)    │
└────────┬────────┘
         │
┌────────▼────────┐
│   REST API      │
│  Flask Service  │
└────────┬────────┘
         │
┌────────▼────────┐
│ Service Logic   │
│  (Threading)    │
└────────┬────────┘
         │
┌────────▼────────┐
│  SQLite + FTS5  │
│   Database      │
└─────────────────┘
```

### File Structure
```
episodic_memory/
├── service.py          # Flask REST API and business logic
├── database.py         # SQLite database operations
├── test_episodic.py    # Integration test suite
└── README.md          # This documentation
```

## Core Features

### 1. Conversation Archival
- Stores complete conversation exchanges with metadata
- Automatic topic extraction from conversation content
- Auto-generated summaries
- Trigger-based archival (manual, buffer_full, time_gap, system_restart)

### 2. Search Capabilities
- Full-text search using SQLite FTS5
- Filter by participants, topics, date ranges
- Combination queries supported

### 3. Data Model
```json
{
  "conversation_id": "unique_identifier",
  "exchanges": [
    {
      "user_message": "string",
      "assistant_response": "string",
      "timestamp": "ISO-8601"
    }
  ],
  "participants": ["human", "assistant"],
  "topics": ["python", "coding"],
  "summary": "auto-generated",
  "trigger_reason": "buffer_full"
}
```

## API Endpoints

### Health Check
```bash
GET /health
Response: {
  "status": "healthy",
  "service_id": "uuid",
  "database_path": "/tmp/episodic_memory.db"
}
```

### Archive Conversation
```bash
POST /archive
Body: {
  "conversation_data": {...},
  "trigger_reason": "manual"
}
Response: {
  "conversation_id": "episode_123"
}
```

### Search Episodes
```bash
GET /search?query=python&participants=human&topics=coding
Response: {
  "results": [...],
  "count": 5
}
```

### Get Specific Episode
```bash
GET /conversation/{conversation_id}
Response: {
  "conversation": {...}
}
```

### Export as Text
```bash
GET /conversation/{conversation_id}/export
Response: {
  "text_export": "formatted conversation"
}
```

### Recent Conversations
```bash
GET /recent?limit=10
Response: {
  "conversations": [...],
  "count": 10
}
```

### Service Statistics
```bash
GET /stats
Response: {
  "stats": {
    "uptime_hours": 2.5,
    "episodes_stored": 42,
    "database_stats": {...}
  }
}
```

## Running the Service

### Start Service
```bash
python3 /home/grinnling/Development/docker_agent_environment/memory_system/episodic_memory/service.py
```
Default port: 8005

### Environment Variables
```bash
EPISODIC_PORT=8005              # Service port
EPISODIC_DB_PATH=/tmp/episodic_memory.db  # Database location
```

### Run Tests
```bash
python3 /home/grinnling/Development/docker_agent_environment/memory_system/episodic_memory/test_episodic.py
```

## Database Schema

### Episodes Table
- `conversation_id`: Unique identifier
- `start_timestamp`: Conversation start time
- `end_timestamp`: Conversation end time
- `participants`: JSON array of participants
- `exchange_count`: Number of exchanges
- `summary`: Auto-generated summary
- `full_conversation`: Complete JSON of exchanges
- `topics`: Extracted topics (JSON array)
- `trigger_reason`: Why episode was archived
- `created_at`: Database insertion time

### Indexes
- Timestamp indexes for date range queries
- Participant and topic indexes for filtering
- FTS5 virtual table for full-text search

## Security Considerations (Planned)

### Current Security Features
- Parameterized SQL queries (no SQL injection)
- Request UUID tracking for audit trails
- Structured logging throughout
- Thread-safe operations with locks

### Future Security Enhancements
- [ ] Input validation and sanitization
- [ ] Rate limiting on endpoints
- [ ] Authentication/authorization layer
- [ ] Encrypted storage at rest
- [ ] API key management
- [ ] Network segmentation
- [ ] Comprehensive audit logging
- [ ] Data retention policies

## Testing

### Current Test Coverage
✅ All endpoints tested with happy-path scenarios
✅ Multiple trigger types tested
✅ Search functionality verified
✅ Export functionality tested

### Missing Test Cases
- Invalid JSON payloads
- Missing required fields
- Database connection failures
- Malformed timestamps
- 404 responses for non-existent conversations
- Concurrent access scenarios
- Data cleanup/deletion

## Integration with Memory Heat Map

This service is part of a larger memory system architecture:

1. **Working Memory** → Short-term conversation buffer
2. **Episodic Memory** → This service (long-term storage)
3. **Semantic Memory** → Concept relationships (planned)
4. **Procedural Memory** → Learned patterns (planned)

### Trigger Points for Archival
- **Buffer Full**: Working memory reaches capacity
- **Time Gap**: Long pause in conversation
- **System Restart**: Graceful shutdown
- **Manual**: Explicit archive request

## Performance Characteristics

- SQLite with WAL mode for concurrent access
- FTS5 for fast full-text search
- Indexed columns for quick filtering
- Thread-safe with lock management
- Request timing middleware for monitoring

## Troubleshooting

### Service Won't Start
- Check port 8005 is available
- Verify write permissions for database path
- Check Python dependencies (Flask, sqlite3)

### Search Not Working
- Verify FTS5 triggers are created
- Check database indexes exist
- Ensure proper JSON formatting in queries

### Archive Failures
- Validate JSON structure of conversation data
- Check timestamp formats (ISO-8601)
- Verify database disk space

## Future Enhancements

1. **Memory Consolidation**
   - Merge similar episodes
   - Extract common patterns
   - Build knowledge graphs

2. **Advanced Search**
   - Semantic similarity search
   - Vector embeddings for conversations
   - Multi-modal search (if images included)

3. **Analytics**
   - Conversation flow analysis
   - Topic trending over time
   - Participant interaction patterns

4. **Integration**
   - WebSocket support for real-time updates
   - Event streaming for other services
   - Backup and restore functionality

## Contributing

When adding features:
1. Maintain clean separation between API, service, and database layers
2. Add appropriate logging
3. Include request IDs in all operations
4. Write integration tests
5. Update this documentation

## License
[Specify your license]

## Contact
[Your contact information]