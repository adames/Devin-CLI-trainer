# Devin CLI study guide (for support work)

Written against Devin CLI **v3000.11.92** (released 2026-10-14) and the docs
snapshots in `docs/`. When the binary and the docs disagree, trust
`devin <cmd> --help` for the installed version and write the difference down:
those mismatches are exactly what customers run into.

This guide is the course behind [Professor Devin](README.md). The commands in
section 4 are the answers to the game's `shell` cards, and the break-it drills
in section 6 are its mystery tickets.

---

## 0. How to learn it: four loops

| Loop | What you do | Why it works | Time |
|---|---|---|---|
| 1. **Model** | Draw the architecture (section 2) from memory, then check it against the real thing | With a mental model you can navigate a bug; without one, commands are trivia | 20 min, week 1 |
| 2. **Retrieve** | Flashcards (`professor-devin` or `./drill.sh`) and predicting what a command will print | Recalling an answer makes it stick far better than rereading it | 10 min daily |
| 3. **Practice** | The labs in section 5, each with a pass/fail check | Fluency comes from doing, and the checks show what you still don't know | 45 min, 4-5x/week |
| 4. **Break** | Break something on purpose, then diagnose it cold (section 6) | That is support work: start from a symptom and find the cause | 1-2x/week |

Rules that make the loops work:
- **Predict before running.** Say what you expect a command to print. When you're wrong, write it in `journal.md`; that is the part worth remembering.
- **Check the source.** `devin <cmd> --help` for the installed version first, then the docs and the changelog, and only then your memory.
- **Space the reviews.** Missed cards come back sooner, known cards wait longer. The game and `drill.sh` both do this for you.
- **Teach it back.** Once a week, write a one-page runbook for a new support engineer. The gaps are your next study topics.
- **Keep a shell open.** Tie every idea to a file, a process, or a log line.

### A version mismatch to remember
- `devin --help` (v3000.11.92): `--permission-mode` takes `auto` (default), `accept-edits`, `smart`, or `dangerous`; env `DEVIN_PERMISSION_MODE`.
- Docs, Commands & Flags page: `normal` (alias `auto`), `accept-edits`, `smart`, `dangerous` (aliases `yolo`, `bypass`), and `autonomous` (needs `--sandbox`).
- Slash commands use a third set of names: `/normal /accept-edits /smart /plan /bypass /autonomous`, with `/dangerous` and `/yolo` as aliases, and `/code` to return to Code mode from Plan or Ask.

Same feature, three vocabularies. Check `devin --version` before you dig into a ticket.

---

## 1. A four-week plan (about an hour a day)

| Week | Focus | Exit criteria |
|---|---|---|
| 1 | Install, auth, file layout, sessions, `-p` scripting, general CLI basics (rg, jq, less, find, xargs) | You can redraw section 2 from memory; labs L1-L3 done; drill >= 80% |
| 2 | Config layers, permissions, rules/AGENTS.md, skills, hooks | Labs L4-L7 done; you predict precedence outcomes correctly |
| 3 | MCP, subagents, plugins, sandbox, logging/tracing, proxy/TLS; process-level CLI (ps, lsof, fs_usage) | Labs L8-L11 done; two break-it drills solved cold |
| 4 | Cloud: `--cloud` / `devin cloud`, `/handoff`, `devin ssh/forward`, `devin cloud drs`, ACP (IDE integration) | Labs L12-L14 done; your personal support runbook written |

After week four, work one mystery ticket (section 6) a week and read each new changelog entry as it ships (`docs.devin.ai/cli/changelog/stable`).

---

## 2. What runs and what gets saved

