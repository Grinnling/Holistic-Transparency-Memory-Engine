# OZOLITH Test Mapping: Automated ↔ Manual Walkthrough

Created: 2025-12-08
Updated: 2025-12-09
Purpose: Map automated test coverage to manual walkthrough sections for efficient review

**Test Count:** 122 automated tests across 18 test suites

---

## Quick Reference

| Walkthrough Section | Primary Test Suite(s) | Coverage Level |
|---------------------|----------------------|----------------|
| 1. Basic Chain Integrity | `test_hash_chain_integrity` | FULL |
| 2. Tampering Detection | `test_hash_chain_integrity`, `test_tampering_scenarios` | FULL |
| 3. Correction System | `test_tampering_scenarios`, `test_helper_functions`, `test_correction_validation` | FULL |
| 4. Anchors (Checkpoints) | `test_anchors`, `test_anchor_policy` | FULL |
| 5. Query Capabilities | `test_query_methods`, `test_query_builder` | FULL |
| 6. Statistics & Learning | `test_statistics`, `test_helper_functions` | FULL |
| 7. Persistence | `test_persistence`, `test_corruption_recovery` | FULL |
| 8. Final Verification | `test_renderer` | FULL |

---

## Detailed Mapping

### Section 1: Basic Chain Integrity (Walkthrough lines 43-113)

**What it tests:** Does the hash chain actually link entries together?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 1.1 First Entry (empty previous_hash) | "First entry has empty previous_hash" | `test_hash_chain_integrity` |
| 1.2 Chain Linking (previous matches entry_hash) | "Subsequent entries link to previous hash" | `test_hash_chain_integrity` |
| 1.3 Verify the Chain | "verify_chain() passes on untampered log" | `test_hash_chain_integrity` |

**Review strategy:**
- If automated passes: Review walkthrough for *understanding* only
- If automated fails: Walk through manually to see WHERE chain breaks

---

### Section 2: Tampering Detection (Walkthrough lines 115-183)

**What it tests:** Can we detect when someone modifies the log?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 2.1 Modify Payload | "Detects content modification" | `test_hash_chain_integrity` |
| 2.2 Break Chain Link | "Detects broken chain link" | `test_hash_chain_integrity` |
| 2.3 Verify Restoration | (implicit in all tests that restore state) | - |

**Additional automated coverage:**
- "Detects direct hash modification" | `test_hash_chain_integrity`
- "Detects inserted entry" | `test_tampering_scenarios`
- "Detects deleted entry" | `test_tampering_scenarios`
- "Detects swapped entries" | `test_tampering_scenarios`
- "Detects payload modification" | `test_tampering_scenarios`
- "Detects entry signed with wrong key" | `test_tampering_scenarios`

**Review strategy:**
- Automated covers MORE attack vectors than walkthrough
- Manual walkthrough good for seeing tamper detection in action

---

### Section 3: The Correction System (Walkthrough lines 185-275)

**What it tests:** Can corrections hide tampering? (Answer: NO)

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 3.1 Add an Exchange to Correct | (setup for test) | - |
| 3.2 Log a Correction | "log_correction() creates entry" | `test_helper_functions` |
| 3.3 Original Entry Still Exists | (implicit - corrections are NEW entries) | - |
| 3.4 Can We Find Corrections? | "get_corrections_for() finds linked corrections" | `test_query_methods` |
| 3.5 Corrections Can't Hide Tampering | "Corrections can't hide tampering" | `test_tampering_scenarios` |

**Key insight this section teaches:**
- Corrections are METADATA, not modifications
- Original entry stays untouched in chain
- Hash chain catches tampering regardless of corrections

**Review strategy:**
- If "Corrections can't hide tampering" passes: Core guarantee is solid
- Manual walkthrough helps understand WHY this is important

---

### Section 4: Anchors (Checkpoints) (Walkthrough lines 277-329)

**What it tests:** Can we create snapshots for external verification?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 4.1 Create an Anchor | "Anchor captures correct root hash" | `test_anchors` |
| 4.2 Verify Against Anchor | "verify_against_anchor() passes on untampered log" | `test_anchors` |
| 4.3 Export Anchor | "export_anchor() produces valid dict" | `test_anchors` |

**Additional automated coverage:**
- "Anchor has correct sequence range" | `test_anchors`
- "Anchor has signature" | `test_anchors`
- "verify_against_anchor() detects tampering" | `test_anchors`
- All anchor policy triggers | `test_anchor_policy`

**Review strategy:**
- Automated tests anchor mechanics thoroughly
- Manual walkthrough shows what exported anchor LOOKS like (useful for understanding)

---

### Section 5: Query Capabilities (Walkthrough lines 331-409)

**What it tests:** Can the AI find what it needs in the log?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 5.1 Add More Test Data | (setup) | - |
| 5.2 Query by Type | "get_by_type() filters correctly" | `test_query_methods` |
| 5.3 Query by Context | "get_by_context() filters correctly" | `test_query_methods` |
| 5.4 Find Uncertain Exchanges | "get_uncertain_exchanges() filters by threshold" | `test_query_methods` |
| 5.5 Chainable Query Builder | All tests in `test_query_builder` | `test_query_builder` |

**Query builder coverage:**
- Single filter
- Multiple filters (AND)
- where_payload comparators (<, >, =)
- has_uncertainty_flag
- with_corrections
- count(), first(), last()
- by_actor, by_types

**Review strategy:**
- Automated covers all query methods
- Manual walkthrough useful for seeing query RESULTS (what data looks like)

---

### Section 6: Statistics & Learning (Walkthrough lines 411-446)

**What it tests:** Can we analyze patterns in the log?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 6.1 Full Statistics | All stats tests | `test_statistics` |
| 6.2 Find Learning Opportunities | "find_learning_opportunities() finds issues" | `test_helper_functions` |

