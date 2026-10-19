# Learning Devin CLI for support work

I wrote this guide around Devin CLI **v3000.11.3** and the CLI docs.
I saved the docs snapshots in `docs/`. If the installed binary and docs disagree, trust `--help` for that version and log the drift.

---

## 0. How I learn it: four loops

| Loop | What I do | Why it helps | Time |
|---|---|---|---|
| 1. **Model** | Draw the architecture (section 2) from memory, then check it against the real thing | A mental model helps me navigate a bug. Without one, commands are trivia | 20 min, week 1 |
| 2. **Retrieve** | Use flashcards (`./drill.sh`) and predict what a command will do | Recalling an answer helps it stick better than rereading it | 10 min daily |
| 3. **Practice** | Work through the labs (section 5) and their pass/fail checks | Practice builds fluency and shows me what I still need to learn | 45 min, 4–5×/week |
| 4. **Break** | Break something on purpose, then diagnose it cold (section 6) | This is support work: start with a symptom and find its cause | 1–2×/week |

Rules I use:
- **Predict before running.** Say what I expect a command to print. When I'm wrong, I write it in `journal.md`; that is the part I need to remember.
- **Check the source.** Start with `devin <cmd> --help` for the installed version, then check the docs, changelog, and only then my memory. Log differences as support findings.
- **Use spaced repetition.** I review missed cards sooner and let the ones I know wait longer. `drill.sh` handles the order.
- **Teach it back.** Each week, write a one-page runbook for a new support engineer. The gaps show me what to study next.
- **Keep a shell open.** I can connect each idea to a file, process, or log line.

### A version mismatch I found while writing this
- Docs, Commands & Flags page: `--permission-mode` = `normal | dangerous | bypass`
- `devin --help` (v3000.11.3): `auto` (default) | `accept-edits` | `smart` | `dangerous`, env `DEVIN_PERMISSION_MODE`
- Slash commands use yet another set of names: `/normal /accept-edits /smart /plan /bypass /autonomous`

These mismatches show up in support tickets. I check `devin --version` before digging in.

---

## 1. A four-week plan (about an hour a day)

| Week | Focus | Exit criteria |
|---|---|---|
| 1 | Install, auth, file layout, sessions, `-p` scripting, general CLI basics (rg, jq, less, find, xargs) | You can redraw section 2 from memory; labs L1–L3 done; drill ≥80% |
| 2 | Config layers, permissions, rules/AGENTS.md, skills, hooks | Labs L4–L7 done; you can predict precedence outcomes correctly |
| 3 | MCP, subagents, plugins, sandbox, logging/tracing, proxy/TLS; process-level CLI (ps, lsof, fs_usage) | Labs L8–L11 done; 2 break-it drills solved cold |
| 4 | Cloud: `--cloud`, `/handoff`, `devin ssh/forward`, `devin cloud drs`, ACP (IDE integration) | Labs L12–L14 done; write your personal support runbook |

After week four, I work one mystery ticket (section 6) each week and read new changelog entries as they ship (`docs.devin.ai/cli/changelog/stable`).

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
        '-- --cloud: relays ACP to the Devin Cloud ACP WebSocket
                                   |
                     Devin Cloud session VM  <-- devin ssh / devin forward / /handoff / /pickup