```
             you
              |
     devin (REPL / TUI) -----------------------------  devin -p "..." (print mode, one shot)
              |  spawns child, speaks ACP (JSON-RPC over stdio)
              v
     devin acp  (the agent loop: model calls, tools, permissions, hooks)
        |-- exec tool (shell; env = login-shell snapshot taken at startup; optional --sandbox bwrap/seatbelt)
        |-- file tools, web, MCP clients (stdio / streamable HTTP / SSE)
        |-- subagents (foreground/background, own profile + permissions)
        '-- --cloud / devin cloud: relays ACP to the Devin Cloud ACP WebSocket
                                   |
                     Devin Cloud session VM  <-- devin ssh / devin forward / /handoff / /pickup
                                   ^-- devin connect <code>: pairs this machine to a cloud session for local tool use (hidden from --help)
IDEs (Zed, JetBrains, Xcode) ---- ACP ---> devin acp
```
The root help says print mode's agent "runs in that child" and that `--cloud` uses `devin acp --cloud`. Cloud sessions never check directory trust.

### Files to check on macOS and Linux
| Path | What it is |
|---|---|
| `~/.local/bin/devin` | binary (installer target) |
| `~/.local/share/devin/cli/_versions/` | installed versions |
| `~/.local/share/devin/credentials.toml` | auth credentials (`$XDG_DATA_HOME/devin/credentials.toml` when that variable is set; `devin auth status` prints the path) |
| `~/.local/share/devin/cli/sessions.db` | local session store (SQLite); `DEVIN_SESSIONS_DIR` moves it, e.g. off an NFS home |
| `~/.local/share/devin/cli/logs/devin_<ts>_<pid>.log` | one log per run; `.log.gz` after 48h untouched |
| `~/.local/share/devin/mcp/` | MCP state |
| `~/.local/share/devin/summaries/<session>.md` | summarizer agent output |
| `~/.cache/devin/` | caches: `team_settings.bin`, `model_configs.bin`, `cli/unleash_definitions.*.bin` (likely feature flags), `cached_version.json`. Found by tracing file lookups (section 4, item 10); a suspect when things look stale |
| `/etc/devin/system.json` | MDM-managed system policy (login/proxy pinning; docs: cli/enterprise/system-config) |
| `~/.codeium/windsurf/memories/global_rules.md`, `~/.config/devin/.windsurfrules` | legacy/imported rule paths probed at startup (found by tracing file lookups) |
| `~/.config/devin/config.json` | user config (lowest-priority layer) |
| `~/.config/devin/mcp_config.json` | user MCP servers (v3000.3+; older versions used `mcpServers` in config.json) |
| `~/.config/devin/AGENTS.md` | global rules |
| `~/.config/devin/skills/<name>/SKILL.md` (also `~/.agents/skills`, `~/.config/cognition/skills`) | user skills |
| `.devin/config.json` / `.devin/config.local.json` | project / personal project config (local is gitignored) |
| `.devin/mcp_config.json` / `.devin/mcp_config.local.json` | project MCP |
| `.devin/hooks.v1.json` | project hooks (the whole file is the hooks object) |
| `.devin/skills/`, `.agents/skills/`, `.cognition/skills/` | project skills |
| `AGENTS.md`, `.windsurf/rules/*.md`, `.cursor/rules/*.md` | project rules |
| `.claude/settings*.json`, `~/.claude/CLAUDE.md` | imported when `read_config_from.claude` is on (default) |

