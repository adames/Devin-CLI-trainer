# Recorded outputs for the support pack (devin 3000.11.3 (9c803229faa4))

Recorded 2026-09-30 on this box: throwaway HOME/XDG dirs, throwaway cwd, logged out, stdin </dev/null.
Paths scrubbed: temp HOME -> /home/customer, temp cwd -> /home/customer/app.

## R-CWD: devin --cwd ~/app --mode bypass-permissions --prompt "hi"   (exit 2)
```
error: unexpected argument '--cwd' found

  tip: to pass '--cwd' as a value, use '-- --cwd'

Usage: devin [OPTIONS] [PATH]... [-- <PROMPT>...] [COMMAND]

For more information, try '--help'.
```
Note: clap stops at the first unknown flag, so only --cwd is reported.

## R-MODEL: devin --model "SWE-1.7 (medium)" -p "hi"   (exit 1)
Needs auth: logged out it prints the login prompt then `Error: Login canceled`. No model validation happens
before auth, so the 'Unknown model' error could not be recorded. Same for `devin --permission-mode dangerous -p hi`.

## R-STATUS: devin auth status   (exit 0, logged out)
```
Not logged in.
  Credentials path: /home/customer/.local/share/devin/credentials.toml
Run `devin auth login` to authenticate.
```

## R-VERSION: devin --version   (exit 0)
```
devin 3000.11.3 (9c803229faa4)
```

## Docs check
- "Use Devin CLI" role permission: confirmed in docs/cli_enterprise_devin-auth.md (fetched from
  https://docs.devin.ai/cli/enterprise/devin-auth). The troubleshooting page itself only says "the correct permission".
- "tokens do not expire by default", `devin auth logout && devin auth login`: docs/cli_troubleshooting.md:108-116.
- "Each MCP client authenticates independently ... run `devin mcp login` separately": docs/cli_extensibility_mcp_configuration.md:437-445.
