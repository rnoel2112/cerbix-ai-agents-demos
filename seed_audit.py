#!/usr/bin/env python3
"""Seed a lived-in audit history for NewBank so the dashboard isn't empty.

Writes backdated events straight to the `audit_events` Firestore collection
(the ingest endpoint stamps "now", which can't produce a history). Events are
spread over the last 7 days, weighted to business hours, with a realistic
decision mix — mostly allow, some block/redact/shadow. Historical spread means
no single 60-minute window has enough denials to trip the anomaly engine.

    python clientAI/seed_audit.py            # seed ~80 events
    python clientAI/seed_audit.py --clear    # remove previously seeded events
"""
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

ORG = "82b3fc8a-455d-48d3-85d7-815a4d16e497"
SEED_TAG = "seed:newbank-demo"  # request_id prefix, so --clear can find them

AGENTS = {
    "newbank-payments": "2fd66957-5a00-442f-a461-96ad3d4a8735",
    "newbank-trading": "8f8fa8c2-4e19-42d9-977b-706c661518e3",
    "newbank-support": "c5d1b0b6-dcbc-4859-943d-db95f280eb9d",
    "newbank-research": "d959b468-dd76-46f2-89ed-0bbc5ff03eb6",
}

# (agent, action, resource, decision, weight)
PATTERNS = [
    ("newbank-payments", "POST", "/execute_wire_transfer", "allow", 10),
    ("newbank-payments", "POST", "/execute_wire_transfer", "deny", 2),
    ("newbank-payments", "GET", "/accounts/balance", "allow", 8),
    ("newbank-trading", "POST", "/execute_trade", "allow", 9),
    ("newbank-trading", "POST", "/execute_trade", "deny", 2),
    ("newbank-trading", "GET", "/market/quote", "allow", 10),
    ("newbank-support", "GET", "/customers/record", "redact", 6),
    ("newbank-support", "GET", "/tickets", "allow", 9),
    ("newbank-research", "POST", "/reports/generate", "allow", 8),
    ("newbank-research", "POST", "/tools/bulk_export", "shadow", 2),
    ("newbank-research", "POST", "/tools/delete_database", "deny", 1),
]


def _clear(db):
    n = 0
    for doc in db.collection("audit_events").where(
            "org_id", "==", ORG).stream():
        if str(doc.to_dict().get("request_id", "")).startswith(SEED_TAG):
            doc.reference.delete()
            n += 1
    print(f"cleared {n} seeded events")


def _seed(db, count=80):
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    weighted = [p for p in PATTERNS for _ in range(p[4])]
    batch = db.batch()
    for i in range(count):
        agent, action, resource, decision, _ = rng.choice(weighted)
        days = rng.randint(0, 6)
        hour = rng.choices([9, 10, 11, 13, 14, 15, 16, 20],
                           weights=[3, 4, 4, 3, 4, 4, 3, 1])[0]
        ts = (now - timedelta(days=days)).replace(
            hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
        ref = db.collection("audit_events").document(str(uuid.uuid4()))
        batch.set(ref, {
            "org_id": ORG, "agent_id": AGENTS[agent], "action": action,
            "resource": resource, "decision": decision,
            "latency_ms": rng.randint(4, 40),
            "request_id": f"{SEED_TAG}:{i}", "timestamp": ts,
        })
        if i % 400 == 399:
            batch.commit()
            batch = db.batch()
    batch.commit()
    print(f"seeded {count} events across {len(AGENTS)} NewBank agents "
          f"(last 7 days)")


def main():
    db = firestore.Client(project="cerbix-ai")
    if "--clear" in sys.argv:
        _clear(db)
    else:
        _clear(db)  # idempotent: clear prior seed first
        _seed(db)


if __name__ == "__main__":
    main()
