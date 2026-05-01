# SpryCode Syntax Guide

## Comments

```spry
// Single-line comment

/*
  Multi-line comment
*/
```

## Variables

### Immutable (let)

```spry
let name = "SpryCode"
let count = 42
let active = true
let ratio = 3.14
```

### Mutable (var)

```spry
var retries = 0
retries = retries + 1
```

### Type Annotations

```spry
let username: Text = "alex"
let age: Number = 32
let active: Bool = true
let balance: Money = 249.99
```

## Types

| Type | Description | Example |
|------|-------------|---------|
| `Text` | String value | `"hello"` |
| `Number` | Numeric value (int or float) | `42`, `3.14` |
| `Int` | Integer | `42` |
| `Float` | Floating-point | `3.14` |
| `Bool` | Boolean | `true`, `false` |
| `Date` | Calendar date | `today()` |
| `DateTime` | Date and time | `now()` |
| `File` | File reference | `SpryFile` |
| `Folder` | Folder reference | `SpryFolder` |
| `Json` | JSON value | `{}` |
| `Secret` | Redacted secret | `secret "KEY"` |
| `Money` | Monetary value | `249.99` |
| `Result` | Success or failure | `ok` / `failed` |

## Operators

### Arithmetic
```spry
let sum = a + b
let diff = a - b
let product = a * b
let quotient = a / b
let remainder = a % b
```

### Comparison
```spry
a == b    // equal
a != b    // not equal
a < b     // less than
a > b     // greater than
a <= b    // less than or equal
a >= b    // greater than or equal
```

### Logical
```spry
a && b    // and
a || b    // or
!a        // not
not a     // not (keyword form)
```

### Pipeline
```spry
value |> operation
```

## Functions

### Full Form
```spry
fn greet(name: Text) -> Text {
    return "Hello, " + name
}
```

### Short Form (Expression)
```spry
fn double(x: Number) => x * 2
```

### Calling Functions
```spry
let result = greet("World")
let doubled = double(21)
```

## Tasks

Tasks are named executable workflows:

```spry
task processData {
    allow filesystem.read "./data"
    allow filesystem.write "./output"

    let data = read file "./data/input.txt"
    write file "./output/result.txt" with data.value
}
```

## Permissions

Every sensitive operation requires explicit permission:

```spry
allow filesystem.read "./data"
allow filesystem.write "./output"
allow network.request "https://api.example.com"
allow secret.read "API_KEY"
deny network.all
```

## Control Flow

### If/Else
```spry
if condition {
    // true branch
} else {
    // false branch
}
```

### Try/Catch
```spry
try {
    let result = read file "missing.txt"
} catch err {
    log error err
}
```

### Stop
```spry
if result failed {
    log error result.error
    stop
}
```

## File Operations

```spry
// Read
let content = read file "./data.txt"

// Write
write file "./output.txt" with "hello world"

// Copy
copy file "./source.txt" to "./dest.txt"

// Move
move file "./input.txt" to "./archive/input.txt"
    verify checksum sha256
    preserve metadata

// Delete
delete file "./temp.txt"

// Move folder
move folder "./data" to "./backup"
    parallel 8
    retry 3

// Sync
sync folder "./local" with "./backup"
    mode mirror
```

## Pipelines

```spry
read file "users.csv"
    |> parse csv
    |> filter user => user.active == "true"
    |> map user => user.email
    |> write file "active-emails.txt"
```

## Transactions

```spry
// Atomic block
atomic {
    move file "./in/payment.json" to "./processed/payment.json"
}

// Transaction with compensation
transaction filesystem {
    copy file "./contract.pdf" to "./archive/contract.pdf"
    write file "./archive/contract.meta.json" with { archivedAt: now() }

    compensate {
        log warn "Rolling back — compensation would run here"
    }
}
```

## Objects and Arrays

```spry
// Object literal
let user = {
    name: "Alice",
    age: 30,
    active: true
}

// Array literal
let tags = ["fast", "secure", "reliable"]

// Access
let name = user.name
let first = tags[0]
```

## Privacy Annotations

```spry
private data email: Email
sensitive data token: Secret
```

Rules:
- `private` data is redacted in logs
- `sensitive` data cannot leave local scope without explicit permission

## Logging

```spry
log info "Task started"
log warn "Retrying operation"
log error "Something went wrong"
log error err    // Error objects are formatted automatically
```

Secrets are always redacted in log output.

## Secrets

```spry
allow secret.read "API_KEY"
let key = secret "API_KEY"
log info key    // Prints: <secret:API_KEY>
```

## Connectors

```spry
connector paymentGateway {
    allow network.request "https://api.stripe.com"
    allow secret.read "STRIPE_API_KEY"
}
```

## Adapters

```spry
use adapter python

adapter pyScript sandboxed {
    allow filesystem.read "./scripts"
    deny network.all
}
```

## Fraud Check (Pro Feature)

```spry
fraud check transaction tx_12345 {
    reason "technical verification of duplicate payment signal"
    case "CASE-2026-0001"
    scope minimal
    redact personalData
}
```

## Built-in Functions

```spry
uuid()              // Generate UUID
now()               // Current datetime
today()             // Current date
len(value)          // Length of string or list
str(value)          // Convert to string
int(value)          // Convert to integer
float(value)        // Convert to float
abs(number)         // Absolute value
min(a, b)           // Minimum
max(a, b)           // Maximum
round(number)       // Round to nearest integer
encode("json", val) // Encode as JSON string
parse("json", text) // Parse JSON string
parse("csv", text)  // Parse CSV text
hash(text)          // SHA-256 hash of text
checksum(path)      // SHA-256 checksum of file
```
