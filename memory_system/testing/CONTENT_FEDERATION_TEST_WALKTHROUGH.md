# Content Federation Testing Walkthrough

**Created:** 2025-12-15
**Purpose:** Verify content federation structures work correctly before OZOLITH integration
**Prerequisites:** Run from `/home/grinnling/Development/CODE_IMPLEMENTATION`

---

## Setup

```python
import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from datashapes import (
    # Content types and processing
    ContentSourceType, ProcessingPipeline, ProcessingStatus,
    ContentReference, ContentChunk,
    # Relationships
    ContentRelationType, ContentRelationship,
    # Citations
    CitationType, CitationReference,
    # Re-embedding
    ReembedTrigger, EmbeddingDisposition,
    OzolithPayloadReembedding, OzolithPayloadContentIngestion,
    # OZOLITH integration
    OzolithEventType, OZOLITH_PAYLOAD_MAP, OZOLITH_REQUIRED_FIELDS,
    validate_ozolith_payload
)
from datetime import datetime
import hashlib

print("All imports successful!")
```

**Expected:** "All imports successful!"

---

## Section 1: Content Source Types

### 1.1 Verify All Content Types Exist

```python
# Should have 17 content source types
print(f"Content source types: {len(ContentSourceType)}")

# Check key categories exist
text_types = [t for t in ContentSourceType if t.value.startswith('text_')]
doc_types = [t for t in ContentSourceType if t.value.startswith('doc_')]
media_types = [t for t in ContentSourceType if t.value.startswith('media_')]

print(f"Text types: {[t.value for t in text_types]}")
print(f"Doc types: {[t.value for t in doc_types]}")
print(f"Media types: {[t.value for t in media_types]}")
```

**Expected:**
- 17 total types
- Text: text_plain, text_markdown, text_code, text_config, text_log
- Doc: doc_pdf_text, doc_pdf_scanned, doc_word, doc_spreadsheet
- Media: media_image, media_diagram, media_screenshot, media_audio, media_video

### 1.2 Verify Processing Pipelines

```python
print(f"Processing pipelines: {len(ProcessingPipeline)}")
for p in ProcessingPipeline:
    print(f"  {p.value}")
```

**Expected:** 6 pipelines - curator, docling, transcription, direct, manual, pending

### 1.3 Verify PARTIAL Status Exists

```python
print(f"Processing statuses: {len(ProcessingStatus)}")
for s in ProcessingStatus:
    print(f"  {s.value}")

# Specifically check PARTIAL exists
assert ProcessingStatus.PARTIAL.value == "partial"
print("PARTIAL status confirmed!")
```

**Expected:** 6 statuses including "partial"

---

## Section 2: ContentReference with Staleness

### 2.1 Create a ContentReference

```python
content_ref = ContentReference(
    content_id="CONTENT-abc123",
    source_type=ContentSourceType.TEXT_MARKDOWN,
    original_path="/home/user/docs/architecture.md",
    original_hash=hashlib.sha256(b"test content").hexdigest(),
    original_size_bytes=1024,
    pipeline_used=ProcessingPipeline.CURATOR,
    processing_status=ProcessingStatus.COMPLETED,
    processed_at=datetime.utcnow().isoformat(),
    embedding_id="EMB-xyz789",
    embedding_model="text-embedding-ada-002",
    embedded_at=datetime.utcnow().isoformat(),
    created_at=datetime.utcnow().isoformat(),
    created_by="system",
    tags=["architecture", "design"]
)

print(f"Created: {content_ref.content_id}")
print(f"Source type: {content_ref.source_type.value}")
print(f"Pipeline: {content_ref.pipeline_used.value}")
print(f"Status: {content_ref.processing_status.value}")
```

**Expected:** ContentReference created with all fields populated

### 2.2 Test Staleness Fields

```python
from datetime import timedelta

# Set staleness tracking
now = datetime.utcnow()
content_ref.verified_current_at = now.isoformat()
content_ref.stale_after = (now + timedelta(days=30)).isoformat()
content_ref.staleness_note = "Architecture docs may change with each sprint"

print(f"Verified current at: {content_ref.verified_current_at}")
print(f"Stale after: {content_ref.stale_after}")
print(f"Staleness note: {content_ref.staleness_note}")

# Check if content is stale
def is_stale(ref):
    if ref.stale_after is None:
        return False
    stale_date = datetime.fromisoformat(ref.stale_after)
    return datetime.utcnow() > stale_date

print(f"Is stale now? {is_stale(content_ref)}")
```

