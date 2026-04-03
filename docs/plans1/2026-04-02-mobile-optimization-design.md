# Mobile Module Optimization Design

> Date: 2026-04-02
> Status: Approved
> Author: Tech Lead (Claude Code)

## Overview

Comprehensive optimization of the mobile ticket-grabbing module targeting three goals: performance (warm < 1.0s, cold < 3.0s), stability (> 95% success rate, 0% accidental "预约" clicks), and maintainability (split 3559-line monolith into 7 focused modules).

## Context & Findings

### Real Device Benchmark Data (2026-04-02)

| Metric | Current | Target |
|--------|---------|--------|
| Warm path | 1.3-3.0s | < 1.0s |
| Cold path (first run) | 17.8s (often fails) | < 3.0s |
| Success rate | ~50% (cold) / ~90% (warm) | > 95% |
| Back navigation reliability | ~50% | > 95% |

### Root Causes Identified

1. **Polling timeout cascade**: SKU detection (6s) + confirm detection (8s) = 14s dead time on failure
2. **probe_current_page() costs 1.5s per call**: 12+ element lookups, called 2-4 times per run
3. **Back navigation underestimates stack depth**: max 4 backs insufficient, app lands on homepage
4. **No safe guard against "预约抢票" button**: clicking before sale opens enters reservation flow, wastes time
5. **damai_app.py is 3559 lines / 122 methods**: unmaintainable monolith

### Critical Discovery: Sale-Start Button Transition

From real device screenshots:

```
Pre-sale (detail1.jpg):
  - Button: "预约抢票" (reservation, NOT purchase)
  - Countdown timer: "04月02日 15:18 开抢"
  - Clicking enters reservation page (3.jpg) — WRONG FLOW

Post-sale (detail2.jpg):
  - Button: "立即购票" (actual purchase)
  - No countdown
  - App auto-refreshes, no manual action needed
```

Constraint: MUST NOT click during "预约抢票" state. MUST detect transition to "立即购票" and click within milliseconds.

---

## Section 1: Performance Fixes

### 1.1 Global Pipeline Deadline (Fixes 17.8s Failure)

**Problem**: `damai_app.py:3060` gives SKU detection a 6s deadline, `:3112` gives confirm page an 8s deadline. These cascade: 6s + 8s = 14s wasted on failure.

**Fix**: Replace per-phase deadlines with a single pipeline deadline.

```python
# Before (cascading)
sku_deadline = time.time() + 6.0      # Phase 2: up to 6s
confirm_deadline = time.time() + 8.0  # Phase 4: up to 8s more
# Worst case: 14s

# After (shared)
pipeline_deadline = time.time() + 5.0  # Entire pipeline: 5s hard cap
# Each phase checks same deadline; earlier phases being slow
# automatically shortens later phases
```

**Expected**: Cold path max time 17.8s -> 5.0s hard cap.

### 1.2 Fast Probe Mode (Fixes 1.5s x 2-4 Calls)

**Problem**: `probe_current_page()` does 12+ element lookups every call (~1.5s). Called 2-4 times per run = 3-6s of pure probing.

**Fix**: Two-tier probe with TTL cache.

```python
def probe_current_page(self, fast=False):
    # TTL cache: return cached result if < 500ms old
    if self._probe_cache and time.time() - self._probe_cache_time < 0.5:
        return self._probe_cache

    if fast:
        # Only check activity name + 1 key element ID (~100ms)
        activity = self._get_current_activity()
        if "ProjectDetail" in activity:
            return {"state": "detail_page", ...}
        if "NcovSku" in activity:
            return {"state": "sku_page", ...}
        # Uncertain -> fall through to full probe

    # Full probe (existing 12+ lookups, ~1.5s)
    ...
```

**Expected**: Most probe calls 1.5s -> 0.1s. Full probe only when needed.

### 1.3 Countdown-to-Sale Precision Trigger

**Problem**: Current `wait_for_sale_start()` uses local clock sleep. Doesn't account for server/app timing. No button-state validation.

**Fix**: High-frequency button text polling in the final seconds before sale.

