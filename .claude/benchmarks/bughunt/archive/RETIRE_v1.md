# Saturated Bug Retirement — 2026-06-23

## Retired Bugs

| Bug | Type | Perfect Runs | Variant | Reason |
|-----|------|-------------|---------|--------|
| B01 | T0 nil deref | 3/3 8/8 | B01v2 | +cache indirection, +misleading stack trace |
| B02 | T1 race condition | 3/3 8/8 | B02v2 | +cross-endpoint, +misleading UNIQUE violation |
| B06 | T5 state machine | 3/3 8/8 | pending | — |
| B08 | T7 NOT_A_BUG | 3/3 8/8 | pending | — |
| B09 | T1 missing await | 3/3 8/8 | pending | — |

## Variant Design Pattern

Per FINAL_DESIGN.md Section 4: same type, +1 indirection layer, +1 misleading signal.

B01v2: nil deref → panic in cache.go (1 hop away), stack trace misleads
B02v2: race → UNIQUE violation error (misleads to constraint issue) + cross-endpoint read inconsistency

## Archive

Original bugs moved to `archive/v1_saturated/`.
