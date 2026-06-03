# Slack Status — Alfred Workflow

Set your Slack status from Alfred. Type `slack`, pick a preset or type anything for a custom status.

## Setup

### 1. Create a Slack app and get a token

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App → From scratch**
2. Give it a name (e.g. "Status Setter") and select your workspace
3. Go to **OAuth & Permissions → User Token Scopes** and add: `users.profile:write`
4. Click **Install to Workspace** and authorize
5. Copy the **User OAuth Token** — it starts with `xoxp-`

### 2. Create your config file

```bash
mkdir -p ~/.config/slack-alfred
cp config.example.json ~/.config/slack-alfred/config.json
```

Open `~/.config/slack-alfred/config.json` and replace `xoxp-YOUR-TOKEN-HERE` with your token.

### 3. Install the workflow

```bash
./build.sh
```

Double-click `slack-status.alfredworkflow` to install it in Alfred.

## Usage

- **`slack`** — shows all preset statuses
- **`slack meeting`** — filters presets matching "meeting"
- **`slack at the gym`** — no match → offers to set "at the gym" as a custom status with a 💬 emoji
- Selecting any item sets it immediately and shows a notification

## Customizing statuses

Edit the `statuses` array in `~/.config/slack-alfred/config.json`. Each entry needs:

```json
{"title": "Display name in Alfred", "emoji": ":slack_emoji:", "text": "Status text in Slack"}
```

Leave `emoji` and `text` empty to use the entry as a "clear status" option.

## First run (no token yet)

If no config file exists, the workflow shows **"Setup Required"**. Press Enter to open the Slack API page and see a setup dialog.
