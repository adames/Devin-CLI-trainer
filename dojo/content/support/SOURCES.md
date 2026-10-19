# Sources (every card/scenario `source` field maps here)

Evidence comes from hands-on repro sessions and the public docs. Support cases
are generalized: no ticket numbers, customer details, or session links.

| key | evidence | kind |
|---|---|---|
| S-MASTER | Hands-on CLI session: flags verified on v3000.11.3, login flow exercised for real, file-lookup trace of the policy file, shell-function shadowing | own repro |
| S-RE | resource_exhausted / "Connection error" banner repro: invented flags exit 2, tty suspension, model IDs, grep pattern, quota hypothesis | own repro |
| S-MW | Multi-window Desktop "Connection error" repro: failed to start, ECONNREFUSED loop, Reload Window, one language server per window, red-herring warnings | own repro |
| S-WSL | WSL remote connect_failure repro: Windows log paths | own repro |
| R-WIN-BASH | Windows command never finishes: `bash.exe -c` resolved from PATH, MKS Toolkit vs Git Bash (not reproduced with Git Bash) | generalized support case |
| R-WS-TRANSITION | Workspace transition on chat init: 2 windows / 4 ACP processes next launch, reproduced 2/2 | generalized support case |
| R-TYPING-LAG | Typing/paste lag in Desktop: ext-host `get userSettings` dominates the CPU profile (seen on macOS and Windows) | generalized support cases |
| R-SUBAGENT | Subagent interruption: UNTESTED (run_subagent unavailable). No card made on purpose. | generalized support case |
| DOCS | Devin CLI troubleshooting docs (manual token flow, Not authorized, MCP auth per client) | https://docs.devin.ai |
| S-REPROS | Pattern across the repro sessions above: env mismatch stalled several repros | (all of the above) |
