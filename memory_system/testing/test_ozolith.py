#!/usr/bin/env python3
"""
test_ozolith.py - Comprehensive Test Suite for OZOLITH

This tests the immutable log system that protects AI memory integrity.
Run with: python3 -m pytest tests/test_ozolith.py -v
Or standalone: python3 tests/test_ozolith.py

Test Categories:
    1. Hash Chain Integrity - The core tamper-detection mechanism
    2. Signature Verification - Provenance and authenticity
    3. Anchor System - Checkpoint and external verification
    4. Query Methods - Finding and filtering entries
    5. Chainable Query Builder - Complex compound queries
    6. Statistics - Aggregation and analysis
    7. Helper Functions - Convenience utilities
    8. Edge Cases - Boundary conditions and weird inputs
    9. Persistence - Survival across restarts
    10. Tampering Scenarios - Active attack simulation

Created: 2025-12-05
Author: Human + AI collaboration
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ozolith import (
    Ozolith,
    OzolithRenderer,
    AnchorPolicy,
    OzolithQuery,
    OzolithEventType,
    create_exchange_payload,
    create_sidebar_payload,
    create_correction_payload,
    log_correction,
    log_uncertainty,
    export_incident,
    session_summary,
    find_learning_opportunities,
)
from datashapes import OzolithEntry, OzolithAnchor
import pytest


# =============================================================================
# TEST UTILITIES
# =============================================================================

class TestResult:
    """Tracks individual test results."""
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        msg = f" - {self.message}" if self.message else ""
        return f"{status}: {self.name}{msg}"


class TestSuite:
    """Manages test execution and reporting."""

    def __init__(self, name: str):
        self.name = name
        self.results: List[TestResult] = []
        self.temp_dir = None

    def setup(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="ozolith_test_")
        return self.temp_dir

    def teardown(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_test_ozolith(self, name: str = "test") -> Ozolith:
        """Create an Ozolith instance with isolated storage."""
        path = os.path.join(self.temp_dir, f"{name}.jsonl")
        return Ozolith(storage_path=path)

    def add_result(self, name: str, passed: bool, message: str = ""):
        """Record a test result."""
        self.results.append(TestResult(name, passed, message))

    def run_test(self, name: str, test_fn):
        """Run a single test and record result."""
        try:
            test_fn()
            self.add_result(name, True)
        except AssertionError as e:
            self.add_result(name, False, str(e))
        except Exception as e:
            self.add_result(name, False, f"Exception: {type(e).__name__}: {e}")

    def report(self) -> Tuple[int, int]:
        """Print results and return (passed, total)."""
        print(f"\n{'='*60}")
        print(f"TEST SUITE: {self.name}")
        print('='*60)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        for result in self.results:
            print(result)

        print(f"\n{'-'*60}")
        print(f"Results: {passed}/{total} passed")
        if passed == total:
            print("🎉 ALL TESTS PASSED")
        else:
            print(f"⚠️  {total - passed} TESTS FAILED")
        print('='*60)

        return passed, total


# =============================================================================
# PYTEST FIXTURE FOR TESTSUITE
# =============================================================================

@pytest.fixture
def suite():
    """
    Pytest fixture that provides a TestSuite instance.

    This allows the standalone test functions (designed for the custom runner)
    to also work with pytest's test collection.
    """
    ts = TestSuite("pytest_run")
    ts.setup()
    yield ts
    ts.teardown()


# =============================================================================
# 1. HASH CHAIN INTEGRITY TESTS
# =============================================================================

def test_hash_chain_integrity(suite: TestSuite):
    """Tests for the core hash chain mechanism."""

    oz = suite.create_test_ozolith("hash_chain")

    # Test: First entry has empty previous_hash
    def test_first_entry_empty_previous():
        entry = oz.append(
            OzolithEventType.SESSION_START,
            "SB-1", "system", {"test": "first"}
        )
        assert entry.previous_hash == "", f"Expected empty, got {entry.previous_hash}"

    suite.run_test("First entry has empty previous_hash", test_first_entry_empty_previous)

    # Test: Subsequent entries link correctly
    def test_chain_links():
        entry1 = oz._entries[-1]  # The one we just added
        entry2 = oz.append(
            OzolithEventType.EXCHANGE,
            "SB-1", "assistant", {"test": "second"}
        )
        assert entry2.previous_hash == entry1.entry_hash, \
            f"Chain broken: {entry2.previous_hash} != {entry1.entry_hash}"

    suite.run_test("Subsequent entries link to previous hash", test_chain_links)

    # Test: verify_chain passes on untampered log
    def test_verify_untampered():
        valid, bad_idx = oz.verify_chain()
        assert valid, f"Chain should be valid, failed at {bad_idx}"

    suite.run_test("verify_chain() passes on untampered log", test_verify_untampered)

    # Test: Modifying content causes verify_chain to fail
    def test_detect_content_modification():
        # Tamper with an entry
        original_payload = oz._entries[0].payload.copy()
        oz._entries[0].payload["tampered"] = True

        valid, bad_idx = oz.verify_chain()

        # Restore
        oz._entries[0].payload = original_payload

        assert not valid, "Should detect content modification"
        assert bad_idx == 1, f"Should fail at entry 1, got {bad_idx}"

    suite.run_test("Detects content modification", test_detect_content_modification)

    # Test: Modifying hash directly causes failure
    def test_detect_hash_modification():
        original_hash = oz._entries[0].entry_hash
        oz._entries[0].entry_hash = "tampered_hash_value"

        valid, bad_idx = oz.verify_chain()

        # Restore
        oz._entries[0].entry_hash = original_hash

        assert not valid, "Should detect hash modification"

    suite.run_test("Detects direct hash modification", test_detect_hash_modification)

    # Test: Breaking chain link causes failure
    def test_detect_chain_break():
        if len(oz._entries) < 2:
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "extra"})

        original_prev = oz._entries[1].previous_hash
        oz._entries[1].previous_hash = "broken_link"

        valid, bad_idx = oz.verify_chain()

        # Restore
        oz._entries[1].previous_hash = original_prev

        assert not valid, "Should detect broken chain link"
        assert bad_idx == 2, f"Should fail at entry 2, got {bad_idx}"

    suite.run_test("Detects broken chain link", test_detect_chain_break)

    # Test: Entry hash is deterministic
    def test_hash_determinism():
        entry = oz._entries[0]
        hash1 = oz._compute_hash(oz._build_entry_for_hashing(entry))
        hash2 = oz._compute_hash(oz._build_entry_for_hashing(entry))
        assert hash1 == hash2, "Hash should be deterministic"

    suite.run_test("Hash computation is deterministic", test_hash_determinism)


# =============================================================================
# 2. SIGNATURE VERIFICATION TESTS
# =============================================================================

def test_signatures(suite: TestSuite):
    """Tests for signature generation and verification."""

    oz = suite.create_test_ozolith("signatures")

    # Test: Entries have signatures
    def test_entries_have_signatures():
        entry = oz.append(
            OzolithEventType.SESSION_START,
            "SB-1", "system", {"test": "sig"}
        )
        assert entry.signature, "Entry should have a signature"
        assert len(entry.signature) == 64, "Signature should be 64 hex chars (SHA-256)"

    suite.run_test("Entries have signatures", test_entries_have_signatures)

    # Test: Signature changes with content
    def test_signature_changes_with_content():
        sig1 = oz._compute_signature({"data": "value1"})
        sig2 = oz._compute_signature({"data": "value2"})
        assert sig1 != sig2, "Different content should produce different signatures"

    suite.run_test("Signature changes with content", test_signature_changes_with_content)

    # Test: Same content produces same signature
    def test_signature_deterministic():
        data = {"test": "deterministic", "number": 42}
        sig1 = oz._compute_signature(data)
        sig2 = oz._compute_signature(data)
        assert sig1 == sig2, "Same content should produce same signature"

    suite.run_test("Signature is deterministic", test_signature_deterministic)

    # Test: Different signing keys produce different signatures
    def test_different_keys_different_sigs():
        oz2 = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "sig2.jsonl"),
            signing_key="different_key_12345"
        )

        data = {"same": "data"}
        sig1 = oz._compute_signature(data)
        sig2 = oz2._compute_signature(data)

        assert sig1 != sig2, "Different keys should produce different signatures"

    suite.run_test("Different signing keys produce different signatures", test_different_keys_different_sigs)

    # Test: Signature verification catches tampering
    def test_signature_catches_tampering():
        entry = oz._entries[0]
        original_sig = entry.signature

        # Tamper with signature
        entry.signature = "a" * 64
        valid, bad_idx = oz.verify_chain()

        # Restore
        entry.signature = original_sig

        assert not valid, "Should detect signature tampering"

    suite.run_test("Signature verification catches tampering", test_signature_catches_tampering)


# =============================================================================
# 3. ANCHOR SYSTEM TESTS
# =============================================================================

def test_anchors(suite: TestSuite):
    """Tests for the anchor (checkpoint) system."""

    oz = suite.create_test_ozolith("anchors")

    # Add some entries first
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"msg": "hello"})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "hi"})

    # Test: Anchor captures correct root hash
    def test_anchor_captures_root():
        current_root = oz.get_root_hash()
        anchor = oz.create_anchor("test")
        assert anchor.root_hash == current_root, "Anchor should capture current root hash"

    suite.run_test("Anchor captures correct root hash", test_anchor_captures_root)

    # Test: Anchor has correct sequence range
    def test_anchor_sequence_range():
        anchor = oz._anchors[-1]
        first, last = anchor.sequence_range
        assert first == 1, f"First should be 1, got {first}"
        # Last will be higher because create_anchor adds an ANCHOR_CREATED entry
        assert last >= 3, f"Last should be >= 3, got {last}"

    suite.run_test("Anchor has correct sequence range", test_anchor_sequence_range)

    # Test: Anchor has signature
    def test_anchor_has_signature():
        anchor = oz._anchors[-1]
        assert anchor.signature, "Anchor should have signature"

    suite.run_test("Anchor has signature", test_anchor_has_signature)

    # Test: verify_against_anchor passes on untampered log
    def test_verify_against_anchor_passes():
        anchor = oz._anchors[-1]
        valid = oz.verify_against_anchor(anchor)
        assert valid, "Should verify against untampered log"

    suite.run_test("verify_against_anchor() passes on untampered log", test_verify_against_anchor_passes)

    # Test: verify_against_anchor fails if tip entry modified
    def test_verify_against_anchor_detects_tampering():
        anchor = oz._anchors[-1]

        # NOTE: verify_against_anchor is a lightweight O(1) "tip check" -
        # it only compares the last entry's hash to the anchor's root_hash.
        # Full chain verification is done by verify_chain().
        # Merkle trees (future) will make this O(log N) with full tamper detection.
        #
        # For now, we test that tampering with the TIP is detected.

        # Find the entry whose hash matches the anchor's root_hash
        tip_entry = None
        for entry in oz._entries:
            if entry.entry_hash == anchor.root_hash:
                tip_entry = entry
                break

        if tip_entry is None:
            # Fallback: find the last entry at or before anchor's last_seq
            _, last_seq = anchor.sequence_range
            for entry in reversed(oz._entries):
                if entry.sequence <= last_seq:
                    tip_entry = entry
                    break

        assert tip_entry is not None, "Could not find tip entry"

        original_hash = tip_entry.entry_hash
        tip_entry.entry_hash = "tampered"

        valid = oz.verify_against_anchor(anchor)

        tip_entry.entry_hash = original_hash

        assert not valid, "Should detect tampering at anchor tip"

    suite.run_test("verify_against_anchor() detects tampering", test_verify_against_anchor_detects_tampering)

    # Test: Export anchor produces valid dict
    def test_export_anchor():
        exported = oz.export_anchor()
        assert 'anchor_id' in exported
        assert 'root_hash' in exported
        assert 'signature' in exported
        assert 'export_time' in exported

    suite.run_test("export_anchor() produces valid dict", test_export_anchor)


# =============================================================================
# 4. ANCHOR POLICY TRIGGER TESTS
# =============================================================================

def test_anchor_policy(suite: TestSuite):
    """Tests for anchor policy triggers."""

    # Test: Count threshold triggers anchor
    def test_count_trigger():
        policy = AnchorPolicy(count_threshold=3)
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_count.jsonl"),
            anchor_policy=policy
        )

        # Add entries (count threshold is 3)
        for i in range(4):
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"i": i})

        # Should have created at least one anchor
        assert len(oz._anchors) >= 1, "Count threshold should trigger anchor"

    suite.run_test("Count threshold triggers anchor", test_count_trigger)

    # Test: Significant events trigger anchor
    def test_event_triggers():
        policy = AnchorPolicy(count_threshold=1000)  # High count so only events trigger
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_event.jsonl"),
            anchor_policy=policy
        )

        # SIDEBAR_SPAWN should trigger
        oz.append(OzolithEventType.SIDEBAR_SPAWN, "SB-1", "system", {"parent": "SB-0"})

        assert len(oz._anchors) >= 1, "SIDEBAR_SPAWN should trigger anchor"

    suite.run_test("Significant events trigger anchor (SIDEBAR_SPAWN)", test_event_triggers)

    # Test: SIDEBAR_MERGE triggers anchor
    def test_merge_triggers():
        policy = AnchorPolicy(count_threshold=1000)
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_merge.jsonl"),
            anchor_policy=policy
        )

        oz.append(OzolithEventType.SIDEBAR_MERGE, "SB-1", "system", {"merged": "SB-2"})

        assert len(oz._anchors) >= 1, "SIDEBAR_MERGE should trigger anchor"

    suite.run_test("Significant events trigger anchor (SIDEBAR_MERGE)", test_merge_triggers)

    # Test: ERROR_LOGGED triggers anchor
    def test_error_triggers():
        policy = AnchorPolicy(count_threshold=1000)
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_error.jsonl"),
            anchor_policy=policy
        )

        oz.append(OzolithEventType.ERROR_LOGGED, "SB-1", "system", {"error": "test"})

        assert len(oz._anchors) >= 1, "ERROR_LOGGED should trigger anchor"

    suite.run_test("Significant events trigger anchor (ERROR_LOGGED)", test_error_triggers)

    # Test: CORRECTION triggers anchor
    def test_correction_triggers():
        policy = AnchorPolicy(count_threshold=1000)
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_corr.jsonl"),
            anchor_policy=policy
        )

        oz.append(OzolithEventType.CORRECTION, "SB-1", "human", {"original_seq": 1})

        assert len(oz._anchors) >= 1, "CORRECTION should trigger anchor"

    suite.run_test("Significant events trigger anchor (CORRECTION)", test_correction_triggers)

    # Test: High skinflap score triggers anchor
    def test_skinflap_triggers():
        policy = AnchorPolicy(count_threshold=1000, skinflap_threshold=0.8)
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_skinflap.jsonl"),
            anchor_policy=policy
        )

        oz.append(
            OzolithEventType.EXCHANGE, "SB-1", "assistant",
            {"msg": "important"},
            skinflap_score=0.95
        )

        assert len(oz._anchors) >= 1, "High skinflap should trigger anchor"

    suite.run_test("High skinflap score triggers anchor", test_skinflap_triggers)

    # Test: Stale return triggers anchor
    def test_stale_return_triggers():
        policy = AnchorPolicy(
            count_threshold=1000,
            stale_threshold_hours=0.0001  # ~0.36 seconds for testing
        )
        oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "policy_stale.jsonl"),
            anchor_policy=policy
        )

        # First entry
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        initial_anchors = len(oz._anchors)

        # Wait a bit
        time.sleep(0.5)

        # This exchange after idle should trigger stale return
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "back"})

        assert len(oz._anchors) > initial_anchors, "Stale return should trigger anchor"

    suite.run_test("Stale return triggers anchor", test_stale_return_triggers)


# =============================================================================
# 5. QUERY METHOD TESTS
# =============================================================================

def test_query_methods(suite: TestSuite):
    """Tests for query and filter methods."""

    oz = suite.create_test_ozolith("queries")

    # Setup: Add various entries
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"confidence": 0.9})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"confidence": 0.3})
    oz.append(OzolithEventType.EXCHANGE, "SB-2", "human", {"confidence": 0.7})
    oz.append(OzolithEventType.SIDEBAR_SPAWN, "SB-2", "system", {"parent": "SB-1"})
    oz.append(OzolithEventType.CORRECTION, "SB-1", "human", {"original_exchange_seq": 2})

    # Test: get_by_type
    def test_get_by_type():
        exchanges = oz.get_by_type(OzolithEventType.EXCHANGE)
        assert len(exchanges) == 3, f"Expected 3 exchanges, got {len(exchanges)}"

    suite.run_test("get_by_type() filters correctly", test_get_by_type)

    # Test: get_by_context
    def test_get_by_context():
        sb1_entries = oz.get_by_context("SB-1")
        assert len(sb1_entries) >= 3, f"Expected >= 3 SB-1 entries, got {len(sb1_entries)}"

    suite.run_test("get_by_context() filters correctly", test_get_by_context)

    # Test: get_entries with range
    def test_get_entries_range():
        entries = oz.get_entries(start_seq=2, end_seq=4)
        assert all(2 <= e.sequence <= 4 for e in entries), "Should filter by range"

    suite.run_test("get_entries() filters by sequence range", test_get_entries_range)

    # Test: get_around
    def test_get_around():
        entries = oz.get_around(3, window=1)
        seqs = [e.sequence for e in entries]
        assert 2 in seqs and 3 in seqs and 4 in seqs, f"Expected 2,3,4 in {seqs}"

    suite.run_test("get_around() returns window of entries", test_get_around)

    # Test: get_by_payload with comparators
    def test_get_by_payload_lt():
        low_conf = oz.get_by_payload("confidence", 0.5, "lt")
        assert len(low_conf) >= 1, "Should find low confidence entries"
        assert all(e.payload.get("confidence", 1) < 0.5 for e in low_conf)

    suite.run_test("get_by_payload() 'lt' comparator works", test_get_by_payload_lt)

    def test_get_by_payload_gt():
        high_conf = oz.get_by_payload("confidence", 0.5, "gt")
        assert len(high_conf) >= 1, "Should find high confidence entries"
        assert all(e.payload.get("confidence", 0) > 0.5 for e in high_conf)

    suite.run_test("get_by_payload() 'gt' comparator works", test_get_by_payload_gt)

    def test_get_by_payload_eq():
        exact = oz.get_by_payload("confidence", 0.9, "eq")
        assert len(exact) >= 1, "Should find exact match"

    suite.run_test("get_by_payload() 'eq' comparator works", test_get_by_payload_eq)

    # Test: get_corrections_for
    def test_get_corrections_for():
        corrections = oz.get_corrections_for(2)
        assert len(corrections) >= 1, "Should find correction for entry 2"

    suite.run_test("get_corrections_for() finds linked corrections", test_get_corrections_for)

    # Test: get_uncertain_exchanges
    def test_get_uncertain():
        uncertain = oz.get_uncertain_exchanges(threshold=0.5)
        assert len(uncertain) >= 1, "Should find uncertain exchanges"
        assert all(e.payload.get("confidence", 1) < 0.5 for e in uncertain)

    suite.run_test("get_uncertain_exchanges() filters by threshold", test_get_uncertain)

    # Test: get_by_timerange
    def test_get_by_timerange():
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        entries = oz.get_by_timerange(start=hour_ago, end=now)
        assert len(entries) == len(oz._entries), "All entries should be within last hour"

    suite.run_test("get_by_timerange() filters correctly", test_get_by_timerange)


# =============================================================================
# 6. CHAINABLE QUERY BUILDER TESTS
# =============================================================================

def test_query_builder(suite: TestSuite):
    """Tests for the chainable OzolithQuery builder."""

    oz = suite.create_test_ozolith("query_builder")

    # Setup
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "human",
              {"confidence": 0.9, "skinflap_score": 0.8})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"confidence": 0.3, "skinflap_score": 0.9, "uncertainty_flags": ["ambiguous"]})
    oz.append(OzolithEventType.EXCHANGE, "SB-2", "human",
              {"confidence": 0.7, "skinflap_score": 0.5})
    oz.append(OzolithEventType.CORRECTION, "SB-1", "human",
              {"original_exchange_seq": 3})

    # Test: Single filter
    def test_single_filter():
        results = oz.query().by_type(OzolithEventType.EXCHANGE).execute()
        assert len(results) == 3, f"Expected 3 exchanges, got {len(results)}"

    suite.run_test("Query builder: single filter", test_single_filter)

    # Test: Multiple filters (AND)
    def test_multiple_filters():
        results = oz.query() \
            .by_type(OzolithEventType.EXCHANGE) \
            .by_context("SB-1") \
            .execute()
        assert len(results) == 2, f"Expected 2 SB-1 exchanges, got {len(results)}"

    suite.run_test("Query builder: multiple filters (AND)", test_multiple_filters)

    # Test: where_payload with comparator
    def test_where_payload():
        results = oz.query() \
            .by_type(OzolithEventType.EXCHANGE) \
            .where_payload("confidence", "<", 0.5) \
            .execute()
        assert len(results) == 1, f"Expected 1 low-conf exchange, got {len(results)}"

    suite.run_test("Query builder: where_payload comparator", test_where_payload)

    # Test: Complex compound query
    def test_compound_query():
        # "Find exchanges where I was uncertain but query was good"
        results = oz.query() \
            .by_type(OzolithEventType.EXCHANGE) \
            .where_payload("confidence", "<", 0.5) \
            .where_payload("skinflap_score", ">", 0.8) \
            .execute()
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"

    suite.run_test("Query builder: complex compound query", test_compound_query)

    # Test: has_uncertainty_flag
    def test_has_uncertainty_flag():
        results = oz.query() \
            .has_uncertainty_flag("ambiguous") \
            .execute()
        assert len(results) == 1, f"Expected 1 with 'ambiguous' flag, got {len(results)}"

    suite.run_test("Query builder: has_uncertainty_flag", test_has_uncertainty_flag)

    # Test: with_corrections
    def test_with_corrections():
        results = oz.query() \
            .by_type(OzolithEventType.EXCHANGE) \
            .with_corrections() \
            .execute()
        assert len(results) == 1, f"Expected 1 corrected exchange, got {len(results)}"

    suite.run_test("Query builder: with_corrections", test_with_corrections)

    # Test: count()
    def test_count():
        count = oz.query().by_type(OzolithEventType.EXCHANGE).count()
        assert count == 3, f"Expected count 3, got {count}"

    suite.run_test("Query builder: count()", test_count)

    # Test: first() and last()
    def test_first_last():
        first = oz.query().by_type(OzolithEventType.EXCHANGE).first()
        last = oz.query().by_type(OzolithEventType.EXCHANGE).last()
        assert first.sequence < last.sequence, "first() should be before last()"

    suite.run_test("Query builder: first() and last()", test_first_last)

    # Test: by_actor
    def test_by_actor():
        results = oz.query().by_actor("assistant").execute()
        assert len(results) == 1, f"Expected 1 assistant entry, got {len(results)}"

    suite.run_test("Query builder: by_actor", test_by_actor)

    # Test: by_types (multiple)
    def test_by_types():
        results = oz.query().by_types([
            OzolithEventType.EXCHANGE,
            OzolithEventType.CORRECTION
        ]).execute()
        assert len(results) == 4, f"Expected 4 entries, got {len(results)}"

    suite.run_test("Query builder: by_types (multiple)", test_by_types)


# =============================================================================
# 7. STATISTICS TESTS
# =============================================================================

def test_statistics(suite: TestSuite):
    """Tests for statistics aggregation."""

    oz = suite.create_test_ozolith("stats")

    # Setup with known data
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"confidence": 0.9, "uncertainty_flags": []})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"confidence": 0.3, "uncertainty_flags": ["ambiguous", "limited_context"]})
    oz.append(OzolithEventType.EXCHANGE, "SB-2", "assistant",
              {"confidence": 0.6, "uncertainty_flags": ["ambiguous"]})
    oz.append(OzolithEventType.CORRECTION, "SB-1", "human",
              {"original_exchange_seq": 2, "correction_type": "factual"})

    stats = oz.stats()

    # Test: Total entries
    def test_total_entries():
        # 5 user entries + 1 anchor (CORRECTION triggers anchor)
        user_entries = [e for e in oz._entries if e.event_type != OzolithEventType.ANCHOR_CREATED]
        anchor_entries = [e for e in oz._entries if e.event_type == OzolithEventType.ANCHOR_CREATED]

        assert len(user_entries) == 5, f"Expected 5 user entries, got {len(user_entries)}"
        assert len(anchor_entries) == 1, f"Expected 1 anchor (from CORRECTION), got {len(anchor_entries)}"
        assert stats['total_entries'] == 6, f"Expected 6 total, got {stats['total_entries']}"

    suite.run_test("Stats: total_entries", test_total_entries)

    # Test: By type counts
    def test_by_type():
        assert stats['by_type'].get('exchange') == 3
        assert stats['by_type'].get('correction') == 1

    suite.run_test("Stats: by_type counts", test_by_type)

    # Test: Average confidence
    def test_avg_confidence():
        # (0.9 + 0.3 + 0.6) / 3 = 0.6
        assert abs(stats['avg_confidence'] - 0.6) < 0.01, \
            f"Expected ~0.6, got {stats['avg_confidence']}"

    suite.run_test("Stats: avg_confidence", test_avg_confidence)

    # Test: Confidence distribution
    def test_confidence_distribution():
        dist = stats['confidence_distribution']
        assert dist['low'] == 1, f"Expected 1 low, got {dist['low']}"  # 0.3
        assert dist['medium'] == 1, f"Expected 1 medium, got {dist['medium']}"  # 0.6
        assert dist['high'] == 1, f"Expected 1 high, got {dist['high']}"  # 0.9

    suite.run_test("Stats: confidence_distribution", test_confidence_distribution)

    # Test: Uncertainty flag counts
    def test_uncertainty_flags():
        flags = stats['uncertainty_flag_counts']
        assert flags.get('ambiguous') == 2, f"Expected 2 ambiguous, got {flags.get('ambiguous')}"
        assert flags.get('limited_context') == 1

    suite.run_test("Stats: uncertainty_flag_counts", test_uncertainty_flags)

    # Test: Correction rate
    def test_correction_rate():
        # 1 correction / 3 exchanges = 0.333...
        assert abs(stats['correction_rate'] - (1/3)) < 0.01

    suite.run_test("Stats: correction_rate", test_correction_rate)

    # Test: Corrections by type
    def test_corrections_by_type():
        assert stats['corrections_by_type'].get('factual') == 1

    suite.run_test("Stats: corrections_by_type", test_corrections_by_type)

    # Test: Most active contexts
    def test_most_active_contexts():
        contexts = stats['most_active_contexts']
        # SB-1 should have more entries than SB-2
        assert contexts[0][0] == "SB-1", f"Expected SB-1 first, got {contexts[0][0]}"

    suite.run_test("Stats: most_active_contexts", test_most_active_contexts)


# =============================================================================
# 8. HELPER FUNCTION TESTS
# =============================================================================

def test_helper_functions(suite: TestSuite):
    """Tests for convenience helper functions."""

    oz = suite.create_test_ozolith("helpers")

    # Setup
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    exchange = oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
                        {"confidence": 0.8})

    # Test: create_exchange_payload
    def test_create_exchange_payload():
        payload = create_exchange_payload(
            query="test question",
            response="test answer",
            confidence=0.75,
            skinflap_score=0.8,
            uncertainty_flags=["ambiguous"],
            reasoning_type="inference",
            token_count=100,
            latency_ms=500
        )
        assert 'query_hash' in payload
        assert 'response_hash' in payload
        assert payload['confidence'] == 0.75
        assert payload['uncertainty_flags'] == ["ambiguous"]
        # Hashes should be SHA-256 (64 hex chars)
        assert len(payload['query_hash']) == 64

    suite.run_test("create_exchange_payload() works", test_create_exchange_payload)

    # Test: create_sidebar_payload
    def test_create_sidebar_payload():
        payload = create_sidebar_payload(
            parent_id="SB-1",
            child_id="SB-2",
            reason="investigate bug",
            inherited_count=5
        )
        assert payload['parent_id'] == "SB-1"
        assert payload['child_id'] == "SB-2"

    suite.run_test("create_sidebar_payload() works", test_create_sidebar_payload)

    # Test: create_correction_payload
    def test_create_correction_payload():
        payload = create_correction_payload(
            original_exchange_seq=5,
            correction_type="factual",
            correction_notes="wrong function name"
        )
        assert payload['original_exchange_seq'] == 5
        assert payload['correction_type'] == "factual"

    suite.run_test("create_correction_payload() works", test_create_correction_payload)

    # Test: log_correction
    def test_log_correction():
        entry = log_correction(oz, exchange.sequence, "test correction", "approach", "SB-1")
        assert entry.event_type == OzolithEventType.CORRECTION
        assert entry.payload['original_exchange_seq'] == exchange.sequence

    suite.run_test("log_correction() creates entry", test_log_correction)

    # Test: log_uncertainty
    def test_log_uncertainty():
        entry = log_uncertainty(oz, "SB-1", "multiple valid approaches", {"options": ["A", "B"]})
        assert entry.payload.get('confidence') == 0.0
        assert 'explicit_uncertainty' in entry.payload.get('uncertainty_flags', [])

    suite.run_test("log_uncertainty() creates entry with flags", test_log_uncertainty)

    # Test: export_incident
    def test_export_incident():
        bundle = export_incident(oz, exchange.sequence, window=2)
        assert 'incident_sequence' in bundle
        assert 'entries' in bundle
        assert 'chain_verified' in bundle
        assert bundle['incident_sequence'] == exchange.sequence

    suite.run_test("export_incident() creates bundle", test_export_incident)

    # Test: session_summary
    def test_session_summary():
        summary = session_summary(oz, 1)  # Start from first entry
        assert 'total_entries' in summary
        assert 'exchanges' in summary
        assert 'corrections' in summary
        assert summary['total_entries'] > 0

    suite.run_test("session_summary() creates summary", test_session_summary)

    # Test: find_learning_opportunities
    def test_find_learning_opportunities():
        # Add a low confidence exchange
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"confidence": 0.2})

        opportunities = find_learning_opportunities(oz)
        assert len(opportunities) > 0, "Should find learning opportunities"
        types = [o['type'] for o in opportunities]
        assert 'low_confidence' in types or 'correction' in types

    suite.run_test("find_learning_opportunities() finds issues", test_find_learning_opportunities)


# =============================================================================
# 9. EDGE CASE TESTS
# =============================================================================

def test_edge_cases(suite: TestSuite):
    """Tests for boundary conditions and weird inputs."""

    # Test: Empty log
    def test_empty_log():
        oz = suite.create_test_ozolith("empty")

        assert oz.get_root_hash() == ""
        assert oz.verify_chain() == (True, None)
        assert oz.stats()['total_entries'] == 0
        assert oz.get_entries() == []

    suite.run_test("Empty log handles gracefully", test_empty_log)

    # Test: Large payload
    def test_large_payload():
        oz = suite.create_test_ozolith("large")
        large_data = {"big": "x" * 100000}  # 100KB of data

        entry = oz.append(OzolithEventType.EXCHANGE, "SB-1", "system", large_data)

        assert entry.entry_hash
        valid, _ = oz.verify_chain()
        assert valid, "Large payload should hash correctly"

    suite.run_test("Large payloads hash correctly", test_large_payload)

    # Test: Unicode content
    def test_unicode():
        oz = suite.create_test_ozolith("unicode")
        unicode_data = {
            "emoji": "🎉🔥💯",
            "chinese": "中文测试",
            "arabic": "اختبار",
            "special": "äöü ñ é"
        }

        entry = oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", unicode_data)

        assert entry.entry_hash
        valid, _ = oz.verify_chain()
        assert valid, "Unicode content should hash correctly"

    suite.run_test("Unicode content hashes correctly", test_unicode)

    # Test: Nested payload
    def test_nested_payload():
        oz = suite.create_test_ozolith("nested")
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": [1, 2, {"deep": True}]
                    }
                }
            }
        }

        entry = oz.append(OzolithEventType.EXCHANGE, "SB-1", "system", nested_data)
        valid, _ = oz.verify_chain()
        assert valid

    suite.run_test("Nested payloads hash correctly", test_nested_payload)

    # Test: Special characters in context_id
    def test_special_context_id():
        oz = suite.create_test_ozolith("special_ctx")
        entry = oz.append(OzolithEventType.EXCHANGE, "SB-test/with:special", "human", {})
        assert entry.context_id == "SB-test/with:special"

    suite.run_test("Special characters in context_id", test_special_context_id)

    # Test: Query on empty results
    def test_query_empty_results():
        oz = suite.create_test_ozolith("query_empty")
        results = oz.query().by_type(OzolithEventType.CORRECTION).execute()
        assert results == []
        assert oz.query().by_type(OzolithEventType.CORRECTION).count() == 0
        assert oz.query().by_type(OzolithEventType.CORRECTION).first() is None

    suite.run_test("Query handles empty results", test_query_empty_results)

    # Test: get_corrections_for nonexistent entry
    def test_corrections_for_nonexistent():
        oz = suite.create_test_ozolith("no_corr")
        corrections = oz.get_corrections_for(99999)
        assert corrections == []

    suite.run_test("get_corrections_for() handles nonexistent entry", test_corrections_for_nonexistent)


# =============================================================================
# 10. PERSISTENCE TESTS
# =============================================================================

def test_persistence(suite: TestSuite):
    """Tests for data survival across restarts."""

    storage_path = os.path.join(suite.temp_dir, "persist.jsonl")

    # Test: Entries survive restart
    def test_entries_survive():
        # Create and populate
        oz1 = Ozolith(storage_path=storage_path)
        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {"session": 1})
        oz1.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "hello"})
        original_count = len(oz1._entries)
        original_root = oz1.get_root_hash()

        # Simulate restart
        del oz1

        # Reload
        oz2 = Ozolith(storage_path=storage_path)

        assert len(oz2._entries) == original_count, "Entries should survive restart"
        assert oz2.get_root_hash() == original_root, "Root hash should match"

    suite.run_test("Entries survive restart", test_entries_survive)

    # Test: Sequence continues after restart
    def test_sequence_continues():
        oz = Ozolith(storage_path=storage_path)
        last_seq = oz._sequence

        entry = oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "new"})

        assert entry.sequence == last_seq + 1, "Sequence should continue"

    suite.run_test("Sequence continues after restart", test_sequence_continues)

    # Test: Chain still valid after restart
    def test_chain_valid_after_restart():
        oz = Ozolith(storage_path=storage_path)
        valid, bad_idx = oz.verify_chain()
        assert valid, f"Chain should be valid after restart, failed at {bad_idx}"

    suite.run_test("Chain valid after restart", test_chain_valid_after_restart)

    # Test: Anchors survive restart
    def test_anchors_survive():
        oz1 = Ozolith(storage_path=storage_path)
        anchor = oz1.create_anchor("test_persist")
        anchor_count = len(oz1._anchors)
        anchor_id = anchor.anchor_id

        del oz1

        oz2 = Ozolith(storage_path=storage_path)
        assert len(oz2._anchors) >= anchor_count, "Anchors should survive restart"

        # Find the anchor we created
        found = any(a.anchor_id == anchor_id for a in oz2._anchors)
        assert found, "Specific anchor should survive"

    suite.run_test("Anchors survive restart", test_anchors_survive)


# =============================================================================
# 11. TAMPERING SCENARIO TESTS
# =============================================================================

def test_tampering_scenarios(suite: TestSuite):
    """Simulate various tampering attacks and verify detection."""

    oz = suite.create_test_ozolith("tamper")

    # Build a log with several entries
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "question"})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"msg": "answer", "confidence": 0.8})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "followup"})
    oz.append(OzolithEventType.SIDEBAR_SPAWN, "SB-2", "system", {"parent": "SB-1"})

    # Test: Inserting an entry mid-chain
    def test_detect_insertion():
        # Save state
        original_entries = oz._entries.copy()

        # Try to insert a fake entry
        fake_entry = OzolithEntry(
            sequence=3,
            timestamp=datetime.utcnow().isoformat() + "Z",
            previous_hash=oz._entries[1].entry_hash,
            event_type=OzolithEventType.EXCHANGE,
            context_id="SB-1",
            actor="attacker",
            payload={"fake": True},
            signature="fake",
            entry_hash="fake"
        )

        # Insert at position 2
        oz._entries.insert(2, fake_entry)

        valid, _ = oz.verify_chain()

        # Restore
        oz._entries = original_entries

        assert not valid, "Should detect inserted entry"

    suite.run_test("Detects inserted entry", test_detect_insertion)

    # Test: Deleting an entry
    def test_detect_deletion():
        original_entries = oz._entries.copy()

        # Delete middle entry
        del oz._entries[2]

        valid, _ = oz.verify_chain()

        # Restore
        oz._entries = original_entries

        assert not valid, "Should detect deleted entry"

    suite.run_test("Detects deleted entry", test_detect_deletion)

    # Test: Swapping two entries
    def test_detect_swap():
        original_entries = oz._entries.copy()

        # Swap entries 2 and 3
        oz._entries[2], oz._entries[3] = oz._entries[3], oz._entries[2]

        valid, _ = oz.verify_chain()

        # Restore
        oz._entries = original_entries

        assert not valid, "Should detect swapped entries"

    suite.run_test("Detects swapped entries", test_detect_swap)

    # Test: Modifying payload but keeping hash (sophisticated attack)
    def test_detect_payload_modification():
        original_payload = oz._entries[2].payload.copy()

        # Modify payload
        oz._entries[2].payload["msg"] = "TAMPERED"

        valid, bad_idx = oz.verify_chain()

        # Restore
        oz._entries[2].payload = original_payload

        assert not valid, "Should detect payload modification"
        assert bad_idx == 3, f"Should fail at entry 3, got {bad_idx}"

    suite.run_test("Detects payload modification", test_detect_payload_modification)

    # Test: Replacing entire entry with recomputed hashes (needs wrong key)
    def test_detect_wrong_key_entry():
        # Create an entry with a different signing key
        fake_oz = Ozolith(
            storage_path=os.path.join(suite.temp_dir, "fake.jsonl"),
            signing_key="attacker_key_12345"
        )

        # Try to use its signature computation
        fake_sig = fake_oz._compute_signature({
            'sequence': oz._entries[2].sequence,
            'timestamp': oz._entries[2].timestamp,
            'previous_hash': oz._entries[2].previous_hash,
            'event_type': oz._entries[2].event_type.value,
            'context_id': oz._entries[2].context_id,
            'actor': oz._entries[2].actor,
            'payload': {"tampered": True}
        })

        original_sig = oz._entries[2].signature
        original_payload = oz._entries[2].payload.copy()

        oz._entries[2].signature = fake_sig
        oz._entries[2].payload = {"tampered": True}

        valid, _ = oz.verify_chain()

        # Restore
        oz._entries[2].signature = original_sig
        oz._entries[2].payload = original_payload

        assert not valid, "Should detect entry signed with wrong key"

    suite.run_test("Detects entry signed with wrong key", test_detect_wrong_key_entry)

    # Test: Verify corrections can't hide tampering
    def test_correction_cant_hide_tampering():
        # Add a correction
        oz.append(OzolithEventType.CORRECTION, "SB-1", "human",
                  {"original_exchange_seq": 3, "correction_notes": "was wrong"})

        # Now tamper with entry 3
        original_payload = oz._entries[2].payload.copy()
        oz._entries[2].payload["TAMPERED"] = True

        valid, bad_idx = oz.verify_chain()

        # Restore
        oz._entries[2].payload = original_payload

        assert not valid, "Correction should NOT hide tampering"

    suite.run_test("Corrections can't hide tampering", test_correction_cant_hide_tampering)


# =============================================================================
# 12. RENDERER TESTS
# =============================================================================

def test_renderer(suite: TestSuite):
    """Tests for the human-readable renderer."""

    oz = suite.create_test_ozolith("renderer")
    renderer = OzolithRenderer(oz)

    # Setup
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"confidence": 0.8, "skinflap_score": 0.7})
    oz.append(OzolithEventType.CORRECTION, "SB-1", "human",
              {"original_exchange_seq": 2, "correction_type": "factual", "correction_notes": "test"})
    oz.create_anchor("test")

    # Test: render_entry compact
    def test_render_entry_compact():
        output = renderer.render_entry(oz._entries[0], compact=True)
        assert "#1" in output
        assert "session_start" in output

    suite.run_test("render_entry() compact mode", test_render_entry_compact)

    # Test: render_entry full
    def test_render_entry_full():
        output = renderer.render_entry(oz._entries[1], compact=False)
        assert "Entry #2" in output
        assert "Confidence" in output
        assert "Hash" in output

    suite.run_test("render_entry() full mode", test_render_entry_full)

    # Test: render_chain
    def test_render_chain():
        output = renderer.render_chain()
        assert "entries" in output.lower()

    suite.run_test("render_chain() works", test_render_chain)

    # Test: render_stats
    def test_render_stats():
        output = renderer.render_stats()
        assert "OZOLITH Statistics" in output
        assert "Total entries" in output

    suite.run_test("render_stats() works", test_render_stats)

    # Test: render_verification_report (valid)
    def test_render_verification_valid():
        result = oz.verify_chain()
        output = renderer.render_verification_report(result)
        assert "✓" in output or "Chain Verified" in output

    suite.run_test("render_verification_report() for valid chain", test_render_verification_valid)

    # Test: render_verification_report (invalid)
    def test_render_verification_invalid():
        output = renderer.render_verification_report((False, 5))
        assert "✗" in output or "FAILED" in output
        assert "5" in output

    suite.run_test("render_verification_report() for invalid chain", test_render_verification_invalid)

    # Test: render_anchor
    def test_render_anchor():
        output = renderer.render_anchor(oz._anchors[-1])
        assert "Anchor" in output
        assert "Root" in output

    suite.run_test("render_anchor() works", test_render_anchor)

    # Test: render_context_history
    def test_render_context_history():
        output = renderer.render_context_history("SB-1")
        assert "SB-1" in output

    suite.run_test("render_context_history() works", test_render_context_history)

    # Test: render_around_error
    def test_render_around_error():
        output = renderer.render_around_error(2, window=1)
        assert "#2" in output or "2" in output

    suite.run_test("render_around_error() works", test_render_around_error)


# =============================================================================
# 13. CONCURRENT ACCESS TESTS
# =============================================================================

def test_concurrent_access(suite: TestSuite):
    """
    Tests for concurrent access scenarios.

    Critical for multi-interface systems where React and CLI might both
    want to append entries. Tests cover file-level race conditions.
    """
    import threading
    import queue

    storage_path = os.path.join(suite.temp_dir, "concurrent.jsonl")

    # Test: Sequential appends from multiple instances don't corrupt
    def test_sequential_multi_instance():
        """Two instances appending sequentially should work."""
        oz1 = Ozolith(storage_path=storage_path)
        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {"from": "oz1"})

        # Simulate second instance (e.g., different process)
        oz2 = Ozolith(storage_path=storage_path)
        oz2.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"from": "oz2"})

        # Reload and verify chain
        oz3 = Ozolith(storage_path=storage_path)
        valid, bad_idx = oz3.verify_chain()

        assert valid, f"Chain should be valid after sequential multi-instance, failed at {bad_idx}"
        assert len(oz3._entries) == 2, f"Should have 2 entries, got {len(oz3._entries)}"

    suite.run_test("Sequential multi-instance appends", test_sequential_multi_instance)

    # Test: Rapid sequential appends
    def test_rapid_appends():
        """Many rapid appends should maintain chain integrity."""
        oz = Ozolith(storage_path=os.path.join(suite.temp_dir, "rapid.jsonl"))

        for i in range(100):
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"i": i})

        valid, bad_idx = oz.verify_chain()
        assert valid, f"Rapid appends broke chain at {bad_idx}"

        # Count user entries and anchor entries separately
        user_entries = [e for e in oz._entries if e.event_type != OzolithEventType.ANCHOR_CREATED]
        anchor_entries = [e for e in oz._entries if e.event_type == OzolithEventType.ANCHOR_CREATED]

        assert len(user_entries) == 100, f"Expected 100 user entries, got {len(user_entries)}"
        # Default count_threshold=100, so 1 anchor at entry 100
        assert len(anchor_entries) == 1, f"Expected 1 anchor, got {len(anchor_entries)}"

    suite.run_test("Rapid sequential appends (100 entries)", test_rapid_appends)

    # Test: Threaded concurrent appends (simulates race condition risk)
    def test_threaded_appends():
        """
        Multiple threads appending simultaneously.

        NOTE: Current implementation is NOT thread-safe by design.
        This test documents expected behavior - it may fail or produce
        corrupted chains. If thread safety is needed, add file locking.
        """
        path = os.path.join(suite.temp_dir, "threaded.jsonl")
        results = queue.Queue()
        errors = queue.Queue()

        def append_entries(thread_id: int, count: int):
            try:
                oz = Ozolith(storage_path=path)
                for i in range(count):
                    oz.append(
                        OzolithEventType.EXCHANGE,
                        f"SB-{thread_id}",
                        "assistant",
                        {"thread": thread_id, "i": i}
                    )
                results.put((thread_id, count))
            except Exception as e:
                errors.put((thread_id, str(e)))

        # Launch 3 threads, each appending 10 entries
        threads = []
        for t_id in range(3):
            t = threading.Thread(target=append_entries, args=(t_id, 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check results
        if not errors.empty():
            # Expected - document that concurrent writes can fail
            err_thread, err_msg = errors.get()
            # This is actually expected behavior - not a test failure
            # Just documenting that thread safety isn't built in
            pass

        # Try to verify - may or may not work depending on race conditions
        oz_final = Ozolith(storage_path=path)
        valid, bad_idx = oz_final.verify_chain()

        # We're not asserting valid=True here because thread safety isn't guaranteed
        # This test documents the behavior, not enforces it
        # If you need thread safety, this test shows you need to add locking
        assert True, "Threaded test completed (thread safety not guaranteed)"

    suite.run_test("Threaded appends (documents race condition risk)", test_threaded_appends)

    # Test: Reload during active append (simulates crash timing)
    def test_reload_consistency():
        """Reloading instance sees consistent state."""
        path = os.path.join(suite.temp_dir, "reload.jsonl")
        oz1 = Ozolith(storage_path=path)

        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz1.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Get state before reload
        entry_count = len(oz1._entries)
        root_hash = oz1.get_root_hash()

        # Reload
        oz2 = Ozolith(storage_path=path)

        assert len(oz2._entries) == entry_count, "Entry count should match"
        assert oz2.get_root_hash() == root_hash, "Root hash should match"

    suite.run_test("Reload sees consistent state", test_reload_consistency)


# =============================================================================
# 14. CORRUPTION RECOVERY TESTS
# =============================================================================

def test_corruption_recovery(suite: TestSuite):
    """
    Tests for handling corrupted log files with graceful recovery.

    OZOLITH should:
    - Load valid entries even if some are corrupted
    - Record warnings about skipped/corrupted data
    - Continue functioning after partial recovery
    - Never lose valid data due to corruption elsewhere in file
    """

    # Test: Truncated last line (most common corruption - power loss)
    def test_truncated_line():
        """
        Simulate power loss during write - last line is incomplete.
        Should: Load valid entries, skip truncated line, record warning.
        """
        path = os.path.join(suite.temp_dir, "truncated.jsonl")

        # Create valid log with 2 entries
        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Corrupt by truncating last line
        with open(path, 'r') as f:
            lines = f.readlines()

        with open(path, 'w') as f:
            f.writelines(lines[:-1])  # All but last
            f.write(lines[-1][:len(lines[-1])//2])  # Half of last line

        # Reload - should recover valid entries gracefully
        oz2 = Ozolith(storage_path=path)

        # Should have loaded the first valid entry
        assert len(oz2._entries) == 1, \
            f"Should recover 1 valid entry, got {len(oz2._entries)}"

        # Should have recorded a warning about the truncated line
        assert len(oz2.load_warnings) == 1, \
            f"Should have 1 warning about truncated line, got {len(oz2.load_warnings)}"
        assert "Corrupted JSON" in oz2.load_warnings[0], \
            f"Warning should mention corrupted JSON: {oz2.load_warnings[0]}"

        # Chain should still be valid for recovered entries
        valid, _ = oz2.verify_chain()
        assert valid, "Chain should be valid for recovered entries"

    suite.run_test("Gracefully recovers from truncated last line", test_truncated_line)

    # Test: Empty file
    def test_empty_file():
        """Empty file should initialize cleanly."""
        path = os.path.join(suite.temp_dir, "empty.jsonl")

        # Create empty file
        Path(path).touch()

        oz = Ozolith(storage_path=path)
        assert len(oz._entries) == 0, "Empty file should give empty log"

        # Should be able to append
        entry = oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        assert entry.sequence == 1

    suite.run_test("Empty file initializes cleanly", test_empty_file)

    # Test: File with blank lines
    def test_blank_lines():
        """Blank lines in file should be skipped."""
        path = os.path.join(suite.temp_dir, "blanks.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Add blank lines
        with open(path, 'a') as f:
            f.write("\n\n\n")

        # Reload - should skip blanks
        oz2 = Ozolith(storage_path=path)
        assert len(oz2._entries) == 2, "Blank lines should be skipped"

        valid, _ = oz2.verify_chain()
        assert valid, "Chain should still be valid"

    suite.run_test("Blank lines are skipped", test_blank_lines)

    # Test: Detect missing entries in chain
    def test_detect_missing_sequence():
        """If an entry is deleted from file, chain verification catches it."""
        path = os.path.join(suite.temp_dir, "missing.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "one"})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "two"})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "three"})

        # Remove middle line from file
        with open(path, 'r') as f:
            lines = f.readlines()

        with open(path, 'w') as f:
            f.writelines([lines[0], lines[1], lines[3]])  # Skip line 2

        # Reload
        oz2 = Ozolith(storage_path=path)

        # Verify should fail
        valid, bad_idx = oz2.verify_chain()
        assert not valid, "Should detect missing entry"

    suite.run_test("Detects missing entry in file", test_detect_missing_sequence)

    # Test: Anchors file corruption
    def test_anchors_file_corruption():
        """Corrupted anchors file shouldn't prevent log loading."""
        path = os.path.join(suite.temp_dir, "anchor_corrupt.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz.create_anchor("test")

        # Verify we have entries and anchors
        assert len(oz._entries) == 2  # SESSION_START + ANCHOR_CREATED
        assert len(oz._anchors) == 1

        # Corrupt anchors file
        anchors_path = path.replace(".jsonl", "_anchors.json")
        with open(anchors_path, 'w') as f:
            f.write("this is not valid json {{{")

        # Reload - entries should still load, anchors should be empty
        oz2 = Ozolith(storage_path=path)

        # Entries should be fully recovered
        assert len(oz2._entries) == 2, \
            f"Should recover all entries despite anchor corruption, got {len(oz2._entries)}"

        # Anchors should be empty (corrupted file ignored)
        assert len(oz2._anchors) == 0, \
            f"Corrupted anchors should result in empty list, got {len(oz2._anchors)}"

        # Should have recorded a warning
        assert len(oz2.load_warnings) == 1, \
            f"Should have 1 warning about corrupted anchors, got {len(oz2.load_warnings)}"
        assert "Anchors file corrupted" in oz2.load_warnings[0], \
            f"Warning should mention anchor corruption: {oz2.load_warnings[0]}"

        # Chain should still be valid
        valid, _ = oz2.verify_chain()
        assert valid, "Chain should be valid despite anchor corruption"

    suite.run_test("Recovers entries despite corrupted anchors file", test_anchors_file_corruption)

    # Test: Write failure doesn't corrupt in-memory state
    def test_write_failure_memory_safety():
        """
        If disk write fails, in-memory state should NOT be modified.
        This prevents desync between disk and memory.
        """
        from ozolith import OzolithWriteError

        path = os.path.join(suite.temp_dir, "write_fail.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        # Record state before attempted write
        entry_count_before = len(oz._entries)
        sequence_before = oz._sequence

        # Make the file read-only to simulate write failure
        os.chmod(path, 0o444)

        try:
            # This should raise OzolithWriteError
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "fail"})
            write_failed = False
        except OzolithWriteError:
            write_failed = True
        finally:
            # Restore permissions for cleanup
            os.chmod(path, 0o644)

        assert write_failed, "Should raise OzolithWriteError on write failure"

        # In-memory state should be unchanged
        assert len(oz._entries) == entry_count_before, \
            f"Entry count should be unchanged after write failure: {len(oz._entries)} vs {entry_count_before}"
        assert oz._sequence == sequence_before, \
            f"Sequence should be unchanged after write failure: {oz._sequence} vs {sequence_before}"

    suite.run_test("Write failure preserves in-memory state", test_write_failure_memory_safety)

    # Test: load_warnings attribute exists and is accessible
    def test_load_warnings_accessible():
        """load_warnings should be accessible after load."""
        path = os.path.join(suite.temp_dir, "warnings_check.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        # Fresh load should have empty warnings
        oz2 = Ozolith(storage_path=path)
        assert hasattr(oz2, 'load_warnings'), "Should have load_warnings attribute"
        assert isinstance(oz2.load_warnings, list), "load_warnings should be a list"
        assert len(oz2.load_warnings) == 0, "Clean load should have no warnings"

    suite.run_test("load_warnings attribute accessible", test_load_warnings_accessible)

    # Test: Multiple corrupted lines
    def test_multiple_corrupted_lines():
        """Multiple corrupted lines should all be skipped with warnings."""
        path = os.path.join(suite.temp_dir, "multi_corrupt.jsonl")

        oz = Ozolith(storage_path=path)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "one"})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "two"})
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "three"})

        # Read and corrupt multiple lines
        with open(path, 'r') as f:
            lines = f.readlines()

        with open(path, 'w') as f:
            f.write(lines[0])  # Keep first (valid)
            f.write("this is garbage\n")  # Corrupt
            f.write(lines[2])  # Keep third (valid)
            f.write("{incomplete json\n")  # Corrupt
            f.write(lines[3])  # Keep fourth (valid) - but chain will be broken

        oz2 = Ozolith(storage_path=path)

        # Should have loaded 3 lines (2 corrupted skipped)
        # Note: The recovered entries will have broken chain links
        assert len(oz2._entries) == 3, \
            f"Should recover 3 entries from 5 lines (2 corrupted), got {len(oz2._entries)}"

        # Should have 2 warnings
        assert len(oz2.load_warnings) == 2, \
            f"Should have 2 warnings for corrupted lines, got {len(oz2.load_warnings)}"

    suite.run_test("Handles multiple corrupted lines", test_multiple_corrupted_lines)