**Expected:** Staleness fields populated, is_stale returns False (since stale_after is 30 days in future)

### 2.3 Test PARTIAL Processing Status

```python
partial_ref = ContentReference(
    content_id="CONTENT-partial123",
    source_type=ContentSourceType.DOC_PDF_TEXT,
    original_path="/home/user/docs/large_report.pdf",
    processing_status=ProcessingStatus.PARTIAL,
    processing_notes="Processed 8 of 10 pages. Pages 7-8 had OCR errors."
)

print(f"Status: {partial_ref.processing_status.value}")
print(f"Notes: {partial_ref.processing_notes}")

# PARTIAL should be valid
assert partial_ref.processing_status == ProcessingStatus.PARTIAL
print("PARTIAL status works correctly!")
```

**Expected:** PARTIAL status accepted and stored

---

## Section 3: Content Chunks

### 3.1 Create Chunks for a Document

```python
# Simulate chunking a document
parent_content_id = "CONTENT-doc456"
chunks = []

chunk_texts = [
    "This is the first chunk of the document...",
    "This is the second chunk with some overlap...",
    "This is the third and final chunk..."
]

position = 0
for i, text in enumerate(chunk_texts):
    chunk = ContentChunk(
        chunk_id=f"CHUNK-{parent_content_id}-{i}",
        parent_content_id=parent_content_id,
        sequence=i,
        start_position=position,
        end_position=position + len(text),
        overlap_chars=20 if i > 0 else 0,
        chunk_text=text,
        chunk_hash=hashlib.sha256(text.encode()).hexdigest(),
        token_count=len(text.split()),
        embedding_id=f"EMB-chunk-{i}",
        embedding_model="text-embedding-ada-002",
        embedded_at=datetime.utcnow().isoformat()
    )
    chunks.append(chunk)
    position += len(text) - 20  # Account for overlap

print(f"Created {len(chunks)} chunks for {parent_content_id}")
for chunk in chunks:
    print(f"  {chunk.chunk_id}: positions {chunk.start_position}-{chunk.end_position}, {chunk.token_count} tokens")
```

**Expected:** 3 chunks created with sequential IDs and correct position tracking

### 3.2 Verify Chunk Relationships

```python
# All chunks should reference same parent
parent_ids = set(c.parent_content_id for c in chunks)
assert len(parent_ids) == 1
print(f"All chunks belong to: {parent_ids.pop()}")

# Chunks should be in sequence
sequences = [c.sequence for c in chunks]
assert sequences == [0, 1, 2]
print(f"Chunk sequences: {sequences}")

# Verify overlap tracking
for i, chunk in enumerate(chunks):
    if i == 0:
        assert chunk.overlap_chars == 0
    else:
        assert chunk.overlap_chars == 20
print("Overlap tracking correct!")
```

**Expected:** All assertions pass

---

## Section 4: Content Relationships

### 4.1 Verify Relationship Types

```python
print(f"Relationship types: {len(ContentRelationType)}")
for rt in ContentRelationType:
    print(f"  {rt.value}")
```

**Expected:** 11 relationship types

### 4.2 Create Parent-Child Relationship (PDF contains images)

```python
# PDF document
pdf_content_id = "CONTENT-pdf001"

# Image extracted from PDF
image_content_id = "CONTENT-img001"

# Create relationship: PDF contains image
rel_contains = ContentRelationship(
    relationship_id="REL-001",
    relationship_type=ContentRelationType.CONTAINS,
    source_content_id=pdf_content_id,
    target_content_id=image_content_id,
    created_at=datetime.utcnow().isoformat(),
    created_by="docling_processor",
    confidence=1.0,
    relationship_note="Image extracted from page 3 of PDF"
)

print(f"Relationship: {rel_contains.source_content_id} --{rel_contains.relationship_type.value}--> {rel_contains.target_content_id}")
print(f"Note: {rel_contains.relationship_note}")
```

**Expected:** Relationship created showing PDF contains image

### 4.3 Create Version Relationship

