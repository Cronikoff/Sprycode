# SpryCode Security Model

## Overview

SpryCode is **secure by default**. Every sensitive operation requires an explicit permission declaration. This means programs cannot accidentally read files, make network requests, or access secrets without the developer explicitly allowing it.

## Permission System

### Declaring Permissions

```spry
allow filesystem.read "./data"
allow filesystem.write "./output"
allow network.request "https://api.example.com"
allow secret.read "PAYMENT_API_KEY"
```

### Denying Operations

```spry
deny network.all
deny filesystem.write "/system"
```

### Permission Scopes

Permissions can be scoped to paths or URLs:

```spry
allow filesystem.read "./data"       // Only ./data and below
allow filesystem.write "./output"    // Only ./output and below
allow network.request "https://api.example.com"  // Only this host
```

### Permission Categories

| Category | Description |
|----------|-------------|
| `filesystem.read` | Read files and folders |
| `filesystem.write` | Write, create, move, delete files |
| `filesystem.all` | All filesystem operations |
| `network.request` | HTTP/HTTPS requests |
| `network.websocket` | WebSocket connections |
| `network.all` | All network operations |
| `secret.read` | Read secrets from vault/environment |
| `secret.write` | Write secrets (Pro) |
| `fraud.check` | Run fraud verification workflows (Pro) |
| `db.query` | Query a database connection |
| `db.write` | Write to a database connection |

## Secrets

Secrets are loaded from environment variables or a secure vault:

```spry
allow secret.read "API_KEY"
let key = secret "API_KEY"
```

### Secret Safety Rules

1. **Never printed**: Secrets are never included in log output
2. **Automatic redaction**: If a secret appears in log context, it shows as `<secret:KEY_NAME>`
3. **No accidental exposure**: Secrets cannot be converted to strings without explicit intent
4. **Vault integration**: SpryCode Pro supports hardware security modules and enterprise vaults

## Privacy Annotations

```spry
private data customerEmail: Email
sensitive data paymentToken: Secret
```

### Rules

- `private` fields are **redacted in all log output**
- `sensitive` fields **cannot leave the local system** without explicit permission
- Access to private data is **audit logged** (Pro feature)

## Secure Mode

Enable strict permission enforcement:

```bash
spry run main.spry --secure
```

In secure mode:
- Every operation requires an explicit `allow` declaration
- Any undeclared operation raises a `PermissionError`
- All access is logged

## Sandboxing

External adapters run in a sandbox:

```spry
adapter external sandboxed {
    allow filesystem.read "./scripts"
    deny network.all
}
```

## Supply Chain Security

SpryCode package management enforces:
- **Signed packages**: All packages must be cryptographically signed
- **Lockfiles**: `spry.lock` pins exact versions
- **Checksum validation**: Package contents are verified
- **Dependency scanning**: `sprypm audit` checks for vulnerabilities

## Audit Logging (Pro)

SpryCode Pro provides immutable audit logs:

```spry
connector paymentGateway {
    provider "Stripe"
    mode production
    audit full
    privacy strict
}
```

## Fraud Verification (Pro)

Fraud check capabilities require strong governance:

```spry
fraud check transaction tx_12345 {
    reason "technical verification of duplicate payment signal"
    case "CASE-2026-0001"
    scope minimal
    redact personalData
}
```

Requirements:
- Role-based access control
- Mandatory reason codes
- Case IDs for audit trail
- Automatic personal data redaction
- Approval workflows for sensitive investigations

## Anti-Abuse Controls

SpryCode prevents misuse by:
- Enforcing least privilege
- Logging every sensitive access
- Requiring multi-factor authentication for admin operations (Pro)
- Supporting immutable audit logs
- Alerting on suspicious behavior patterns

## What SpryCode Prohibits

SpryCode explicitly prohibits:
- Unauthorized surveillance
- Hidden data extraction
- Credential theft
- Bypassing access controls
- Malicious persistence
- Unapproved personal data profiling
