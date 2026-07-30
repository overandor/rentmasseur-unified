# The Canonical Vision

## What was built

A capsule kernel with a cryptographic identity. The agent is not identified by a container name, a process number, an IP address, a cloud account, or whatever random machine happens to be running it. It has an Ed25519 identity and signed manifests. The agent's state can be verified independently of the machine storing or executing it.

Each state has an epoch. Each new capsule references its parent. The manifests are canonical. The workspace is content-addressed. If one byte changes, the evidence chain changes. If somebody modifies the manifest, corrupts a block, broadens the capabilities, attempts path traversal, or restores an older state after a newer state exists, the verifier rejects it.

The capsule carries lineage, identity, authority, and evidence. It is the agent's skeleton, passport, birth certificate, fingerprint, family tree, and evidence locker.

Authority is constitutional: typed operations, deny-by-default execution policy, policy receipts, execution receipts, and capability non-expansion. Migration may preserve authority or reduce it, but it may never silently increase it. The remote runtime verifies the owner's signature using the public key but cannot mint a new authoritative state.

## What remains

### Exclusive ownership
A durable lease system with generations and fencing tokens. Only the holder of the newest token can commit external effects, use sensitive capabilities, publish a new capsule, or advance the official epoch. An old runtime might remain physically alive briefly, but it becomes computationally unauthorized.

### Safe sleep
Real semantic quiescence. Every external effect needs a stable operation identity and a known state: committed, cancelled, or proven not started. If the status is unknown, the capsule cannot be sealed.

### Real embodiment
Turn the Apple adapter into a real container controller. Create a named isolated runtime, record its identity, CPU, memory, mount, network policy, start time. Execute. Stop and delete. Prove absence.

### Verified death
No agent process, container VM, leased execution resource, or active inference runtime remains. Only the capsule and the small wake-control service remain.

### Remote reincarnation
The capsule travels to a genuinely independent Linux host. Host B verifies the owner's signature and every content block. Restores the exact files and structured task state. Finishes the unfinished work. Returns changed blocks and a signed execution receipt. Host B does not possess the owner's private key.

### One stable door
The SSH address identifies the agent, not the machine. The gateway finds the latest capsule, acquires the authoritative lease, selects a provider, restores the agent, verifies its state, and attaches the session. When the session ends and the agent reaches quiescence, the runtime seals the next capsule and disappears.

### The decisive test
Start on M5 Pro → multi-step job → leave unfinished → quiesce → seal → destroy → prove absent → transport to independent Linux host → verify → restore → finish work → return signed receipt → owner verifies → seal next epoch → reconnect through same SSH identity → confirm complete.

### Attack your own system
Corrupt blocks, modify receipts, reuse old epochs, broaden capabilities, race two wake attempts, present stale fencing tokens, interrupt transport, fake test results, attempt rollback. The offline verifier must reject every broken chain.

### Publish metrics
Restore success rate, wake latency, transfer size, deduplication ratio, verification time, corruption detection, split-brain prevention, semantic-continuation success. Repeat dozens or hundreds of times.

## The claim

> We built a provider-neutral continuity kernel that detaches an agent's signed operational state from its execution machine, permits only one authoritative continuation, restores it on heterogeneous compute under attenuated authority, and proves the entire transition without trusting the destination machine.

Home is now whichever hardware the agent temporarily materializes on.
