# SSH Gateway Configuration

## OpenSSH forced-command setup

Add to `sshd_config`:

```sshconfig
Match User capsule-agent
    ForceCommand /usr/local/bin/capsule-ssh-gateway
    DisableForwarding yes
    PermitTTY yes
    X11Forwarding no
    PermitTunnel no
```

## How it works

1. User connects: `ssh capsule-agent@runtime-network`
2. sshd invokes `capsule-ssh-gateway` via ForceCommand
3. The gateway reads `$USER` to identify the SSH user
4. It resolves the SSH user to an agent registration (agent_id, capsule_hash, epoch)
5. It acquires an exclusive fenced wake lease
6. It selects a provider and materializes a runtime
7. It restores the capsule into the runtime
8. It attaches the SSH session to the runtime
9. When the session ends, the gateway collapses the agent:
   - Checks semantic quiescence
   - Seals the next capsule
   - Destroys the runtime
   - Verifies destruction
   - Releases the lease

## Key design points

- **ForceCommand ignores arbitrary client commands.** The client's requested
  command is available in `$SSH_ORIGINAL_COMMAND` for controlled interpretation.
- **DisableForwarding is required separately.** ForceCommand alone does not
  block port forwarding, agent forwarding, or X11 forwarding.
- **The SSH identity is stable.** The same `capsule-agent@runtime-network`
  address works regardless of which machine currently hosts the runtime.
- **The agent identity is separate from the SSH identity.** The gateway maps
  SSH users to agent registrations, allowing multiple agents per host.

## Current status

- `gateway/forced_command.py` — implemented and tested (demo step 10)
- SSH config — documented above, not yet deployed
- Real sshd integration — not yet demonstrated