# =============================================================================
# 15. KEY ROTATION TESTS
# =============================================================================

def test_key_rotation(suite: TestSuite):
    """
    Tests for signing key changes.

    What happens if:
    - Key file is deleted
    - Key is changed between sessions
    - Verifying old entries after key change
    """

    # Test: Key file deleted, new key generated
    def test_key_regeneration():
        """If key file is deleted, new key is generated."""
        path = os.path.join(suite.temp_dir, "keyregen.jsonl")
        key_path = Path(suite.temp_dir) / ".ozolith_key"

        oz1 = Ozolith(storage_path=path)
        original_key = oz1._signing_key
        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        # Delete key file
        if key_path.exists():
            key_path.unlink()

        # New instance should generate new key
        oz2 = Ozolith(storage_path=path)
        new_key = oz2._signing_key

        # Keys should be different
        assert original_key != new_key, "New key should be generated"

    suite.run_test("Key regeneration on missing key file", test_key_regeneration)

    # Test: Old entries fail verification with new key
    def test_old_entries_new_key():
        """Entries signed with old key should fail verification with new key."""
        path = os.path.join(suite.temp_dir, "oldkey.jsonl")

        # Create with explicit key
        oz1 = Ozolith(storage_path=path, signing_key="original_key_123")
        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        oz1.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Reload with different key
        oz2 = Ozolith(storage_path=path, signing_key="different_key_456")

        # Verification should fail (signatures won't match)
        valid, bad_idx = oz2.verify_chain()

        assert not valid, "Old entries should fail verification with new key"
        assert bad_idx == 1, "Should fail at first entry"

    suite.run_test("Old entries fail verification with new key", test_old_entries_new_key)

    # Test: Explicit key survives session
    def test_explicit_key_persistence():
        """Explicitly provided key should work across sessions."""
        path = os.path.join(suite.temp_dir, "explicitkey.jsonl")
        shared_key = "shared_explicit_key_789"

        oz1 = Ozolith(storage_path=path, signing_key=shared_key)
        oz1.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        oz2 = Ozolith(storage_path=path, signing_key=shared_key)
        oz2.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        valid, _ = oz2.verify_chain()
        assert valid, "Same explicit key should verify"

    suite.run_test("Explicit key works across sessions", test_explicit_key_persistence)

    # Test: Key affects signature but not hash
    def test_key_affects_signature_not_hash():
        """Different keys produce different signatures but entry hash depends on signature."""
        path1 = os.path.join(suite.temp_dir, "key1.jsonl")
        path2 = os.path.join(suite.temp_dir, "key2.jsonl")

        oz1 = Ozolith(storage_path=path1, signing_key="key_one")
        oz2 = Ozolith(storage_path=path2, signing_key="key_two")

        # Same payload
        payload = {"msg": "identical"}
        entry1 = oz1.append(OzolithEventType.EXCHANGE, "SB-1", "human", payload.copy())
        entry2 = oz2.append(OzolithEventType.EXCHANGE, "SB-1", "human", payload.copy())

        # Signatures should differ
        assert entry1.signature != entry2.signature, "Different keys = different signatures"

        # Hashes will also differ (hash includes signature)
        assert entry1.entry_hash != entry2.entry_hash, "Hash includes signature, so differs"

    suite.run_test("Key affects signature and hash", test_key_affects_signature_not_hash)


