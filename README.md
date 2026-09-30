# Service Health Probe

Release 1.0 within its documented scope. See [release and operating notes](RELEASE.md).
A small Python operations tool that distinguishes a reachable server from a working application. It checks status and optional response content, retries transient failures within fixed limits, and writes a JSON report with attempt timings. Exit codes make it usable in a shell or CI.

## Two concrete cases
- `/ready` responds 200 with the expected text: healthy after one attempt.
- `/broken` responds 503: two attempts are recorded, then the target is unhealthy. A 200 login page lacking the expected marker is also unhealthy.

## Run (Python 3.11+, no packages required)
```bash
python -m unittest discover -s tests -v
python demo.py
# With Inventory Reservation Lab running on port 8004:
python probe.py example-config.json --output health-report.json
```
The demo uses only a temporary localhost server, with one healthy and one deliberately failing endpoint. See results/demo.json. Timings are observations from this run, not an SLA or a performance promise. Use only endpoints you own or are authorized to probe; keep credentials and personal data out of the config.

## Design
At most 20 targets, four worker threads, 1–5 attempts, a per-operation socket timeout capped at 30 seconds, response cap 64 KiB, and exponential retry delays. Redirects are not followed. Only network failures and 5xx responses are retried. HTTP error response objects are closed. No response bodies or exception details are written to the report. URLs with embedded credentials, queries, or fragments are rejected.

This is a one-shot probe, not a monitoring platform. A socket timeout is not a strict overall deadline: DNS and slow trickle responses can exceed it. It cannot establish long-term uptime, diagnose a root cause, handle authenticated checks, or repair a service. Public deployment would require an explicit destination allowlist to prevent misuse against internal services. No alert messages or external services are used by the demo.

## Why it belongs in a student portfolio
Demonstrates HTTP troubleshooting, bounded retries, concurrent work, machine-readable evidence, and meaningful failure tests. Read STUDENT_GUIDE.md before claiming individual contributions. AI-assisted initial implementation; no production use or customer impact claimed.
