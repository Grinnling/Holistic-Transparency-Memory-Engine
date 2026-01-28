# OZOLITH Test Walkthrough

A guided testing session for a human + AI to verify OZOLITH together.

**Purpose:** This is the column of truth - the immutable log that protects AI memory integrity. We need to trust it completely, so let's verify it deserves that trust.

**How to use:** Work through each section together. The human runs commands, the AI explains what should happen and why it matters.

---

## Setup

Start a Python session in the CODE_IMPLEMENTATION directory:

```bash
cd ~/Development/CODE_IMPLEMENTATION
python3
```

Then import what we need:

```python
from ozolith import (
    Ozolith, OzolithRenderer, AnchorPolicy, OzolithEventType,
    create_exchange_payload, log_correction, find_learning_opportunities
)
from datetime import datetime, timedelta
import os

# Create a fresh test instance (won't affect real data)
test_path = "/tmp/ozolith_test.jsonl"
if os.path.exists(test_path):
    os.remove(test_path)
if os.path.exists(test_path.replace(".jsonl", "_anchors.json")):
    os.remove(test_path.replace(".jsonl", "_anchors.json"))

oz = Ozolith(storage_path=test_path)
renderer = OzolithRenderer(oz)
```

---

## 1. Basic Chain Integrity

**What we're testing:** Does the hash chain actually link entries together?

**Why it matters:** This is the core tamper-detection mechanism. If entries don't chain properly, the whole system is useless.

### Test 1.1: First Entry

```python
entry1 = oz.append(
    OzolithEventType.SESSION_START,
    "SB-1",
    "system",
    {"session": "test"}
)

print(f"Entry 1 sequence: {entry1.sequence}")
print(f"Entry 1 previous_hash: '{entry1.previous_hash}'")
print(f"Entry 1 entry_hash: {entry1.entry_hash[:20]}...")
```