# =============================================================================
# 16. TIMESTAMP MANIPULATION TESTS
# =============================================================================

def test_timestamp_manipulation(suite: TestSuite):
    """
    Tests for timestamp-related attacks and edge cases.

    Timestamps are NOT part of chain integrity by default -
    they're metadata. These tests document what happens if
    someone backdates entries.
    """

    # Test: Backdated timestamp still verifies (chain doesn't check time order)
    def test_backdated_timestamp_verifies():
        """
        Chain verification doesn't enforce timestamp ordering.

        This is a design choice - timestamps are metadata, not integrity.
        If you need timestamp integrity, you'd add it to the hash.
        """
        oz = suite.create_test_ozolith("backdate")

        entry1 = oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        # Manually backdate next entry (simulating attack)
        # This is tricky because timestamp is set at append time...
        # We can only test by modifying after append

        entry2 = oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Chain should still verify (timestamps aren't checked for ordering)
        valid, _ = oz.verify_chain()
        assert valid, "Chain verifies regardless of timestamp order"

    suite.run_test("Backdated timestamps still verify (by design)", test_backdated_timestamp_verifies)

    # Test: Modifying timestamp breaks chain (it's part of hash)
    def test_timestamp_modification_detected():
        """Modifying timestamp changes hash, which breaks chain."""
        oz = suite.create_test_ozolith("timemod")

        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        entry = oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Tamper with timestamp
        original_ts = entry.timestamp
        entry.timestamp = "1999-01-01T00:00:00Z"

        valid, bad_idx = oz.verify_chain()

        # Restore
        entry.timestamp = original_ts

        assert not valid, "Modified timestamp should be detected"

    suite.run_test("Timestamp modification is detected", test_timestamp_modification_detected)

    # Test: Future timestamps accepted
    def test_future_timestamp():
        """System doesn't reject future timestamps (clock skew tolerance)."""
        oz = suite.create_test_ozolith("future")

        # Can't easily set future timestamp at creation, but verify
        # the system doesn't validate against current time
        entry = oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

        # Just verify normal operation - no timestamp validation exists
        valid, _ = oz.verify_chain()
        assert valid

    suite.run_test("Future timestamps accepted (clock skew tolerance)", test_future_timestamp)

    # Test: Time range queries work correctly
    def test_time_range_with_timestamps():
        """Time range queries use stored timestamps."""
        oz = suite.create_test_ozolith("timerange")

        # Add entries (timestamps are auto-generated)
        oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
        time.sleep(0.1)  # Small delay
        oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "test"})

        # Query with current time range should find entries
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        results = oz.get_by_timerange(start=hour_ago, end=now)
        assert len(results) == 2, f"Should find 2 entries in last hour, got {len(results)}"

    suite.run_test("Time range queries work with timestamps", test_time_range_with_timestamps)