IDEs (Zed, JetBrains, Xcode) ---- ACP ---> devin acp
```
(The root help says print mode's agent "runs in that child" and that `--cloud` uses `devin acp --cloud`.)

### Files I check on Linux and macOS
| Path | What it is |
|---|---|
| `~/.local/bin/devin` | binary (installer target) |
| `~/.local/share/devin/cli/_versions/` | installed versions |
| `~/.local/share/devin/credentials.toml` | auth credentials (`devin auth status` shows the path) |
| `~/.local/share/devin/cli/sessions.db` | local session store (SQLite) |
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
1. Org / team settings (can't be overridden; org deny/ask rules survive even bypass/dangerous mode)
2. Session approvals (in memory)
3. `.devin/config.local.json`
4. `.devin/config.json`
5. `~/.config/devin/config.json`

---

## 3. Commands I practice first

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
```
**Subcommands**
```
devin auth login [--force-manual-token-flow] | logout | status
devin doctor [--json]          devin version / --version     devin update [--force]
devin models list              devin list [--format json|csv]   devin rm <id> [--force]
devin rules list|show|paths    devin skills list|show|paths
devin mcp add|list|get|remove|login|logout|enable|disable
devin plugins install|list|info|update|remove|prune
devin ssh [SESSION] [ssh args]     devin forward <SESSION> 3000 8080:3000
devin cloud drs whoami|sandbox-create|run|blueprint-list|build|build-logs|...
devin sandbox setup            devin migrate hooks|workflows     devin acp [--agent-type review|summarizer]
devin setup | desktop | uninstall
```
**Slash commands I want to remember**
`/help /mode /plan /ask /smart /bypass /model /clear /steps /fork [step] /revert <step> /resume /ls /loop /btw /hooks /mcp /context /usage /stats /compact /config /bug /cloud /handoff /open /ssh /pickup /add-dir /workspace /login-status /export`

**Debug environment variables**
```
RUST_LOG="chisel=trace,windsurf_api_client=trace,connect_rpc=trace,reqwest=trace,hyper=trace,rustls=trace"
CHISEL_LOG_STDOUT=1   # or CHISEL_LOG_STDERR=1 (stdout logging is auto-suppressed in the REPL/ACP)
HTTPS_PROXY / HTTP_PROXY / ALL_PROXY / NO_PROXY   (proxy.mode "system" respects these)
DEVIN_MODEL  DEVIN_PERMISSION_MODE  DEVIN_SANDBOX  DEVIN_REFUSAL_FALLBACK
```
Trace logs can contain Authorization headers. I scrub them before sharing.

---

## 4. General CLI commands I use in Devin support

I practice these until they feel automatic. Each item is a command I can use in a support investigation.
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

I also learn the flags I use most: `rg` (-l -c -z -g -A/-B), `jq` (select, map, -r, -S), `find -newer`, `xargs -0 -P`, `awk '{print $N}'`, `sed -n 'a,bp'`, `tmux` (panes: agent, log tail, shell), and `git` (log -S -- path, bisect, worktree).

---

## 5. Practice labs (in order, with a check for each)

I keep lab work in `~/devin-cli-mastery/lab/<N>/` and write notes in `journal.md`.

| # | Lab | Done when |
|---|---|---|
| L1 | Install, `auth login` (use `--force-manual-token-flow` over SSH), `auth status`, `doctor`, `version` | You can name every file the install and login created (check with `find ~ -newer <marker>`) |
| L2 | Sessions: start one, `/title`, exit, `devin list --format json`, `-c`, `-r <id>`, `/fork`, `/steps`, `/revert`, `devin rm` | You can explain what `/revert` restores (files **and** conversation) and show it on a real diff |
| L3 | Print mode as a Unix filter: `git diff \| devin -p "review this"`; batch loop; `--export` | A shell script that runs Devin over N files and writes results; exit codes checked |
| L4 | Permissions: make a `.devin/config.json` allow rule and a conflicting `.devin/config.local.json` deny rule | You predicted the outcome **before** running, and got it right |
| L5 | Rules: `AGENTS.md` ("always answer in pirate"), confirm with `devin rules list`, then global `~/.config/devin/AGENTS.md` | You can show which rule won, and why |
| L6 | Skills: write `.devin/skills/log-triage/SKILL.md` that runs your section 4 log commands; invoke it as `/log-triage` | `devin skills list` shows it and it works from a different subdirectory |
| L7 | Hooks: `.devin/hooks.v1.json` PreToolUse hook that blocks `rm -rf` (non-zero exit / deny) and a PostToolUse hook that appends every tool call to a file | `/hooks` lists both; the block fires; the audit file fills up |
| L8 | MCP: add a stdio server (`npx -y @modelcontextprotocol/server-filesystem <dir>`) via `devin mcp add`, check with `devin mcp list/get` and `/mcp`, then disable/enable it | You can find where it was written (`mcp_config.json`) and explain the precedence |
| L9 | Subagents: write a read-only research custom subagent (docs: cli/subagents) and run one in the background | You can explain its model choice and permissions |
| L10 | Observability: run with `RUST_LOG=...trace` + `CHISEL_LOG_STDERR=1`, and separately through `mitmproxy` (install its CA into the OS store) | You can point to the auth request, the model API call and TLS setup in the output |
| L11 | Sandbox: `devin sandbox setup`, then `devin --sandbox`; try writing outside the workspace | You can explain allowed vs. denied operations, and what `Write(...)` / `Deny(Read(...))` scopes do |
| L12 | Cloud: `devin --cloud`, `/repo`, `/open`, `/handoff` from local, `/pickup` back, `/archive` | Round trip local → cloud → local with a PR branch checked out |
| L13 | `devin ssh <session>`, `devin forward <session> 3000`, `scp` via the gateway | A dev server on the cloud VM opens at localhost |
| L14 | ACP by hand: run `devin acp` and send a JSON-RPC `initialize` on stdin (spec: agentclientprotocol.com), then wire it into Zed | You can read raw ACP traffic, which is the key skill for IDE-integration tickets |

