---
name: timer
description: macOS sound + notification capability. Fire immediately (notify) to alert the user — useful when finishing a long task, completing a multi-step operation, or surfacing important state and the user may have stepped away. Also runs named countdown timers (start/list/cancel) for user-requested timers and pomodoros. Use proactively when ending a turn after long-running work; use on request when the user says "set a timer for X", "start a pomodoro", "what timers are running", "cancel my timer".
argument-hint: "notify <message> | start <duration> [label] | list | cancel <id-or-label>"
---

# Timer

A two-purpose skill:

1. **Notification capability** — Claude can fire a Glass sound + macOS notification immediately to alert the user that something is done. Reach for this proactively whenever the user might have stepped away from the screen.
2. **Countdown timers** — Named timers that run as detached background processes and fire the same sound + notification when they expire.

Helper: `${CLAUDE_SKILL_DIR}/scripts/timer.py`. Always invoke with `python3`.

## When Claude should reach for this proactively

Without being asked. These are situations where the user is probably not watching the screen and would benefit from a ping:

- A long-running task just finished (build > 30s, deploy, render, large refactor, anything where Claude was working for minutes).
- A multi-step pipeline completed successfully or hit a blocker.
- A background command Claude was waiting on returned.
- A long-pending question or approval is now needed from the user.
- Anything Claude has discovered or generated that the user should see immediately rather than scroll back to.

Default behavior at the end of a turn that took > 1 minute of work: fire `notify` with a one-line summary. Cost is ~0.1s; benefit is the user actually sees the result when they look back.

## Commands

**Notify (immediate)** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py notify "<message>"`

Fires Glass sound + macOS notification right now. No countdown. Use this for "task done" pings.

**Start (countdown)** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py start <duration> [label]`

- `duration`: `25m`, `90s`, `1h30m`, `2h`, or raw integer (seconds).
- `label`: optional, default `"Timer"`. Quote multi-word labels.

**List** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py list`

Shows id, label, remaining time, and start time for every active timer. Dead PIDs are pruned automatically.

**Cancel** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py cancel <target>`

- Numeric `<target>` → cancel by id.
- Non-numeric → case-insensitive substring match against labels. Cancels every match.

## Intent mapping

User-initiated (the user says):
- "set a timer for 25 minutes" → `start 25m`
- "remind me in 1 hour to check the laundry" → `start 1h "check the laundry"`
- "start a pomodoro" → `start 25m "pomodoro"`
- "what timers are running" / "show my timers" → `list`
- "cancel the pomodoro" → `cancel pomodoro`
- "cancel timer 3" → `cancel 3`

Claude-initiated (you decide on your own):
- Long task just finished → `notify "deep-research done — report in chat"` (or whatever summarizes what's ready)
- Build/deploy/render completed → `notify "build succeeded"` or `notify "render failed at angle B"`
- User-input checkpoint reached after long work → `notify "ready for your review"`

After starting a timer or notifying, print the script's output verbatim — it already confirms the action. No need to restate.

## Notes

- macOS-only. **Zero external dependencies** — uses only built-in `afplay` and `osascript`. Don't suggest `brew install terminal-notifier`.
- **Sound is the reliable signal.** Glass.aiff plays three times via `afplay`. Never needs permission, bypasses DND, always audible.
- **Visual notification is best-effort.** Fired via `osascript display notification`. The notification is attributed to "Script Editor" — that's the osascript host's bundle, and most users have already granted it notification permission long ago.
- **Known limitations of the visual** (don't try to "fix" these — we tried, it's worse):
  - **DND / Focus filters the notification.** Sound still plays.
  - **Clicking the notification opens Script Editor's iCloud folder**, not the user's terminal. Re-attributing requires a permitted app of our own, and there's no programmatic way to grant notification permission to a freshly-built AppleScript applet on modern macOS — macOS silently filters un-permitted apps with no prompt. We tried osacompile+plutil+codesign+lsregister; the apparent fix doesn't actually fire visible notifications.
- Cancellation kills the worker's process group (`killpg` with `SIGTERM`), so no orphan `sleep` lingers.
- State auto-prunes dead PIDs on every `start`, `list`, and `cancel`.
- Timers fire even if Claude Code is closed — workers are detached via `start_new_session=True`.
