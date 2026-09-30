> ## Documentation Index
> Fetch the complete documentation index at: https://docs.devin.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Devin Cloud in the Devin CLI

> Create, steer, resume, and watch Devin Cloud sessions from your terminal with devin --cloud, /cloud, /open, /model, and /archive.

`devin --cloud` runs a Devin Cloud session instead of a local agent. Devin works on its own VM with a shell, browser, and repository clones; the CLI streams the session into your terminal.

## Start a cloud session

```bash theme={null}
devin --cloud                          # interactive
devin --cloud -p "fix flaky CI tests"  # one prompt, print the response, exit
```

Or run `/cloud` in a fresh local session (before the first message; run `/clear` first otherwise).

<Note>
  Requires a Devin account. Run `devin auth login` (or `/login`) if you are not signed in.
</Note>

Before the first message, `/repo`, `/platform`, and `/model` choose the repositories, OS, and model. Then type a task as usual. The session runs on the VM, so closing the terminal does not stop it.

To move an in-progress local session to the cloud, use [`/handoff`](/cli/handoff).

## Resume a cloud session

`--resume` (`-r`) reopens any cloud session, whether it was started from the CLI, the web app, or Desktop:

```bash theme={null}
devin --cloud -r https://app.devin.ai/sessions/…          # by URL
devin --cloud -r devin-0123456789abcdef0123456789abcdef   # by ID
devin --cloud -r                                          # pick from recent sessions
```

## Run non-interactively

`--cloud -p` starts a session, sends one prompt, prints Devin's response to stdout, and exits. The session persists; resume it with `devin --cloud -r`.

```bash theme={null}
devin --cloud -p "fix the failing test in auth.rs"    # inline prompt
devin --cloud -p -- fix the failing test in auth.rs   # trailing arguments
devin --cloud -p --prompt-file prompt.txt             # from a file
```

## Continue the work locally

`/pickup` (or `/handoff`) checks out the session's pull request branch and starts a local session on it. See [Hand off back to local](/cli/handoff#hand-off-back-to-local).

`/ssh` opens a shell on the session's VM. See [SSH](/cli/ssh).

## Cloud slash commands

Available in cloud sessions alongside the usual [slash commands](/cli/essential-commands#slash-commands):

| Command | Description |
| - | - |
| `/cloud` | Switch a fresh local session to Devin Cloud |
| `/repo` | Choose the repositories to clone |
| `/platform` | Choose the OS, when your organization offers more than one |
| `/model` | Choose the model. [SWE-2](https://cognition.com/blog/swe-2) is recommended. |
| `/open [web\|desktop]` | Open the session in the web app (default) or [Devin Desktop](https://devin.ai/desktop) |
| `/ssh` | SSH into the session's VM |
| `/pickup`, `/handoff` | Check out the pull request branch and continue locally |
| `/rename <new title>` | Rename the session |
| `/archive` | Archive the session |

## Related resources

<CardGroup cols={2}>
  <Card title="SSH" icon="terminal" href="/cli/ssh">
    Connect to a cloud session's VM and forward ports
  </Card>

  <Card title="Hand off to cloud Devins" icon="share-from-square" href="/cli/handoff">
    Move a task between local and cloud with /handoff
  </Card>

  <Card title="Commands & Flags" icon="terminal" href="/cli/reference/commands">
    Full reference for `--cloud` and the cloud slash commands
  </Card>
</CardGroup>