---

## 6. Break-it drills and mystery tickets

For each one, set up the fault, reopen the shell, and diagnose it from the symptom. Keep the root-cause analysis to five lines: symptom, evidence, cause, fix, and prevention.
1. Invalid JSON in `~/.config/devin/config.json` (trailing comma). What does the error say? Does `doctor` catch it?
2. `.devin/hooks.v1.json` wrapped in `{"hooks": {...}}` (wrong for this file; correct for config.json). Hooks silently don't load?
3. MCP server command misspelled, and separately a missing env var. Compare what `/mcp`, `devin mcp get` and the logs show.
4. A tool only defined in an interactive-only alias → agent says "command not found".
5. `HTTPS_PROXY` pointing at a dead port → auth/model failures. Find it from the trace logs.
6. Print mode in an untrusted directory fails. Find the flag that fixes it.
7. A `.claude/settings.json` hook you forgot about keeps firing. Find its source with `/hooks`, then turn off `read_config_from.claude`.
8. Two skills with the same name in user and project dirs. Which one wins? Prove it.
9. A stale version after `devin update`: inspect `_versions/`, `type -a devin`, and PATH order.
10. An org deny rule vs. `--permission-mode dangerous`. Explain to a "customer" why dangerous mode didn't bypass it.

### My support triage checklist
```
devin --version; uname -a; echo $TERM $SHELL
devin auth status
devin doctor --json
ls -la ~/.config/devin .devin 2>/dev/null; jq . ~/.config/devin/config.json
devin rules list; devin skills list; devin mcp list; (in REPL) /hooks /mcp /login-status
newest log → rg -z -i 'error|warn|panic'
repro: minimal dir + --config empty + print mode, then add layers back one at a time (bisect the config)
network suspect → RUST_LOG trace / mitmproxy;  env suspect → bash -lic; ps eww <pid>
report: /bug inside the CLI, or support@cognition.ai
```

---

## 7. Daily routine (60 min)
- 10 min: review flashcards with `./drill.sh`
- 5 min: read a docs page or changelog entry, then add two cards to `cards.tsv`
- 40 min: work through one lab or break-it drill
- 5 min: note what I got wrong and what cards I added

- In terminals Devin creates, `type -a devin` shows `devin is a function` before `devin is ~/.local/bin/devin`; call the binary by path or with `command devin`.

## Support one-liners from real repro sessions
- `where bash` — show Windows bash executables resolved from PATH in search order.
- `nohup devin -p <prompt> </dev/null >devin.log 2>&1 &` — detach a prompted CLI job and capture output in devin.log.
- `grep -iE "resource_exhausted|rate limit" repro-*.log` — search repro logs for quota and rate-limit messages.
- `pgrep -fl language_server` — list matching language-server processes with full command lines.
