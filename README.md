# Slack Status — Alfred Workflow

Set your Slack status from Alfred. Requires Alfred with a Powerpack license and Python 3 (`xcode-select --install` or `brew install python3` — the installer checks and tells you if it's missing).

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/dodecasphere/slack-alfred/main/install.sh | bash
```

This downloads the workflow, opens a prefilled Slack app link (all permissions preselected from `slack-app-manifest.json`), takes the token you paste back, and installs everything in Alfred. Two clicks in the browser, one paste.

The app requests four user scopes: `users.profile:write` (set status), `users.profile:read` (show current status), `users:write` (set presence), and `emoji:read` (workspace emoji suggestions). Nothing else, no bot user.

### Manual installation

Clone the repo and run:

```bash
./setup.sh
```

To rebuild after changes:

```bash
./build.sh
```

## Usage

| Keyword | What it does |
|---------|-------------|
| `slacks` | Set your Slack status |
| `slackp` | Set your Slack presence (Active / Away) |
| `slc` | Set your Slack presence to Active instantly, no menu |
| `slw` | Set your Slack presence to Away instantly, no menu |

## Status (`slacks`)

Choose from a list of presets or type your own custom status.

The top item always shows your **current Slack status** with a live expiry countdown. It refreshes on its own the moment it loads, and **⌘Enter** clears your status immediately, even while it's still loading.

Below your presets, any status you've set in the **last 10 days** appears as a recent — ready to re-apply with Enter or save as a preset with ⌘Enter.

- **Enter** — set the status immediately
- **⌘Enter** on a custom status — save as preset (title defaults to the status text)
  - Prefix with `[My Title]` to set a custom name: `[Beach day] :beach_with_umbrella: at the beach`

**Tab on any preset** opens its options:
- Set it with its saved expiry
- Expire in 30m / 1h / 2h, or type a custom duration or time
- **⌘Enter** on an expiry option — set the status *and* save that expiry to the preset
- **Edit preset…** — Tab to pre-fill current values; change title, emoji, or text; Enter to save
- **Remove preset** — with a confirmation step

### Custom status syntax

Type anything after `slacks` to set a one-off status:

| Input | Icon | Slack emoji | Text |
|-------|------|-------------|------|
| `be right back` | 💬 | `:speech_balloon:` | be right back |
| `🏋️ at the gym` | 🏋️ | 🏋️ | at the gym |
| `:brain: deep focus` | 🧠 | `:brain:` | deep focus |
| `🧠 :brain: deep focus` | 🧠 | `:brain:` | deep focus |

The last two rows produce the same result — leading with `:brain:` uses the emoji image as the Alfred icon automatically.

Type `:` anywhere in your input to search and insert emoji. Results include both standard Slack emoji and your workspace's custom emoji.

### Expiry

Append a duration or time to any custom status — the format determines which it is. `for` and `until` are accepted but optional:

```
slacks 🎧 focusing 2h
slacks lunch 45m
slacks 🧠 :brain: deep work 5pm
slacks 🎧 focusing for 2h
slacks 🧠 :brain: deep work until 5pm
```

**Duration formats:** `2m` `2min` `2mins` `2minutes` `2h` `2hr` `2hours` `1h30m` `1.5h`
**Time formats:** `2pm` `2p` `2:30pm` `14:00` `noon` `midnight` `2 o'clock`

A bare number ≤ 23 is treated as a clock hour (`5` → 5:00); a bare number > 23 is treated as hours (`24` → 24h).

### Schedule a status

Add `@` and a time to any status to schedule it instead of setting it now — recurring or one-off:

```
slacks 🎧 Focusing for 2h @ weekdays 9am
slacks ⛔ DND @ tomorrow 3pm
slacks 🏠 Done for the day @ mon,wed,fri 5pm
slacks 🍔 Lunch @ daily 12:30pm
slacks 🧠 deep work @ in 2h
```

Everything before `@` is the status (same syntax as above, including `for 2h` auto-expiry); everything after is when it fires.

**When formats:** `weekdays` · `weekends` · `daily` · day lists (`mon,wed,fri` or `tue thu`) followed by a time · `today 5pm` · `tomorrow 3pm` · `2026-12-25 9am` · `in 2h` · a bare time (`5pm`) for the next occurrence.

Type just `slacks @` to **manage schedules**: **Tab** edits in place, **Enter** pauses/resumes, **⌘Enter** deletes, **⌥Enter** sets it now.

Scheduling runs via a `launchd` agent that checks every minute (installed by `build.sh`/`setup.sh`). It only fires while you're logged in, and skips a recurring time you slept through rather than setting it late.

## Presence (`slackp`)

- **Enter** on Active or Away — set immediately

`slc` and `slw` are one-keystroke shortcuts that skip the menu and set Active / Away directly.

## Config

Presets are managed entirely from Alfred — no file editing needed. Your personal config lives at `~/.config/slack-alfred/config.json`

## Token management

Your Slack token is stored in `config.json`. Tokens can be revoked at any time from the Slack app settings page.

If a request is rejected due to an invalid or revoked token, you'll see an Alfred notification banner and both keywords will show only a single **⚠️ Token invalid** item until it's resolved. Get a new token from your Slack app's **OAuth & Permissions** page, then open either keyword, Tab or → the warning item, and paste it in. The workflow resumes normally on the next use.

To replace a token directly, edit `~/.config/slack-alfred/config.json`.

## Testing

The parsing logic (duration/time/expiry parsing, custom status syntax) has a unit test suite in `tests/`. No dependencies beyond the standard library.

```bash
python3 -m unittest discover tests
```

If you're contributing, please write tests for any new parsing behavior and make sure the full suite passes before opening a PR.
