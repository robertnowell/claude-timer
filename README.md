[![Version](https://img.shields.io/badge/version-1.2.0-blue)](https://github.com/robertnowell/claude-timer)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude Code Skill](https://img.shields.io/badge/Claude_Code-Skill-blueviolet)](https://docs.anthropic.com/en/docs/claude-code/skills)
[![macOS](https://img.shields.io/badge/macOS-only-lightgrey)](https://www.apple.com/macos)

# Claude Timer

macOS sound + notification capability for Claude Code. Two modes:

- **`notify`** — fires sound + notification *immediately*. Claude reaches for this on its own when finishing a long-running task and the user may have stepped away.
- **`start` / `list` / `cancel`** — named countdown timers. User reaches for these for pomodoros, reminders, and "ping me in 25 minutes."

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

The skill exposes one script — `timer.py` — with four subcommands.

| Command | What it does |
|---|---|
| `notify <message> [--context "<longer body>"]` | Fires Glass sound + system notification immediately + drops a `.txt` file in the Script Editor iCloud folder so clicking "Show" surfaces the message. Use `--context` for a longer body Claude can pass to explain why it fired. |
| `start <duration> [label]` | Spawns a detached background worker that sleeps `<duration>`, then fires the same sound + notification + file-drop. |
| `list` | Shows id, label, remaining time, start time for all active timers; auto-prunes dead workers. |
| `cancel <id-or-label>` | Numeric → cancel by id. Non-numeric → case-insensitive substring match on labels. Kills the worker's process group. |

**Duration formats:** `25m`, `90s`, `1h30m`, `2h`, or raw seconds.

**Intent mapping** (when invoked through Claude):

*User-initiated:*
- "set a timer for 25 minutes" → `start 25m`
- "remind me in 1 hour to check the laundry" → `start 1h "check the laundry"`
- "start a pomodoro" → `start 25m "pomodoro"`
- "what timers are running" → `list`
- "cancel the pomodoro" → `cancel pomodoro`

*Claude-initiated (the more interesting case):*
- Long task just finished → `notify "deep-research done" --context "Ranked 18 sources across 4 angles. Report is in the chat above; look for the 'Established' findings at the top."`
- Build / deploy / render completed → `notify "build succeeded"` or `notify "render failed at angle B" --context "ElevenLabs TTS returned 503 three times. Worth retrying or switching providers."`
- Approval checkpoint reached after long work → `notify "ready for your review" --context "The 3 angle thumbnails are rendered. I need you to pick one before I queue the long-form."`

## How it fires

On expiry (or `notify`), the worker:

1. **Writes a `.txt` file** to `~/Library/Mobile Documents/com~apple~ScriptEditor2/Documents/`. Filename is the message; body contains fire time, the cwd you launched from, a "switch back to your terminal" hint, and your `--context` paragraph if you supplied one. Auto-prunes to the 5 most-recent files so iCloud doesn't pile up.
2. **`afplay /System/Library/Sounds/Glass.aiff` × 3** — always audible, never needs permission, bypasses DND.
3. **`osascript display notification`** — visible if user has DND off and Script Editor has notification permission (most users do, granted long ago).

State lives at `~/.claude/timer/state.json` so timers survive Claude restarts. Workers are detached via `start_new_session=True` — they fire even if you close Claude Code.

### Why the file-drop trick

osascript notifications inherit Script Editor's bundle id, which hardcodes the click target to its iCloud Documents folder. Rather than fight macOS, we treat that folder as the canvas: clicking "Show" on the notification opens Finder there, where your message file is the most recent entry. The filename IS the message. Open the file for the full body (cwd + return hint + Claude's context paragraph).

## Known limitations

These are documented as accepted trade-offs rather than bugs to chase:

- **macOS-only.** `afplay` and `osascript display notification` are macOS-native. No Linux/WSL fallback.
- **Notifications get attributed to "Script Editor".** That's the osascript host's bundle. We can't change this without a custom signed `.app` bundle that has its own notification permission — and there's no programmatic way to grant that on modern macOS. The file-drop trick above is the workaround.
- **DND / Focus modes filter the visual notification.** Sound still plays, file still drops, you'll see it next time you click into Finder.
- **macOS bundles consecutive notifications.** If you fire several `notify` calls in quick succession, macOS may stack them under the most recent one — expand the stack to see all.

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
