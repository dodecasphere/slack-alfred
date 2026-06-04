# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Guiding Principles

These are non-negotiable. Apply them to every feature, fix, and interaction.

1. **Understand before building.** Ask questions until the feature is fully clear — no ambiguous requirements, no dangling edge cases. Don't start writing code until the design is settled.

2. **Collaborate, don't just execute.** If you have thoughts on how to improve a feature request, say so. Surface tradeoffs, suggest alternatives. One sentence per option is enough — let the owner decide.

3. **When stuck or the path is risky, present options.** Lay out 2–3 choices with tradeoffs before writing any code. Don't spiral in analysis.

4. **TDD: tests first.** Write failing tests before implementing. Implement until they pass. Never commit a feature without tests. Always run the full suite before committing.

5. **Complete the full cycle.** After every feature or meaningful bug fix: `./build.sh`, commit, push. All three, every time, without being asked.

6. **Keep the README honest and scannable.** Update it for every user-facing change. Write for someone deciding in 30 seconds whether to install — no walls of text.

7. **Suggest new ideas.** After building something, if you spot an opportunity to add usefulness, efficiency, magic, or fun to the user experience — say so. Don't wait to be asked. Imagination is an asset here.

## Build and install

```bash
./build.sh          # package workflow/ into slack-status.alfredworkflow and open in Alfred
```

**After completing any feature or meaningful bug fix, always run all three steps without being asked:**

```bash
./build.sh
git add <changed files> && git commit -m "..."
git push
```

`build.sh` also creates `config.json` from the example if missing, sets up symlinks from `~/.config/slack-alfred/` → repo, and runs `generate_icons.py` to pre-warm the icon cache.

The parsing logic has a unit test suite in `tests/`. Run with:

```bash
python3 -m unittest discover tests
```

**Prefer TDD:** write failing tests first, implement until they pass, then commit. At minimum, every new feature or parsing behavior must have tests before it's committed. Always run the full suite to catch regressions.

## Architecture

This is a two-script Alfred workflow. Alfred pipes `{query}` via stdin; scripts write results to stdout.

### `workflow/filter.py` — Script Filter (runs on every keystroke)

Produces Alfred's JSON result list. Three modes based on the query:

1. **Submenu** — query starts with `» ` (the `_SUBMENU_PREFIX` constant). Two sub-modes:
   - `» <title>` → expiry submenu (30m / 1h / 2h + Remove preset)
   - `» <title> » remove` → remove-confirmation submenu
2. **Preset list** — empty or partial query; filters `statuses` from config. Each item gets `autocomplete: "» <title>"` so Tab enters the submenu.
3. **Custom status** — typed query that doesn't match a preset title. Parses `parse_custom_status()` which understands leading emoji, `:slack_code:` injection, and trailing `for <duration>` / `until <time>` expiry syntax.

Icon PNGs are cached at `~/.config/slack-alfred/icons/` via JXA (rendered at build time by `generate_icons.py`, then lazily on first use at runtime by `icon_path()`).

### `workflow/set_status.py` — Run Script (runs on Enter)

Receives the `arg` JSON from the selected filter item. Dispatches on the `action` field:

| `action` value | Behavior |
|---|---|
| *(absent)* | Call Slack `users.profile.set` API |
| `save_preset` | Append entry to `config.json` statuses |
| `remove_preset` | Remove entry from `config.json` statuses by `title` |
| `"setup"` (plain string) | Open Slack API page + show setup dialog |

### The `arg` JSON contract

`filter.py` serializes all item args as JSON. `set_status.py` deserializes and reads these fields:

| Field | Type | Meaning |
|---|---|---|
| `text` | str | Slack status text |
| `emoji` | str | Slack emoji code e.g. `:headphones:` |
| `icon` | str | Emoji char used as Alfred menu icon |
| `expiry` | int | Unix timestamp, 0 = no expiry |
| `expiry_config` | str | Stored string (`"2h"`, `"5pm"`) for re-computing expiry relative to *now* |
| `action` | str | Optional — omit to set status, or `"save_preset"` / `"remove_preset"` |
| `title` | str | Required only for `remove_preset` |

Success output (printed to stdout): a plain string that Alfred's Post Notification step shows as a banner. Error feedback goes through `notify_error()` via osascript so it doesn't pollute stdout.

### Config

`config.json` (gitignored, lives at repo root, symlinked to `~/.config/slack-alfred/config.json`):

```json
{
  "token": "xoxp-...",
  "statuses": [
    {"title": "Focusing", "emoji": ":headphones:", "text": "Focusing", "icon": "🎧", "expiry": "2h"}
  ]
}
```

