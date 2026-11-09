# Demo Script & Caption (≤ 90 seconds)

## Suggested demo flow (≈ 70–80 detik)

1. **0–10s** — Hook  
   "Most agents forget everything when they restart. draction fixes that."

2. **10–25s** — Create  
   ```bash
   hermes draction create --file example-workflow.yaml
   ```
   Show the new action ID appear.

3. **25–40s** — Resume + current step  
   ```bash
   hermes draction resume <id>
   hermes draction status <id>
   ```
   Highlight the current step instruction.

4. **40–55s** — Human gate  
   Show status becoming `waiting_approval`.  
   Then:
   ```bash
   hermes draction approve <id> --note "looks good"
   ```

5. **55–70s** — Receipt / audit trail  
   ```bash
   hermes draction history <id>
   ```
   Point at the hash chain — every step is recorded and verifiable.

6. **70–80s** — Close  
   "Durable actions. Survive restarts. Human gates. Verifiable receipts.  
   That’s draction for Hermes."

---

## Caption untuk post X (copy-paste)

```
Durable actions for Hermes.

Most agents die when the process restarts.
draction keeps multi-step work alive with:
• checkpoints & resume
• human approval gates
• hash-chained receipts for audit

CLI + tools, pure local, zero telemetry.

Repo: https://github.com/petopen9-stack/draction

@NousResearch #HermesHackathon
```

---

## Tips rekaman
- Pakai terminal yang bersih + font besar
- Tunjukkin `hermes draction list` di akhir biar keliatan state-nya
- Kalau bisa, sekali tunjukkin tool call dari dalam chat Hermes juga (lebih powerful)