```
Timeline:
  sell_start_time - 30s    idle sleep (low CPU)
  sell_start_time - 3s     switch to high-freq button text polling (50ms interval)
  Button text changes       "预约抢票" -> "立即购票" detected
  Immediate click           same element object, no re-lookup
```

Only reads ONE element's text per poll (~30-50ms). Does not do XML dump or full probe during countdown.

### 1.4 Optimized Element Selection

Replace slow UIAUTOMATOR selectors with faster ID lookups where possible:

| Selector | Cost | Usage |
|----------|------|-------|
| `By.ID` | ~60ms | Preferred |
| `By.XPATH` | ~100-150ms | Fallback only |
| `UIAUTOMATOR` | ~150-200ms | Last resort |

Audit all hot-path selectors and replace slow ones.

---

## Section 2: Stability Fixes

### 2.1 BuyButtonGuard (Zero Accidental Reservations)

New module that gates all purchase button clicks:

```python
class BuyButtonGuard:
    SAFE_TEXTS = frozenset({"立即购票", "立即抢票", "立即预定", "选座购买"})
    BLOCKED_TEXTS = frozenset({"预约抢票", "预约", "预售", "即将开抢", "待开售"})

    def is_safe_to_click(self, button_text: str) -> bool
    def wait_until_safe(self, timeout_s: float, poll_ms: int = 50) -> bool
```

All code paths that click `btn_buy_view` MUST go through this guard:
- `_rush_preselect_and_buy_via_xml()`
- `_enter_purchase_flow_from_detail_page()`
- warm/cold validation pipelines

### 2.2 Layered Recovery Strategy

**Problem**: Current recovery tries max 4 backs, often insufficient.

**Fix**: Three-layer recovery with early termination:

```
Layer 1: Fast back (1-2 backs + fast probe)              ~0.3s
         -> detail_page found? -> done
Layer 2: Deep back (up to 8 backs + fast probe each)     ~1.5s
         -> detail_page found? -> done
Layer 3: Homepage detected -> navigate_to_target_event()  ~5s
         -> guaranteed return to detail_page
Layer 4: All failed -> terminate with error (no infinite loop)
```

### 2.3 Fallback Selectors for Key Pages

Each critical page detection uses at least 2 independent methods:

```python
# SKU page: ID + Activity
def _detect_sku_page_fast(self):
    return (self._has_element(By.ID, "cn.damai:id/layout_sku")
            or "NcovSku" in self._get_current_activity())

# Confirm page: checkbox ID + submit button text
def _detect_confirm_page_fast(self):
    return (self._has_element(By.ID, "cn.damai:id/checkbox")
            or self._has_element_with_text("立即提交"))
```

Prevents total failure from single element ID changes in App updates.

---

## Section 3: Code Restructuring

### 3.1 Module Map

| File | Lines | Responsibility | Extracted From |
|------|-------|----------------|----------------|
| `damai_app.py` | ~400 | Thin orchestration, driver setup, public API | Keep (slim down) |
| `page_probe.py` | ~300 | Page state detection, element queries, TTL cache | probe_current_page, _has_element, _wait_for_* |
| `event_navigator.py` | ~400 | Search, navigate, result scoring | navigate_to_target_event, discover_target_event, search methods |
| `buy_button_guard.py` | ~150 | Button safety, countdown polling | New + extracted CTA keywords |
| `price_selector.py` | ~350 | SKU selection, price matching, OCR | _select_price_option, get_visible_price_options, OCR methods |
| `attendee_selector.py` | ~200 | Checkbox detection, name matching | _ensure_attendees_selected, _attendee_checkbox_elements |
| `fast_pipeline.py` | ~400 | Warm/cold validation, coordinate caching, shell batching | _run_warm_validation_pipeline, _run_cold_validation_pipeline |
| `recovery.py` | ~200 | Back navigation, failure recovery | _recover_to_detail_page, layered recovery |

### 3.2 Dependency Graph (No Cycles)

```
DamaiBot (orchestrator)
├── PageProbe              <- driver only
├── EventNavigator         <- PageProbe
├── BuyButtonGuard         <- driver only
├── PriceSelector          <- PageProbe
├── AttendeeSelector       <- driver only
├── FastPipeline           <- PageProbe + BuyButtonGuard
└── RecoveryHelper         <- PageProbe + EventNavigator
```

