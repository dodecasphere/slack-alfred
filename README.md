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
./build.sh
```

## Usage

Type `slack` in Alfred.

- **Enter** — set the selected status
- **⌘Enter** on a custom status — save it as a preset
- **Tab** on any preset — open expiry options or remove it
- **⌘Enter** on an expiry option — update the preset's stored expiry

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

Presets are managed entirely from Alfred — no file editing needed. Your personal config lives at `~/.config/slack-alfred/config.json`
