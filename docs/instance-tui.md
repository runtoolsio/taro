# `taro instance` TUI — Full Design

## Overview

`taro instance <pattern>` opens a Textual TUI showing detailed information about a single job instance.
Supports two modes: **live** (currently running) and **historical** (ended, loaded from persistence).

## Layout

Two-column layout: left panel for phase tree + detail, right panel for output.
Header spans full width above, footer below.

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│  pipeline @ batch-42              RUNNING                              elapsed: 00:05:12      │
│  [downloading 45%] [parsing 120/500 items]  (!slow query)                                     │
├─────────────────────────────────┬─────────────────────────────────────────────────────────────┤
│  Phase Tree                     │  Output                                                     │
│                                 │                                                             │
│  ├─ download  COMPLETED 02:01   │  10:05:00  Processing batch 42...                           │
│  ├─ parse     RUNNING   03:11   │  10:05:01  Downloaded 450/500 items                         │
│  │  ├─ validate  DONE   00:30   │  10:05:02  Parsing item 120...                              │
│  │  └─ transform RUN    02:41   │  10:05:03  Validating schema...                             │
│  └─ upload    CREATED           │  10:05:04  Transform: row 85 ok                             │
│                                 │  10:05:05  Transform: row 86 ok                             │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─     │  10:05:06  Transform: row 87 ok                             │
│  Phase Detail                   │  10:05:07  Warning: slow query on row 88                    │
│                                 │  10:05:08  Transform: row 88 ok                             │
│  phase: transform               │  10:05:09  Transform: row 89 ok                             │
│  type:  FUNC                    │  10:05:10  Transform: row 90 ok                             │
│  vars:  batch_size=100          │  10:05:11  Checkpoint saved                                 │
│                                 │  10:05:12  Transform: row 91 ok                             │
├─────────────────────────────────┴─────────────────────────────────────────────────────────────┤
│  [s]top  [q]uit  [tab]focus                                                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

Split ratio: ~1fr left, ~2fr right (roughly 35/65).

### Responsive behavior

- **Wide terminal (>=100 cols)**: Side-by-side as shown above.
- **Narrow terminal (<100 cols)**: Stack vertically — phase tree on top, output below (like the original layout).

## Data Flow

- **Live mode**: `conn.get_instances(criteria)` returns `JobInstance` proxy.
    - `instance.snap()` for initial `JobRun` state.
    - `instance.notifications` for phase/lifecycle/output events.
    - Events carry updated `JobRun` snapshots — no polling needed for phase/lifecycle.
    - Output events stream via `InstanceOutputEvent`.
    - Control via `instance.stop()`.
- **Historical mode**: `conn.get_run(instance_id)` returns final `JobRun` snapshot only.
    - Static display, no events, no control.
    - Output loaded from file if `output_locations` available.

## Widgets

### Header (`InstanceHeader`)

- Row 1: `{job_id} @ {run_id}` left, stage center/right, elapsed right (ticks 1s while live)
- Row 2: `Status.__str__()` — operations with progress, last event, warnings
- Historical: elapsed = `total_run_time`, stage = terminal status name, no ticking
- Spans full width, docked top

### Left Panel

#### Phase Tree (`PhaseTree`) — future step

- Tree widget showing phase hierarchy with lifecycle info per phase
- Each node: `phase_id  STAGE  elapsed`
- Color-coded by stage (green=running, dim=completed, red=fault)
- Updates on phase events
- Selecting a phase populates the detail panel below

#### Phase Detail (`PhaseDetail`) — future step

- Shows detail for the currently selected phase in the tree
- Fields: phase_id, phase_type, attributes, variables, lifecycle timestamps
- Separated from tree by a light divider
- Collapses/hidden when no phase is selected

### Right Panel — Output (`OutputPanel`) — future step

- Scrollable log of output lines
- Auto-scroll to bottom when new output arrives (unless user scrolled up)
- Live: streams via output events
- Historical: loads from output file if `output_locations` present
- Takes full height of the main area

### Footer — future step

- Keybinding hints: `[s]top  [q]uit  [tab]focus  [↑↓]scroll`
- Stop only shown in live mode
- Docked bottom, spans full width

## Status Refresh Strategy

- **Phase/lifecycle events** update `JobRun` snapshot and refresh header + phase tree
- **Output events** append to output panel
- **Elapsed timer** ticks every 1s (header only) while live
- **No polling** — events are sufficient for all updates
- Bridge events to Textual thread via `app.call_from_thread()`

## Implementation Steps

1. **Step 1** (done): App skeleton + Header widget only
2. **Step 2**: Phase tree widget + left/right panel split
3. **Step 3**: Output panel (right side)
4. **Step 4**: Phase detail panel (below tree)
5. **Step 5**: Footer with keybindings and stop control
6. **Step 6**: Responsive stacking for narrow terminals
7. **Step 7**: Polish — error states, edge cases, styling
