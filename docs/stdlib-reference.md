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
orch.addManagedStep(                             // per-step microservice loop until solved
    "stabilize",
    fn(state, cycle, name, attempt) => state + 1,
    fn(state, cycle, name, attempt) => state >= 3,
    5
)
orch.setManagedStep(                             // promote/update one existing step as managed
    "shape",
    fn(state, cycle, name, attempt) => attempt >= 2,
    5
)
orch.setUnmanagedStep("shape")                   // revert one step back to single-pass behavior
orch.loadRegistryManaged(                        // load all registry services as managed steps
    reg,
    fn(state, cycle, name, attempt) => attempt >= 2,
    5
)
orch.disableStep("shape")                        // skip a step without removing it
orch.enableStep("shape")                         // re-enable a previously disabled step
let isEnabled = orch.isStepEnabled("shape")      // true / false
let cfg = orch.getStepConfig("shape")            // { name, managed, maxLoops, enabled }
// Step priority / ordering
let idx = orch.getStepIndex("shape")             // 0-based index, -1 if not found
orch.moveStepFirst("shape")                      // move to position 0 (highest priority)
orch.moveStepLast("shape")                       // move to last position (lowest priority)
orch.moveStepBefore("shape", "emit")             // move shape immediately before emit
orch.moveStepAfter("shape", "ingest")            // move shape immediately after ingest
let stepNames = orch.stepNames
let stepCount = orch.stepCount
let enabledNames = orch.enabledStepNames         // names of only enabled steps
let enabledCount = orch.enabledStepCount         // number of enabled steps
// After runManaged or runCycle, inspect loop convergence history
let attempts = orch.lastCycleAttempts           // { "ingest": 2, "shape": 1, ... }
let history = orch.cycleHistory                 // [ { ...cycle1... }, { ...cycle2... }, ... ]
let totals = orch.stepAttemptTotals             // { "ingest": 6, "shape": 3, ... }
let peaks = orch.stepAttemptPeaks               // { "ingest": 3, "shape": 1, ... }
let counts = orch.stepCycleCounts               // { "ingest": 3, "shape": 3, ... }
let avgs = orch.stepAttemptAverages             // { "ingest": 2.0, "shape": 1.0, ... }
let util = orch.stepLoopUtilization             // managed steps: avgAttempts/maxLoops
let room = orch.stepLoopHeadroom                // managed steps: maxLoops-avgAttempts
let path = orch.stepPressurePath                // managed steps ordered by loop pressure (high -> low)
let lead = orch.primaryBottleneck               // first step in path, or undefined when no managed history
let stages = orch.stepCapabilityStages          // managed steps mapped to capability stage: critical/stretched/stabilizing/mature
let maturity = orch.pathwayCapabilityMaturity   // { managedSteps, critical, stretched, stabilizing, mature, avgUtilization, maturity }
let capPath = orch.capabilityPathway            // managed steps ordered by capability pathway priority
let nextCap = orch.nextCapabilityTarget         // first non-mature managed step on capability pathway, or undefined
let remainCap = orch.capabilityRemainingTargets // non-mature managed steps in capability pathway order
let fully = orch.capabilityFullyDeveloped       // true when all active managed steps are mature, else false/undefined
let developed = orch.runCapabilityUntilDeveloped(initialState, 20) // run cycles until capability pathway is fully developed
let targeted = orch.runTargetUntilMature("ingest", initialState, 10) // micro-manage one managed target until mature
let nextDone = orch.runNextCapabilityTarget(initialState, 10) // micro-manage the next capability target until mature
let pathDone = orch.runCapabilityPathwayManaged(initialState, 10) // iterate capability targets in pathway order until mature
let pathReport = orch.runCapabilityPathwayManagedReport(initialState, 10) // detailed target-by-target pathway micromanagement report
let svcLoops = pathReport["serviceLoops"]         // [ { name, attempts, cycles, avgAttempts, peakAttempts, stage, mature }, ... ] for active managed services
let targetSvcLoops = pathReport["targets"][0]["serviceLoops"] // per-target service loop breakdown: [ { name, attempts, cycles, avgAttempts, peakAttempts }, ... ]
let targetRemain = pathReport["targets"][0]["remainingTargetsAfter"] // pathway targets still not mature after this target run
let targetFully = pathReport["targets"][0]["fullyDevelopedAfter"] // true when pathway is fully developed after this target run
let cycles = orch.totalCycles                   // total completed cycles
let full = orch.summary                         // [ { name, managed, maxLoops, enabled, totalAttempts, peakAttempts, minAttempts, cycleCounts, avgAttempts, loopUtilization, loopHeadroom, loopPressureRank, loopCapabilityStage, capabilityProgress, capabilityPathRank }, ... ]
let stepSum = orch.getStepSummary("ingest")     // same shape as summary entry, or undefined if not found
orch.resetHistory()                             // reset attempts + timeline + aggregates + cycle counter
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
