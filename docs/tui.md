# TUI

Textual-based terminal UI for monitoring and inspecting jobs.

## Entry Points

- **`taro dash`** — Live dashboard with active and history tables.
- **`taro instance <pattern>`** — Detail view for a single instance.

## Screens

### Dashboard (`DashboardApp` → `DashboardScreen`)

Summary bar (active/completed/failed counts) + two linked `DataTable`s (active, history).
Cursor wraps between tables via `LinkedTable`. Selecting a row pushes `InstanceScreen`;
dismissing it pops back and reconciles ended instances into history.

Subscribes to environment-level events — new instances appear, ended ones move to history.

Bindings: `esc`/`q` quit.

### Instance Detail (`InstanceScreen`)

Two modes:
- **Live** — `JobInstance` proxy with event subscriptions. Header ticks elapsed every 1s.
- **Historical** — static `JobRun` snapshot. No events, no ticking.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  job_id @ run_id            STAGE            elapsed: HH:MM:SS              │
│  [status line: operations, progress, warnings]                              │
├────────────────────────┬────────────────────────────────────────────────────┤
│  Phase Tree            │  Output                                            │
│                        │                                                    │
│  ├─ download  ✓  02:01 │  Processing batch 42...                            │
│  ├─ parse  RUNNING     │  Downloaded 450/500 items                          │
│  │  ├─ validate  ✓     │  Parsing item 120...                               │
│  │  └─ transform RUN   │  Transform: row 85 ok                              │
│  └─ upload  CREATED    │  Warning: slow query on row 88                     │
│                        │                                                    │
│ ── Phase Detail ────── │                                                    │
│  transform (FUNC)      │                                                    │
│  RUNNING               │                                                    │
│  Created: 10:05:00     │                                                    │
│  Elapsed: 02:41        │                                                    │
│  vars: batch_size=100  │                                                    │
├────────────────────────┴────────────────────────────────────────────────────┤
│  esc Back  q Quit                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

Bindings: `esc` back to dashboard, `q` quit.

### Instance Selector (`select_instance`)

Modal pick-and-exit app for action commands (`stop`, `approve`, etc.). Live-updating
`DataTable` of active instances. Returns selected `JobInstance` or `None` on cancel.

## Widgets (`tui/widgets.py`)

| Widget | Base | Purpose |
|--------|------|---------|
| `InstanceHeader` | `Static` | Job identity, stage, elapsed (1s timer), status line |
| `PhaseTree` | `Tree[str]` | Phase hierarchy, always expanded. Posts `PhaseSelected` on navigation. |
| `PhaseDetail` | `Static` | Selected phase metadata: lifecycle, timestamps, attributes, variables, faults, stack traces |
| `OutputPanel` | `RichLog` | Scrollable output with phase-subtree filtering. Live: event stream. Historical: file read. |
| `OutputBuffer` | — | Ordered, deduplicated line buffer (ordinal-based insert-sort) |

## Data Flow

- **No polling** — events carry updated `JobRun` snapshots.
- Events fire on background threads → `call_from_thread()` bridges to Textual event loop.
- Screen dispatches updates to all widgets on each event.
- Elapsed timer (1s) refreshes header only; stops when job ends.
- Output dedup: subscribe before fetching tail, `OutputBuffer` handles overlap.

## Styling

ANSI color names from `theme.Theme` used in `render()` methods (`bright_blue`, `bright_red`, etc.).
TCSS files handle layout only. DataTable cells use column `colour_fnc` from `view/instance.py`.

## Files

```
tui/
├── dashboard.py         DashboardApp, DashboardScreen, DashboardSummary
├── dashboard.tcss       Dashboard layout
├── instance_screen.py   InstanceScreen
├── instance.tcss        Instance detail layout
├── selector.py          LinkedTable, select_instance(), table helpers
└── widgets.py           InstanceHeader, PhaseTree, PhaseDetail, OutputPanel
```

## TODO

- [ ] Theming — Textual design-system variables for colors and backgrounds
- [ ] Responsive stacking for narrow terminals
- [ ] Footer with keybindings and stop control