`expiry` is a stored string (`"2h"`, `"5pm"`) that `compute_expiry_from_config()` converts to a Unix timestamp relative to *now* each time the preset loads — not a fixed timestamp.

`DEFAULT_STATUSES` in `filter.py` is the fallback list shown when `config.json` has no `statuses` key.

### Alfred workflow wiring (`workflow/info.plist`)

```
Script Filter (keyword: slacks)  →  Run Script (set_status.py)   →  Post Notification ("Slack Status")
Script Filter (keyword: slackp)  →  Run Script (set_presence.py) →  Post Notification ("Slack Presence")
```

Both Script Filters use `echo "{query}" | python3 <script>.py`. The Post Notification step reads stdout as the notification body — print a plain string for success, nothing for silent success.

## Extending the workflow

### Adding a new action

1. Add a new `action` value and handler function in `set_status.py::main()`.
2. Build the item in `filter.py` with `"arg": json.dumps({..., "action": "your_action"})`.
3. If the action needs a confirmation step, add a new submenu builder in `filter.py` following the pattern of `build_remove_confirm_submenu`, and route to it via `autocomplete`.

### Adding a new submenu

All submenu routing flows through `filter.py::main()` based on the `_SUBMENU_PREFIX` (`"» "`) sentinel. The autocomplete value on a preset item sets what query Alfred sends when the user presses Tab. Extend the routing block to handle a new suffix pattern.

### Adding or changing expiry formats

`parse_duration()` and `parse_until_time()` in `filter.py` handle all time/duration parsing. Add new patterns to those functions; `extract_expiry()` and `compute_expiry_from_config()` call them automatically.

## Debugging

### Test filter.py from the terminal

```bash
echo "focusing for 2h" | python3 workflow/filter.py | python3 -m json.tool
echo "» Focusing" | python3 workflow/filter.py | python3 -m json.tool
```

### Test set_status.py from the terminal

```bash
echo '{"text":"On a call","emoji":":telephone_receiver:","icon":"📞","expiry":0}' \
  | python3 workflow/set_status.py
```

### Alfred's built-in debugger

Open Alfred Preferences → Workflows → select this workflow → click the bug icon (top right). It shows stdout/stderr from each step in real time as you trigger the workflow.

### Common failure modes

- **Workflow shows nothing / stale UI**: You edited the scripts but didn't rebuild. Run `./build.sh && open slack-status.alfredworkflow` and re-import.
- **Icons missing on first use**: Expected — `icon_path()` fires a background JXA process and returns `None` for uncached emoji. The icon appears from the next keystroke onward. Run `./build.sh` to pre-warm all icons.
- **Notification never appears**: Alfred's Post Notification step reads stdout. If `set_status.py` exits without printing, no notification fires. Make sure success paths print something.
- **Notification appears but is wrong**: Check `info.plist` for stale keys like `lastpathcomponent` or `removeextension` on the notification connection — these are file-path action keys that silently break non-file outputs.

## Working style

If a feature seems risky or harder to build than it's worth, stop and present 2-3 options with tradeoffs before writing any code. Let the owner decide. Don't spiral in analysis — one sentence per option is enough.

When updating the README: keep it concise and scannable — write for someone deciding in 30 seconds whether to install. No walls of text, no over-explaining. Bullet points over prose; cut anything that doesn't help a potential user decide.

## Gotchas and anti-patterns

- **Do not use osascript multi-dialog chains for user input.** Only the first dialog in a chain shows reliably in Alfred's execution environment. Use Alfred-native UI instead: modifier keys (`mods.cmd`), `autocomplete` submenus, or the `valid: false` pattern to block a step.
- **Do not block in `icon_path()` or anywhere in the Script Filter.** Any `subprocess.run()` call per result item introduces 1–2s delay before Alfred shows the list. Spawn background processes with `subprocess.Popen(..., stdout=DEVNULL, stderr=DEVNULL)` and return `None` immediately if the result isn't cached yet.
- **Do not add file-path action keys to non-file Alfred steps.** Keys like `lastpathcomponent` and `removeextension` belong only to file-path actions. On other steps (notifications, run scripts) they silently corrupt the output.
- **Error output must use `notify_error()`, not `print()`.** Anything printed to stdout becomes the notification body. Printing error text there overrides the success message and confuses Alfred's output pipeline.
- **`expiry` in config is a re-computed string, not a fixed timestamp.** `"expiry": "2h"` means "2 hours from whenever this preset is activated," not a wall-clock time. `compute_expiry_from_config()` handles the conversion at activation time.
