# Slack Status — Alfred Workflow

Set your Slack status from Alfred. Requires Alfred with a Powerpack license.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/dodecasphere/slack-alfred/main/install.sh | bash
```

This downloads the workflow, walks you through creating a Slack app and getting a token, then installs everything in Alfred automatically. You only need one Slack permission scope: `users.profile:write`.

### Manual installation

Clone the repo and run:

```bash
./setup.sh
```

To rebuild after changes:

```bash
./build.sh && open slack-status.alfredworkflow
```

## Usage

Type `slack` in Alfred.

- **Enter** — set the selected status
- **⌘Enter** on a custom status — save it as a preset in `config.json`

### Custom status syntax

Type anything after `slack` to set a one-off status:

| Input | Icon | Slack emoji | Text |
|-------|------|-------------|------|
| `be right back` | 💬 | `:speech_balloon:` | be right back |
| `🏋️ at the gym` | 🏋️ | 🏋️ | at the gym |
| `🧠 :brain: deep focus` | 🧠 | `:brain:` | deep focus |

### Expiry

Append `for <duration>` or `until <time>` to any custom status:

```
slack 🎧 focusing for 2h
slack lunch for 45m
slack 🧠 :brain: deep work until 5pm
```

**Duration formats:** `2m` `2min` `2mins` `2minutes` `2h` `2hr` `2hours` `1h30m` `1.5h`  
**Time formats:** `2pm` `2p` `2:30pm` `14:00` `noon` `midnight` `2 o'clock`

## Config

Everything lives in `config.json` at the repo root (gitignored — contains your token). `build.sh` symlinks it to `~/.config/slack-alfred/` so the workflow can find it.

### Preset format

```json
{
  "token": "xoxp-...",
  "statuses": [
    {"title": "Focusing", "emoji": ":headphones:", "text": "Focusing", "icon": "🎧", "expiry": "2h"},
    {"title": "Standup",  "emoji": ":calendar:",   "text": "Standup",  "icon": "📅", "expiry": "9:30am"}
  ]
}
```

- `title` — shown in Alfred
- `text` — the Slack status text
- `emoji` — Slack emoji code shown next to your name (e.g. `:calendar:`)
- `icon` — emoji shown in the Alfred menu
- `expiry` — optional; duration (`2h`, `30m`) or time (`5pm`, `noon`) — re-computed from now each time the preset is loaded