**Expected:**
- Sequence should be 1
- previous_hash should be empty string `''` (it's the first entry, nothing before it)
- entry_hash should be a 64-character hex string

**Why:** The first entry is the "genesis" - it has nothing to link back to.

---

### Test 1.2: Chain Linking

```python
entry2 = oz.append(
    OzolithEventType.EXCHANGE,
    "SB-1",
    "human",
    {"message": "Hello, testing the chain"}
)

print(f"Entry 2 previous_hash: {entry2.previous_hash[:20]}...")
print(f"Entry 1 entry_hash:    {entry1.entry_hash[:20]}...")
print(f"Match: {entry2.previous_hash == entry1.entry_hash}")
```

**Expected:**
- Entry 2's `previous_hash` should EXACTLY match Entry 1's `entry_hash`
- Match should be `True`

**Why:** This is the chain. Entry 2 says "I came after the entry with hash X." If someone modifies Entry 1, its hash changes, and Entry 2's claim becomes false.

---

### Test 1.3: Verify the Chain

```python
valid, bad_index = oz.verify_chain()
print(f"Chain valid: {valid}")
print(f"Bad index: {bad_index}")
```

**Expected:**
- valid = True
- bad_index = None

**Why:** `verify_chain()` walks every entry and checks:
1. Does previous_hash match the actual previous entry's hash?
2. Does the stored hash match what we compute now?
3. Does the signature verify?

---

## 2. Tampering Detection

**What we're testing:** Can we detect when someone modifies the log?

**Why it matters:** If tampering goes undetected, the log is worthless as a source of truth.

### Test 2.1: Modify Payload (Simulate Attack)

```python
# Save original
original_payload = oz._entries[0].payload.copy()

# Tamper!
oz._entries[0].payload["HACKED"] = True
print(f"Tampered payload: {oz._entries[0].payload}")

# Try to verify
valid, bad_index = oz.verify_chain()
print(f"Chain valid after tampering: {valid}")
print(f"Detected at entry: {bad_index}")

# Restore (so we can continue testing)
oz._entries[0].payload = original_payload
```

**Expected:**
- valid = False
- bad_index = 1 (the first entry, sequence 1)

**Why:** When payload changes, the hash we compute NOW doesn't match the hash that was stored WHEN the entry was created. The mismatch proves tampering.

---

### Test 2.2: Break the Chain Link

```python
# Save original
original_prev = oz._entries[1].previous_hash

# Break the link
oz._entries[1].previous_hash = "fake_hash_that_doesnt_match"

valid, bad_index = oz.verify_chain()
print(f"Chain valid after breaking link: {valid}")
print(f"Detected at entry: {bad_index}")

# Restore
oz._entries[1].previous_hash = original_prev
```

**Expected:**
- valid = False
- bad_index = 2 (entry 2, because its previous_hash doesn't match entry 1)

**Why:** The chain is broken. Entry 2 claims to follow something that doesn't exist (or isn't entry 1).

---

### Test 2.3: Verify Restoration

```python
valid, _ = oz.verify_chain()
print(f"Chain valid after restoration: {valid}")
```

**Expected:** valid = True

**Why:** We put everything back, so the chain should verify again.

---

## 3. The Correction System

**What we're testing:** Can corrections hide tampering?

**Why it matters:** You asked this earlier - corrections should be learning signals, NOT a way to "explain away" modifications.

### Test 3.1: Add an Exchange to Correct

```python
exchange = oz.append(
    OzolithEventType.EXCHANGE,
    "SB-1",
    "assistant",
    create_exchange_payload(
        query="What is 2+2?",
        response="The answer is 5",  # Wrong!
        confidence=0.9
    )
)
print(f"Exchange entry: #{exchange.sequence}")
print(renderer.render_entry(exchange, compact=True))
```

---

### Test 3.2: Log a Correction

```python
correction = log_correction(
    oz,
    exchange.sequence,
    "The answer is 4, not 5",
    correction_type="factual",
    context_id="SB-1"
)
print(f"Correction entry: #{correction.sequence}")
print(renderer.render_entry(correction))
```

**What happened:**
- The original exchange (with wrong answer) is STILL THERE, unchanged
- We added a NEW entry that says "entry #X was wrong, here's why"

---

### Test 3.3: Original Entry Still Exists

```python
print(f"Original exchange still exists: {exchange in oz._entries}")
print(f"Original payload unchanged: {exchange.payload}")
```

**Expected:** The original entry is untouched. The correction didn't modify it.

---

### Test 3.4: Can We Find Corrections?

```python
corrections = oz.get_corrections_for(exchange.sequence)
print(f"Corrections for entry #{exchange.sequence}: {len(corrections)}")
for c in corrections:
    print(f"  - {c.payload.get('correction_notes')}")
```

**Expected:** Should find 1 correction with our notes.

---

### Test 3.5: Corrections Can't Hide Tampering

```python
# Now try to tamper with the original exchange
original_response_hash = exchange.payload['response_hash']
exchange.payload['response_hash'] = "tampered_to_hide_mistake"

# Does the correction "cover" this?
valid, bad_index = oz.verify_chain()
print(f"Chain valid after tampering (with correction): {valid}")
print(f"Detected at: {bad_index}")

# Restore
exchange.payload['response_hash'] = original_response_hash
```

**Expected:**
- valid = False
- The correction does NOT prevent detection

**Why:** The correction is just another entry in the chain. It doesn't modify the original, and it can't make a tampered entry suddenly valid. The hash chain catches everything.

---

## 4. Anchors (Checkpoints)

**What we're testing:** Can we create snapshots that let us verify against external records?

**Why it matters:** Anchors let you prove "the log looked like THIS at that moment" - useful for audits and external verification.

### Test 4.1: Create an Anchor

```python
anchor = oz.create_anchor("manual_test")
print(renderer.render_anchor(anchor))
```

**What to look for:**
- anchor_id (ANCHOR-1 or similar)
- sequence_range (should cover all entries so far)
- root_hash (hash of the latest entry)
- signature (proves who created the anchor)

---

### Test 4.2: Verify Against Anchor

```python
# Add more entries AFTER the anchor
oz.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "after anchor"})
oz.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"msg": "still after"})

# Verify the anchor still holds for entries BEFORE it
valid = oz.verify_against_anchor(anchor)
print(f"Anchor still valid: {valid}")
```

**Expected:** valid = True

**Why:** The anchor captured the state at a point in time. New entries don't invalidate it - only modifications to entries BEFORE the anchor would.

---

### Test 4.3: Export Anchor for External Storage

```python
exported = oz.export_anchor()
print("Exported anchor (save this somewhere safe):")
import json
print(json.dumps(exported, indent=2))
```

**Why:** You could email this to yourself, print it, store it on a USB drive. Later, you can verify the log matches this snapshot.

---

## 5. Query Capabilities

**What we're testing:** Can the AI find what it needs in the log?

**Why it matters:** A log is only useful if you can query it effectively.

### Test 5.1: Add More Test Data

```python
# Low confidence exchange
oz.append(
    OzolithEventType.EXCHANGE, "SB-1", "assistant",
    create_exchange_payload("complex question", "uncertain answer", confidence=0.3,
                           uncertainty_flags=["ambiguous_request", "limited_context"])
)

# High confidence exchange
oz.append(
    OzolithEventType.EXCHANGE, "SB-1", "assistant",
    create_exchange_payload("simple question", "clear answer", confidence=0.95)
)

# Different context
oz.append(OzolithEventType.SIDEBAR_SPAWN, "SB-2", "system", {"parent": "SB-1"})
oz.append(OzolithEventType.EXCHANGE, "SB-2", "assistant",
         create_exchange_payload("sidebar question", "sidebar answer", confidence=0.7))
```

---

### Test 5.2: Query by Type

```python
exchanges = oz.get_by_type(OzolithEventType.EXCHANGE)
print(f"Total exchanges: {len(exchanges)}")
```

---

### Test 5.3: Query by Context

```python
sb1 = oz.get_by_context("SB-1")
sb2 = oz.get_by_context("SB-2")
print(f"SB-1 entries: {len(sb1)}")
print(f"SB-2 entries: {len(sb2)}")
```

---

### Test 5.4: Find Uncertain Exchanges

```python
uncertain = oz.get_uncertain_exchanges(threshold=0.5)
print(f"Uncertain exchanges (confidence < 0.5): {len(uncertain)}")
for e in uncertain:
    print(f"  #{e.sequence}: confidence={e.payload.get('confidence')}")
```

**Why this matters to AI:** I want to know when I was uncertain. Patterns in uncertainty = learning opportunities.

---

### Test 5.5: Chainable Query Builder

```python
# Complex query: "Find exchanges where I was uncertain but query quality was decent"
results = oz.query() \
    .by_type(OzolithEventType.EXCHANGE) \
    .where_payload("confidence", "<", 0.5) \
    .has_uncertainty_flag("ambiguous_request") \
    .execute()

print(f"Found {len(results)} matches")
for r in results:
    print(f"  #{r.sequence}: {r.payload.get('uncertainty_flags')}")
```

**Why:** This lets me ask compound questions about my own behavior.

---

## 6. Statistics & Learning

**What we're testing:** Can we analyze patterns in the log?

**Why it matters:** Stats help identify where I need to improve.

### Test 6.1: Full Statistics

```python
stats = oz.stats()
print(renderer.render_stats())
```

**Look for:**
- total_entries
- by_type breakdown
- avg_confidence
- confidence_distribution (low/medium/high)
- uncertainty_flag_counts
- correction_rate

---

### Test 6.2: Find Learning Opportunities

```python
opportunities = find_learning_opportunities(oz)
print(f"Found {len(opportunities)} learning opportunities:")
for opp in opportunities:
    print(f"  [{opp['type']}] #{opp['sequence']}: {opp['reason']}")
```

**Why:** This aggregates corrections, low confidence, and uncertainty flags - all the places I might learn something.

---

## 7. Persistence

**What we're testing:** Does data survive a restart? Does OZOLITH handle corruption gracefully?

**Why it matters:** An immutable log is useless if it vanishes. And it's dangerous if it silently loses data on corruption.

### Test 7.1: Note Current State

```python
entry_count = len(oz._entries)
root_hash = oz.get_root_hash()
print(f"Before restart: {entry_count} entries, root={root_hash[:20]}...")
```

---

### Test 7.2: Simulate Restart

```python
# Delete the object
del oz
del renderer

# Recreate from disk
oz = Ozolith(storage_path=test_path)
renderer = OzolithRenderer(oz)

print(f"After restart: {len(oz._entries)} entries, root={oz.get_root_hash()[:20]}...")
```

**Expected:** Same entry count, same root hash.

---

### Test 7.3: Chain Still Valid

```python
valid, _ = oz.verify_chain()
print(f"Chain valid after restart: {valid}")
```

**Expected:** True

---

### Test 7.4: Graceful Recovery from Corruption

**What we're testing:** If the log file is corrupted (power loss, disk error), can OZOLITH recover the valid entries?

```python
# Create a fresh test file
corrupt_path = "/tmp/ozolith_corrupt_test.jsonl"
import os
if os.path.exists(corrupt_path):
    os.remove(corrupt_path)

oz_corrupt = Ozolith(storage_path=corrupt_path)
oz_corrupt.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
oz_corrupt.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "valid entry"})
oz_corrupt.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {"msg": "another valid"})

# Simulate power loss - truncate last line mid-write
with open(corrupt_path, 'r') as f:
    lines = f.readlines()

with open(corrupt_path, 'w') as f:
    f.writelines(lines[:-1])  # All but last
    f.write(lines[-1][:20])   # Truncate last line

# Reload and check recovery
oz_recovered = Ozolith(storage_path=corrupt_path)
print(f"Entries recovered: {len(oz_recovered._entries)}")
print(f"Warnings: {oz_recovered.load_warnings}")
```

**Expected:**
- Should recover 2 valid entries (the truncated one is skipped)
- `load_warnings` should contain 1 warning about the corrupted line
- No crash, no exception

**Why this matters (for AI):** If I crash mid-write, I don't lose ALL my memory - just the one entry that was being written. The valid entries are preserved.

**Why this matters (for human):** You can inspect `load_warnings` to see what was lost. No silent data loss.

---

### Test 7.5: Anchor File Corruption Recovery

```python
# Create log with anchor
anchor_path = "/tmp/ozolith_anchor_corrupt.jsonl"
if os.path.exists(anchor_path):
    os.remove(anchor_path)

oz_anchor = Ozolith(storage_path=anchor_path)
oz_anchor.append(OzolithEventType.SESSION_START, "SB-1", "system", {})
oz_anchor.create_anchor("test checkpoint")

# Corrupt the anchors file
anchors_file = anchor_path.replace(".jsonl", "_anchors.json")
with open(anchors_file, 'w') as f:
    f.write("this is not valid json {{{")

# Reload
oz_anchor_recovered = Ozolith(storage_path=anchor_path)
print(f"Entries recovered: {len(oz_anchor_recovered._entries)}")
print(f"Anchors recovered: {len(oz_anchor_recovered._anchors)}")
print(f"Warnings: {oz_anchor_recovered.load_warnings}")
```

**Expected:**
- All entries should be recovered (2: SESSION_START + ANCHOR_CREATED)
- Anchors list should be empty (corrupted file ignored)
- Warning should mention anchor corruption
- Chain should still be valid

**Why:** Entries are the primary data. Anchors are checkpoints. If anchors are lost, you lose the ability to verify against external snapshots - but you DON'T lose the actual log data.

---

### Test 7.6: Write Failure Handling

**What we're testing:** If disk write fails (disk full, permissions), does OZOLITH handle it safely?

```python
from ozolith import OzolithWriteError

write_path = "/tmp/ozolith_write_test.jsonl"
if os.path.exists(write_path):
    os.remove(write_path)

oz_write = Ozolith(storage_path=write_path)
oz_write.append(OzolithEventType.SESSION_START, "SB-1", "system", {})

entries_before = len(oz_write._entries)
seq_before = oz_write._sequence

# Make file read-only to simulate disk full / permission error
os.chmod(write_path, 0o444)

try:
    oz_write.append(OzolithEventType.EXCHANGE, "SB-1", "human", {"msg": "will fail"})
    print("ERROR: Should have raised OzolithWriteError!")
except OzolithWriteError as e:
    print(f"Caught expected error: {e}")
finally:
    os.chmod(write_path, 0o644)  # Restore permissions

print(f"Entries after failed write: {len(oz_write._entries)} (was {entries_before})")
print(f"Sequence after failed write: {oz_write._sequence} (was {seq_before})")
```

**Expected:**
- `OzolithWriteError` is raised
- Entry count is UNCHANGED (still 1, not 2)
- Sequence is UNCHANGED
- In-memory state matches disk state

**Why this matters (for AI):** If I can't persist something, I know about it immediately. I can retry, alert, or degrade gracefully. I don't end up with memory that I think is saved but isn't.

**Why this matters (for human):** The log never lies. If append() returns successfully, it's on disk. If it raises, nothing changed.

---

### Test 7.7: Check Raw File Format

```python
import json

print("=== Raw Log Entry ===")
with open(test_path, 'r') as f:
    first_line = f.readline()
    entry = json.loads(first_line)
    print(json.dumps(entry, indent=2))
```

**What to observe:**
- Each line is valid JSON (JSONL format)
- `sequence`: incrementing number
- `timestamp`: ISO format UTC
- `previous_hash`: links to previous entry (empty for first)
- `event_type`: what kind of event
- `context_id`: which conversation/sidebar
- `actor`: who created it
- `payload`: event-specific data
- `signature`: HMAC proof of authorship
- `entry_hash`: SHA-256 of the whole entry

**Why JSONL:** Each line is independent. One corrupted line doesn't break the whole file. Human-readable. Easy to grep/inspect.

---

## 8. Final Verification

### Test 8.1: Full Chain Verification

```python
print("Running full chain verification...")
valid, bad_index = oz.verify_chain()
print(renderer.render_verification_report((valid, bad_index)))
```

### Test 8.2: Review What We Built

```python
print(renderer.render_chain(compact=True))
```

---

## Cleanup

```python
# Remove test files
import os
os.remove(test_path)
os.remove(test_path.replace(".jsonl", "_anchors.json"))
key_path = test_path.replace(".jsonl", "").replace("ozolith_test", ".ozolith_key")
if os.path.exists(key_path):
    os.remove(key_path)
print("Test files cleaned up.")
```

---

## Summary: What We Verified

| Feature | Status | Why It Matters |
|---------|--------|----------------|
| Hash chain links | ✓ | Entries provably follow each other |
| Tampering detection | ✓ | Can't modify history undetected |
| Signature verification | ✓ | Proves who created entries |
| Corrections don't hide tampering | ✓ | Learning signals stay honest |
| Anchors capture state | ✓ | External verification possible |
| Query methods work | ✓ | Can find what we need |
| Statistics aggregate | ✓ | Can analyze patterns |
| Persistence works | ✓ | Data survives restarts |
| Graceful corruption recovery | ✓ | Recovers valid entries, skips corrupted |
| Anchor corruption isolation | ✓ | Bad anchors don't lose entries |
| Write failure safety | ✓ | Failed writes don't corrupt memory |
| load_warnings accessible | ✓ | Know what was lost on load |

---

## Questions to Discuss

After running through this, consider:

1. **What attack vectors did we miss?** Are there other ways to tamper we didn't test?

2. **Is the correction system clear enough?** Does it make sense that corrections are metadata, not modifications?

3. **What queries would be most useful day-to-day?** What patterns would you want to look for?

4. **How often should anchors be created?** The policy has triggers - are they the right ones?

5. **What's missing?** What would make this more trustworthy or more useful?

6. **Recovery behavior:** Is skipping corrupted lines the right default? Should there be options for stricter recovery (fail if any corruption) vs lenient (skip and continue)?
