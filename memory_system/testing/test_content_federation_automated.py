#!/usr/bin/env python3
"""
Automated Content Federation Test Suite
Generated from CONTENT_FEDERATION_TEST_WALKTHROUGH.md
"""

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

import hashlib
from datetime import datetime, timedelta

# Track results
results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def check(name, condition, details=""):
    """Record test result. Named 'check' to avoid pytest collection conflict."""
    if condition:
        results["passed"].append(name)
        print(f"  [PASS] {name}")
    else:
        results["failed"].append((name, details))
        print(f"  [FAIL] {name}: {details}")

def warn(name, message):
    """Record a warning."""
    results["warnings"].append((name, message))
    print(f"  [WARN] {name}: {message}")

# =============================================================================
# =============================================================================

# ======================================================================
# MAIN EXECUTION - Only runs when script is executed directly
# ======================================================================
if __name__ == '__main__':
    # =============================================================================
    # Setup - Imports
    # =============================================================================
    print("\n" + "="*70)
    print("SETUP: Importing modules")
    print("="*70)

    try:
        from datashapes import (
            # Content types and processing
            ContentSourceType, ProcessingPipeline, ProcessingStatus,
            ContentReference, ContentChunk,
            # Staleness and chunking
            StalenessReason, STALENESS_DEFAULTS_DAYS,
            ChunkStrategy,
            # Relationships
            ContentRelationType, ContentRelationship,
            RELATIONSHIP_INVERSE_MAP, get_inverse_relationship_type,
            create_bidirectional_relationship,
            # Citations
            CitationType, CitationReference,
            # Re-embedding
            ReembedTrigger, EmbeddingDisposition,
            OzolithPayloadReembedding, OzolithPayloadContentIngestion,
            # OZOLITH integration
            OzolithEventType, OZOLITH_PAYLOAD_MAP, OZOLITH_REQUIRED_FIELDS,
            validate_ozolith_payload, OzolithPayloadCitation,
            # NEW: Validation helpers from datashapes.py
            is_valid_coco_bbox, is_valid_smpte_timecode, is_valid_confidence, is_stale,
            calculate_stale_after, get_staleness_default_days, get_pipeline_for_content_type,
            CONTENT_TYPE_TO_PIPELINE_MAP,
            ValidationError,
            # Serialization helpers
            payload_to_dict, dict_to_payload
        )
        print("  [PASS] All imports successful")
        imports_ok = True
    except ImportError as e:
        print(f"  [FAIL] Import failed: {e}")
        imports_ok = False

    if not imports_ok:
        print("\nCannot continue without successful imports.")
        sys.exit(1)

    # =============================================================================
    # Section 1: Content Source Types
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 1: Content Source Types")
    print("="*70)

    # 1.1 Verify All Content Types Exist
    print("\n1.1 Verifying content type count...")
    content_type_count = len(ContentSourceType)
    check("ContentSourceType count == 17", content_type_count == 17,
         f"Got {content_type_count}")

    # Check key categories
    text_types = [t for t in ContentSourceType if t.value.startswith('text_')]
    doc_types = [t for t in ContentSourceType if t.value.startswith('doc_')]
    media_types = [t for t in ContentSourceType if t.value.startswith('media_')]

    check("Text types == 5", len(text_types) == 5,
         f"Got {len(text_types)}: {[t.value for t in text_types]}")
    check("Doc types == 4", len(doc_types) == 4,
         f"Got {len(doc_types)}: {[t.value for t in doc_types]}")
    check("Media types == 5", len(media_types) == 5,
         f"Got {len(media_types)}: {[t.value for t in media_types]}")

    # Verify specific types exist
    expected_text = ['text_plain', 'text_markdown', 'text_code', 'text_config', 'text_log']
    actual_text = [t.value for t in text_types]
    check("All expected text types present", set(expected_text) == set(actual_text),
         f"Missing: {set(expected_text) - set(actual_text)}")

    # 1.2 Verify Processing Pipelines
    print("\n1.2 Verifying processing pipelines...")
    pipeline_count = len(ProcessingPipeline)
    check("ProcessingPipeline count == 6", pipeline_count == 6,
         f"Got {pipeline_count}")

    expected_pipelines = ['curator', 'docling', 'transcription', 'direct', 'manual', 'pending']
    actual_pipelines = [p.value for p in ProcessingPipeline]
    check("All expected pipelines present", set(expected_pipelines) == set(actual_pipelines),
         f"Missing: {set(expected_pipelines) - set(actual_pipelines)}")

    # 1.3 Verify PARTIAL Status Exists
    print("\n1.3 Verifying processing statuses...")
    status_count = len(ProcessingStatus)
    check("ProcessingStatus count == 10", status_count == 10,
         f"Got {status_count}")

    check("PARTIAL status exists", hasattr(ProcessingStatus, 'PARTIAL'), "Missing PARTIAL")
    check("PARTIAL value == 'partial'", ProcessingStatus.PARTIAL.value == "partial",
         f"Got '{ProcessingStatus.PARTIAL.value}'")

    # New intermediate states
    check("QUEUED status exists", hasattr(ProcessingStatus, 'QUEUED'), "Missing QUEUED")
    check("BLOCKED status exists", hasattr(ProcessingStatus, 'BLOCKED'), "Missing BLOCKED")
    check("RETRYING status exists", hasattr(ProcessingStatus, 'RETRYING'), "Missing RETRYING")
    check("NEEDS_REVIEW status exists", hasattr(ProcessingStatus, 'NEEDS_REVIEW'), "Missing NEEDS_REVIEW")

    # =============================================================================
    # Section 2: ContentReference with Staleness
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 2: ContentReference with Staleness")
    print("="*70)

    # 2.1 Create a ContentReference
    print("\n2.1 Creating ContentReference...")
    try:
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
        check("ContentReference created", True)
        check("ContentReference content_id correct", content_ref.content_id == "CONTENT-abc123")
        check("ContentReference source_type correct", content_ref.source_type == ContentSourceType.TEXT_MARKDOWN)
        check("ContentReference pipeline_used correct", content_ref.pipeline_used == ProcessingPipeline.CURATOR)
    except Exception as e:
        check("ContentReference created", False, str(e))

    # 2.2 Test Staleness Fields
    print("\n2.2 Testing staleness fields...")
    try:
        now = datetime.utcnow()
        content_ref.verified_current_at = now.isoformat()
        content_ref.stale_after = (now + timedelta(days=30)).isoformat()
        content_ref.staleness_note = "Architecture docs may change with each sprint"

        check("verified_current_at field works", content_ref.verified_current_at is not None)
        check("stale_after field works", content_ref.stale_after is not None)
        check("staleness_note field works", content_ref.staleness_note != "")

        # Use imported is_stale from datashapes.py (takes string directly, not object)
        check("is_stale returns False for future date", not is_stale(content_ref.stale_after))
    except Exception as e:
        check("Staleness fields work", False, str(e))

    # 2.2b Test StalenessReason enum and defaults
    print("\n2.2b Testing StalenessReason and defaults...")
    try:
        staleness_reason_count = len(StalenessReason)
        check("StalenessReason count == 7", staleness_reason_count == 7,
             f"Got {staleness_reason_count}")

        check("SPRINT_CYCLE reason exists", hasattr(StalenessReason, 'SPRINT_CYCLE'))
        check("API_VERSION reason exists", hasattr(StalenessReason, 'API_VERSION'))
        check("DEPENDENCY_CHANGE reason exists", hasattr(StalenessReason, 'DEPENDENCY_CHANGE'))

        # Test defaults mapping
        check("STALENESS_DEFAULTS_DAYS has all content types",
             len(STALENESS_DEFAULTS_DAYS) == len(ContentSourceType),
             f"Got {len(STALENESS_DEFAULTS_DAYS)} defaults for {len(ContentSourceType)} types")

        check("TEXT_CODE default is 14 days", STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_CODE] == 14)
        check("TEXT_CONFIG default is 7 days", STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_CONFIG] == 7)
        check("TEXT_LOG default is None (historical)", STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_LOG] is None)
        check("DOC_PDF_TEXT default is 60 days", STALENESS_DEFAULTS_DAYS[ContentSourceType.DOC_PDF_TEXT] == 60)

        # Test staleness_reason field on ContentReference
        content_with_reason = ContentReference(
            content_id="CONTENT-reason001",
            source_type=ContentSourceType.TEXT_CODE,
            original_path="/home/user/code/api.py",
            staleness_reason=StalenessReason.SPRINT_CYCLE,
            staleness_note="Changes every 2-week sprint"
        )
        check("ContentReference accepts staleness_reason",
             content_with_reason.staleness_reason == StalenessReason.SPRINT_CYCLE)
    except Exception as e:
        check("StalenessReason and defaults", False, str(e))

    # 2.3 Test PARTIAL Processing Status
    print("\n2.3 Testing PARTIAL processing status...")
    try:
        partial_ref = ContentReference(
            content_id="CONTENT-partial123",
            source_type=ContentSourceType.DOC_PDF_TEXT,
            original_path="/home/user/docs/large_report.pdf",
            processing_status=ProcessingStatus.PARTIAL,
            processing_notes="Processed 8 of 10 pages. Pages 7-8 had OCR errors."
        )

        check("PARTIAL status accepted", partial_ref.processing_status == ProcessingStatus.PARTIAL)
        check("processing_notes field works", "8 of 10 pages" in partial_ref.processing_notes)
    except Exception as e:
        check("PARTIAL status works", False, str(e))

    # =============================================================================
    # Section 3: Content Chunks
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 3: Content Chunks")
    print("="*70)

    # 3.1 Create Chunks for a Document
    print("\n3.1 Creating chunks...")
    try:
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

        check("Created 3 chunks", len(chunks) == 3)
        check("Chunks have sequential IDs", all(f"-{i}" in c.chunk_id for i, c in enumerate(chunks)))
    except Exception as e:
        check("Chunk creation", False, str(e))
        chunks = []

    # 3.2 Verify Chunk Relationships
    print("\n3.2 Verifying chunk relationships...")
    if chunks:
        try:
            parent_ids = set(c.parent_content_id for c in chunks)
            check("All chunks have same parent", len(parent_ids) == 1)

            sequences = [c.sequence for c in chunks]
            check("Chunks in sequence [0,1,2]", sequences == [0, 1, 2])

            # Verify overlap tracking
            check("First chunk overlap == 0", chunks[0].overlap_chars == 0)
            check("Later chunks overlap == 20", all(c.overlap_chars == 20 for c in chunks[1:]))
        except Exception as e:
            check("Chunk relationships", False, str(e))

    # 3.3 Verify ChunkStrategy enum
    print("\n3.3 Verifying ChunkStrategy enum...")
    try:
        strategy_count = len(ChunkStrategy)
        check("ChunkStrategy count == 8", strategy_count == 8,
             f"Got {strategy_count}")

        check("FIXED_SIZE strategy exists", hasattr(ChunkStrategy, 'FIXED_SIZE'))
        check("SEMANTIC strategy exists", hasattr(ChunkStrategy, 'SEMANTIC'))
        check("PAGE strategy exists", hasattr(ChunkStrategy, 'PAGE'))
        check("CODE_BLOCK strategy exists", hasattr(ChunkStrategy, 'CODE_BLOCK'))
    except Exception as e:
        check("ChunkStrategy enum", False, str(e))

    # 3.4 Test chunk with strategy and visual boundaries
    print("\n3.4 Testing chunk with strategy and visual boundaries...")
    try:
        # Text chunk with strategy
        text_chunk = ContentChunk(
            chunk_id="CHUNK-doc-0",
            parent_content_id="CONTENT-doc",
            sequence=0,
            chunk_strategy=ChunkStrategy.PARAGRAPH,
            start_position=0,
            end_position=500,
            chunk_text="First paragraph of the document..."
        )
        check("Chunk accepts chunk_strategy", text_chunk.chunk_strategy == ChunkStrategy.PARAGRAPH)

        # PDF chunk with page number
        pdf_chunk = ContentChunk(
            chunk_id="CHUNK-pdf-3",
            parent_content_id="CONTENT-pdf",
            sequence=3,
            chunk_strategy=ChunkStrategy.PAGE,
            page_number=4,
            chunk_text="Content from page 4..."
        )
        check("Chunk accepts page_number", pdf_chunk.page_number == 4)

        # Image chunk with bounding box
        image_chunk = ContentChunk(
            chunk_id="CHUNK-diagram-0",
            parent_content_id="CONTENT-diagram",
            sequence=0,
            chunk_strategy=ChunkStrategy.CUSTOM,
            page_number=1,
            bounding_box={"x": 100.0, "y": 200.0, "width": 400.0, "height": 300.0},
            coordinate_system="image",
            chunk_text="[Diagram: Architecture overview]"
        )
        check("Chunk accepts bounding_box", image_chunk.bounding_box is not None)
        check("Bounding box has coordinates",
             image_chunk.bounding_box.get('x') == 100.0 and image_chunk.bounding_box.get('width') == 400.0)
        check("Chunk accepts coordinate_system", image_chunk.coordinate_system == "image")
    except Exception as e:
        check("Chunk with strategy and visual boundaries", False, str(e))

    # 3.5 Test chunk with temporal boundaries (audio/video)
    print("\n3.5 Testing chunk with temporal boundaries (SMPTE timecode)...")
    try:
        # Audio chunk with SMPTE timecode
        audio_chunk = ContentChunk(
            chunk_id="CHUNK-audio-5",
            parent_content_id="CONTENT-podcast",
            sequence=5,
            chunk_strategy=ChunkStrategy.FIXED_SIZE,
            start_timecode="00:05:30:00",        # 5 minutes, 30 seconds
            end_timecode="00:06:00:00",          # 6 minutes
            frame_rate=29.97,
            duration_ms=30000,                    # 30 seconds
            chunk_text="[Transcript: Discussion about architecture patterns...]"
        )
        check("Chunk accepts start_timecode", audio_chunk.start_timecode == "00:05:30:00")
        check("Chunk accepts end_timecode", audio_chunk.end_timecode == "00:06:00:00")
        check("Chunk accepts frame_rate", audio_chunk.frame_rate == 29.97)
        check("Chunk accepts duration_ms", audio_chunk.duration_ms == 30000)

        # Video chunk
        video_chunk = ContentChunk(
            chunk_id="CHUNK-video-12",
            parent_content_id="CONTENT-tutorial",
            sequence=12,
            chunk_strategy=ChunkStrategy.SEMANTIC,
            start_timecode="00:15:00:00",
            end_timecode="00:17:30:15",
            frame_rate=24.0,
            page_number=None,  # No page for video
            chunk_text="[Scene: Code walkthrough of authentication module]"
        )
        check("Video chunk has SMPTE timecode", video_chunk.start_timecode is not None)
        check("Video chunk frame_rate is 24fps", video_chunk.frame_rate == 24.0)
    except Exception as e:
        check("Chunk with temporal boundaries", False, str(e))

    # =============================================================================
    # Section 4: Content Relationships
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 4: Content Relationships")
    print("="*70)

    # 4.1 Verify Relationship Types
    print("\n4.1 Verifying relationship types...")
    rel_type_count = len(ContentRelationType)
    check("ContentRelationType count == 17", rel_type_count == 17,
         f"Got {rel_type_count}")

    # Check new relationship types exist
    check("DEPENDS_ON exists", hasattr(ContentRelationType, 'DEPENDS_ON'))
    check("DEPENDENCY_OF exists", hasattr(ContentRelationType, 'DEPENDENCY_OF'))
    check("DUPLICATE_OF exists", hasattr(ContentRelationType, 'DUPLICATE_OF'))
    check("HAS_DUPLICATE exists", hasattr(ContentRelationType, 'HAS_DUPLICATE'))
    check("CONTRADICTS exists", hasattr(ContentRelationType, 'CONTRADICTS'))
    check("CONTRADICTED_BY exists", hasattr(ContentRelationType, 'CONTRADICTED_BY'))

    # 4.2 Create Parent-Child Relationship
    print("\n4.2 Creating CONTAINS relationship (PDF contains image)...")
    try:
        rel_contains = ContentRelationship(
            relationship_id="REL-001",
            relationship_type=ContentRelationType.CONTAINS,
            source_content_id="CONTENT-pdf001",
            target_content_id="CONTENT-img001",
            created_at=datetime.utcnow().isoformat(),
            created_by="docling_processor",
            confidence=1.0,
            relationship_note="Image extracted from page 3 of PDF"
        )

        check("CONTAINS relationship created", rel_contains.relationship_type == ContentRelationType.CONTAINS)
        check("Relationship has source and target",
             rel_contains.source_content_id != "" and rel_contains.target_content_id != "")
    except Exception as e:
        check("CONTAINS relationship", False, str(e))

    # 4.3 Create Version Relationship
    print("\n4.3 Creating VERSION_OF relationship...")
    try:
        rel_version = ContentRelationship(
            relationship_id="REL-002",
            relationship_type=ContentRelationType.VERSION_OF,
            source_content_id="CONTENT-doc-v2",
            target_content_id="CONTENT-doc-v1",
            created_at=datetime.utcnow().isoformat(),
            created_by="human",
            confidence=1.0,
            relationship_note="Updated architecture doc after Q4 review"
        )

        check("VERSION_OF relationship created", rel_version.relationship_type == ContentRelationType.VERSION_OF)
    except Exception as e:
        check("VERSION_OF relationship", False, str(e))

    # 4.4 Create Code Import Relationship
    print("\n4.4 Creating IMPORTS relationship...")
    try:
        rel_import = ContentRelationship(
            relationship_id="REL-003",
            relationship_type=ContentRelationType.IMPORTS,
            source_content_id="CONTENT-main.py",
            target_content_id="CONTENT-utils.py",
            created_at=datetime.utcnow().isoformat(),
            created_by="code_analyzer",
            confidence=1.0,
            relationship_note="from utils import helper_function"
        )

        check("IMPORTS relationship created", rel_import.relationship_type == ContentRelationType.IMPORTS)
    except Exception as e:
        check("IMPORTS relationship", False, str(e))

    # 4.5 Test new relationship types
    print("\n4.5 Testing new relationship types (DEPENDS_ON, CONTRADICTS, DUPLICATE_OF)...")
    try:
        # DEPENDS_ON - config depends on schema
        rel_depends = ContentRelationship(
            relationship_id="REL-004",
            relationship_type=ContentRelationType.DEPENDS_ON,
            source_content_id="CONTENT-docker-compose.yml",
            target_content_id="CONTENT-dockerfile",
            created_at=datetime.utcnow().isoformat(),
            created_by="dependency_analyzer",
            confidence=1.0,
            relationship_note="docker-compose references this Dockerfile"
        )
        check("DEPENDS_ON relationship created", rel_depends.relationship_type == ContentRelationType.DEPENDS_ON)

        # CONTRADICTS - conflicting information
        rel_contradicts = ContentRelationship(
            relationship_id="REL-005",
            relationship_type=ContentRelationType.CONTRADICTS,
            source_content_id="CONTENT-doc-old",
            target_content_id="CONTENT-doc-new",
            created_at=datetime.utcnow().isoformat(),
            created_by="consistency_checker",
            confidence=0.85,
            relationship_note="Old doc says use REST, new doc says use GraphQL"
        )
        check("CONTRADICTS relationship created", rel_contradicts.relationship_type == ContentRelationType.CONTRADICTS)

        # DUPLICATE_OF - same content
        rel_duplicate = ContentRelationship(
            relationship_id="REL-006",
            relationship_type=ContentRelationType.DUPLICATE_OF,
            source_content_id="CONTENT-readme-copy",
            target_content_id="CONTENT-readme-original",
            created_at=datetime.utcnow().isoformat(),
            created_by="dedup_scanner",
            confidence=1.0,
            relationship_note="Identical content hash"
        )
        check("DUPLICATE_OF relationship created", rel_duplicate.relationship_type == ContentRelationType.DUPLICATE_OF)
    except Exception as e:
        check("New relationship types", False, str(e))

    # 4.6 Test inverse mapping and bidirectional helper
    print("\n4.6 Testing inverse mapping and bidirectional helper...")
    try:
        # Test inverse mapping
        check("CONTAINS inverse is CONTAINED_BY",
             get_inverse_relationship_type(ContentRelationType.CONTAINS) == ContentRelationType.CONTAINED_BY)
        check("IMPORTS inverse is IMPORTED_BY",
             get_inverse_relationship_type(ContentRelationType.IMPORTS) == ContentRelationType.IMPORTED_BY)
        check("CONTRADICTS inverse is CONTRADICTED_BY",
             get_inverse_relationship_type(ContentRelationType.CONTRADICTS) == ContentRelationType.CONTRADICTED_BY)
        check("RELATED_TO is self-inverse",
             get_inverse_relationship_type(ContentRelationType.RELATED_TO) == ContentRelationType.RELATED_TO)

        # Test bidirectional helper
        forward, inverse = create_bidirectional_relationship(
            source_content_id="CONTENT-pdf-001",
            target_content_id="CONTENT-img-001",
            relationship_type=ContentRelationType.CONTAINS,
            created_by="docling_processor",
            confidence=1.0,
            relationship_note="Image extracted from page 3"
        )

        check("Bidirectional creates forward relationship", forward.relationship_type == ContentRelationType.CONTAINS)
        check("Bidirectional creates inverse relationship", inverse.relationship_type == ContentRelationType.CONTAINED_BY)
        check("Forward source is PDF", forward.source_content_id == "CONTENT-pdf-001")
        check("Inverse source is IMG", inverse.source_content_id == "CONTENT-img-001")
        check("Forward has inverse marker", forward.extra.get("has_inverse") == True)
        check("Inverse has inverse marker", inverse.extra.get("is_inverse") == True)
        check("Same confidence on both", forward.confidence == inverse.confidence)
        check("Same created_by on both", forward.created_by == inverse.created_by)
    except Exception as e:
        check("Inverse mapping and bidirectional helper", False, str(e))

    # =============================================================================
    # Section 5: Re-embedding Workflow
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 5: Re-embedding Workflow")
    print("="*70)

    # 5.1 Verify Re-embed Triggers
    print("\n5.1 Verifying re-embed triggers...")
    trigger_count = len(ReembedTrigger)
    check("ReembedTrigger count == 8", trigger_count == 8,
         f"Got {trigger_count}")

    expected_triggers = ['model_upgrade', 'quality_issue', 'scheduled_refresh',
                         'manual_request', 'content_updated', 'batch_migration',
                         'drift_detected', 'fuckery_detected']
    actual_triggers = [t.value for t in ReembedTrigger]
    check("All expected triggers present", set(expected_triggers) == set(actual_triggers),
         f"Missing: {set(expected_triggers) - set(actual_triggers)}")

    # Test new triggers exist
    check("DRIFT_DETECTED trigger exists", hasattr(ReembedTrigger, 'DRIFT_DETECTED'))
    check("FUCKERY_DETECTED trigger exists", hasattr(ReembedTrigger, 'FUCKERY_DETECTED'))

    # 5.2 Verify Embedding Dispositions (No Delete!)
    print("\n5.2 Verifying embedding dispositions (NO DELETE)...")
    disp_count = len(EmbeddingDisposition)
    check("EmbeddingDisposition count == 4", disp_count == 4,
         f"Got {disp_count}")

    disposition_values = [d.value for d in EmbeddingDisposition]
    check("No 'deleted' disposition", "deleted" not in disposition_values)
    check("No 'delete' disposition", "delete" not in disposition_values)
    check("'archived' disposition exists", "archived" in disposition_values)
    check("'kept_as_fallback' disposition exists", "kept_as_fallback" in disposition_values)
    check("'superseded' disposition exists", "superseded" in disposition_values)
    check("'corrected' disposition exists", "corrected" in disposition_values)
    check("CORRECTED is learning signal", hasattr(EmbeddingDisposition, 'CORRECTED'))

    # 5.3 Create Re-embedding Payload
    print("\n5.3 Creating re-embedding payload...")
    try:
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

        check("Re-embed payload created", True)
        check("Re-embed has content_id", reembed_payload.content_id == "CONTENT-abc123")
        check("Re-embed has trigger_reason", reembed_payload.trigger_reason == "model_upgrade")
        check("Re-embed has both embedding IDs",
             reembed_payload.previous_embedding_id != "" and reembed_payload.new_embedding_id != "")
        check("Re-embed has disposition", reembed_payload.old_embedding_disposition == "archived")
    except Exception as e:
        check("Re-embed payload creation", False, str(e))

    # 5.4 Create Batch Re-embedding Payload
    print("\n5.4 Creating batch re-embedding payload...")
    try:
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

        check("Batch re-embed payload created", True)
        check("Batch re-embed has batch_id", batch_reembed.batch_id == "BATCH-2025-12-model-upgrade")
        check("Batch re-embed has batch_reason", "Migrating" in batch_reembed.batch_reason)
    except Exception as e:
        check("Batch re-embed payload creation", False, str(e))

    # =============================================================================
    # Section 6: OZOLITH Integration
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 6: OZOLITH Integration")
    print("="*70)

    # 6.1 Verify New Event Types Exist
    print("\n6.1 Verifying new event types...")
    check("CONTENT_REEMBEDDED exists", hasattr(OzolithEventType, 'CONTENT_REEMBEDDED'))
    check("CONTENT_REEMBEDDED value correct",
         OzolithEventType.CONTENT_REEMBEDDED.value == "content_reembedded")
    check("CONTENT_INGESTION exists", hasattr(OzolithEventType, 'CONTENT_INGESTION'))
    check("CONTENT_INGESTION value correct",
         OzolithEventType.CONTENT_INGESTION.value == "content_ingestion")
    check("CITATION_CREATED exists", hasattr(OzolithEventType, 'CITATION_CREATED'))

    # New event types
    check("CONTENT_STALE exists", hasattr(OzolithEventType, 'CONTENT_STALE'))
    check("RELATIONSHIP_CREATED exists", hasattr(OzolithEventType, 'RELATIONSHIP_CREATED'))
    check("FUCKERY_DETECTED exists", hasattr(OzolithEventType, 'FUCKERY_DETECTED'))

    event_type_count = len(OzolithEventType)
    check("OzolithEventType count == 29", event_type_count == 29,
         f"Got {event_type_count}")

    # 6.2 Verify Payload Mappings
    print("\n6.2 Verifying payload mappings...")
    check("CONTENT_INGESTION in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.CONTENT_INGESTION in OZOLITH_PAYLOAD_MAP)
    check("CONTENT_REEMBEDDED in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.CONTENT_REEMBEDDED in OZOLITH_PAYLOAD_MAP)
    check("CITATION_CREATED in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.CITATION_CREATED in OZOLITH_PAYLOAD_MAP)

    check("CONTENT_INGESTION maps to OzolithPayloadContentIngestion",
         OZOLITH_PAYLOAD_MAP[OzolithEventType.CONTENT_INGESTION] == OzolithPayloadContentIngestion)
    check("CONTENT_REEMBEDDED maps to OzolithPayloadReembedding",
         OZOLITH_PAYLOAD_MAP[OzolithEventType.CONTENT_REEMBEDDED] == OzolithPayloadReembedding)
    check("CITATION_CREATED maps to OzolithPayloadCitation",
         OZOLITH_PAYLOAD_MAP[OzolithEventType.CITATION_CREATED] == OzolithPayloadCitation)

    # 6.3 Validate Content Ingestion Payload
    print("\n6.3 Validating content ingestion payloads...")
    try:
        valid_ingestion = {
            "content_id": "CONTENT-test001",
            "source_type": "text_markdown",
            "original_path": "/home/user/test.md"
        }

        is_valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.CONTENT_INGESTION,
            valid_ingestion
        )

        check("Valid ingestion payload passes", is_valid)
        check("Valid ingestion has no errors", len(errors) == 0, f"Errors: {errors}")

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

        check("Invalid ingestion payload fails", not is_valid2)
        check("Missing field reported in errors", any("original_path" in e for e in errors2),
             f"Errors: {errors2}")
    except Exception as e:
        check("Ingestion payload validation", False, str(e))

    # 6.4 Validate Re-embedding Payload
    print("\n6.4 Validating re-embedding payloads...")
    try:
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

        check("Valid re-embed payload passes", is_valid)
        check("Valid re-embed has no errors", len(errors) == 0, f"Errors: {errors}")

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

        check("Invalid re-embed payload fails", not is_valid2)
        check("Missing trigger_reason reported", any("trigger_reason" in e for e in errors2),
             f"Errors: {errors2}")
    except Exception as e:
        check("Re-embed payload validation", False, str(e))

    # 6.5 Verify new payload mappings
    print("\n6.5 Verifying new payload mappings...")
    check("CONTENT_STALE in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.CONTENT_STALE in OZOLITH_PAYLOAD_MAP)
    check("RELATIONSHIP_CREATED in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.RELATIONSHIP_CREATED in OZOLITH_PAYLOAD_MAP)
    check("FUCKERY_DETECTED in OZOLITH_PAYLOAD_MAP",
         OzolithEventType.FUCKERY_DETECTED in OZOLITH_PAYLOAD_MAP)

    # 6.6 Test enhanced validation (ID patterns, enum values, ranges)
    print("\n6.6 Testing enhanced validation...")
    try:
        # Test ID pattern validation - bad content_id
        bad_id_payload = {
            "content_id": "bad-id-format",  # Should be CONTENT-xxx
            "source_type": "text_markdown",
            "original_path": "/test/path.md"
        }
        is_valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.CONTENT_INGESTION,
            bad_id_payload
        )
        check("Invalid ID format caught", not is_valid)
        check("ID pattern error reported", any("Invalid ID format" in e for e in errors),
             f"Errors: {errors}")

        # Test enum validation - bad source_type
        bad_enum_payload = {
            "content_id": "CONTENT-test001",
            "source_type": "invalid_type",  # Not a valid ContentSourceType
            "original_path": "/test/path.md"
        }
        is_valid2, errors2, warnings2 = validate_ozolith_payload(
            OzolithEventType.CONTENT_INGESTION,
            bad_enum_payload
        )
        check("Invalid enum value caught", not is_valid2)
        check("Enum validation error reported", any("Invalid enum value" in e for e in errors2),
             f"Errors: {errors2}")

        # Test range validation - confidence out of bounds
        bad_range_payload = {
            "content": "test content",
            "confidence": 1.5  # Should be 0.0-1.0
        }
        is_valid3, errors3, warnings3 = validate_ozolith_payload(
            OzolithEventType.EXCHANGE,
            bad_range_payload
        )
        check("Out of range value caught", not is_valid3)
        check("Range validation error reported", any("out of range" in e for e in errors3),
             f"Errors: {errors3}")

        # Test valid payload with all validations passing
        good_payload = {
            "content_id": "CONTENT-abc123",
            "source_type": "text_markdown",
            "original_path": "/home/user/test.md",
            "pipeline_used": "curator",
            "processing_status": "completed"
        }
        is_valid4, errors4, warnings4 = validate_ozolith_payload(
            OzolithEventType.CONTENT_INGESTION,
            good_payload
        )
        check("Valid payload with enums passes", is_valid4)
        check("Valid payload has no errors", len(errors4) == 0, f"Errors: {errors4}")
    except Exception as e:
        check("Enhanced validation", False, str(e))

    # =============================================================================
    # Section 7: Citation References
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 7: Citation References")
    print("="*70)

    # 7.1 Create Different Citation Types
    print("\n7.1 Creating citation types...")
    try:
        # Contextual bookmark
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

        check("CONTEXTUAL_BOOKMARK citation created",
             bookmark_citation.citation_type == CitationType.CONTEXTUAL_BOOKMARK)

        # Document link
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

        check("DOCUMENT_LINK citation created",
             doc_citation.citation_type == CitationType.DOCUMENT_LINK)

        # Confidence anchor
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

        check("CONFIDENCE_ANCHOR citation created",
             confidence_citation.citation_type == CitationType.CONFIDENCE_ANCHOR)

        # ICK reference - inverse of GOLD (learning signal for mistakes)
        ick_citation = CitationReference(
            citation_id="CITE-004",
            citation_type=CitationType.ICK_REFERENCE,
            target_type="exchange",
            target_id="MSG-bad-advice",
            cited_from_context="SB-main",
            cited_at=datetime.utcnow().isoformat(),
            cited_by="assistant",
            relevance_note="This advice was wrong - don't use as reference",
            confidence_at_citation=0.1
        )
        check("ICK_REFERENCE citation created",
             ick_citation.citation_type == CitationType.ICK_REFERENCE)

        # Verify all citation types exist
        citation_type_count = len(CitationType)
        check("CitationType count == 6", citation_type_count == 6,
             f"Got {citation_type_count}")
        check("GOLD_REFERENCE exists", hasattr(CitationType, 'GOLD_REFERENCE'))
        check("ICK_REFERENCE exists", hasattr(CitationType, 'ICK_REFERENCE'))
    except Exception as e:
        check("Citation creation", False, str(e))

    # =============================================================================
    # Section 8: Extra Dict Evolution
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 8: Extra Dict Evolution")
    print("="*70)

    # 8.1 Test Extra Dict for Discovered Fields
    print("\n8.1 Testing extra dict on ContentReference...")
    try:
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

        check("ContentReference accepts extra dict", content_with_extra.extra is not None)
        check("Extra dict has custom fields", len(content_with_extra.extra) == 4)
        check("Extra dict values accessible", content_with_extra.extra.get('language') == 'python')
        check("Extra dict numeric values work", content_with_extra.extra.get('complexity_score') == 7.2)
    except Exception as e:
        check("ContentReference extra dict", False, str(e))

    # 8.2 Test Extra Dict in Re-embedding
    print("\n8.2 Testing extra dict on OzolithPayloadReembedding...")
    try:
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

        check("Reembedding accepts extra dict", reembed_with_quality.extra is not None)
        check("Extra dict has quality metrics", len(reembed_with_quality.extra) == 4)
        check("Quality issue type accessible",
             reembed_with_quality.extra.get('quality_issue_type') == 'low_retrieval_accuracy')
        check("Numeric quality metrics work",
             reembed_with_quality.extra.get('retrieval_failures_before') == 15)
    except Exception as e:
        check("Reembedding extra dict", False, str(e))

    # =============================================================================
    # Section 1b: Content Type → Pipeline Semantic Validation
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 1b: Content Type → Pipeline Semantic Validation")
    print("="*70)

    # Define expected pipeline mappings (test as specification)
    # This documents the architectural intent from datashapes.py comments
    EXPECTED_PIPELINE_FOR_TYPE = {
        # Text-based → Curator pipeline
        ContentSourceType.TEXT_PLAIN: ProcessingPipeline.CURATOR,
        ContentSourceType.TEXT_MARKDOWN: ProcessingPipeline.CURATOR,
        ContentSourceType.TEXT_CODE: ProcessingPipeline.CURATOR,
        ContentSourceType.TEXT_CONFIG: ProcessingPipeline.CURATOR,
        ContentSourceType.TEXT_LOG: ProcessingPipeline.CURATOR,

        # Document-based → Docling or Curator depending on complexity
        ContentSourceType.DOC_PDF_TEXT: ProcessingPipeline.CURATOR,       # Extractable text
        ContentSourceType.DOC_PDF_SCANNED: ProcessingPipeline.DOCLING,    # Needs OCR
        ContentSourceType.DOC_WORD: ProcessingPipeline.CURATOR,
        ContentSourceType.DOC_SPREADSHEET: ProcessingPipeline.CURATOR,

        # Visual media → Docling
        ContentSourceType.MEDIA_IMAGE: ProcessingPipeline.DOCLING,
        ContentSourceType.MEDIA_DIAGRAM: ProcessingPipeline.DOCLING,
        ContentSourceType.MEDIA_SCREENSHOT: ProcessingPipeline.DOCLING,

        # Audio/Video → Transcription
        ContentSourceType.MEDIA_AUDIO: ProcessingPipeline.TRANSCRIPTION,
        ContentSourceType.MEDIA_VIDEO: ProcessingPipeline.TRANSCRIPTION,

        # Internal → Direct (already in system format)
        ContentSourceType.EXCHANGE: ProcessingPipeline.DIRECT,
        ContentSourceType.SIDEBAR: ProcessingPipeline.DIRECT,

        # Unknown → Manual classification needed
        ContentSourceType.UNKNOWN: ProcessingPipeline.MANUAL,
    }

    print("\n1b.1 Verifying all content types have expected pipeline mapping...")
    check("All 17 content types have expected pipeline",
         len(EXPECTED_PIPELINE_FOR_TYPE) == 17,
         f"Got {len(EXPECTED_PIPELINE_FOR_TYPE)} mappings for 17 types")

    print("\n1b.2 Verifying semantic groupings (text types use CURATOR)...")
    text_type_pipelines = {t: EXPECTED_PIPELINE_FOR_TYPE[t] for t in ContentSourceType if t.value.startswith('text_')}
    check("All text types use CURATOR",
         all(p == ProcessingPipeline.CURATOR for p in text_type_pipelines.values()),
         f"Non-CURATOR text types: {[t.value for t, p in text_type_pipelines.items() if p != ProcessingPipeline.CURATOR]}")

    print("\n1b.3 Verifying audio/video use TRANSCRIPTION...")
    check("MEDIA_AUDIO uses TRANSCRIPTION",
         EXPECTED_PIPELINE_FOR_TYPE[ContentSourceType.MEDIA_AUDIO] == ProcessingPipeline.TRANSCRIPTION)
    check("MEDIA_VIDEO uses TRANSCRIPTION",
         EXPECTED_PIPELINE_FOR_TYPE[ContentSourceType.MEDIA_VIDEO] == ProcessingPipeline.TRANSCRIPTION)

    print("\n1b.4 Verifying visual media uses DOCLING...")
    visual_types = [ContentSourceType.MEDIA_IMAGE, ContentSourceType.MEDIA_DIAGRAM,
                    ContentSourceType.MEDIA_SCREENSHOT, ContentSourceType.DOC_PDF_SCANNED]
    visual_use_docling = all(EXPECTED_PIPELINE_FOR_TYPE[t] == ProcessingPipeline.DOCLING for t in visual_types)
    check("All visual media types use DOCLING", visual_use_docling,
         f"Non-DOCLING visual types: {[t.value for t in visual_types if EXPECTED_PIPELINE_FOR_TYPE[t] != ProcessingPipeline.DOCLING]}")

    print("\n1b.5 Verifying internal types use DIRECT...")
    check("EXCHANGE uses DIRECT",
         EXPECTED_PIPELINE_FOR_TYPE[ContentSourceType.EXCHANGE] == ProcessingPipeline.DIRECT)
    check("SIDEBAR uses DIRECT",
         EXPECTED_PIPELINE_FOR_TYPE[ContentSourceType.SIDEBAR] == ProcessingPipeline.DIRECT)

    # =============================================================================
    # Section 2b: Staleness Logic Deep Validation
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 2b: Staleness Logic Deep Validation")
    print("="*70)

    print("\n2b.1 Testing is_stale() with PAST date (should return True)...")
    try:
        stale_content = ContentReference(
            content_id="CONTENT-stale001",
            source_type=ContentSourceType.TEXT_CODE,
            original_path="/home/user/old_code.py",
            stale_after=(datetime.utcnow() - timedelta(days=7)).isoformat()  # 7 days ago
        )

        # Use imported is_stale from datashapes.py (takes string directly)
        check("is_stale returns True for past date", is_stale(stale_content.stale_after))
    except Exception as e:
        check("Stale past date test", False, str(e))

    print("\n2b.2 Testing STALENESS_DEFAULTS_DAYS coverage...")
    # Verify every content type has a default
    missing_defaults = [t for t in ContentSourceType if t not in STALENESS_DEFAULTS_DAYS]
    check("All content types have staleness default",
         len(missing_defaults) == 0,
         f"Missing: {[t.value for t in missing_defaults]}")

    print("\n2b.3 Testing staleness defaults are sensible...")
    # Code should be shorter than docs
    check("Code staleness < Doc staleness",
         STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_CODE] < STALENESS_DEFAULTS_DAYS[ContentSourceType.DOC_PDF_TEXT])
    # Config should be shortest (most volatile)
    check("Config staleness <= Code staleness",
         STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_CONFIG] <= STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_CODE])
    # Logs don't go stale (historical)
    check("Logs never go stale (None)",
         STALENESS_DEFAULTS_DAYS[ContentSourceType.TEXT_LOG] is None)
    # Internal content doesn't go stale
    check("Exchange never goes stale (None)",
         STALENESS_DEFAULTS_DAYS[ContentSourceType.EXCHANGE] is None)
    check("Sidebar never goes stale (None)",
         STALENESS_DEFAULTS_DAYS[ContentSourceType.SIDEBAR] is None)

    print("\n2b.4 Testing staleness_reason + staleness_note can coexist...")
    try:
        content_with_both = ContentReference(
            content_id="CONTENT-both001",
            source_type=ContentSourceType.TEXT_CODE,
            original_path="/home/user/api.py",
            staleness_reason=StalenessReason.SPRINT_CYCLE,
            staleness_note="Review after each 2-week sprint"
        )
        check("ContentReference accepts both staleness_reason and staleness_note",
             content_with_both.staleness_reason == StalenessReason.SPRINT_CYCLE and
             "sprint" in content_with_both.staleness_note.lower())
    except Exception as e:
        check("Staleness reason + note coexistence", False, str(e))

    print("\n2b.5 Testing all StalenessReason values explicitly...")
    expected_reasons = ['sprint_cycle', 'api_version', 'manual_review', 'time_decay',
                        'dependency_change', 'content_updated', 'unknown']
    actual_reasons = [r.value for r in StalenessReason]
    check("All 7 StalenessReason values exist",
         set(expected_reasons) == set(actual_reasons),
         f"Missing: {set(expected_reasons) - set(actual_reasons)}")

    # =============================================================================
    # Section 3b: Format Validation (COCO bbox, SMPTE timecode)
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 3b: Format Validation (COCO, SMPTE)")
    print("="*70)

    print("\n3b.1 Testing COCO bounding box constraints...")
    try:
        # Valid COCO bbox: x, y >= 0, width, height > 0
        valid_bbox = {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
        chunk_valid_bbox = ContentChunk(
            chunk_id="CHUNK-bbox-valid",
            parent_content_id="CONTENT-pdf",
            sequence=0,
            bounding_box=valid_bbox,
            coordinate_system="pdf"
        )
        check("Valid COCO bbox accepted", chunk_valid_bbox.bounding_box is not None)
        check("Valid bbox has all required keys",
             all(k in chunk_valid_bbox.bounding_box for k in ['x', 'y', 'width', 'height']))

        # Test bbox with zero-origin (valid)
        check("Zero-origin bbox is valid",
             chunk_valid_bbox.bounding_box['x'] >= 0 and chunk_valid_bbox.bounding_box['y'] >= 0)

        # Using imported is_valid_coco_bbox from datashapes.py (returns tuple)
        valid, _ = is_valid_coco_bbox(valid_bbox)
        check("is_valid_coco_bbox correctly validates good bbox", valid)

        valid, _ = is_valid_coco_bbox({"x": -10, "y": 0, "width": 100, "height": 50})
        check("is_valid_coco_bbox rejects negative x", not valid)

        valid, _ = is_valid_coco_bbox({"x": 0, "y": 0, "width": 0, "height": 50})
        check("is_valid_coco_bbox rejects zero width", not valid)

        valid, _ = is_valid_coco_bbox({"x": 0, "y": 0})
        check("is_valid_coco_bbox rejects missing keys", not valid)
    except Exception as e:
        check("COCO bbox validation", False, str(e))

    print("\n3b.2 Testing coordinate_system values...")
    try:
        pdf_chunk = ContentChunk(
            chunk_id="CHUNK-pdf-coord",
            parent_content_id="CONTENT-pdf",
            sequence=0,
            coordinate_system="pdf"
        )
        image_chunk = ContentChunk(
            chunk_id="CHUNK-img-coord",
            parent_content_id="CONTENT-img",
            sequence=0,
            coordinate_system="image"
        )
        check("'pdf' coordinate_system accepted", pdf_chunk.coordinate_system == "pdf")
        check("'image' coordinate_system accepted", image_chunk.coordinate_system == "image")

        # Document what coordinate systems mean
        # PDF: bottom-left origin, Y increases upward
        # Image: top-left origin, Y increases downward
        warn("coordinate_system semantics", "pdf=bottom-left origin (Y up), image=top-left origin (Y down)")
    except Exception as e:
        check("Coordinate system test", False, str(e))

    print("\n3b.3 Testing SMPTE timecode format validation...")
    try:
        # Using imported is_valid_smpte_timecode from datashapes.py (returns tuple)
        valid, _ = is_valid_smpte_timecode("00:05:30:00")
        check("Valid SMPTE timecode '00:05:30:00' accepted", valid)

        valid, _ = is_valid_smpte_timecode("23:59:59:29")
        check("Valid SMPTE timecode '23:59:59:29' accepted", valid)

        valid, _ = is_valid_smpte_timecode("5:30")
        check("Invalid SMPTE (bad format) rejected", not valid)

        valid, _ = is_valid_smpte_timecode("99:00:00:00")
        check("Invalid SMPTE (99 hours) rejected", not valid)

        valid, _ = is_valid_smpte_timecode("00:99:00:00")
        check("Invalid SMPTE (99 minutes) rejected", not valid)

        valid, _ = is_valid_smpte_timecode("00:00:99:00")
        check("Invalid SMPTE (99 seconds) rejected", not valid)

        # Test chunk with timecodes
        audio_chunk = ContentChunk(
            chunk_id="CHUNK-audio-tc",
            parent_content_id="CONTENT-podcast",
            sequence=0,
            start_timecode="00:00:00:00",
            end_timecode="00:05:00:00",
            frame_rate=29.97
        )
        check("Audio chunk timecodes stored correctly",
             audio_chunk.start_timecode == "00:00:00:00" and audio_chunk.end_timecode == "00:05:00:00")
    except Exception as e:
        check("SMPTE timecode validation", False, str(e))

    print("\n3b.4 Testing all 8 ChunkStrategy values explicitly...")
    expected_strategies = ['fixed_size', 'semantic', 'paragraph', 'sentence',
                           'page', 'sliding_window', 'code_block', 'custom']
    actual_strategies = [s.value for s in ChunkStrategy]
    check("All 8 ChunkStrategy values exist",
         set(expected_strategies) == set(actual_strategies),
         f"Missing: {set(expected_strategies) - set(actual_strategies)}")

    # =============================================================================
    # Section 4b: Relationship Completeness and Edge Cases
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 4b: Relationship Completeness and Edge Cases")
    print("="*70)

    print("\n4b.1 Verifying RELATIONSHIP_INVERSE_MAP completeness...")
    try:
        # Every relationship type should have an inverse mapping
        missing_from_map = [t for t in ContentRelationType if t not in RELATIONSHIP_INVERSE_MAP]
        check("All relationship types in inverse map",
             len(missing_from_map) == 0,
             f"Missing: {[t.value for t in missing_from_map]}")

        # Verify inverses are reflexive: inverse(inverse(X)) == X
        reflexive_failures = []
        for rel_type, inverse_type in RELATIONSHIP_INVERSE_MAP.items():
            double_inverse = RELATIONSHIP_INVERSE_MAP.get(inverse_type)
            if double_inverse != rel_type:
                reflexive_failures.append(f"{rel_type.value} -> {inverse_type.value} -> {double_inverse}")
        check("Inverse mapping is reflexive (inverse of inverse = original)",
             len(reflexive_failures) == 0,
             f"Non-reflexive: {reflexive_failures}")
    except Exception as e:
        check("Inverse map completeness", False, str(e))

    print("\n4b.2 Testing all 17 ContentRelationType values explicitly...")
    expected_rel_types = [
        'contains', 'contained_by', 'imports', 'imported_by',
        'depends_on', 'dependency_of', 'references', 'referenced_by',
        'version_of', 'superseded_by', 'derived_from', 'source_of',
        'duplicate_of', 'has_duplicate', 'contradicts', 'contradicted_by',
        'related_to'
    ]
    actual_rel_types = [r.value for r in ContentRelationType]
    check("All 17 ContentRelationType values exist",
         set(expected_rel_types) == set(actual_rel_types),
         f"Missing: {set(expected_rel_types) - set(actual_rel_types)}, Extra: {set(actual_rel_types) - set(expected_rel_types)}")

    print("\n4b.3 Testing self-referential relationship (source == target)...")
    try:
        # Document: A document can reference itself (e.g., "see section 3 above")
        self_ref = ContentRelationship(
            relationship_id="REL-self-001",
            relationship_type=ContentRelationType.REFERENCES,
            source_content_id="CONTENT-doc-001",
            target_content_id="CONTENT-doc-001",  # Same as source
            created_by="human",
            relationship_note="Internal cross-reference within document"
        )
        check("Self-referential relationship allowed",
             self_ref.source_content_id == self_ref.target_content_id)
    except Exception as e:
        check("Self-referential relationship", False, str(e))

    print("\n4b.4 Testing create_bidirectional_relationship edge cases...")
    try:
        # Test with RELATED_TO (self-inverse)
        forward, inverse = create_bidirectional_relationship(
            source_content_id="CONTENT-a",
            target_content_id="CONTENT-b",
            relationship_type=ContentRelationType.RELATED_TO,
            created_by="test"
        )
        check("RELATED_TO forward is RELATED_TO", forward.relationship_type == ContentRelationType.RELATED_TO)
        check("RELATED_TO inverse is also RELATED_TO", inverse.relationship_type == ContentRelationType.RELATED_TO)

        # Test that both have linked IDs in extra
        check("Forward has has_inverse marker", forward.extra.get("has_inverse") == True)
        check("Inverse has is_inverse marker", inverse.extra.get("is_inverse") == True)
    except Exception as e:
        check("Bidirectional edge cases", False, str(e))

    # =============================================================================
    # Section 5b: No-Delete Enforcement and Disposition Semantics
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 5b: No-Delete Enforcement and Disposition Semantics")
    print("="*70)

    print("\n5b.1 Verifying no 'delete' in EmbeddingDisposition...")
    try:
        disposition_values = [d.value.lower() for d in EmbeddingDisposition]
        check("No 'delete' in disposition values", 'delete' not in disposition_values)
        check("No 'deleted' in disposition values", 'deleted' not in disposition_values)
        check("No 'remove' in disposition values", 'remove' not in disposition_values)
        check("No 'purge' in disposition values", 'purge' not in disposition_values)
    except Exception as e:
        check("No-delete enforcement", False, str(e))

    print("\n5b.2 Testing disposition semantic differences...")
    try:
        # Document what each disposition means
        disposition_semantics = {
            EmbeddingDisposition.ARCHIVED: "Moved to archive, still accessible, may be referenced",
            EmbeddingDisposition.KEPT_AS_FALLBACK: "Still active as backup if new embedding has issues",
            EmbeddingDisposition.SUPERSEDED: "Marked as replaced, kept for history, not active",
            EmbeddingDisposition.CORRECTED: "Was wrong - don't use as fallback, learning signal, propagates distrust"
        }

        check("All 4 dispositions have documented semantics",
             len(disposition_semantics) == len(EmbeddingDisposition))

        # CORRECTED should be distinct - it's a "we were wrong" signal
        corrected = EmbeddingDisposition.CORRECTED
        check("CORRECTED exists as learning signal", corrected.value == "corrected")
    except Exception as e:
        check("Disposition semantics", False, str(e))

    print("\n5b.3 Testing all 8 ReembedTrigger values explicitly...")
    expected_triggers = ['model_upgrade', 'quality_issue', 'scheduled_refresh',
                         'manual_request', 'content_updated', 'batch_migration',
                         'drift_detected', 'fuckery_detected']
    actual_triggers = [t.value for t in ReembedTrigger]
    check("All 8 ReembedTrigger values exist",
         set(expected_triggers) == set(actual_triggers),
         f"Missing: {set(expected_triggers) - set(actual_triggers)}")

    print("\n5b.4 Testing FUCKERY_DETECTED trigger semantics...")
    try:
        # FUCKERY_DETECTED should trigger re-embed with CORRECTED disposition
        fuckery_reembed = OzolithPayloadReembedding(
            content_id="CONTENT-fuckery001",
            previous_embedding_id="EMB-old",
            new_embedding_id="EMB-new",
            trigger_reason=ReembedTrigger.FUCKERY_DETECTED.value,
            old_embedding_disposition=EmbeddingDisposition.CORRECTED.value  # Not just archived!
        )
        check("FUCKERY_DETECTED can use CORRECTED disposition",
             fuckery_reembed.trigger_reason == "fuckery_detected" and
             fuckery_reembed.old_embedding_disposition == "corrected")
    except Exception as e:
        check("FUCKERY_DETECTED semantics", False, str(e))

    # =============================================================================
    # Section 6b: Payload Instantiation and Multi-Error Validation
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 6b: Payload Instantiation and Multi-Error Validation")
    print("="*70)

    print("\n6b.1 Testing OzolithPayloadContentStale instantiation...")
    try:
        from datashapes import OzolithPayloadContentStale

        stale_payload = OzolithPayloadContentStale(
            content_id="CONTENT-stale001",
            stale_after="2025-12-01T00:00:00",
            detected_at="2025-12-15T10:30:00",
            staleness_reason="sprint_cycle",
            days_overdue=14,
            recommended_action="re_verify"
        )
        check("OzolithPayloadContentStale created successfully", stale_payload is not None)
        check("Stale payload has content_id", stale_payload.content_id == "CONTENT-stale001")
        check("Stale payload has days_overdue", stale_payload.days_overdue == 14)
    except Exception as e:
        check("OzolithPayloadContentStale instantiation", False, str(e))

    print("\n6b.2 Testing OzolithPayloadRelationshipCreated instantiation...")
    try:
        from datashapes import OzolithPayloadRelationshipCreated

        rel_payload = OzolithPayloadRelationshipCreated(
            relationship_id="REL-001",
            relationship_type="contains",
            source_content_id="CONTENT-pdf001",
            target_content_id="CONTENT-img001",
            confidence=0.95,
            bidirectional=True,
            inverse_relationship_id="REL-002"
        )
        check("OzolithPayloadRelationshipCreated created successfully", rel_payload is not None)
        check("Relationship payload has bidirectional flag", rel_payload.bidirectional == True)
        check("Relationship payload has inverse_relationship_id", rel_payload.inverse_relationship_id == "REL-002")
    except Exception as e:
        check("OzolithPayloadRelationshipCreated instantiation", False, str(e))

    print("\n6b.3 Testing OzolithPayloadFuckeryDetected instantiation...")
    try:
        from datashapes import OzolithPayloadFuckeryDetected

        fuckery_payload = OzolithPayloadFuckeryDetected(
            detection_type="hash_mismatch",
            affected_ids=["CONTENT-001", "CONTENT-002"],
            evidence_summary="Hash of CONTENT-001 doesn't match stored value",
            severity="critical",
            recommended_action="quarantine"
        )
        check("OzolithPayloadFuckeryDetected created successfully", fuckery_payload is not None)
        check("Fuckery payload has affected_ids list", len(fuckery_payload.affected_ids) == 2)
        check("Fuckery payload has severity", fuckery_payload.severity == "critical")
    except Exception as e:
        check("OzolithPayloadFuckeryDetected instantiation", False, str(e))

    print("\n6b.4 Testing validation with MULTIPLE errors...")
    try:
        # Payload with multiple problems
        multi_error_payload = {
            "content_id": "bad-id",           # Bad ID format
            "source_type": "invalid_type",    # Invalid enum
            "original_path": ""               # Empty required field
        }

        is_valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.CONTENT_INGESTION,
            multi_error_payload
        )

        check("Multi-error payload is invalid", not is_valid)
        check("Multiple errors reported (at least 2)", len(errors) >= 2,
             f"Only got {len(errors)} error(s): {errors}")

        # Check specific errors are reported
        has_id_error = any("ID format" in e or "content_id" in e for e in errors)
        has_enum_error = any("enum" in e.lower() or "source_type" in e for e in errors)
        has_empty_error = any("empty" in e.lower() or "original_path" in e for e in errors)

        check("ID format error reported", has_id_error, f"Errors: {errors}")
        check("Enum validation error reported", has_enum_error, f"Errors: {errors}")
        check("Empty required field error reported", has_empty_error, f"Errors: {errors}")
    except Exception as e:
        check("Multi-error validation", False, str(e))

    print("\n6b.5 Testing validation reports ALL errors, not just first...")
    try:
        # Different bad payload
        another_bad_payload = {
            "citation_id": "not-cite-format",    # Bad
            "citation_type": "invalid",          # Bad
            "target_id": ""                      # Empty
        }

        is_valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.CITATION_CREATED,
            another_bad_payload
        )

        check("Citation multi-error reports >= 2 errors", len(errors) >= 2,
             f"Got {len(errors)} error(s)")
    except Exception as e:
        check("Citation multi-error validation", False, str(e))

    # =============================================================================
    # Section 7b: Citation Semantic Validation
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 7b: Citation Semantic Validation")
    print("="*70)

    print("\n7b.1 Testing all 6 CitationType values explicitly...")
    expected_citation_types = ['contextual_bookmark', 'document_link', 'relationship_marker',
                               'confidence_anchor', 'gold_reference', 'ick_reference']
    actual_citation_types = [c.value for c in CitationType]
    check("All 6 CitationType values exist",
         set(expected_citation_types) == set(actual_citation_types),
         f"Missing: {set(expected_citation_types) - set(actual_citation_types)}")

    print("\n7b.2 Testing GOLD vs ICK semantic inverses...")
    try:
        # GOLD = high confidence, trusted anchor
        gold_cite = CitationReference(
            citation_id="CITE-gold-001",
            citation_type=CitationType.GOLD_REFERENCE,
            target_type="exchange",
            target_id="MSG-trusted",
            confidence_at_citation=0.95  # High confidence
        )

        # ICK = low confidence, "this was wrong"
        ick_cite = CitationReference(
            citation_id="CITE-ick-001",
            citation_type=CitationType.ICK_REFERENCE,
            target_type="exchange",
            target_id="MSG-wrong",
            confidence_at_citation=0.1  # Low confidence
        )

        check("GOLD_REFERENCE has high confidence",
             gold_cite.confidence_at_citation >= 0.8 if gold_cite.confidence_at_citation else False)
        check("ICK_REFERENCE has low confidence",
             ick_cite.confidence_at_citation <= 0.3 if ick_cite.confidence_at_citation else False)

        # Document semantic expectation
        warn("GOLD vs ICK semantics",
             "GOLD = trusted anchor (confidence boost), ICK = learning signal (confidence reducer)")
    except Exception as e:
        check("GOLD vs ICK semantics", False, str(e))

    print("\n7b.3 Testing confidence_at_citation bounds...")
    try:
        # Valid confidence (0.0 - 1.0)
        valid_cite = CitationReference(
            citation_id="CITE-valid",
            citation_type=CitationType.CONFIDENCE_ANCHOR,
            target_type="content",
            target_id="CONTENT-001",
            confidence_at_citation=0.75
        )
        check("Valid confidence (0.75) accepted", valid_cite.confidence_at_citation == 0.75)

        # Using imported is_valid_confidence from datashapes.py (returns tuple)
        valid, _ = is_valid_confidence(0.0)
        check("is_valid_confidence(0.0) = True", valid)

        valid, _ = is_valid_confidence(1.0)
        check("is_valid_confidence(1.0) = True", valid)

        valid, _ = is_valid_confidence(0.5)
        check("is_valid_confidence(0.5) = True", valid)

        valid, _ = is_valid_confidence(1.5)
        check("is_valid_confidence(1.5) = False", not valid)

        valid, _ = is_valid_confidence(-0.1)
        check("is_valid_confidence(-0.1) = False", not valid)

        valid, _ = is_valid_confidence(None)
        check("is_valid_confidence(None) = True (optional)", valid)
    except Exception as e:
        check("Confidence bounds validation", False, str(e))

    # =============================================================================
    # Section 8b: Extra Dict Coverage and Serialization
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 8b: Extra Dict Coverage and Serialization")
    print("="*70)

    print("\n8b.1 Testing OzolithAnchor has extra field...")
    try:
        from datashapes import OzolithAnchor

        anchor = OzolithAnchor(
            anchor_id="ANCHOR-001",
            timestamp=datetime.utcnow().isoformat(),
            sequence_range=(0, 100),
            root_hash="abc123",
            entry_count=100,
            extra={"custom_field": "test_value", "numeric": 42}
        )
        check("OzolithAnchor accepts extra dict", anchor.extra is not None)
        check("OzolithAnchor extra has custom fields", anchor.extra.get("custom_field") == "test_value")
    except Exception as e:
        check("OzolithAnchor extra field", False, str(e))

    print("\n8b.2 Testing ArchivedSidebar has extra field...")
    try:
        from datashapes import ArchivedSidebar

        archived = ArchivedSidebar(
            archived_by="test_agent",
            archive_reason="manual",
            summary="Test archive",
            extra={"archive_metadata": "test", "version": 2}
        )
        check("ArchivedSidebar accepts extra dict", archived.extra is not None)
        check("ArchivedSidebar extra has custom fields", archived.extra.get("archive_metadata") == "test")
    except Exception as e:
        check("ArchivedSidebar extra field", False, str(e))

    print("\n8b.3 Testing payload_to_dict serialization with extra...")
    try:
        from datashapes import payload_to_dict, OzolithPayloadExchange

        exchange_payload = OzolithPayloadExchange(
            content="Test content",
            confidence=0.9,
            reasoning_type="inference",
            extra={"custom_metric": 0.75, "tags": ["test", "validation"]}
        )

        serialized = payload_to_dict(exchange_payload)

        check("payload_to_dict produces dict", isinstance(serialized, dict))
        check("Serialized has content field", serialized.get("content") == "Test content")
        check("Serialized has confidence field", serialized.get("confidence") == 0.9)
        # Extra fields should be merged into main dict
        check("Extra fields merged (custom_metric)", serialized.get("custom_metric") == 0.75)
        check("Extra fields merged (tags)", serialized.get("tags") == ["test", "validation"])
        check("'extra' key removed after merge", "extra" not in serialized)
    except Exception as e:
        check("payload_to_dict serialization", False, str(e))

    print("\n8b.4 Testing dict_to_payload deserialization with unknown fields...")
    try:
        from datashapes import dict_to_payload

        # Dict with known and unknown fields
        payload_dict = {
            "content": "Test content",
            "confidence": 0.85,
            "unknown_field": "should go to extra",
            "another_unknown": 123
        }

        reconstituted = dict_to_payload(OzolithEventType.EXCHANGE, payload_dict)

        check("dict_to_payload returns typed payload",
             isinstance(reconstituted, OzolithPayloadExchange))
        check("Known fields restored", reconstituted.content == "Test content")
        check("Unknown fields in extra", "unknown_field" in reconstituted.extra)
        check("Unknown field values preserved", reconstituted.extra.get("another_unknown") == 123)
    except Exception as e:
        check("dict_to_payload deserialization", False, str(e))

    print("\n8b.5 Testing deeply nested extra values...")
    try:
        nested_extra = {
            "level1": {
                "level2": {
                    "level3": "deep value"
                },
                "list_value": [1, 2, 3]
            }
        }

        content_with_nested = ContentReference(
            content_id="CONTENT-nested",
            source_type=ContentSourceType.TEXT_CODE,
            original_path="/test/path.py",
            extra=nested_extra
        )

        check("Deeply nested extra accepted", content_with_nested.extra is not None)
        check("Nested dict preserved",
             content_with_nested.extra.get("level1", {}).get("level2", {}).get("level3") == "deep value")
        check("Nested list preserved",
             content_with_nested.extra.get("level1", {}).get("list_value") == [1, 2, 3])
    except Exception as e:
        check("Deeply nested extra", False, str(e))

    # =============================================================================
    # Section 9: Integration Tests
    # =============================================================================
    print("\n" + "="*70)
    print("SECTION 9: Integration Tests")
    print("="*70)

    print("\n9.1 Testing datashapes.py validators (not inline duplicates)...")
    try:
        # These now come from datashapes.py, not defined inline in tests
        valid, msg = is_valid_coco_bbox({"x": 10, "y": 20, "width": 100, "height": 50})
        check("datashapes.is_valid_coco_bbox validates good bbox", valid and msg == "")

        valid, msg = is_valid_coco_bbox({"x": -10, "y": 20, "width": 100, "height": 50})
        check("datashapes.is_valid_coco_bbox rejects negative x", not valid and "x must be" in msg)

        valid, msg = is_valid_smpte_timecode("00:05:30:00")
        check("datashapes.is_valid_smpte_timecode validates good timecode", valid and msg == "")

        valid, msg = is_valid_smpte_timecode("99:00:00:00")
        check("datashapes.is_valid_smpte_timecode rejects bad hours", not valid and "Hours" in msg)

        valid, msg = is_valid_confidence(0.75)
        check("datashapes.is_valid_confidence validates good confidence", valid and msg == "")

        valid, msg = is_valid_confidence(1.5)
        check("datashapes.is_valid_confidence rejects out of range", not valid and "must be" in msg)
    except Exception as e:
        check("datashapes.py validators", False, str(e))

    print("\n9.2 Testing __post_init__ validation (default=True, can opt out)...")
    try:
        # Explicit validate=False lets bad data through (opt out of safety)
        bad_chunk_no_validate = ContentChunk(
            chunk_id="CHUNK-bad",
            parent_content_id="CONTENT-parent",
            sequence=0,
            bounding_box={"x": -999, "y": 0, "width": 0, "height": 50},  # Invalid!
            validate=False  # Opt out of validation
        )
        check("validate=False allows invalid data (opt-out)", bad_chunk_no_validate is not None)

        # Default (validation on) should raise ValidationError for bad data
        validation_raised = False
        try:
            bad_chunk_default = ContentChunk(
                chunk_id="CHUNK-bad",
                parent_content_id="CONTENT-parent",
                sequence=0,
                bounding_box={"x": -999, "y": 0, "width": 0, "height": 50},  # Invalid!
                # No validate= parameter - defaults to True now!
            )
        except ValidationError as ve:
            validation_raised = True
            check("ValidationError contains bbox error", "bounding_box" in str(ve))

        check("Default validation (True) rejects invalid data", validation_raised)
    except Exception as e:
        check("ContentChunk __post_init__ validation", False, str(e))

    print("\n9.3 Testing __post_init__ validation rejects invalid timecodes...")
    try:
        validation_raised = False
        try:
            bad_timecode_chunk = ContentChunk(
                chunk_id="CHUNK-badtc",
                parent_content_id="CONTENT-parent",
                sequence=0,
                start_timecode="99:99:99:99",  # Invalid!
                validate=True
            )
        except ValidationError as ve:
            validation_raised = True
            check("ValidationError contains timecode error", "start_timecode" in str(ve))

        check("Invalid timecode raises ValidationError", validation_raised)
    except Exception as e:
        check("Timecode validation", False, str(e))

    print("\n9.4 Testing __post_init__ validation on ContentRelationship...")
    try:
        # Invalid confidence
        validation_raised = False
        try:
            bad_rel = ContentRelationship(
                relationship_id="REL-bad",
                relationship_type=ContentRelationType.CONTAINS,
                source_content_id="CONTENT-a",
                target_content_id="CONTENT-b",
                confidence=2.0,  # Invalid! Must be 0-1
                validate=True
            )
        except ValidationError as ve:
            validation_raised = True
            check("ValidationError contains confidence error", "confidence" in str(ve))

        check("Invalid relationship confidence raises ValidationError", validation_raised)

        # Empty source_content_id
        validation_raised = False
        try:
            empty_source_rel = ContentRelationship(
                relationship_id="REL-empty",
                relationship_type=ContentRelationType.CONTAINS,
                source_content_id="",  # Invalid!
                target_content_id="CONTENT-b",
                validate=True
            )
        except ValidationError as ve:
            validation_raised = True
            check("ValidationError contains empty ID error", "source_content_id" in str(ve))

        check("Empty source_content_id raises ValidationError", validation_raised)
    except Exception as e:
        check("ContentRelationship validation", False, str(e))

    print("\n9.5 Testing CitationReference semantic warnings (GOLD/ICK)...")
    try:
        # GOLD with low confidence should add warning
        gold_low = CitationReference(
            citation_id="CITE-gold-low",
            citation_type=CitationType.GOLD_REFERENCE,
            target_id="MSG-test",
            confidence_at_citation=0.3,  # Low for GOLD!
            validate=True
        )
        check("GOLD with low confidence stores warning",
             'validation_warnings' in gold_low.extra and
             any("GOLD_REFERENCE" in w for w in gold_low.extra['validation_warnings']))

        # ICK with high confidence should add warning
        ick_high = CitationReference(
            citation_id="CITE-ick-high",
            citation_type=CitationType.ICK_REFERENCE,
            target_id="MSG-test",
            confidence_at_citation=0.9,  # High for ICK!
            validate=True
        )
        check("ICK with high confidence stores warning",
             'validation_warnings' in ick_high.extra and
             any("ICK_REFERENCE" in w for w in ick_high.extra['validation_warnings']))

        # GOLD with appropriate confidence should NOT warn
        gold_good = CitationReference(
            citation_id="CITE-gold-good",
            citation_type=CitationType.GOLD_REFERENCE,
            target_id="MSG-test",
            confidence_at_citation=0.95,  # Appropriate for GOLD
            validate=True
        )
        check("GOLD with high confidence has no warnings",
             'validation_warnings' not in gold_good.extra or len(gold_good.extra.get('validation_warnings', [])) == 0)
    except Exception as e:
        check("CitationReference semantic validation", False, str(e))

    print("\n9.6 Testing calculate_stale_after applies defaults...")
    try:
        # TEXT_CODE should have 14 day default
        code_stale_after = calculate_stale_after(ContentSourceType.TEXT_CODE)
        check("calculate_stale_after returns string for TEXT_CODE",
             code_stale_after is not None and isinstance(code_stale_after, str))

        # Parse and verify it's ~14 days in the future
        stale_date = datetime.fromisoformat(code_stale_after)
        days_diff = (stale_date - datetime.utcnow()).days
        check("TEXT_CODE stale_after is ~14 days from now",
             13 <= days_diff <= 14)  # Allow for timing

        # TEXT_LOG should return None (never stales)
        log_stale_after = calculate_stale_after(ContentSourceType.TEXT_LOG)
        check("calculate_stale_after returns None for TEXT_LOG", log_stale_after is None)

        # get_staleness_default_days returns correct values
        check("get_staleness_default_days(TEXT_CODE) == 14",
             get_staleness_default_days(ContentSourceType.TEXT_CODE) == 14)
        check("get_staleness_default_days(TEXT_CONFIG) == 7",
             get_staleness_default_days(ContentSourceType.TEXT_CONFIG) == 7)
    except Exception as e:
        check("calculate_stale_after", False, str(e))

    print("\n9.7 Testing get_pipeline_for_content_type...")
    try:
        check("TEXT_CODE maps to CURATOR",
             get_pipeline_for_content_type(ContentSourceType.TEXT_CODE) == ProcessingPipeline.CURATOR)
        check("MEDIA_VIDEO maps to TRANSCRIPTION",
             get_pipeline_for_content_type(ContentSourceType.MEDIA_VIDEO) == ProcessingPipeline.TRANSCRIPTION)
        check("MEDIA_IMAGE maps to DOCLING",
             get_pipeline_for_content_type(ContentSourceType.MEDIA_IMAGE) == ProcessingPipeline.DOCLING)
        check("EXCHANGE maps to DIRECT",
             get_pipeline_for_content_type(ContentSourceType.EXCHANGE) == ProcessingPipeline.DIRECT)
        check("UNKNOWN maps to MANUAL",
             get_pipeline_for_content_type(ContentSourceType.UNKNOWN) == ProcessingPipeline.MANUAL)
    except Exception as e:
        check("get_pipeline_for_content_type", False, str(e))

    print("\n9.8 Testing create_bidirectional_relationship output validates correctly...")
    try:
        forward, inverse = create_bidirectional_relationship(
            source_content_id="CONTENT-pdf-001",
            target_content_id="CONTENT-img-001",
            relationship_type=ContentRelationType.CONTAINS,
            created_by="test_suite",
            confidence=0.95
        )

        # Convert to OZOLITH payload format
        from datashapes import OzolithPayloadRelationshipCreated

        forward_payload = OzolithPayloadRelationshipCreated(
            relationship_id=forward.relationship_id,
            relationship_type=forward.relationship_type.value,
            source_content_id=forward.source_content_id,
            target_content_id=forward.target_content_id,
            confidence=forward.confidence,
            bidirectional=True
        )

        # Validate through OZOLITH validation
        payload_dict = {
            "relationship_id": forward.relationship_id,
            "relationship_type": forward.relationship_type.value,
            "source_content_id": forward.source_content_id,
            "target_content_id": forward.target_content_id,
            "confidence": forward.confidence
        }

        is_valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.RELATIONSHIP_CREATED,
            payload_dict
        )

        check("create_bidirectional_relationship output validates via OZOLITH", is_valid,
             f"Errors: {errors}")
    except Exception as e:
        check("Bidirectional relationship → OZOLITH validation", False, str(e))

    print("\n9.9 Testing serialize → deserialize → serialize roundtrip...")
    try:
        from datashapes import OzolithPayloadExchange

        # Create original payload
        original = OzolithPayloadExchange(
            content="Test content for roundtrip",
            confidence=0.85,
            reasoning_type="inference",
            context_depth=3,
            extra={"custom_field": "test_value", "nested": {"a": 1}}
        )

        # Serialize
        serialized = payload_to_dict(original)
        check("Serialize produces dict", isinstance(serialized, dict))

        # Deserialize
        deserialized = dict_to_payload(OzolithEventType.EXCHANGE, serialized)
        check("Deserialize produces typed payload",
             isinstance(deserialized, OzolithPayloadExchange))

        # Verify content preserved
        check("Content preserved through roundtrip",
             deserialized.content == original.content)
        check("Confidence preserved through roundtrip",
             deserialized.confidence == original.confidence)
        check("Custom extra fields preserved",
             deserialized.extra.get("custom_field") == "test_value")

        # Serialize again
        re_serialized = payload_to_dict(deserialized)
        check("Re-serialization produces dict", isinstance(re_serialized, dict))

        # Compare (ignoring extra merging differences)
        check("Roundtrip preserves content field",
             serialized.get("content") == re_serialized.get("content"))
        check("Roundtrip preserves confidence field",
             serialized.get("confidence") == re_serialized.get("confidence"))
    except Exception as e:
        check("Serialize roundtrip", False, str(e))

    print("\n9.10 Testing is_stale function from datashapes.py...")
    try:
        # Past date should be stale
        past_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        check("is_stale returns True for past date", is_stale(past_date))

        # Future date should not be stale
        future_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        check("is_stale returns False for future date", not is_stale(future_date))

        # None should not be stale
        check("is_stale returns False for None", not is_stale(None))

        # Invalid format should not crash (returns False)
        check("is_stale handles invalid format gracefully", not is_stale("not-a-date"))
    except Exception as e:
        check("is_stale function", False, str(e))

    print("\n9.11 Testing factory functions...")
    try:
        from datashapes import (
            create_content_reference, create_content_chunk, create_citation,
            generate_id, ValidationResult
        )

        # Test generate_id
        id1 = generate_id("TEST")
        id2 = generate_id("TEST")
        check("generate_id produces prefixed ID", id1.startswith("TEST-"))
        check("generate_id produces unique IDs", id1 != id2)
        check("generate_id produces reasonable length", 15 <= len(id1) <= 25)

        # Test create_content_reference
        ref = create_content_reference(
            ContentSourceType.TEXT_CODE,
            "/home/user/code.py"
        )
        check("create_content_reference produces valid ContentReference",
             isinstance(ref, ContentReference))
        check("create_content_reference auto-generates CONTENT- ID",
             ref.content_id.startswith("CONTENT-"))
        check("create_content_reference applies staleness default",
             ref.stale_after is not None)  # TEXT_CODE has 14 day default
        check("create_content_reference sets created_at",
             ref.created_at != "")

        # Test create_content_reference with EXCHANGE (no staleness default)
        exchange_ref = create_content_reference(
            ContentSourceType.EXCHANGE,
            ""  # Internal types don't need path
        )
        check("EXCHANGE type has None stale_after (never stales)",
             exchange_ref.stale_after is None)

        # Test create_content_reference with custom ID
        custom_ref = create_content_reference(
            ContentSourceType.TEXT_PLAIN,
            "/test/path.txt",
            content_id="CONTENT-custom123"
        )
        check("create_content_reference accepts custom ID",
             custom_ref.content_id == "CONTENT-custom123")

        # Test create_content_chunk
        chunk = create_content_chunk("CONTENT-parent123", 0)
        check("create_content_chunk produces valid ContentChunk",
             isinstance(chunk, ContentChunk))
        check("create_content_chunk auto-generates chunk ID",
             chunk.chunk_id == "CHUNK-parent123-0")

        # Test create_citation
        cite = create_citation(
            CitationType.GOLD_REFERENCE,
            "MSG-trusted-001",
            confidence_at_citation=0.95
        )
        check("create_citation produces valid CitationReference",
             isinstance(cite, CitationReference))
        check("create_citation auto-generates CITE- ID",
             cite.citation_id.startswith("CITE-"))
        check("create_citation sets cited_at timestamp",
             cite.cited_at != "")

        # Test ValidationResult
        result = ValidationResult(
            is_valid=False,
            errors=["error1", "error2"],
            warnings=["warning1"]
        )
        check("ValidationResult stores errors", len(result.errors) == 2)
        check("ValidationResult stores warnings", len(result.warnings) == 1)

        # Test raise_if_invalid
        raised = False
        try:
            result.raise_if_invalid()
        except ValidationError:
            raised = True
        check("ValidationResult.raise_if_invalid raises for invalid", raised)

        # Valid result should not raise
        valid_result = ValidationResult(is_valid=True)
        raised = False
        try:
            valid_result.raise_if_invalid()
        except ValidationError:
            raised = True
        check("ValidationResult.raise_if_invalid does not raise for valid", not raised)

    except Exception as e:
        check("Factory functions", False, str(e))

    print("\n9.12 Testing ContentReference validation (new)...")
    try:
        # Valid ContentReference should work
        valid_ref = ContentReference(
            content_id="CONTENT-valid123",
            source_type=ContentSourceType.TEXT_CODE,
            original_path="/home/user/code.py"
        )
        check("Valid ContentReference passes validation", valid_ref is not None)

        # Invalid content_id format should fail
        raised = False
        try:
            bad_id_ref = ContentReference(
                content_id="BAD-FORMAT",  # Should start with CONTENT-
                source_type=ContentSourceType.TEXT_CODE,
                original_path="/home/user/code.py"
            )
        except ValidationError as ve:
            raised = True
            check("ValidationError mentions content_id", "content_id" in str(ve))
        check("Invalid content_id format raises ValidationError", raised)

        # Missing original_path for non-internal type should fail
        raised = False
        try:
            no_path_ref = ContentReference(
                content_id="CONTENT-nopath",
                source_type=ContentSourceType.TEXT_CODE,
                original_path=""  # Required for TEXT_CODE
            )
        except ValidationError as ve:
            raised = True
            check("ValidationError mentions original_path", "original_path" in str(ve))
        check("Missing original_path raises ValidationError", raised)

        # EXCHANGE type without original_path should be OK
        exchange_ref = ContentReference(
            content_id="CONTENT-exchange",
            source_type=ContentSourceType.EXCHANGE,
            original_path=""  # OK for internal types
        )
        check("EXCHANGE type allows empty original_path", exchange_ref is not None)

        # Invalid stale_after format should fail
        raised = False
        try:
            bad_stale_ref = ContentReference(
                content_id="CONTENT-badstale",
                source_type=ContentSourceType.EXCHANGE,
                stale_after="not-a-timestamp"
            )
        except ValidationError as ve:
            raised = True
            check("ValidationError mentions stale_after", "stale_after" in str(ve))
        check("Invalid stale_after format raises ValidationError", raised)

    except Exception as e:
        check("ContentReference validation", False, str(e))

    # =============================================================================
    # SUMMARY
    # =============================================================================
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = len(results["passed"])
    failed = len(results["failed"])
    warnings = len(results["warnings"])
    total = passed + failed

    print(f"\nPassed:   {passed}/{total}")
    print(f"Failed:   {failed}/{total}")
    print(f"Warnings: {warnings}")

    if results["failed"]:
        print("\n--- FAILURES ---")
        for name, details in results["failed"]:
            print(f"  {name}: {details}")

    if results["warnings"]:
        print("\n--- WARNINGS ---")
        for name, message in results["warnings"]:
            print(f"  {name}: {message}")

    print("\n" + "="*70)
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{failed} TEST(S) FAILED")
    print("="*70)

    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)
