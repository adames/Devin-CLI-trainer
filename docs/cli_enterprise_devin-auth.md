# Devin Auth (snapshot of https://docs.devin.ai/cli/enterprise/devin-auth, fetched 2026-09-30)

## Prerequisites
1. Your organization has a Devin enterprise account
2. Your administrator has configured Devin CLI access permissions (see Configuring Access below)
3. You have been assigned a role with the Use Devin CLI permission

## Credentials file location
After `devin auth login`, Devin CLI stores your API token in `credentials.toml`. By default, this token is persistent and does not expire.
- macOS / Linux: `$XDG_DATA_HOME/devin/credentials.toml` when `XDG_DATA_HOME` is set; otherwise `~/.local/share/devin/credentials.toml`
- Windows: `%APPDATA%\devin\credentials.toml`
Run `devin auth logout` to remove stored credentials.

## Configuring Access
Devin CLI access is controlled through Devin's custom roles and RBAC system. Administrators must create a custom role with the Use Devin CLI role permission and assign it to users who need access.
1. Navigate to Enterprise Settings > Roles
2. Click Create a custom role
3. Provide a descriptive name (e.g., "Devin CLI User")
4. Select the Use Devin CLI permission
5. Save the role
