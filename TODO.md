# TODO

## Cap OutputPanel buffer for live instances
- `OutputBuffer` and `RichLog` grow unbounded in live mode
- Add `_MAX_LINES` constant (e.g. 10,000) to `OutputPanel`
- Pass `max_lines` to `RichLog.__init__()` (built-in support, drops from head)
- Trim `OutputBuffer._lines` head + evict old ordinals from `_seen` after `add_line()`
- Show "truncated" hint on phase filter re-display if buffer was capped
- File: `src/runtools/taro/tui/widgets.py` — `OutputBuffer` / `OutputPanel`
