# draction — Durable Actions for Hermes

> Turn ephemeral agent runs into reliable, resumable, checkpointed workflows  
> with human-approval gates and verifiable receipts.

**Hackathon entry for the Hermes Agent Plugin Hackathon (Nov 2026)**

## Why this exists

Most AI agents today are ephemeral.  
A long-running research task, a multi-step content pipeline, or anything that needs a human checkpoint is lost the moment the process dies or the machine reboots.

**draction** brings *durable execution* to personal agents:

- Actions survive restarts
- Explicit human gates (`waiting_approval`)
- Checkpoint + resume at any step
- Simple hash-chained receipts for audit / provenance
- Both **tools** (for the model) and a full **CLI** (`hermes draction ...`)

This is the foundation for the next generation of reliable personal agents — closer to Temporal / durable workflows than to chatbots.

## Quick start

```bash
# After the plugin is installed & enabled
hermes draction list
hermes draction create --file example-workflow.yaml
hermes draction status <id>
hermes draction resume <id>
hermes draction approve <id>
hermes draction history <id>
```

The same capabilities are available to the agent via tools:

- `draction_create`
- `draction_list`
- `draction_status`
- `draction_resume`
- `draction_approve`
- `draction_cancel`
- `draction_history`

## Example workflow file

```yaml
title: Weekly research digest
description: Collect, summarize, human-review, then publish
steps:
  - name: gather
    instruction: Search and collect the top relevant items from the last 7 days
  - name: summarize
    instruction: Write a concise bullet-point summary for each item
  - name: human-review
    instruction: Wait for human approval of the draft digest
    needs_approval: true
  - name: publish
    instruction: Post the approved digest to the configured channel
```

## Architecture (v0.1)

- Pure local storage under the plugin data directory (survives plugin updates)
- JSON action documents + individual receipt files
- SHA-256 hash chain for a simple verifiable audit trail
- Zero external dependencies beyond PyYAML
- No network calls, no telemetry

## Design principles

1. **Durability first** — state must survive process death
2. **Human gates are first-class** — not an afterthought
3. **Auditability** — every important transition produces a receipt
4. **Minimal surface** — easy to understand, easy to extend later
5. **Agent + human** — both the model and the CLI user can drive the same actions

## Future directions (post-hackathon)

- Parallel steps / DAG support
- Time-based triggers & cron integration
- Signed receipts with user keys
- Export to OpenTelemetry / external audit stores
- Multi-agent hand-off of a single durable action
- Desktop pane showing live action boards

## Installation (for reviewers)

```bash
# From a local checkout
hermes plugins install /path/to/draction --no-enable
hermes plugins enable draction

# Or once accepted into the catalog
hermes plugins install draction
```

Validate locally:

```bash
hermes plugins validate /path/to/draction --install-deps
hermes plugins doctor draction
```

## License

MIT

---

Built for the Hermes Agent Plugin Hackathon.  
GLHF.
