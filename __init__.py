"""
draction — Durable Actions for Hermes

A plugin that turns ephemeral agent work into durable, resumable,
checkpointed workflows with human-approval gates and verifiable receipts.

This is the future of reliable personal agents.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir(ctx) -> Path:
    """Return the durable data directory for this plugin (survives updates)."""
    return Path(ctx.plugin_data_dir())


def _actions_path(ctx) -> Path:
    p = _data_dir(ctx) / "actions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _receipts_path(ctx) -> Path:
    p = _data_dir(ctx) / "receipts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_action(ctx, action_id: str) -> Optional[dict]:
    path = _actions_path(ctx) / f"{action_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_action(ctx, action: dict) -> None:
    path = _actions_path(ctx) / f"{action['id']}.json"
    path.write_text(json.dumps(action, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_receipt(action: dict, event: str, detail: dict | None = None) -> dict:
    """Create a simple verifiable receipt (hash of previous + new event)."""
    payload = {
        "action_id": action["id"],
        "event": event,
        "ts": _now(),
        "detail": detail or {},
        "prev_hash": action.get("last_hash", "genesis"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(raw.encode()).hexdigest()
    payload["hash"] = h
    return payload


def _append_receipt(ctx, action: dict, event: str, detail: dict | None = None) -> dict:
    receipt = _make_receipt(action, event, detail)
    action["last_hash"] = receipt["hash"]
    action.setdefault("receipts", []).append(receipt["hash"])
    # Persist receipt file
    rpath = _receipts_path(ctx) / f"{receipt['hash']}.json"
    rpath.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


# ---------------------------------------------------------------------------
# Core action model
# ---------------------------------------------------------------------------

def create_action(
    ctx,
    title: str,
    steps: list[dict],
    description: str = "",
    require_approval: bool = True,
    tags: list[str] | None = None,
) -> dict:
    """Create a new durable action definition."""
    action_id = str(uuid.uuid4())[:8]
    action = {
        "id": action_id,
        "title": title,
        "description": description,
        "status": "pending",          # pending | running | waiting_approval | paused | completed | failed | cancelled
        "require_approval": require_approval,
        "tags": tags or [],
        "created_at": _now(),
        "updated_at": _now(),
        "current_step": 0,
        "steps": steps,               # list of {"name": str, "instruction": str, "status": str, "result": any}
        "checkpoints": [],
        "receipts": [],
        "last_hash": "genesis",
        "meta": {},
    }
    _append_receipt(ctx, action, "created", {"title": title})
    _save_action(ctx, action)
    return action


# ---------------------------------------------------------------------------
# Tool implementations (exposed to the model)
# ---------------------------------------------------------------------------

def tool_create(ctx, title: str, steps: list[dict], description: str = "", require_approval: bool = True, tags: list[str] | None = None) -> dict:
    """
    Create a durable action.
    steps: list of objects with at least "name" and "instruction".
    """
    if not steps:
        return {"ok": False, "error": "At least one step is required"}
    for i, s in enumerate(steps):
        if "name" not in s or "instruction" not in s:
            return {"ok": False, "error": f"Step {i} must have 'name' and 'instruction'"}
        s.setdefault("status", "pending")
        s.setdefault("result", None)

    action = create_action(ctx, title, steps, description, require_approval, tags)
    return {
        "ok": True,
        "action_id": action["id"],
        "title": action["title"],
        "status": action["status"],
        "steps": len(action["steps"]),
        "message": f"Durable action '{action['id']}' created. Use draction_resume or the CLI to run it.",
    }


def tool_list(ctx, status: str | None = None, limit: int = 20) -> dict:
    """List durable actions, optionally filtered by status."""
    actions = []
    for p in sorted(_actions_path(ctx).glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        a = json.loads(p.read_text(encoding="utf-8"))
        if status and a.get("status") != status:
            continue
        actions.append({
            "id": a["id"],
            "title": a["title"],
            "status": a["status"],
            "current_step": a["current_step"],
            "total_steps": len(a["steps"]),
            "updated_at": a["updated_at"],
            "tags": a.get("tags", []),
        })
        if len(actions) >= limit:
            break
    return {"ok": True, "count": len(actions), "actions": actions}


def tool_status(ctx, action_id: str) -> dict:
    """Get full status of one action."""
    a = _load_action(ctx, action_id)
    if not a:
        return {"ok": False, "error": f"Action {action_id} not found"}
    return {
        "ok": True,
        "action": {
            "id": a["id"],
            "title": a["title"],
            "description": a.get("description", ""),
            "status": a["status"],
            "current_step": a["current_step"],
            "steps": a["steps"],
            "require_approval": a.get("require_approval", True),
            "created_at": a["created_at"],
            "updated_at": a["updated_at"],
            "last_hash": a.get("last_hash"),
            "tags": a.get("tags", []),
        },
    }


def tool_resume(ctx, action_id: str, note: str = "") -> dict:
    """
    Mark an action as running / continue from current step.
    The agent is expected to actually execute the current step's instruction
    and then call draction_approve or update via another tool later.
    """
    a = _load_action(ctx, action_id)
    if not a:
        return {"ok": False, "error": f"Action {action_id} not found"}

    if a["status"] in ("completed", "cancelled", "failed"):
        return {"ok": False, "error": f"Action is already {a['status']}"}

    if a["status"] == "waiting_approval":
        return {
            "ok": False,
            "error": "Action is waiting for human approval. Use draction_approve first.",
            "action_id": action_id,
        }

    a["status"] = "running"
    a["updated_at"] = _now()
    if note:
        a.setdefault("checkpoints", []).append({"ts": _now(), "note": note, "step": a["current_step"]})

    _append_receipt(ctx, a, "resumed", {"note": note, "step": a["current_step"]})
    _save_action(ctx, a)

    current = a["steps"][a["current_step"]] if a["current_step"] < len(a["steps"]) else None
    return {
        "ok": True,
        "action_id": action_id,
        "status": "running",
        "current_step": a["current_step"],
        "current_step_name": current["name"] if current else None,
        "instruction": current["instruction"] if current else None,
        "message": "Action is now running. Execute the current step, then call draction_approve or advance.",
    }


def tool_approve(ctx, action_id: str, result: Any = None, advance: bool = True, note: str = "") -> dict:
    """
    Record the result of the current step and optionally advance.
    If require_approval is True and this is a human gate, this is the approval signal.
    """
    a = _load_action(ctx, action_id)
    if not a:
        return {"ok": False, "error": f"Action {action_id} not found"}

    idx = a["current_step"]
    if idx >= len(a["steps"]):
        return {"ok": False, "error": "No more steps"}

    step = a["steps"][idx]
    step["status"] = "completed"
    step["result"] = result
    step["completed_at"] = _now()
    if note:
        step["note"] = note

    a["updated_at"] = _now()
    _append_receipt(ctx, a, "step_completed", {
        "step_index": idx,
        "step_name": step["name"],
        "note": note,
    })

    if advance:
        a["current_step"] = idx + 1
        if a["current_step"] >= len(a["steps"]):
            a["status"] = "completed"
            _append_receipt(ctx, a, "completed", {})
        else:
            # If the next step is marked as needing approval, go to waiting
            next_step = a["steps"][a["current_step"]]
            if next_step.get("needs_approval") or a.get("require_approval"):
                a["status"] = "waiting_approval"
            else:
                a["status"] = "running"

    _save_action(ctx, a)

    return {
        "ok": True,
        "action_id": action_id,
        "status": a["status"],
        "current_step": a["current_step"],
        "completed_step": step["name"],
        "message": f"Step '{step['name']}' recorded. Action status: {a['status']}",
    }


def tool_cancel(ctx, action_id: str, reason: str = "") -> dict:
    a = _load_action(ctx, action_id)
    if not a:
        return {"ok": False, "error": f"Action {action_id} not found"}
    if a["status"] in ("completed", "cancelled"):
        return {"ok": False, "error": f"Already {a['status']}"}

    a["status"] = "cancelled"
    a["updated_at"] = _now()
    a["cancel_reason"] = reason
    _append_receipt(ctx, a, "cancelled", {"reason": reason})
    _save_action(ctx, a)
    return {"ok": True, "action_id": action_id, "status": "cancelled"}


def tool_history(ctx, action_id: str) -> dict:
    a = _load_action(ctx, action_id)
    if not a:
        return {"ok": False, "error": f"Action {action_id} not found"}

    receipts = []
    for h in a.get("receipts", []):
        rpath = _receipts_path(ctx) / f"{h}.json"
        if rpath.exists():
            receipts.append(json.loads(rpath.read_text(encoding="utf-8")))

    return {
        "ok": True,
        "action_id": action_id,
        "title": a["title"],
        "status": a["status"],
        "receipts": receipts,
        "last_hash": a.get("last_hash"),
    }


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

def _cli_handler(args):
    """Entry point for `hermes draction ...`"""
    # Resolve the plugin data directory the same way Hermes does.
    # Fallback keeps the CLI usable even if internal helpers move.
    try:
        from hermes_cli.plugin_storage import plugin_data_dir  # type: ignore
        data_root = plugin_data_dir("draction")
    except Exception:
        data_root = Path.home() / ".hermes" / "plugin-data" / "draction"
        data_root.mkdir(parents=True, exist_ok=True)

    class FakeCtx:
        def plugin_data_dir(self):
            return str(data_root)

    ctx = FakeCtx()

    cmd = getattr(args, "draction_cmd", None)

    if cmd == "list":
        result = tool_list(ctx, status=getattr(args, "status", None), limit=getattr(args, "limit", 20))
        if not result["actions"]:
            print("No durable actions found.")
            return
        print(f"{'ID':<10} {'STATUS':<18} {'STEP':<8} TITLE")
        print("-" * 70)
        for a in result["actions"]:
            step = f"{a['current_step']}/{a['total_steps']}"
            print(f"{a['id']:<10} {a['status']:<18} {step:<8} {a['title']}")
        return

    if cmd == "status":
        aid = getattr(args, "action_id", None)
        if not aid:
            print("Usage: hermes draction status <action_id>")
            return
        result = tool_status(ctx, aid)
        if not result["ok"]:
            print(result["error"])
            return
        a = result["action"]
        print(f"ID:          {a['id']}")
        print(f"Title:       {a['title']}")
        print(f"Status:      {a['status']}")
        print(f"Step:        {a['current_step']} / {len(a['steps'])}")
        print(f"Created:     {a['created_at']}")
        print(f"Updated:     {a['updated_at']}")
        print(f"Last hash:   {a.get('last_hash', '')[:16]}…")
        print()
        for i, s in enumerate(a["steps"]):
            marker = "→" if i == a["current_step"] else " "
            print(f"  {marker} [{s['status']:<10}] {s['name']}")
            if s.get("result") is not None:
                print(f"               result: {str(s['result'])[:80]}")
        return

    if cmd == "create":
        # Minimal create from CLI (YAML file or interactive)
        title = getattr(args, "title", None) or "Untitled action"
        steps_file = getattr(args, "file", None)
        if steps_file:
            data = yaml.safe_load(Path(steps_file).read_text(encoding="utf-8"))
            steps = data.get("steps", data if isinstance(data, list) else [])
            title = data.get("title", title)
            desc = data.get("description", "")
        else:
            print("Interactive create not fully implemented in CLI yet.")
            print("Prefer using the agent tools or pass --file workflow.yaml")
            return

        result = tool_create(ctx, title=title, steps=steps, description=desc)
        if result["ok"]:
            print(f"Created durable action: {result['action_id']}")
            print(f"  Title : {result['title']}")
            print(f"  Steps : {result['steps']}")
        else:
            print("Error:", result.get("error"))
        return

    if cmd == "resume":
        aid = getattr(args, "action_id", None)
        if not aid:
            print("Usage: hermes draction resume <action_id>")
            return
        result = tool_resume(ctx, aid, note=getattr(args, "note", ""))
        print(json.dumps(result, indent=2))
        return

    if cmd == "approve":
        aid = getattr(args, "action_id", None)
        if not aid:
            print("Usage: hermes draction approve <action_id> [--note '...']")
            return
        result = tool_approve(ctx, aid, note=getattr(args, "note", ""), advance=True)
        print(json.dumps(result, indent=2))
        return

    if cmd == "cancel":
        aid = getattr(args, "action_id", None)
        if not aid:
            print("Usage: hermes draction cancel <action_id>")
            return
        result = tool_cancel(ctx, aid, reason=getattr(args, "reason", ""))
        print(json.dumps(result, indent=2))
        return

    if cmd == "history":
        aid = getattr(args, "action_id", None)
        if not aid:
            print("Usage: hermes draction history <action_id>")
            return
        result = tool_history(ctx, aid)
        if not result["ok"]:
            print(result["error"])
            return
        print(f"History for {result['action_id']} — {result['title']}")
        print(f"Status: {result['status']}  |  Last hash: {result.get('last_hash', '')[:20]}…")
        print()
        for r in result["receipts"]:
            print(f"  {r['ts']}  {r['event']:<18}  {r['hash'][:12]}…")
        return

    # default help
    print("""draction — Durable Actions for Hermes