### 3.3 Public API Preserved

`DamaiBot` keeps all existing public methods as thin pass-throughs:

```python
class DamaiBot:
    def run_ticket_grabbing(self, initial_page_probe=None):
        # Orchestrates sub-modules, same signature
    
    def probe_current_page(self, fast=False):
        return self.probe.probe_current_page(fast=fast)
    
    def navigate_to_target_event(self):
        return self.navigator.navigate_to_target_event()
```

External callers (`prompt_runner.py`, `hot_path_benchmark.py`, tests) require zero changes.

### 3.4 Shared Utilities (Extracted Patterns)

Duplicated patterns consolidated into helpers:

```python
# In page_probe.py or a small utils module
def poll_until(condition_fn, deadline, interval_s=0.05):
    """Generic polling loop with deadline. Returns True if condition met."""
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval_s)
    return False

def batch_shell_taps(device, coordinates: list[tuple[int,int]]):
    """Send multiple tap commands in a single shell call."""
    cmds = [f"input tap {x} {y}" for x, y in coordinates]
    device.shell("; ".join(cmds))
```

---

## Section 4: Testing Strategy

### 4.1 Test Structure

```
tests/unit/
├── test_page_probe.py            # fast probe, TTL cache, state detection
├── test_buy_button_guard.py      # safe texts, blocked texts, countdown polling
├── test_event_navigator.py       # search, keyword matching, result scoring
├── test_price_selector.py        # index selection, text matching, OCR fallback
├── test_attendee_selector.py     # checkbox logic, multi-person, count
├── test_fast_pipeline.py         # warm/cold path, global deadline, timeout
├── test_recovery.py              # layered recovery, homepage detection
├── test_mobile_damai_app.py      # Updated: orchestration pass-through tests
```

### 4.2 Critical Test Scenarios

**BuyButtonGuard (highest priority — safety critical)**
- "预约抢票" -> `is_safe_to_click()` returns False
- "立即购票" -> returns True
- `wait_until_safe()` simulates text change: poll detects within 100ms
- 10s timeout with no change -> returns False, doesn't hang

**FastPipeline**
- Global 5s deadline: phase 1 takes 3s -> phase 2 gets 2s, no cascade
- Warm path with full cache -> completes < 1s
- Cold path with XML dump -> completes < 3s
- SKU page absent -> exits at 5s, not 14s

**PageProbe**
- `fast=True` checks activity only -> ~100ms
- TTL cache: two calls within 500ms -> second returns cached
- Unknown page -> falls through to full probe

**RecoveryHelper**
- detail_page: 1 back suffices -> returns immediately
- confirm_page: 2 backs -> reaches detail_page
- Homepage detected -> triggers forward navigation
- All recovery fails -> terminates with error

### 4.3 Acceptance Criteria

| Metric | Target |
|--------|--------|
| All tests pass | 100% |
| Code coverage | >= 80% |
| Warm path benchmark (5 runs) | < 1.0s average |
| Cold path benchmark (5 runs) | < 3.0s average |
| Recovery success rate | > 95% |
| BuyButtonGuard false positive | 0% (MUST NOT click "预约抢票") |
| Each module file | < 400 lines |

### 4.4 Real Device Validation

After unit tests pass, run `hot_path_benchmark.py` on real device (5 runs).
Enhanced benchmark outputs per-component timing:
- probe_time, xml_dump_time, polling_time, click_time (separately)
- Compare before/after refactoring numbers

---

## Execution Priority

```
Phase 1: BuyButtonGuard + countdown trigger     <- safety first
Phase 2: Performance fixes (deadline, fast probe) <- speed
Phase 3: Stability fixes (recovery, fallback)     <- reliability  
Phase 4: Code restructuring (split monolith)       <- maintainability
Phase 5: Full test suite + real device benchmark   <- validation
```

Phase 1-3 can be done on the current monolith. Phase 4 restructures the improved code into modules. Phase 5 validates everything.

## Non-Goals

- Orchestrator / API hybrid mode (proven not helpful in real scenarios)
- Web module fixes (channel blocked by Damai)
- Desktop module (deprecated)
- Multi-device support
