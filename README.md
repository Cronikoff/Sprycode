# SpryCode

> **SpryCode: agile code for fast, secure, adaptive systems.**

SpryCode is a fast, reliable, adaptive programming language and runtime platform designed for:

- ⚡ **Fast file and data movement** — parallel, atomic, verified
- 🔒 **Security by default** — explicit permissions, secret redaction, sandboxing
- 🔐 **Privacy-first** — private/sensitive data annotations, audit logging
- 🔄 **Transactions** — safe operations with rollback and compensation logic
- 🔌 **Interoperability** — adapters for SQL and REST APIs
- 📦 **Easy to learn** — clear, readable syntax
- 🏢 **Commercial-ready** — Free and Pro licensing tiers

---

## Installation

```bash
pip install sprycode
```

Or from source:

```bash
git clone https://github.com/Cronikoff/Sprycode
cd Sprycode
pip install -e ".[dev]"
```

## Quick Start

```bash
# Create a new project
spry new app my-project
cd my-project

# Run the main task
spry run main.spry main

# Lint your code
spry lint .

# Build
spry build main.spry
```

## Hello World

```spry
app Hello version "1.0.0"

task main {
    log info "Hello from SpryCode!"
}
```

Run with:
```bash
spry run main.spry main
```

## Language Features

### Variables

```spry
let name = "SpryCode"      // immutable
var count = 0              // mutable
count = count + 1
```

### Functions

```spry
fn greet(name: Text) -> Text {
    return "Hello, " + name
}

fn double(x: Number) => x * 2    // short form
```

### Tasks (Workflows)

```spry
task backupReports {
    allow filesystem.read "./reports"
    allow filesystem.write "./backup"

    move folder "./reports" to "./backup/reports"
        parallel 8
        verify checksum sha256
        retry 3
}
```

### File Operations

```spry
// Read
let content = read file "./data.txt"

// Write
write file "./output.txt" with "hello world"

// Move with verification
move file "./input.pdf" to "./archive/input.pdf"
    verify checksum sha256
    preserve metadata

// Streaming pipeline
stream file "./users.csv"
    |> parse csv
    |> filter user => user.active == "true"
    |> map user => user.email
    |> write file "./active-emails.txt"
```

### Security Model

```spry
// Permissions must be declared
allow filesystem.read "./data"
allow filesystem.write "./output"
allow secret.read "API_KEY"

// Secrets are auto-redacted in logs
let key = secret "API_KEY"
log info key    // Prints: <secret:API_KEY>

// Privacy annotations
private data customerEmail: Email
sensitive data paymentToken: Secret
```

### Transactions

```spry
// Atomic block
atomic {
    move file "./in/payment.json" to "./processed/payment.json"
}

// Transaction with compensation
transaction db.bank {
    debit account "A" amount 50
    credit account "B" amount 50

    compensate {
        log warn "Rolling back transfer"
    }
}
```

### Error Handling

```spry
let result = read file "data.csv"

if result failed {
    log error result.error
    stop
}

// Or with try/catch
try {
    let data = read file "data.csv"
} catch err {
    log error err
}
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `spry run <file> [task]` | Run a program or task |
| `spry build <file>` | Build/check a program |
| `spry test [path]` | Run tests |
| `spry fmt [files]` | Format source files |
| `spry lint [files]` | Lint source files |
| `spry new app <name>` | Create a new project |
| `spry audit` | Audit dependencies |
| `spry --version` | Show version |

## File Extensions & Tooling

| Item | Value |
|------|-------|
| Source files | `.spry` |
| Package manifest | `spry.toml` |
| Lock file | `spry.lock` |
| CLI | `spry` |
| Package manager | `sprypm` |
| Compiler | `spryc` |
| Runtime | `spryrt` |

## Licensing

SpryCode is a closed-source commercial programming language platform:

| Feature | Free | Pro |
|---------|------|-----|
| Personal & learning use | ✓ | ✓ |
| Non-commercial deployment | ✓ | ✓ |
| Commercial deployment | ✗ | ✓ |
| Enterprise connectors | Limited | Full |
| Advanced optimization | ✗ | ✓ |
| Private registry | ✗ | ✓ |
| Priority support | ✗ | ✓ |
| Fraud verification workflows | ✗ | ✓ |
| Audit logging | Basic | Full |

## Documentation

- [Getting Started](docs/getting-started.md)
- [Syntax Guide](docs/syntax.md)
- [Security Model](docs/security.md)
- [Standard Library Reference](docs/stdlib-reference.md)

## Architecture

SpryCode is implemented in phases:

- **Phase 1** ✅ Language core (lexer, parser, interpreter, basic types, variables, functions, tasks)
- **Phase 2** ✅ Safety core (permission system, secret redaction, privacy annotations, logging)
- **Phase 3** ✅ Runtime core (transactions, atomic operations, file streaming, retry)
- **Phase 4** 🔄 Interop (adapters for SQL and REST)
- **Phase 5** 🔄 SpryControl (connector dashboard, audit logs, fraud verification)
- **Phase 6** 🔄 Licensing (Free/Pro license enforcement, offline grace)
- **Phase 7** 🔄 Optimization (compiler optimizations, parallel I/O, streaming)

---

*SpryCode: built for people who need to move quickly without sacrificing safety, privacy, reliability, or control.*