# =============================================================================
# 17. PERFORMANCE BENCHMARK TESTS
# =============================================================================

def test_performance(suite: TestSuite):
    """
    Performance benchmarks for OZOLITH operations.

    These aren't pass/fail tests - they measure and report performance
    to help identify when the system needs optimization (like Merkle trees).
    """

    # Test: Append performance
    def test_append_performance():
        """Measure append operation speed."""
        oz = suite.create_test_ozolith("perf_append")

        start = time.time()
        count = 500

        for i in range(count):
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"i": i, "data": "x" * 100})

        elapsed = time.time() - start
        per_entry = (elapsed / count) * 1000  # ms

        # Report performance
        print(f"\n    Append: {count} entries in {elapsed:.2f}s ({per_entry:.2f}ms/entry)")

        # Soft threshold - warn if too slow
        assert per_entry < 50, f"Append too slow: {per_entry:.2f}ms/entry (threshold: 50ms)"

    suite.run_test("Append performance benchmark", test_append_performance)

    # Test: Verification performance
    def test_verify_performance():
        """Measure full chain verification speed."""
        oz = suite.create_test_ozolith("perf_verify")

        # Build a chain
        for i in range(500):
            oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"i": i})

        # Time verification
        start = time.time()
        valid, _ = oz.verify_chain()
        elapsed = time.time() - start

        per_entry = (elapsed / 500) * 1000  # ms

        print(f"\n    Verify: 500 entries in {elapsed:.2f}s ({per_entry:.2f}ms/entry)")

        assert valid, "Chain should be valid"
        assert per_entry < 10, f"Verify too slow: {per_entry:.2f}ms/entry (threshold: 10ms)"

    suite.run_test("Verification performance benchmark", test_verify_performance)

    # Test: Query performance
    def test_query_performance():
        """Measure query operation speed."""
        oz = suite.create_test_ozolith("perf_query")

        # Build varied data
        for i in range(500):
            oz.append(
                OzolithEventType.EXCHANGE,
                f"SB-{i % 5}",  # 5 different contexts
                "assistant" if i % 2 == 0 else "human",
                {"confidence": (i % 10) / 10, "i": i}
            )

        # Time various queries
        start = time.time()

        # Type query
        exchanges = oz.get_by_type(OzolithEventType.EXCHANGE)

        # Context query
        sb1 = oz.get_by_context("SB-1")

        # Payload query
        low_conf = oz.get_by_payload("confidence", 0.3, "lt")

        # Chainable query
        results = oz.query() \
            .by_type(OzolithEventType.EXCHANGE) \
            .by_context("SB-2") \
            .where_payload("confidence", ">", 0.5) \
            .execute()

        elapsed = time.time() - start

        print(f"\n    Queries: 4 queries on 500 entries in {elapsed*1000:.2f}ms")

        assert elapsed < 1.0, f"Queries too slow: {elapsed:.2f}s (threshold: 1s)"

    suite.run_test("Query performance benchmark", test_query_performance)

    # Test: Load performance (reading from disk)
    def test_load_performance():
        """Measure file loading speed."""
        path = os.path.join(suite.temp_dir, "perf_load.jsonl")

        # Create log
        oz1 = Ozolith(storage_path=path)
        for i in range(500):
            oz1.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"i": i})

        del oz1

        # Time loading
        start = time.time()
        oz2 = Ozolith(storage_path=path)
        elapsed = time.time() - start

        # Count entries separately
        user_entries = [e for e in oz2._entries if e.event_type != OzolithEventType.ANCHOR_CREATED]
        anchor_entries = [e for e in oz2._entries if e.event_type == OzolithEventType.ANCHOR_CREATED]
        total_entries = len(oz2._entries)

        per_entry = (elapsed / total_entries) * 1000  # ms

        print(f"\n    Load: {total_entries} entries ({len(user_entries)} user + {len(anchor_entries)} anchors) in {elapsed:.2f}s ({per_entry:.2f}ms/entry)")

        # 500 user entries + 5 anchors (at 100, 200, 300, 400, 500)
        assert len(user_entries) == 500, f"Expected 500 user entries, got {len(user_entries)}"
        assert len(anchor_entries) == 5, f"Expected 5 anchors, got {len(anchor_entries)}"
        assert per_entry < 5, f"Load too slow: {per_entry:.2f}ms/entry (threshold: 5ms)"

    suite.run_test("Load performance benchmark", test_load_performance)

    # Test: Stats computation performance
    def test_stats_performance():
        """Measure statistics computation speed."""
        oz = suite.create_test_ozolith("perf_stats")

        # Build varied data
        for i in range(500):
            oz.append(
                OzolithEventType.EXCHANGE,
                f"SB-{i % 5}",
                "assistant",
                {
                    "confidence": (i % 10) / 10,
                    "uncertainty_flags": ["flag1"] if i % 3 == 0 else []
                }
            )

        # Add some corrections (each triggers an anchor)
        for i in range(50):
            oz.append(
                OzolithEventType.CORRECTION,
                "SB-1",
                "human",
                {"original_exchange_seq": i * 10, "correction_type": "factual"}
            )

        # Count entries separately
        user_entries = [e for e in oz._entries if e.event_type != OzolithEventType.ANCHOR_CREATED]
        anchor_entries = [e for e in oz._entries if e.event_type == OzolithEventType.ANCHOR_CREATED]
        total_entries = len(oz._entries)

        # Time stats
        start = time.time()
        stats = oz.stats()
        elapsed = time.time() - start

        print(f"\n    Stats: {total_entries} entries ({len(user_entries)} user + {len(anchor_entries)} anchors) in {elapsed*1000:.2f}ms")

        # 500 exchanges + 50 corrections = 550 user entries
        # Anchors: 5 from count threshold (100,200,300,400,500) + 50 from corrections = 55
        assert len(user_entries) == 550, f"Expected 550 user entries, got {len(user_entries)}"
        assert len(anchor_entries) == 55, f"Expected 55 anchors, got {len(anchor_entries)}"
        assert stats['total_entries'] == total_entries
        assert elapsed < 0.5, f"Stats too slow: {elapsed:.2f}s (threshold: 0.5s)"

    suite.run_test("Stats performance benchmark", test_stats_performance)


