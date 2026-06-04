# Slack Status — Alfred Workflow

Set your Slack status from Alfred. Requires Alfred with a Powerpack license.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/dodecasphere/slack-alfred/main/install.sh | bash
```

This downloads the workflow, walks you through creating a Slack app and getting a token, then installs everything in Alfred automatically. You need three Slack permission scopes: `users.profile:write` for setting status, `users:write` for setting presence, and `emoji:read` for workspace emoji suggestions.

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

Choose form a list of presets or type in your own custom status!

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

## Presence (`slackp`)

- **Enter** on Active or Away — set immediately

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
