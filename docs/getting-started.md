# Getting Started with SpryCode

SpryCode is a fast, reliable, adaptive programming language designed for file movement, data processing, transactions, and secure automation.

> SpryCode: agile code for fast, secure, adaptive systems.

## Installation

```bash
pip install sprycode
```

Or install from source:

```bash
git clone https://github.com/Cronikoff/Sprycode
cd Sprycode
pip install -e ".[dev]"
```

## Your First SpryCode Program

Create a file called `hello.spry`:

```spry
app Hello version "1.0.0"

task main {
    log info "Hello from SpryCode!"
}
```

Run it:

```bash
spry run main.spry main
```

Or use `spry new` to scaffold a project:

```bash
spry new app my-project
cd my-project
spry run main
```

## Core Concepts

### Variables

SpryCode variables are **immutable by default**:

```spry
let name = "SpryCode"
let version = "1.0.0"
```

Use `var` for mutable values:

```spry
var retries = 0
retries = retries + 1
```

### Types

SpryCode has a rich type system:

```spry
let username: Text = "alex"
let age: Number = 32
let active: Bool = true
let balance: Money = 249.99
```

Core types:
- `Text`, `Number`, `Int`, `Float`, `Bool`
- `Date`, `Time`, `DateTime`, `Duration`
- `File`, `Folder`, `Path`
- `Json`, `Xml`, `Binary`
- `Secret`, `Email`, `Url`, `Uuid`
- `Money`, `Transaction`, `Result`, `Option`
- `List`, `Map`, `Stream`, `Event`

### Functions

```spry
fn greet(name: Text) -> Text {
    return "Hello, " + name
}
```

Short form:

```spry
fn double(x: Number) => x * 2
```

### Tasks

Tasks are named executable workflows:

```spry
task backupReports {
    allow filesystem.read "./reports"
    allow filesystem.write "./backup"

    move folder "./reports" to "./backup/reports"
}
```

Run with:

```bash
spry run main.spry backupReports
```

### Error Handling

```spry
let result = read file "data.csv"

if result failed {
    log error result.error
    stop
}
```

Or with try/catch:

```spry
try {
    let data = read file "data.csv"
} catch err {
    log error err
}
```

## Security Model

SpryCode is **secure by default**. Programs must explicitly declare permissions:

```spry
allow filesystem.read "./data"
allow filesystem.write "./output"
allow network.request "https://api.example.com"
allow secret.read "PAYMENT_API_KEY"
```

Secrets are **always redacted** in logs:

```spry
let apiKey: Secret = secret "PAYMENT_API_KEY"
log info apiKey  // Prints: <secret:PAYMENT_API_KEY>
```

## CLI Reference

```bash
spry run <file> [task]     # Run a .spry file or task
spry build [file]          # Build/compile a .spry file
spry test [path]           # Run tests
spry fmt [files]           # Format source files
spry lint [files]          # Lint source files
spry new app <name>        # Create a new project
spry audit                 # Audit dependencies
```

## Next Steps

- [Syntax Guide](syntax.md) — Full language syntax reference
- [Security Model](security.md) — Permission system and secrets
- [File Operations Guide](file-operations.md) — Moving and processing files
- [Transactions Guide](transactions.md) — Safe data operations
- [Standard Library Reference](stdlib-reference.md) — Built-in functions