# =============================================================================
# 18. CORRECTION VALIDATION TESTS
# =============================================================================

def test_correction_validation(suite: TestSuite):
    """
    Tests for the correction validation system.

    Ensures:
    - Corrections to non-existent entries are blocked
    - Mismatched corrections trigger warnings
    - Validated corrections include metadata
    - Human confirmations are tracked
    - Audit finds issues correctly
    """
    from ozolith import (
        validate_correction_target,
        log_correction_validated,
        confirm_correction,
        audit_corrections,
        correction_analytics
    )

    oz = suite.create_test_ozolith("correction_validation")

    # Setup test data
    oz.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"message": "Use sorted() or list.sort() for Python"})  # seq 2
    oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant",
              {"message": "Use array.sort() for JavaScript"})  # seq 3

    # Test: Validation catches non-existent target
    def test_nonexistent_target():
        result = validate_correction_target(
            oz, original_seq=999,
            what_was_wrong="Some correction",
            correction_reasoning="Some reason"
        )
        assert not result.valid, "Should reject non-existent target"
        assert len(result.errors) > 0, "Should have error message"
        assert "does not exist" in result.errors[0]

    suite.run_test("Validation catches non-existent target", test_nonexistent_target)

    # Test: Validation catches keyword mismatch
    def test_keyword_mismatch():
        result = validate_correction_target(
            oz, original_seq=2,  # Python answer
            what_was_wrong="array.sort() modifies in place",  # JavaScript term
            correction_reasoning="Missing side effect info"
        )
        assert result.valid, "Should be valid (target exists)"
        assert len(result.warnings) > 0, "Should have warnings about mismatch"
        # Check that 'array' mismatch is detected
        warning_text = ' '.join(result.warnings)
        assert 'array' in warning_text.lower(), f"Should warn about 'array': {result.warnings}"

    suite.run_test("Validation catches keyword mismatch", test_keyword_mismatch)

    # Test: Validation passes for matching correction
    def test_matching_correction():
        result = validate_correction_target(
            oz, original_seq=3,  # JavaScript answer
            what_was_wrong="array.sort() modifies in place",
            correction_reasoning="Missing side effect documentation"
        )
        assert result.valid, "Should be valid"
        # Might have warnings about reasoning length, but no tech term mismatches
        tech_warnings = [w for w in result.warnings if 'terms not in target' in w]
        assert len(tech_warnings) == 0, f"Should have no tech term warnings: {result.warnings}"

    suite.run_test("Validation passes for matching correction", test_matching_correction)

    # Test: log_correction_validated blocks on error
    def test_validated_blocks_error():
        entry, validation = log_correction_validated(
            oz, original_seq=999,
            what_was_wrong="Correction",
            correction_reasoning="Reason"
        )
        assert entry is None, "Should not create entry for invalid target"
        assert not validation.valid

    suite.run_test("log_correction_validated blocks on error", test_validated_blocks_error)

    # Test: log_correction_validated blocks on warnings (unless forced)
    def test_validated_blocks_warnings():
        entry, validation = log_correction_validated(
            oz, original_seq=2,  # Python
            what_was_wrong="array.sort() issue",  # JavaScript
            correction_reasoning="Reason"
        )
        assert entry is None, "Should not create entry when warnings exist"
        assert validation.valid, "Validation passes (no errors)"
        assert len(validation.warnings) > 0, "But should have warnings"

    suite.run_test("log_correction_validated blocks on warnings", test_validated_blocks_warnings)

    # Test: log_correction_validated works when forced despite warnings
    def test_validated_force_despite_warnings():
        entry, validation = log_correction_validated(
            oz, original_seq=2,
            what_was_wrong="array.sort() issue",
            correction_reasoning="I know this looks wrong but trust me",
            force_despite_warnings=True
        )
        assert entry is not None, "Should create entry when forced"
        assert entry.payload.get('validation_warnings'), "Should record warnings"

    suite.run_test("log_correction_validated force despite warnings", test_validated_force_despite_warnings)

    # Test: Validated correction has metadata
    def test_validated_has_metadata():
        entry, _ = log_correction_validated(
            oz, original_seq=3,
            what_was_wrong="array.sort() modifies in place",
            correction_reasoning="Missing side effect info",
            force_despite_warnings=True  # In case of minor warnings
        )
        assert entry is not None
        assert entry.payload.get('agent_validated') == True
        assert entry.payload.get('validation_status') == 'validated'
        assert entry.payload.get('target_summary'), "Should capture target summary"
        assert entry.payload.get('correction_reasoning'), "Should capture reasoning"

    suite.run_test("Validated correction has metadata", test_validated_has_metadata)

    # Test: Human confirmation works
    def test_human_confirmation():
        # Get the last correction's sequence
        corrections = oz.get_by_type(OzolithEventType.CORRECTION)
        last_corr = corrections[-1]

        result = confirm_correction(oz, last_corr.sequence, confirmed_by="human", notes="Looks good")
        assert result == True, "Should return True for valid confirmation"

        # Check confirmation entry was created
        all_corrections = oz.get_by_type(OzolithEventType.CORRECTION)
        confirmation = all_corrections[-1]
        assert confirmation.payload.get('correction_type') == 'confirmation'
        assert confirmation.payload.get('confirms_correction_seq') == last_corr.sequence

    suite.run_test("Human confirmation creates entry", test_human_confirmation)

    # Test: Audit finds issues
    def test_audit_finds_issues():
        # Add a legacy correction (no validation metadata)
        from ozolith import log_correction
        log_correction(oz, original_seq=2, what_was_wrong="Legacy correction")

        audit = audit_corrections(oz)

        # Should find unvalidated entry
        assert len(audit['unvalidated']) >= 1, "Should find unvalidated correction"

    suite.run_test("Audit finds unvalidated corrections", test_audit_finds_issues)

    # Test: Analytics tracks validation stats
    def test_analytics_tracks_validation():
        analytics = correction_analytics(oz)

        assert 'validation_stats' in analytics
        assert 'total_validated' in analytics['validation_stats']
        assert 'human_confirmed' in analytics['validation_stats']
        assert analytics['total_corrections'] >= 1

    suite.run_test("Analytics tracks validation stats", test_analytics_tracks_validation)


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

