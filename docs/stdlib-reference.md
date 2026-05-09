# SpryCode Standard Library Reference

## Filesystem

### Reading

```spry
let result = read file "./data.txt"
// result.ok    -> Bool
// result.value -> Text (file contents)
// result.error -> Text (error message if failed)
```

### Writing

```spry
write file "./output.txt" with "hello world"
write file "./data.json" with { key: "value" }
```

### Copying

```spry
copy file "./source.txt" to "./dest.txt"
copy file "./source.txt" to "./dest.txt"
    verify checksum sha256
    preserve metadata
```

### Moving

```spry
move file "./input.txt" to "./archive/input.txt"
move file "./report.pdf" to "./archive/report.pdf"
    verify checksum sha256
    preserve metadata
    retry 3

move folder "./data" to "./backup"
    parallel 8
    verify checksum sha256
    retry 3
```

### Deleting

```spry
delete file "./temp.txt"
delete folder "./temp-dir"
```

### Watching

```spry
watch folder "./incoming"
```

### Streaming

```spry
stream file "./large.csv"
    |> parse csv
    |> filter row => row.active == "true"
    |> write file "./active.csv"

stream folder "./media"
    |> filter file => file.extension == "jpg"
    |> each file => log info file.name
```

### Syncing

```spry
sync folder "./local" with "./backup"
    mode mirror
    compare checksum
    encrypt true
```

---

## Data Parsing

```spry
// JSON
let data = parse json raw.value
let encoded = encode json data

// CSV
let rows = parse csv raw.value

// Checksum
let hash = checksum "./file.pdf"              // sha256 by default
let md5 = checksum "./file.pdf" "md5"

// Hashing (text)
let textHash = hash "my text"
```

---

## Time

```spry
let timestamp = now()          // ISO 8601 datetime string
let date = today()             // ISO 8601 date string
```

---

## Math

```spry
abs(-5)         // 5
min(3, 7)       // 3
max(3, 7)       // 7
round(3.7)      // 4
```

---

## String Utilities

```spry
let s = "Hello, World"
let n = len(s)          // 13
let upper = s.upper     // "HELLO, WORLD"
let lower = s.lower     // "hello, world"
let trimmed = s.trim    // Trimmed whitespace
```

---

## Collections

```spry
let items = [1, 2, 3, 4, 5]
let count = len(items)      // 5
let first = items[0]        // 1
let last = items[4]         // 5
```

### Microservice Coordination

```spry
let q = Queue()
q.enqueue("job-1")
let next = q.dequeue()

let ch = Channel()
ch.send({ id: 1 })
let msg = ch.receive()

let cb = CircuitBreaker(3, 1000)
let result = retry((attempt) => cb.execute(() => callService(attempt)), 5)

let throttled = throttle(() => pollHealth(), 500)
let debounced = debounce(() => refreshDashboard(), 200)

let solved = micromanage(
    (attempt) => runPipelineStep(attempt),
    (lastResult) => lastResult.done,
    100
)

// EventBus — pub/sub for decoupled microservice communication
let bus = EventBus.new()
bus.subscribe("order.created", fn(order) { processOrder(order) })
bus.publish("order.created", { id: 42 })
let n = bus.subscriberCount("order.created")   // 1
bus.unsubscribe("order.created", handler)
bus.clear()                                     // remove all subscribers

// Supervisor — manages and restarts failing services
let sv = Supervisor.new(3)                       // up to 3 restarts per service
sv.watch("auth", fn() { authService() })
sv.watch("data", fn() { dataService() })
sv.start()
let rc = sv.restartCount
let statuses = sv.status                         // { auth: "stopped", data: "failed" }

// WorkerPool — drain a task queue through a worker function
let pool = WorkerPool.new(fn(item) => item * 2)
pool.submit(1)
pool.submit(2)
pool.submit(3)
pool.run()                                       // processes all pending items
let results = pool.results                       // [2, 4, 6]
let errors  = pool.errors                        // []
let pending = pool.pending                       // 0
pool.reset()                                     // clear results + errors + queue

// ServiceRegistry — register and resolve named services
let reg = ServiceRegistry.new()
reg.register("ingest", fn(state, cycle) => state + 1)
reg.register("shape", fn(state) => state * 2)
let svcNames = reg.names
let count = reg.size
let out = reg.call("ingest", 41, 1)              // 42
let converged = reg.runUntilSolved(
    "ingest",
    fn(state, attempt, name) => state >= 10,
    0,
    100
)

// Orchestrator — loop service steps by cycle until solved
let orch = Orchestrator.new()
orch.loadRegistry(reg)                           // adds all registered services as steps
let final = orch.runUntilSolved(
    fn(state, cycle) => state >= 10,
    0,
    100
)
let finalManaged = orch.runManaged(              // alias for managed structural pathway loops
    fn(state, cycle) => state >= 20,
    0,
    100
)
let stepNames = orch.stepNames
let stepCount = orch.stepCount
```

---

## Identity

```spry
let id = uuid()    // "550e8400-e29b-41d4-a716-446655440000"
```

---

## Network (with permission)

```spry
allow network.request "https://api.example.com"

let response = http.get "https://api.example.com/users"
// response.ok     -> Bool
// response.value  -> { status: 200, body: "..." }

let response = http.post "https://api.example.com/data" with {
    key: "value"
}
```

---

## Logging

```spry
log info "Operation started"
log warn "Retrying..."
log error "Fatal: cannot continue"
log error err       // SpryResult.error is formatted automatically
```

All secrets and `private data` fields are automatically redacted.

---

## Secrets

```spry
allow secret.read "MY_SECRET"
let apiKey = secret "MY_SECRET"
// Prints as: <secret:MY_SECRET> in logs
```

---

## Money

```spry
let price: Money = 99.99
let tax = price * 0.20
let total = price + tax
let sum = money.sum([price, tax])
```

---

## Result Type

```spry
let result = read file "./data.txt"

if result failed {
    log error result.error
    stop
}

let content = result.value    // Only available when ok
```

---

## Encoding

```spry
let json = encode "json" myObject
let b64 = encode "base64" "hello world"
let decoded = decode "base64" b64Data
```

---

## Redaction

```spry
let safe = redact payment fields ["cardNumber", "cvv", "ssn"]
```

---

## Validation

```spry
validate data using MySchema
```
