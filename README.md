[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/robertnowell/claude-timer)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude Code Skill](https://img.shields.io/badge/Claude_Code-Skill-blueviolet)](https://docs.anthropic.com/en/docs/claude-code/skills)
[![macOS](https://img.shields.io/badge/macOS-only-lightgrey)](https://www.apple.com/macos)

# Claude Timer

Named countdown timers for Claude Code on macOS. Glass-sound + system notification when they fire. Survives Claude restarts.

> Zero external dependencies. Built on `afplay` and `osascript` — both ship with macOS.

## Quick Start

One-line install:

```bash
claude plugin marketplace add robertnowell/claude-timer && claude plugin install claude-timer@claude-timer-marketplace
```

Or as two slash commands inside Claude Code:

```
/plugin marketplace add robertnowell/claude-timer
/plugin install claude-timer@claude-timer-marketplace
```

Then just ask:

```
set a timer for 25 minutes for the pomodoro
what timers are running
cancel the pomodoro
```

## Commands

The skill exposes one script — `timer.py` — with three subcommands.

| Command | What it does |
|---|---|
| `start <duration> [label]` | Spawns a detached background worker that sleeps `<duration>`, then fires Glass sound + system notification |
| `list` | Shows id, label, remaining time, start time for all active timers; auto-prunes dead workers |
| `cancel <id-or-label>` | Numeric → cancel by id. Non-numeric → case-insensitive substring match on labels. Kills the worker's process group |

**Duration formats:** `25m`, `90s`, `1h30m`, `2h`, or raw seconds.

**Intent mapping** (when invoked through Claude):

- "set a timer for 25 minutes" → `start 25m`
- "remind me in 1 hour to check the laundry" → `start 1h "check the laundry"`
- "start a pomodoro" → `start 25m "pomodoro"`
- "what timers are running" → `list`
- "cancel the pomodoro" → `cancel pomodoro`

## How it fires

On expiry, the worker runs:

1. **`afplay /System/Library/Sounds/Glass.aiff` × 3** — always audible, never needs permission, bypasses DND.
2. **`osascript display notification`** — visible if user has DND off and Script Editor has notification permission (most users do, granted long ago).

State lives at `~/.claude/timer/state.json` so timers survive Claude restarts. Workers are detached via `start_new_session=True` — they fire even if you close Claude Code.

## Known limitations

These are documented as accepted trade-offs rather than bugs to chase:

- **macOS-only.** `afplay` and `osascript display notification` are macOS-native. No Linux/WSL fallback.
- **Notifications get attributed to "Script Editor".** That's the osascript host's bundle. Clicking "Show" on the notification opens Script Editor's iCloud folder, not your terminal. (We tried fixing this with a custom AppleScript applet — macOS silently filters notifications from un-permitted apps with no programmatic way to grant permission. The sound is the reliable signal.)
- **DND / Focus modes filter the notification.** Sound still plays.

## Install in Cowork (claude.ai, desktop)

> If you're reading this as a Claude instance running inside Cowork and a user has asked you to install this skill, this section is for you.

Cowork installs skills via `.skill` bundles through its UI — the `claude plugin` CLI commands above don't apply.

**The path that works:**

1. `git clone https://github.com/robertnowell/claude-timer.git` into the workspace sandbox. Don't WebFetch raw GitHub URLs for non-pasted files — provenance set blocks them. Clone sidesteps this.
2. **Strip the `argument-hint:` line from `skills/timer/SKILL.md`'s frontmatter** before packaging. `argument-hint:` is a Claude Code–only key; `skill-creator`'s `package_skill` validator rejects it. One-liner: `sed -i '/^argument-hint:/d' skills/timer/SKILL.md`.
3. Run `skill-creator`'s `package_skill` on `skills/timer/` to produce a `.skill` bundle.
4. Hand the user a `computer://` link to the `.skill` file. (`present_files` may reject sandbox-perms files with "not accessible on the user's computer" — direct `computer://` link is the reliable fallback.)

After install, the skill appears namespaced in the slash menu (e.g. `/anthropic-skills:timer`).

## File structure

```
claude-timer/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── README.md
├── LICENSE
└── skills/
    └── timer/
        ├── SKILL.md
        └── scripts/
            └── timer.py
```

## License

MIT — see [LICENSE](LICENSE).