### Config precedence (highest wins)
1. Org / team settings (can't be overridden; org deny/ask rules survive even bypass/dangerous mode, and since 3000.11.92 a prompt forced by an org "ask" rule says so)
2. Session approvals (in memory)
3. `.devin/config.local.json`
4. `.devin/config.json`
5. `~/.config/devin/config.json`

---

## 3. Commands to practice first

**Starting sessions**
```
devin                          # REPL
devin -- fix the flaky test    # REPL with initial prompt (-- separates the prompt)
devin -p "summarize README"    # print mode: one shot, stdout, exits
devin --prompt-file task.md    # prompt from file
devin -c / devin -r [ID]       # continue latest in cwd / resume by id or picker
devin --model opus  --permission-mode accept-edits  --sandbox  --export [PATH]
devin --config /tmp/empty.json # isolate user config (great for bisecting a bug)
devin -p --respect-workspace-trust false "..."   # print mode in an untrusted dir
devin --cloud  /  devin cloud  # drive a Devin Cloud session instead of the local agent (same thing)
```
**Subcommands**
```
devin auth login [--force-manual-token-flow] | logout | status
devin doctor [--json]          devin version / --version     devin update [--force]
devin models list              devin list [--format json|csv]   devin rm <id> [--force]
devin rules list|show|paths    devin skills list|show|paths
devin mcp add|list|get|remove|login|logout|enable|disable      (list/get print a Source: line per server)
devin plugins install|list|info|update|remove|prune            (install accepts skills-only repos such as anthropics/skills)
devin ssh [SESSION] [ssh args]     devin forward <SESSION> 3000 8080:3000
devin cloud drs whoami|sandbox-create|run|blueprint-list|build|build-logs|...
devin sandbox setup            devin migrate hooks|workflows     devin acp [--agent-type review|summarizer]
devin setup | desktop | uninstall
devin connect <code>           # hidden: pair this machine to a cloud session (local tool use)
```
**Slash commands worth remembering**
`/help /mode /code /plan /ask /smart /bypass /model /fusion /goal /recap /share /clear /steps /fork [step] /revert <step> /resume /ls /loop /btw /hooks /mcp /context /usage /stats /compact /config /billing /bug /cloud /handoff /open /ssh /pickup /add-dir /workspace /login-status /export`

New in 3000.11.92 and easy to miss:
- `/goal <objective>` keeps Devin working across turns until it reports done or blocked; `/goal` shows status, `/goal resume` continues after an interrupt, `/goal clear` drops it. A run pauses itself after 50 turns.
- Steering: a message typed while Devin is working goes to the running turn at its next step, nothing is cancelled. `Cmd+Enter` (`Ctrl+Enter` elsewhere) queues it until the turn ends instead.
- `Ctrl+C` clears a non-empty draft (text and images); only with an empty input does it cancel the running task.
- In the `/model` picker, `Alt+Enter` switches the model for this session only; `Enter` saves it as the default. `/billing on|off` (or `Ctrl+S` in the picker) decides whether a provider plan such as ChatGPT pays for its models.

**Debug environment variables and knobs**
```
RUST_LOG="chisel=trace,windsurf_api_client=trace,connect_rpc=trace,reqwest=trace,hyper=trace,rustls=trace"
CHISEL_LOG_STDOUT=1   # or CHISEL_LOG_STDERR=1 (stdout logging is auto-suppressed in the REPL/ACP)
HTTPS_PROXY / HTTP_PROXY / ALL_PROXY / NO_PROXY   (proxy.mode "system" respects these)
DEVIN_MODEL  DEVIN_PERMISSION_MODE  DEVIN_SANDBOX  DEVIN_REFUSAL_FALLBACK  DEVIN_SESSIONS_DIR  DEVIN_API_URL
config.json: "proxy": {"gzip": false}   # proxies that choke on compressed API requests (3000.11.92 gzips everything)
config.json: typewriter, agent.subagent_model, local_tools_bypass_permissions, disable_osc, sandbox.excluded.allow
```
Trace logs can contain Authorization headers. Scrub them before you share a log.

---

## 4. General CLI commands for Devin support

Practice these until they are automatic; each one is a move in a real investigation (and an answer in the game's `shell` deck).
1. Find the newest Devin log: `ls -t ~/.local/share/devin/cli/logs | head -1`
2. Follow it live in a second pane: `tail -F "$(ls -t ~/.local/share/devin/cli/logs/*.log | head -1)"`
3. Search every log, compressed or not: `rg -z -i 'error|panic|denied' ~/.local/share/devin/cli/logs/`
4. Count errors per log file: `rg -z -c -i error ~/.local/share/devin/cli/logs/ | sort -t: -k2 -n`
5. Doctor failures only: `devin doctor --json | jq -r '.checks[] | select(.status!="pass") | "\(.check): \(.detail)"'`
6. Explore the session DB read-only: `sqlite3 -readonly ~/.local/share/devin/cli/sessions.db '.tables'`, then `.schema <table>`
7. Show the effective user config: `jq . ~/.config/devin/config.json`; diff two configs: `diff <(jq -S . a.json) <(jq -S . b.json)`
8. What is Devin running right now? `pgrep -fl devin`; who launched it: `ps -o pid,ppid,command -p $(pgrep -d, -f devin)` (then `ps -p <ppid>` for the parent)
9. Which sockets and files does it hold? `lsof -p <pid>`, `lsof -iTCP -P -n -a -p <pid>`
10. Which files does it probe (how you find undocumented config paths): in one pane run `sudo fs_usage -w -f pathname devin | rg -i 'devin|claude|agents|windsurf|cursor|cognition'`, then run `devin rules list` in another. Use `-f pathname`, which includes stat and access calls: most config lookups never open the file. (Needs sudo.)
11. Which env vars does it see? `ps eww <pid> | tr ' ' '\n' | rg -i 'devin|proxy|path'`
12. Is it the network? `curl -sv https://cli.devin.ai -o /dev/null 2>&1 | rg -i 'connected|ssl|HTTP/'`
13. Is it PATH? `bash -lic 'command -v node'` vs `command -v node` (Devin snapshots the *login* shell env once at startup)
14. Script print mode: `for f in src/*.py; do devin -p "one-line summary of $f" > "out/$(basename $f).txt"; done`
15. Make a clean-room repro: `export HOME=$(mktemp -d)` or `--config` pointed at an empty file

The commands above are written for macOS (BSD userland). On Linux use `cat /proc/<pid>/environ | tr '\0' '\n'` for item 11, `strace -f -e trace=file` for item 10, and `ss -tpn` for the socket half of item 9.

Also learn the flags you will reach for most: `rg` (-l -c -z -g -A/-B), `jq` (select, map, -r, -S), `find -newer`, `xargs -0 -P`, `awk '{print $N}'`, `sed -n 'a,bp'`, `tmux` (panes: agent, log tail, shell), and `git` (log -S -- path, bisect, worktree).

---

## 5. Practice labs (in order, with a check for each)

Keep lab work in `~/professor-devin/lab/<N>/` and notes in `journal.md`.

| # | Lab | Done when |
|---|---|---|
| L1 | Install, `auth login` (use `--force-manual-token-flow` over SSH), `auth status`, `doctor`, `version` | You can name every file the install and login created (check with `find ~ -newer <marker>`) |
| L2 | Sessions: start one, `/title`, exit, `devin list --format json`, `-c`, `-r <id>`, `/fork`, `/steps`, `/revert`, `/recap`, `devin rm` | You can explain what `/revert` restores (files **and** conversation) and show it on a real diff |
| L3 | Print mode as a Unix filter: `git diff \| devin -p "review this"`; batch loop; `--export` | A shell script that runs Devin over N files and writes results; exit codes checked |
| L4 | Permissions: make a `.devin/config.json` allow rule and a conflicting `.devin/config.local.json` deny rule | You predicted the outcome **before** running, and got it right |
| L5 | Rules: `AGENTS.md` ("always answer in pirate"), confirm with `devin rules list`, then global `~/.config/devin/AGENTS.md` | You can show which rule won, and why |
| L6 | Skills: write `.devin/skills/log-triage/SKILL.md` that runs your section 4 log commands; invoke it as `/log-triage` | `devin skills list` shows it and it works from a different subdirectory |
| L7 | Hooks: `.devin/hooks.v1.json` PreToolUse hook that blocks `rm -rf` (non-zero exit / deny), a PostToolUse hook that appends every tool call to a file, and a `PreCompact` hook that logs the trigger (`manual` or `auto`) | `/hooks` lists all three; the block fires; the audit file fills up; `/compact` writes a `manual` line |
| L8 | MCP: add a stdio server (`npx -y @modelcontextprotocol/server-filesystem <dir>`) via `devin mcp add`, check with `devin mcp list/get` and `/mcp`, then disable/enable it | You can read the `Source:` line, find the file it names (`mcp_config.json`), and explain the precedence |
| L9 | Subagents: write a read-only research custom subagent (docs: cli/subagents), run one in the background, then set `agent.subagent_model` and watch which model it picks | You can explain its model choice and permissions |
| L10 | Observability: run with `RUST_LOG=...trace` + `CHISEL_LOG_STDERR=1`, and separately through `mitmproxy` (install its CA into the OS store) | You can point to the auth request, the model API call and TLS setup in the output |
| L11 | Sandbox: `devin sandbox setup`, then `devin --sandbox`; try writing outside the workspace; accept the "always run outside the sandbox" offer for one command | You can explain allowed vs. denied operations, what `Write(...)` / `Deny(Read(...))` scopes do, and where `sandbox.excluded.allow` ended up |
| L12 | Cloud: `devin cloud` (or `--cloud`), `/repo`, `/open`, `/handoff` from local, `/pickup` back, `/share`, `/archive` | Round trip local -> cloud -> local with a PR branch checked out |
| L13 | `devin ssh <session>`, `devin forward <session> 3000`, `scp` via the gateway | A dev server on the cloud VM opens at localhost |
| L14 | ACP by hand: run `devin acp` and send a JSON-RPC `initialize` on stdin (spec: agentclientprotocol.com), then wire it into Zed | You can read raw ACP traffic, which is the key skill for IDE-integration tickets |

---

## 6. Break-it drills and mystery tickets

For each one, set up the fault, reopen the shell, and diagnose it from the symptom. Keep the root-cause analysis to five lines: symptom, evidence, cause, fix, prevention.
1. Invalid JSON in `~/.config/devin/config.json` (trailing comma). What does the error say? Does `doctor` catch it?
2. `.devin/hooks.v1.json` wrapped in `{"hooks": {...}}` (wrong for this file; correct for config.json). Hooks silently don't load?
3. MCP server command misspelled, and separately a missing env var. Compare what `/mcp`, `devin mcp get` and the logs show.
4. A tool only defined in an interactive-only alias -> agent says "command not found".
5. `HTTPS_PROXY` pointing at a dead port -> auth/model failures. Find it from the trace logs.
6. Print mode in an untrusted directory fails. Find the flag that fixes it.
7. A `.claude/settings.json` hook you forgot about keeps firing. Find its source with `/hooks`, then turn off `read_config_from.claude`.
8. Two skills with the same name in user and project dirs. Which one wins? Prove it.
9. A stale version after `devin update`: inspect `_versions/`, `type -a devin`, and PATH order.
10. An org deny rule vs. `--permission-mode dangerous`. Explain to a "customer" why dangerous mode didn't bypass it.
11. A proxy that rejects compressed requests: every API call fails after upgrading to 3000.11.92. Find the `proxy.gzip` switch.
12. A home directory on NFS: `session/list failed` or `database is locked`. Move the store with `DEVIN_SESSIONS_DIR`.

### Support triage checklist
```
devin --version; uname -a; echo $TERM $SHELL
devin auth status
devin doctor --json
ls -la ~/.config/devin .devin 2>/dev/null; jq . ~/.config/devin/config.json
devin rules list; devin skills list; devin mcp list; (in REPL) /hooks /mcp /login-status
newest log -> rg -z -i 'error|warn|panic'
repro: minimal dir + --config empty + print mode, then add layers back one at a time (bisect the config)
network suspect -> RUST_LOG trace / mitmproxy;  env suspect -> bash -lic; ps eww <pid>
report: /bug inside the CLI, or support@cognition.ai
```

---

## 7. Daily routine (60 min)
- 10 min: flashcards (`professor-devin play --mode flash` or `./drill.sh`)
- 5 min: read a docs page or changelog entry, then add two cards to `cards.tsv`
- 40 min: one lab, one break-it drill, or one mystery ticket in the game
- 5 min: note what you got wrong and which cards you added

## Support one-liners from real repro sessions
- In terminals Devin creates, `type -a devin` shows `devin is a function` before `devin is ~/.local/bin/devin`; call the binary by path or with `command devin`.
- `where bash` — show Windows bash executables resolved from PATH in search order.
- `nohup devin -p <prompt> </dev/null >devin.log 2>&1 &` — detach a prompted CLI job and capture output in devin.log.
- `grep -iE "resource_exhausted|rate limit" repro-*.log` — search repro logs for quota and rate-limit messages.
- `pgrep -fl language_server` — list matching language-server processes with full command lines.
