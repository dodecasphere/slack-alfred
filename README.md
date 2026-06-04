# Slack Status — Alfred Workflow

Set your Slack status from Alfred. Requires Alfred with a Powerpack license.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/dodecasphere/slack-alfred/main/install.sh | bash
```

This downloads the workflow, walks you through creating a Slack app and getting a token, then installs everything in Alfred automatically. You only need two Slack permission scopes: `users.profile:write` for setting status, and `users:write` for setting presence.

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

## Status (`slacks`)

- **Enter** — set the selected status
- **⌘Enter** on a custom status — save it as a preset
- **Tab** on any preset — open expiry options or remove it
- **⌘Enter** on an expiry option — update the preset's stored expiry

### Custom status syntax

Type anything after `slacks` to set a one-off status:

| Input | Icon | Slack emoji | Text |
|-------|------|-------------|------|
| `be right back` | 💬 | `:speech_balloon:` | be right back |
| `🏋️ at the gym` | 🏋️ | 🏋️ | at the gym |
| `🧠 :brain: deep focus` | 🧠 | `:brain:` | deep focus |

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

## Presence (`slackp`)

- **Enter** on Active or Away — set immediately

## Config

Presets are managed entirely from Alfred — no file editing needed. Your personal config lives at `~/.config/slack-alfred/config.json`

## Testing

The parsing logic (duration/time/expiry parsing, custom status syntax) has a unit test suite in `tests/`. No dependencies beyond the standard library.

```bash
python3 -m unittest discover tests
```

If you're contributing, please write tests for any new parsing behavior and make sure the full suite passes before opening a PR.