Usage:
  hermes draction list [--status STATUS]
  hermes draction status <action_id>
  hermes draction create --title "..." --file workflow.yaml
  hermes draction resume <action_id>
  hermes draction approve <action_id> [--note "..."]
  hermes draction cancel <action_id>
  hermes draction history <action_id>

This plugin gives Hermes durable, resumable, checkpointed workflows
with human gates and verifiable receipts — the foundation for reliable
long-running personal agents.
""")


def _setup_argparse(subparser):
    """Build the argparse tree for `hermes draction`."""
    subs = subparser.add_subparsers(dest="draction_cmd")

    # list
    p_list = subs.add_parser("list", help="List durable actions")
    p_list.add_argument("--status", help="Filter by status")
    p_list.add_argument("--limit", type=int, default=20)

    # status
    p_status = subs.add_parser("status", help="Show detailed status of an action")
    p_status.add_argument("action_id")

    # create
    p_create = subs.add_parser("create", help="Create a durable action from a YAML file")
    p_create.add_argument("--title", default="Untitled")
    p_create.add_argument("--file", "-f", required=True, help="YAML file describing steps")

    # resume
    p_resume = subs.add_parser("resume", help="Resume / start an action")
    p_resume.add_argument("action_id")
    p_resume.add_argument("--note", default="")

    # approve
    p_approve = subs.add_parser("approve", help="Approve / complete current step")
    p_approve.add_argument("action_id")
    p_approve.add_argument("--note", default="")

    # cancel
    p_cancel = subs.add_parser("cancel", help="Cancel an action")
    p_cancel.add_argument("action_id")
    p_cancel.add_argument("--reason", default="")

    # history
    p_hist = subs.add_parser("history", help="Show receipt / audit history")
    p_hist.add_argument("action_id")

    subparser.set_defaults(func=_cli_handler)


# ---------------------------------------------------------------------------
# Plugin entrypoint
# ---------------------------------------------------------------------------

def register(ctx):
    """Called once by Hermes when the plugin is loaded."""

    # --- Tools the model can call ---
    ctx.register_tool(
        name="draction_create",
        description="Create a durable, resumable action with multiple steps. Use this when a task should survive restarts, need human approval gates, or produce an audit trail.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title of the action"},
                "description": {"type": "string", "description": "Optional longer description"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "instruction": {"type": "string"},
                            "needs_approval": {"type": "boolean"},
                        },
                        "required": ["name", "instruction"],
                    },
                    "description": "Ordered list of steps the agent (or human) will execute",
                },
                "require_approval": {"type": "boolean", "default": True},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "steps"],
        },
        handler=lambda **kw: tool_create(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_list",
        description="List existing durable actions, optionally filtered by status (pending, running, waiting_approval, completed, ...).",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
        handler=lambda **kw: tool_list(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_status",
        description="Get full status and step details of one durable action.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
            },
            "required": ["action_id"],
        },
        handler=lambda **kw: tool_status(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_resume",
        description="Start or resume a durable action. Returns the current step instruction that should be executed next.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["action_id"],
        },
        handler=lambda **kw: tool_resume(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_approve",
        description="Record the result of the current step and advance the action. Use after finishing a step or when a human has approved.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "result": {"description": "Any JSON-serializable result of the step"},
                "advance": {"type": "boolean", "default": True},
                "note": {"type": "string"},
            },
            "required": ["action_id"],
        },
        handler=lambda **kw: tool_approve(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_cancel",
        description="Cancel a durable action.",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["action_id"],
        },
        handler=lambda **kw: tool_cancel(ctx, **kw),
    )

    ctx.register_tool(
        name="draction_history",
        description="Return the full receipt / audit trail of a durable action (hashes form a simple chain).",
        parameters={
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
            },
            "required": ["action_id"],
        },
        handler=lambda **kw: tool_history(ctx, **kw),
    )

    # --- CLI subcommand tree ---
    ctx.register_cli_command(
        name="draction",
        help="Durable, resumable actions with checkpoints and verifiable receipts",
        setup_fn=_setup_argparse,
        handler_fn=_cli_handler,
    )

    # --- Optional: ship a skill that teaches the agent how to use this ---
    skill_dir = Path(__file__).parent / "skills" / "durable-actions"
    if skill_dir.exists():
        ctx.register_skill(
            name="durable-actions",
            path=str(skill_dir),
        )