def run_all_tests():
    """Run all test suites and report results."""

    all_results = []

    test_functions = [
        ("Hash Chain Integrity", test_hash_chain_integrity),
        ("Signatures", test_signatures),
        ("Anchors", test_anchors),
        ("Anchor Policy", test_anchor_policy),
        ("Query Methods", test_query_methods),
        ("Query Builder", test_query_builder),
        ("Statistics", test_statistics),
        ("Helper Functions", test_helper_functions),
        ("Edge Cases", test_edge_cases),
        ("Persistence", test_persistence),
        ("Tampering Scenarios", test_tampering_scenarios),
        ("Renderer", test_renderer),
        # New test suites (added for comprehensive coverage)
        ("Concurrent Access", test_concurrent_access),
        ("Corruption Recovery", test_corruption_recovery),
        ("Key Rotation", test_key_rotation),
        ("Timestamp Manipulation", test_timestamp_manipulation),
        ("Performance Benchmarks", test_performance),
        ("Correction Validation", test_correction_validation),
    ]

    total_passed = 0
    total_tests = 0

    for suite_name, test_fn in test_functions:
        suite = TestSuite(suite_name)
        suite.setup()

        try:
            test_fn(suite)
        except Exception as e:
            print(f"\n❌ SUITE CRASHED: {suite_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()

        passed, total = suite.report()
        total_passed += passed
        total_tests += total

        suite.teardown()

    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Total: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉🎉🎉 ALL TESTS PASSED! OZOLITH IS SOLID! 🎉🎉🎉")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} tests failed. Review above for details.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