```python
# Old version
old_doc_id = "CONTENT-doc-v1"
# New version
new_doc_id = "CONTENT-doc-v2"

rel_version = ContentRelationship(
    relationship_id="REL-002",
    relationship_type=ContentRelationType.VERSION_OF,
    source_content_id=new_doc_id,
    target_content_id=old_doc_id,
    created_at=datetime.utcnow().isoformat(),
    created_by="human",
    confidence=1.0,
    relationship_note="Updated architecture doc after Q4 review"
)

print(f"Version relationship: {rel_version.source_content_id} is VERSION_OF {rel_version.target_content_id}")
```

**Expected:** Version relationship created

### 4.4 Create Code Import Relationship

```python
# Main code file
main_file_id = "CONTENT-main.py"
# Imported module
util_file_id = "CONTENT-utils.py"

rel_import = ContentRelationship(
    relationship_id="REL-003",
    relationship_type=ContentRelationType.IMPORTS,
    source_content_id=main_file_id,
    target_content_id=util_file_id,
    created_at=datetime.utcnow().isoformat(),
    created_by="code_analyzer",
    confidence=1.0,
    relationship_note="from utils import helper_function"
)

print(f"Import relationship: {rel_import.source_content_id} IMPORTS {rel_import.target_content_id}")
```

**Expected:** Import relationship created

---

## Section 5: Re-embedding Workflow

### 5.1 Verify Re-embed Triggers

```python
print(f"Re-embed triggers: {len(ReembedTrigger)}")
for t in ReembedTrigger:
    print(f"  {t.value}")
```

**Expected:** 6 triggers - model_upgrade, quality_issue, scheduled_refresh, manual_request, content_updated, batch_migration

### 5.2 Verify Embedding Dispositions (No Delete!)

```python
print(f"Embedding dispositions: {len(EmbeddingDisposition)}")
for d in EmbeddingDisposition:
    print(f"  {d.value}")

# Verify NO delete option exists
disposition_values = [d.value for d in EmbeddingDisposition]
assert "deleted" not in disposition_values
assert "delete" not in disposition_values
print("Confirmed: No delete option - we preserve everything!")
```

**Expected:** 3 dispositions (archived, kept_as_fallback, superseded), NO delete option

### 5.3 Create Re-embedding Payload

```python
reembed_payload = OzolithPayloadReembedding(
    content_id="CONTENT-abc123",
    previous_embedding_id="EMB-old-001",
    new_embedding_id="EMB-new-001",
    trigger_reason=ReembedTrigger.MODEL_UPGRADE.value,
    previous_embedding_model="text-embedding-ada-002",
    new_embedding_model="text-embedding-3-large",
    content_hash_verified=True,
    content_hash_at_reembed=hashlib.sha256(b"original content").hexdigest(),
    old_embedding_disposition=EmbeddingDisposition.ARCHIVED.value,
    archive_location="/archive/embeddings/2025/12/"
)

print(f"Re-embed payload created:")
print(f"  Content: {reembed_payload.content_id}")
print(f"  Old embedding: {reembed_payload.previous_embedding_id} ({reembed_payload.previous_embedding_model})")
print(f"  New embedding: {reembed_payload.new_embedding_id} ({reembed_payload.new_embedding_model})")
print(f"  Trigger: {reembed_payload.trigger_reason}")
print(f"  Hash verified: {reembed_payload.content_hash_verified}")
print(f"  Old embedding disposition: {reembed_payload.old_embedding_disposition}")
print(f"  Archive location: {reembed_payload.archive_location}")
```

**Expected:** Full re-embedding payload with all tracking info

### 5.4 Create Batch Re-embedding Payload

```python
batch_reembed = OzolithPayloadReembedding(
    content_id="CONTENT-batch-item-042",
    previous_embedding_id="EMB-old-042",
    new_embedding_id="EMB-new-042",
    trigger_reason=ReembedTrigger.BATCH_MIGRATION.value,
    batch_id="BATCH-2025-12-model-upgrade",
    batch_reason="Migrating all embeddings from ada-002 to text-embedding-3-large",
    previous_embedding_model="text-embedding-ada-002",
    new_embedding_model="text-embedding-3-large",
    content_hash_verified=True,
    old_embedding_disposition=EmbeddingDisposition.ARCHIVED.value
)

print(f"Batch re-embed:")
print(f"  Batch ID: {batch_reembed.batch_id}")
print(f"  Batch reason: {batch_reembed.batch_reason}")
```

**Expected:** Batch tracking fields populated

---

## Section 6: OZOLITH Integration

### 6.1 Verify New Event Types Exist