**Stats coverage:**
- total_entries
- by_type counts
- avg_confidence
- confidence_distribution (low/medium/high)
- uncertainty_flag_counts
- correction_rate
- corrections_by_type
- most_active_contexts

**Review strategy:**
- Automated verifies stats compute correctly
- Manual walkthrough shows what rendered stats LOOK like

---

### Section 7: Persistence (Walkthrough lines 448-639)

**What it tests:** Does data survive a restart? Does OZOLITH handle corruption gracefully?

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 7.1 Note Current State | (setup) | - |
| 7.2 Simulate Restart | "Entries survive restart" | `test_persistence` |
| 7.3 Chain Still Valid | "Chain valid after restart" | `test_persistence` |
| 7.4 Graceful Recovery from Corruption | "Gracefully recovers from truncated last line" | `test_corruption_recovery` |
| 7.5 Anchor File Corruption Recovery | "Recovers entries despite corrupted anchors file" | `test_corruption_recovery` |
| 7.6 Write Failure Handling | "Write failure preserves in-memory state" | `test_corruption_recovery` |
| 7.7 Check Raw File Format | (interactive - understand JSONL structure) | - |

**Additional automated coverage:**
- "Sequence continues after restart" | `test_persistence`
- "Anchors survive restart" | `test_persistence`
- "Empty file initializes cleanly" | `test_corruption_recovery`
- "Blank lines are skipped" | `test_corruption_recovery`
- "Detects missing entry in file" | `test_corruption_recovery`
- "load_warnings attribute accessible" | `test_corruption_recovery`
- "Handles multiple corrupted lines" | `test_corruption_recovery`

**Key behaviors verified:**
- Truncated lines are skipped, valid entries recovered
- Corrupted anchor file doesn't lose entry data
- Write failures raise `OzolithWriteError`, memory state unchanged
- `load_warnings` attribute shows what was lost on load

**Review strategy:**
- Automated covers all persistence AND corruption scenarios
- Manual walkthrough useful for understanding recovery behavior

---

### Section 8: Final Verification (Walkthrough lines 641-656)

**What it tests:** Full chain verification and review

| Walkthrough Test | Automated Test | Suite |
|------------------|----------------|-------|
| 8.1 Full Chain Verification | "render_verification_report() for valid chain" | `test_renderer` |
| 8.2 Review What We Built | (interactive - no automated equivalent) | - |

**Review strategy:**
- Run automated tests first to confirm everything works
- Manual Section 8 is the "victory lap" - verify with your own eyes

---

## New Test Suites (Not in Original Walkthrough)

These automated tests cover scenarios beyond the original walkthrough:

### 13. Concurrent Access (4 tests)
- Sequential multi-instance appends
- Rapid sequential appends (100 entries)
- Threaded appends (documents race condition risk)
- Reload sees consistent state

**Why it matters:** Multi-interface systems (React + CLI) need this

### 14. Corruption Recovery (8 tests) - NOW IN WALKTHROUGH
- Gracefully recovers from truncated last line
- Empty file initializes cleanly
- Blank lines are skipped
- Detects missing entry in file
- Recovers entries despite corrupted anchors file
- Write failure preserves in-memory state
- load_warnings attribute accessible
- Handles multiple corrupted lines

**Why it matters:** Real-world file corruption scenarios. Added to walkthrough Section 7.

### 15. Key Rotation (4 tests)
- Key regeneration on missing key file
- Old entries fail with new key
- Explicit key across sessions
- Key affects signature and hash

**Why it matters:** Key management is critical for signature verification

### 16. Timestamp Manipulation (4 tests)
- Backdated timestamps still verify (by design)
- Timestamp modification detected
- Future timestamps accepted
- Time range queries work

**Why it matters:** Understanding what timestamps DO and DON'T protect

### 17. Performance Benchmarks (5 tests)
- Append: ~1ms/entry (with fsync)
- Verify: <0.02ms/entry
- Query: 4 queries in <0.5ms on 500 entries
- Load: <0.01ms/entry from disk
- Stats: <1ms for 600 entries

**Why it matters:** Know when you need Merkle trees

### 18. Correction Validation (10 tests) - NEW
- Validation catches non-existent target
- Validation catches keyword mismatch
- Validation passes for matching correction
- log_correction_validated blocks on error
- log_correction_validated blocks on warnings
- log_correction_validated force despite warnings
- Validated correction has metadata
- Human confirmation creates entry
- Audit finds unvalidated corrections
- Analytics tracks validation stats

**Why it matters:** Prevents incorrect corrections (pointing at wrong entry), enables human review workflow, provides correction analytics

---

## Review Decision Tree

```
Run automated tests
        │
        ▼
   All pass?
   ┌───┴───┐
   │       │
  YES      NO
   │       │
   ▼       ▼
Walkthrough     Look at which
is LEARNING     suite failed
session         │
   │            ▼
   │       Go to mapped
   │       walkthrough section
   │            │
   │            ▼
   │       Debug manually
   │       with context
   │            │
   └────────────┘
            │
            ▼
    Understand WHY
    (both success & failure)
```

---

## Sections to Always Review Manually

Even with passing tests, these are worth walking through:

1. **Section 3 (Corrections)** - The conceptual distinction matters
2. **Section 4.3 (Export Anchor)** - See what you'd actually store externally
3. **Section 8.2 (Review What We Built)** - Interactive exploration

---

## Running the Tests

```bash
cd ~/Development/CODE_IMPLEMENTATION
python3 tests/test_ozolith.py
```

Or with pytest for more detail:
```bash
python3 -m pytest tests/test_ozolith.py -v
```
