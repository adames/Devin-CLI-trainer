# Sources (every card/scenario `source` field maps here)

| key | evidence | url |
|---|---|---|
| S-MASTER | Master Devin CLI session: flags verified on v3000.11.3, login flow hit for real, strace of policy file, shell-function shadowing | https://app.devin.ai/sessions/f6f25f819b20440bb122fa6908485c3b |
| S-RE | resource_exhausted / Connection error banner repro: invented flags exit 2, tty suspension, model IDs, grep pattern, quota hypothesis | https://app.devin.ai/sessions/cb374ad75efb4e498f7a3b5cfbb73eec |
| S-MW | Multi-window Desktop Connection error repro: failed to start, ECONNREFUSED loop, Reload Window, per-window LS, red-herring warnings | https://app.devin.ai/sessions/21b861925738412b9c6d7d54ce7963fe |
| S-WSL | windsurfremotewsl connect_failure repro: Windows log paths | https://app.devin.ai/sessions/52d6e81722724d71a1b014fb9d0a8980 |
| P-71893 | Windows command never finishes, bash.exe -c from PATH, MKS vs Git Bash (not reproduced with Git Bash) | https://app.devin.ai/sessions/718c6aefcf144d4598b39d919fbd483f |
| P-67687 | Workspace transition on chat init, 2 windows / 4 ACP procs, reproduced 2/2 | https://app.devin.ai/sessions/ecf3cf2eb36349ca9f03cda3f4b40ae6 |
| P-70919 | Typing lag, ext-host `get userSettings` | https://app.devin.ai/sessions/bf85c4b2f6e74fdaa29e838954fa158c |
| P-70882 | Same family, macOS | https://app.devin.ai/sessions/eb60b45b6f68422097a2b786c969c9a8 |
| P-70933 | Same family | https://app.devin.ai/sessions/b663a12e02fe431bb7ecf2c4d3ea6784 |
| P-72140 | Subagent interruption: UNTESTED (run_subagent unavailable). No card made on purpose. | https://app.devin.ai/sessions/029e0482a6314c6aacf6b696e7386062 |
| DOCS | Devin CLI troubleshooting docs (manual token flow, Not authorized, MCP auth per client) | https://docs.devin.ai |
| S-REPROS | Pattern across the repro sessions above: env mismatch stalled several repros | (all of the above) |
