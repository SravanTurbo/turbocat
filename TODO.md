# Known Debt

Items below are accepted trade-offs at pilot stage. Revisit as client count grows.

---

## Scheduling reliability — APScheduler single-pod

APScheduler runs in-process with the FastAPI app. If the orchestrator pod crashes between a cron tick and job enqueue, that run is silently skipped. For sub-hourly syncs this is acceptable; for daily syncs a missed run matters.

**Options when this becomes painful:**
- Switch APScheduler jobstore to Postgres (`APScheduler[sqlalchemy]`) — schedules survive pod restarts and two pods won't double-fire.
- Evaluate Prefect if we need full retry, backfill, and observability UI.

**Threshold:** address before going beyond ~10 clients or before any pipeline moves to once-daily or less frequent schedules.

---

## No explicit job retry policy

Failed `job_run` rows stay `FAILED`. Recovery happens indirectly via the `lookback_days` overlap on the next scheduled run. Users will notice missing data before we notice the failure.

**What's needed:**
- A `retry_count` / `max_retries` column on `job_runs`.
- A scheduler check: if `status = FAILED` and `retry_count < max_retries`, re-enqueue with backoff.
- Or use APScheduler's built-in `misfire_grace_time` + a retry job.

**Threshold:** address before the first client with an SLA or before adding a job history UI.

---

## No backfill story

There is no way to re-run a pipeline for a specific historical time window. If a connector fails for a day and is fixed, the gap is partially covered by `lookback_days` overlap but not fully replayed.

**What's needed:**
- A `POST /pipelines/{id}/backfill` endpoint that accepts `start_time` / `end_time` and enqueues a one-off job with those bounds.
- Agent executor already supports explicit `start_time` / `end_time` — the orchestrator side is what's missing.

**Threshold:** address when the first client asks "can you re-pull last month's data."

---

## `job_runs` has no record of input/output state

`pipeline.state` is overwritten on each successful run. There is no per-run record of what cursor the job received or what cursor it produced. Debugging a wrong time window requires reading git history or guessing.

**What's needed:**
- Add `input_state JSONB` and `output_state JSONB` columns to `job_runs`.
- Orchestrator writes `input_state` when building the `JobPayload`; agent reports `output_state` (already sent as `next_state` in the status update).

**Threshold:** low effort, do it the next time migrations are being written anyway.

---

## Secrets Manager call on every job poll (O(n) per cycle)

`get_pending_jobs` calls `get_secret()` once per job in the response. At 5 pipelines per client × 10 clients = 50 Secrets Manager calls per poll cycle. SM has a rate limit of 10,000 requests/second per region — not an immediate concern, but cost and latency add up.

**Options:**
- Cache decrypted credentials in-process for a short TTL (60s). Acceptable since credentials are long-lived API keys, not short-lived tokens.
- Or fetch the secret once per connection (not per job) and pass it through.

**Threshold:** address before 50+ active pipelines across all clients, or if SM costs become visible on the bill.
