# UI Responsiveness Framework

## Principle

**Tk main thread = UI only.**  
No HTTP, no file I/O, no heavy JSON/list work, no `time.sleep` in button handlers.

```
MAIN THREAD                    BACKGROUND (ThreadPoolExecutor)
-----------                    -------------------------------
Navigation (instant)           API / network
Button feedback                Heavy list transform
Rendering                      Cache fill
after() apply_data()  <------  results via UI queue
```

## Mechanisms

| Piece | Role |
|--------|------|
| `utils/async_tasks.py` | Thread pool + generation tokens + UI queue |
| `utils/data_cache.py` | TTL cache so back-navigation is instant |
| `utils/debounce.py` | Search/filter spam control |
| `utils/image_cache.py` | Icons loaded once |
| `ui/base_workspace_view.py` | load_data / apply_data / on_show / on_hide |
| `AppController._view_cache` | Reuse page instances (grid_remove, not destroy) |

## Navigation flow

1. Sidebar click → `show_workspace_view` **immediately**
2. Previous page `on_hide()` → bump generation (drop stale callbacks)
3. Cached page? → show it + `on_show()` soft refresh from cache
4. New page? → build widgets only → cache → `on_show()` loads in background
5. Slow response from old page ignored (generation mismatch)

## What we did **not** do

- Did not replace CustomTkinter
- Did not change business logic or branding
- Spinners only reflect real background work; they are not a substitute for removing blocks

## Adding a new page

1. Subclass `BaseWorkspaceView`
2. Implement `build`, `load_data`, `apply_data`, optional `cache_key`
3. Never call `requests` / services from event handlers without `run_in_background`