```python
# Check CONTENT_REEMBEDDED exists
assert OzolithEventType.CONTENT_REEMBEDDED.value == "content_reembedded"
print(f"CONTENT_REEMBEDDED event type: {OzolithEventType.CONTENT_REEMBEDDED.value}")

# Check CONTENT_INGESTION exists
assert OzolithEventType.CONTENT_INGESTION.value == "content_ingestion"
print(f"CONTENT_INGESTION event type: {OzolithEventType.CONTENT_INGESTION.value}")

print(f"\nTotal event types: {len(OzolithEventType)}")
```

**Expected:** Both event types exist, 14 total event types

### 6.2 Verify Payload Mappings

```python
# Check new payloads are mapped
assert OzolithEventType.CONTENT_INGESTION in OZOLITH_PAYLOAD_MAP
assert OzolithEventType.CONTENT_REEMBEDDED in OZOLITH_PAYLOAD_MAP
assert OzolithEventType.CITATION_CREATED in OZOLITH_PAYLOAD_MAP

print(f"Payload mappings: {len(OZOLITH_PAYLOAD_MAP)}")
print(f"  CONTENT_INGESTION -> {OZOLITH_PAYLOAD_MAP[OzolithEventType.CONTENT_INGESTION].__name__}")
print(f"  CONTENT_REEMBEDDED -> {OZOLITH_PAYLOAD_MAP[OzolithEventType.CONTENT_REEMBEDDED].__name__}")
print(f"  CITATION_CREATED -> {OZOLITH_PAYLOAD_MAP[OzolithEventType.CITATION_CREATED].__name__}")
```

**Expected:** All 3 new event types mapped to correct payload classes

### 6.3 Validate Content Ingestion Payload

```python
# Valid payload
valid_ingestion = {
    "content_id": "CONTENT-test001",
    "source_type": "text_markdown",
    "original_path": "/home/user/test.md"
}

is_valid, errors, warnings = validate_ozolith_payload(
    OzolithEventType.CONTENT_INGESTION,
    valid_ingestion
)

print(f"Valid ingestion payload: {is_valid}")
print(f"Errors: {errors}")
print(f"Warnings: {warnings}")

# Invalid payload (missing required field)
invalid_ingestion = {
    "content_id": "CONTENT-test001",
    "source_type": "text_markdown"
    # missing original_path
}

is_valid2, errors2, warnings2 = validate_ozolith_payload(
    OzolithEventType.CONTENT_INGESTION,
    invalid_ingestion
)

print(f"\nInvalid ingestion payload: {is_valid2}")
print(f"Errors: {errors2}")
```

**Expected:** First validation passes, second fails with "Missing required field: original_path"

### 6.4 Validate Re-embedding Payload

```python
# Valid re-embedding payload
valid_reembed = {
    "content_id": "CONTENT-test001",
    "previous_embedding_id": "EMB-old",
    "new_embedding_id": "EMB-new",
    "trigger_reason": "model_upgrade"
}

is_valid, errors, warnings = validate_ozolith_payload(
    OzolithEventType.CONTENT_REEMBEDDED,
    valid_reembed
)

print(f"Valid re-embed payload: {is_valid}")
print(f"Errors: {errors}")

# Invalid (missing trigger_reason)
invalid_reembed = {
    "content_id": "CONTENT-test001",
    "previous_embedding_id": "EMB-old",
    "new_embedding_id": "EMB-new"
}

is_valid2, errors2, warnings2 = validate_ozolith_payload(
    OzolithEventType.CONTENT_REEMBEDDED,
    invalid_reembed
)

print(f"\nInvalid re-embed payload: {is_valid2}")
print(f"Errors: {errors2}")
```

**Expected:** First validation passes, second fails with "Missing required field: trigger_reason"

---

## Section 7: Citation References

### 7.1 Create Different Citation Types

