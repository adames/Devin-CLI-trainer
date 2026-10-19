# docs/ — Devin CLI documentation snapshots

Offline copies of docs.devin.ai CLI pages, fetched 2026-10-19 against CLI
version 3000.11.92. If a snapshot disagrees with the installed binary, the
`--help` output of the binary wins. (GUIDE.md documents one known drift on
`--permission-mode` values.)

| File | Source URL | What it covers |
| - | - | - |
| cli_cloud.md | https://docs.devin.ai/cli/cloud | Devin Cloud sessions from the terminal: `devin --cloud`, `/cloud`, `/open`, `/model`, `/archive` |
| cli_enterprise_devin-auth.md | https://docs.devin.ai/cli/enterprise/devin-auth | Enterprise auth: credentials file location, RBAC roles, the Use Devin CLI permission |
| cli_essential-commands.md | https://docs.devin.ai/cli/essential-commands | Must-know commands: starting/resuming sessions, cloud sessions, slash commands, keyboard shortcuts |
| cli_extensibility_hooks_overview.md | https://docs.devin.ai/cli/extensibility/hooks/overview | Hooks: run shell commands or LLM prompts on lifecycle events, block or rewrite tool calls |
| cli_extensibility_mcp_configuration.md | https://docs.devin.ai/cli/extensibility/mcp/configuration | Adding, configuring, authenticating, and troubleshooting MCP servers (stdio, HTTP, SSE) |
| cli_extensibility_rules.md | https://docs.devin.ai/cli/extensibility/rules | Rules and AGENTS.md: always-on instructions for the agent |
| cli_extensibility_skills_creating-skills.md | https://docs.devin.ai/cli/extensibility/skills/creating-skills | SKILL.md format: frontmatter, allowed-tools auto-approval, permissions, subagent skills |
| cli_handoff.md | https://docs.devin.ai/cli/handoff | Handing a task to a cloud Devin with `/handoff` and pulling its PR back |
| cli_reference_commands.md | https://docs.devin.ai/cli/reference/commands | Full command/flag reference: global flags, subcommands, interactive slash commands |
| cli_reference_configuration_config-file.md | https://docs.devin.ai/cli/reference/configuration/config-file | Config file format: every user and project option (permissions, proxy, sandbox, `read_config_from`) |
| cli_reference_configuration_global-vs-local.md | https://docs.devin.ai/cli/reference/configuration/global-vs-local | How global, project, and local settings interact |
| cli_reference_keyboard-shortcuts.md | https://docs.devin.ai/cli/reference/keyboard-shortcuts | Common keyboard shortcuts |
| cli_reference_permissions.md | https://docs.devin.ai/cli/reference/permissions | Permission rules: allow, deny, or prompt for commands, file access, and MCP tools |
| cli_sandbox.md | https://docs.devin.ai/cli/sandbox | OS-level isolation: writable paths, network filtering, enterprise enforcement |
| cli_subagents.md | https://docs.devin.ai/cli/subagents | Delegating to foreground/background subagents with their own profiles and permissions |
| cli_troubleshooting.md | https://docs.devin.ai/cli/troubleshooting | Common issues and fixes |

Filenames map to URLs by turning `cli_` into `https://docs.devin.ai/cli/` and
remaining underscores into `/`; hyphens stay as-is.

- `dojo/content/help/slash-help.txt` is the REPL's own `/help` listing; it is
  the source for slash commands the docs don't list yet (`/billing`, `/code`,
  `/fusion`, `/goal`, `/recap`, `/share`, plus aliases).
