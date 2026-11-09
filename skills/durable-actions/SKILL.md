---
name: durable-actions
description: How to create and manage durable, resumable, checkpointed actions with human gates and verifiable receipts using the draction plugin.
---

# Durable Actions

Use the **draction** tools whenever a task should:

- Survive Hermes restarts or machine reboots
- Contain explicit human approval gates
- Produce an audit trail / verifiable receipt chain
- Be pauseable and resumable days later

## When to use

Good candidates:
- Multi-day research or content pipelines
- Any workflow that needs a human to approve a risky step
- Long-running local automation that must not be lost
- Tasks you may want to audit later ("what exactly did the agent do?")

Bad candidates:
- One-shot questions
- Purely conversational replies

## Typical flow

1. **Create** the action with clear steps:
   ```
   draction_create(
     title="Prepare weekly research digest",
     steps=[
       {"name": "gather", "instruction": "Search and collect the top 10 papers/articles on X this week"},
       {"name": "summarize", "instruction": "Write a concise summary of each item"},
       {"name": "review", "instruction": "Human reviews the digest before sending", "needs_approval": true},
       {"name": "publish", "instruction": "Post the approved digest to the target channel"}
     ],
     require_approval=true
   )
   ```

2. **Resume** when you (or the agent) are ready to work on it:
   ```
   draction_resume(action_id="...")
   ```
   This returns the current step instruction.

3. Execute the instruction (using other tools, browsing, etc.).

4. **Approve / record result** and advance:
   ```
   draction_approve(action_id="...", result={...}, note="optional note")
   ```

5. If the next step has `needs_approval` or the action was created with `require_approval=true`, status becomes `waiting_approval`. A human (or another agent session) must call `draction_approve` again.

6. Inspect progress anytime:
   ```
   draction_status(action_id="...")
   draction_history(action_id="...")   # full receipt chain
   draction_list(status="waiting_approval")
   ```

## CLI equivalents

Everything is also available from the terminal:

```bash
hermes draction list
hermes draction status <id>
hermes draction resume <id>
hermes draction approve <id>
hermes draction history <id>
hermes draction create --file workflow.yaml
```

## Design notes

- Each significant event produces a receipt whose hash chains to the previous one. This gives a simple, local, verifiable audit trail.
- State lives in the plugin data directory and survives `hermes plugins update`.
- The plugin deliberately stays minimal: no external database, no network calls, pure local durability.

Prefer durable actions for anything that matters beyond the current session.
