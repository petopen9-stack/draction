# Pull Request Body (copy-paste ke PR catalog)

**Title saran:**
```
Add draction — durable, resumable actions with human gates & verifiable receipts
```

---

## PR Body

```markdown
## Summary

Adds **draction** to the plugin catalog.

`draction` gives Hermes durable, resumable, checkpointed actions with first-class human-approval gates and a simple hash-chained receipt trail. It is aimed at long-running or multi-day work that must survive restarts and remain auditable.

## What the plugin does

- **CLI**: `hermes draction list | status | create | resume | approve | cancel | history`
- **Tools** (model-callable):
  - `draction_create`
  - `draction_list`
  - `draction_status`
  - `draction_resume`
  - `draction_approve`
  - `draction_cancel`
  - `draction_history`
- **Skill**: ships `durable-actions` that teaches the agent when and how to use the tools
- **State**: pure local JSON under the plugin data directory (survives `hermes plugins update`)
- **Receipts**: every significant transition produces a SHA-256 receipt that chains to the previous one

## Surfaces used

- `ctx.register_tool` (7 tools)
- `ctx.register_cli_command`
- `ctx.register_skill`
- `ctx.plugin_data_dir()` for durable storage

No privileged capabilities, no network calls, no telemetry, no core overrides.

## Disclosure

- All state is local (plugin data directory only).
- No external services, no credentials required, no environment variables.
- No background processes or long-running daemons.
- Receipts are plain JSON + SHA-256; they are not cryptographically signed with a user key (future work).

## Validation

```bash
hermes plugins validate . --install-deps
hermes plugins doctor draction
```

(Pin is the commit that contains the full `__init__.py` implementation.)

## Links

- Repository: https://github.com/petopen9-stack/draction
- Pinned commit: a7be73edd3a2e9c35bc4f20751e5f8bde0069baf
- Example workflow: `example-workflow.yaml` in the repo

## Demo

Demo video will be posted on X tagging @NousResearch (link to be added after recording).
```

---

Setelah PR dibuka, tempel juga link PR-nya di form submission + di caption video.