```python
# Contextual bookmark - reference to conversation moment
bookmark_citation = CitationReference(
    citation_id="CITE-001",
    citation_type=CitationType.CONTEXTUAL_BOOKMARK,
    target_type="exchange",
    target_id="MSG-12345",
    target_sequence=42,
    cited_from_context="SB-main",
    cited_at=datetime.utcnow().isoformat(),
    cited_by="assistant",
    relevance_note="Key decision point about architecture",
    confidence_at_citation=0.9
)

# Document link - reference to static artifact
doc_citation = CitationReference(
    citation_id="CITE-002",
    citation_type=CitationType.DOCUMENT_LINK,
    target_type="content",
    target_id="CONTENT-arch-doc",
    cited_from_context="SB-research",
    cited_at=datetime.utcnow().isoformat(),
    cited_by="assistant",
    relevance_note="Architecture documentation"
)

# Confidence anchor - certainty tracking
confidence_citation = CitationReference(
    citation_id="CITE-003",
    citation_type=CitationType.CONFIDENCE_ANCHOR,
    target_type="exchange",
    target_id="MSG-99999",
    cited_from_context="SB-main",
    cited_at=datetime.utcnow().isoformat(),
    cited_by="assistant",
    relevance_note="High confidence answer verified against docs",
    confidence_at_citation=0.95
)

print("Created citations:")
print(f"  {bookmark_citation.citation_id}: {bookmark_citation.citation_type.value} -> {bookmark_citation.target_id}")
print(f"  {doc_citation.citation_id}: {doc_citation.citation_type.value} -> {doc_citation.target_id}")
print(f"  {confidence_citation.citation_id}: {confidence_citation.citation_type.value} -> {confidence_citation.target_id}")
```

**Expected:** Three different citation types created successfully

---

## Section 8: Extra Dict Evolution

### 8.1 Test Extra Dict for Discovered Fields

```python
# ContentReference with extra fields
content_with_extra = ContentReference(
    content_id="CONTENT-extra001",
    source_type=ContentSourceType.TEXT_CODE,
    original_path="/home/user/code/main.py",
    extra={
        "language": "python",
        "framework": "fastapi",
        "line_count": 500,
        "complexity_score": 7.2
    }
)

print(f"Content with extra fields:")
print(f"  Standard field - source_type: {content_with_extra.source_type.value}")
print(f"  Extra fields: {content_with_extra.extra}")

# Access extra fields
print(f"  Language: {content_with_extra.extra.get('language')}")
print(f"  Complexity: {content_with_extra.extra.get('complexity_score')}")
```

**Expected:** Extra dict stores arbitrary fields for evolution

### 8.2 Test Extra Dict in Re-embedding (Quality Metrics)

```python
reembed_with_quality = OzolithPayloadReembedding(
    content_id="CONTENT-quality001",
    previous_embedding_id="EMB-old",
    new_embedding_id="EMB-new",
    trigger_reason=ReembedTrigger.QUALITY_ISSUE.value,
    extra={
        "quality_issue_type": "low_retrieval_accuracy",
        "retrieval_failures_before": 15,
        "similarity_score_avg_before": 0.62,
        "expected_improvement": "Higher similarity scores with new model"
    }
)

print(f"Re-embed with quality context:")
print(f"  Trigger: {reembed_with_quality.trigger_reason}")
print(f"  Quality issue: {reembed_with_quality.extra.get('quality_issue_type')}")
print(f"  Failures before: {reembed_with_quality.extra.get('retrieval_failures_before')}")
```

**Expected:** Quality metrics stored in extra dict

---

## Summary Checklist

Run through this checklist to confirm all tests passed:

- [ ] Section 1: All 17 content types, 6 pipelines, PARTIAL status exists
- [ ] Section 2: ContentReference created with staleness tracking
- [ ] Section 3: ContentChunk created with parent linkage and boundaries
- [ ] Section 4: ContentRelationship created for CONTAINS, VERSION_OF, IMPORTS
- [ ] Section 5: Re-embedding workflow with triggers, NO delete option, batch tracking
- [ ] Section 6: OZOLITH integration - event types mapped, validation works
- [ ] Section 7: CitationReference created for different purposes
- [ ] Section 8: Extra dict works for evolution

---

## Discussion Questions

After completing the walkthrough, consider:

1. **Content type coverage:** Did we miss any content types you work with?

2. **Relationship types:** Are the 11 relationship types sufficient? Any missing?

3. **Staleness tracking:** Is 30 days a reasonable default for stale_after? Should we have presets?

4. **Chunk boundaries:** Is character-based positioning sufficient, or do we need token-based?

5. **Re-embed triggers:** Any trigger scenarios we didn't anticipate?

6. **Extra dict patterns:** What fields are you already putting in extra that should be promoted?

---

*Testing document created: 2025-12-15*
*Structures tested: Content Federation additions to datashapes.py*
