# SPDX-License-Identifier: GPL-2.0-only
"""Original external-debugger bookkeeping; never native qualification.

The live set spans successful allocator return to normal free return. These
observed boundaries are not the allocator's internal commit/release points.
Requested bytes are not physical pool charges; neither is renamed here.
"""
import argparse
import json
import re
from pathlib import Path


def u32(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError("explicit uint32 required")
    return value


def owner_claim(value):
    if not isinstance(value, dict) or value.get("kind") == "unknown":
        return "unknown", None
    if value.get("kind") not in ("storage", "other") or not re.fullmatch(
            r"[0-9a-f]{64}", str(value.get("evidence_sha256"))):
        return "unknown", "unbound-owner-claim"
    return value["kind"], None


def identity(entry):
    extra = 16 if entry["call"] == "allocate" else 12
    expected = u32(entry["entry_esp"]) + extra
    if expected >= 2**32:
        raise ValueError("return ESP overflows")
    return u32(entry["thread"]), u32(entry["caller_pc"]), expected


class ReturnMatcher:
    """Exact thread/caller-PC/post-stdcall-ESP matching, not stack unwinding."""
    def __init__(self, limit=4096):
        self.pending = {}
        self.limit = limit

    def enter(self, entry):
        key = identity(entry)
        if key in self.pending:
            raise ValueError("ambiguous return identity")
        if len(self.pending) >= self.limit:
            raise ValueError("pending-call capacity exceeded")
        self.pending[key] = entry
        return key

    def returned(self, thread, pc, esp):
        return self.pending.pop((u32(thread), u32(pc), u32(esp)), None)


def analyze(events):
    issues, pending, seen_ids, live = [], {}, set(), {}
    observed = dict(successful_allocations=0, failed_allocations=0, completed_frees=0,
                    unknown_owner_successful_allocations=0,
                    declared_storage_successful_allocations=0,
                    current_requested_bytes=0, peak_requested_bytes=0,
                    declared_storage_current_requested_bytes=0,
                    declared_storage_peak_requested_bytes=0)
    service, start_seen, end_seen, baseline_complete = [], False, False, False
    consumed = 0
    ambiguous_ids = set()

    def issue(code, seq=None, detail=None):
        issues.append(dict(code=code, seq=seq, detail=detail))

    def refresh():
        observed["current_requested_bytes"] = sum(item["requested_bytes"] for item in live.values())
        observed["declared_storage_current_requested_bytes"] = sum(
            item["requested_bytes"] for item in live.values() if item["owner"] == "storage")
        for current, peak in (("current_requested_bytes", "peak_requested_bytes"),
                              ("declared_storage_current_requested_bytes", "declared_storage_peak_requested_bytes")):
            observed[peak] = max(observed[peak], observed[current])

    for index, event in enumerate(events):
        consumed += 1
        if not isinstance(event, dict):
            issue("malformed-event", index)
            continue
        seq = event.get("seq")
        if type(seq) is not int or seq != index:
            issue("sequence-gap-or-duplicate", seq)
        if end_seen:
            issue("event-after-end", seq)
            continue
        kind = event.get("kind")
        try:
            if kind == "start":
                if index != 0 or start_seen:
                    issue("duplicate-or-late-start", seq)
                    continue
                start_seen = True
                if type(event.get("baseline_complete")) is not bool or not isinstance(event.get("baseline"), list):
                    raise ValueError("explicit baseline status and list required")
                baseline_complete = event["baseline_complete"]
                for row in event["baseline"]:
                    address, size = u32(row["address"]), u32(row["requested_bytes"])
                    owner, error = owner_claim(row.get("owner"))
                    if error:
                        issue(error, seq)
                    if not address or address in live:
                        raise ValueError("invalid or duplicate baseline address")
                    live[address] = dict(requested_bytes=size, owner=owner, allocation_call_id=None)
                refresh()
            elif not start_seen:
                issue("missing-start", seq)
            elif kind == "entry":
                call_id = u32(event["call_id"])
                if call_id in seen_ids:
                    issue("duplicate-call-id", seq)
                    continue
                seen_ids.add(call_id)
                if event.get("call") not in ("allocate", "free"):
                    raise ValueError("unsupported call")
                identity(event)
                args = event["args"]
                if not isinstance(args, list) or len(args) != (3 if event["call"] == "allocate" else 2):
                    raise ValueError("exact declared arguments required")
                for value in args:
                    u32(value)
                owner, error = owner_claim(event.get("owner"))
                if error:
                    issue(error, seq)
                colliding = [old_id for old_id, old in pending.items() if identity(old) == identity(event)]
                if colliding:
                    issue("ambiguous-return-identity", seq)
                    ambiguous_ids.update([call_id, *colliding])
                pending[call_id] = dict(event, declared_owner=owner)
                if event["call"] == "free":
                    address = args[0]
                    pending[call_id]["free_target"] = live.get(address)
                    if not address or address not in live:
                        issue("free-without-live-allocation", seq, address)
                    if any(old["call"] == "free" and old["args"][0] == address
                           for old_id, old in pending.items() if old_id != call_id):
                        issue("overlapping-free-lifetime", seq, address)
            elif kind == "return":
                call_id = u32(event["call_id"])
                call = pending.get(call_id)
                if call is None:
                    issue("return-without-entry", seq)
                    continue
                if call_id in ambiguous_ids:
                    issue("ambiguous-return-rejected", seq, call_id)
                    continue
                actual = u32(event["thread"]), u32(event["pc"]), u32(event["esp"])
                if actual != identity(call):
                    issue("return-identity-mismatch", seq)
                    continue
                eax = u32(event["eax"])
                del pending[call_id]
                if call["call"] == "allocate":
                    if eax == 0:
                        observed["failed_allocations"] += 1
                        continue
                    observed["successful_allocations"] += 1
                    owner = call["declared_owner"]
                    if owner == "unknown":
                        observed["unknown_owner_successful_allocations"] += 1
                    elif owner == "storage":
                        observed["declared_storage_successful_allocations"] += 1
                    if eax in live:
                        issue("duplicate-live-address", seq, eax)
                        continue
                    live[eax] = dict(requested_bytes=call["args"][1], owner=owner,
                                     owner_evidence=call.get("owner"), caller_pc=call["caller_pc"],
                                     thread=call["thread"], tag=call["args"][2], allocation_call_id=call_id)
                else:
                    address = call["args"][0]
                    if call.get("free_target") is None or live.get(address) is not call["free_target"]:
                        issue("free-lifetime-mismatch", seq, address)
                        continue
                    observed["completed_frees"] += 1
                    del live[address]
                refresh()
            elif kind == "service_count":
                service.append(u32(event["value"]))
            elif kind == "loss":
                issue("capture-loss", seq, event.get("reason"))
            elif kind == "end":
                end_seen = True
                if event.get("status") != "ok" or "error" not in event or event["error"] is not None:
                    issue("unsuccessful-capture-outcome", seq, event.get("error"))
            else:
                issue("unsupported-event", seq, kind)
        except (KeyError, TypeError, ValueError) as exc:
            issue("malformed-event", seq, str(exc))
    if not start_seen:
        issue("missing-start")
    if not end_seen:
        issue("missing-end")
    for call_id in pending:
        issue("pending-call", detail=call_id)
    return dict(schema_version=1, integrity="unknown" if issues else "complete",
                issues=issues, events_consumed=consumed, baseline_complete=baseline_complete,
                observed=observed, live_allocations=[dict(address=k, **v) for k, v in sorted(live.items())],
                service_count=dict(readings=service,
                                   observed_modulo_delta=(service[-1] - service[0]) % 2**32 if len(service) >= 2 else None,
                                   qualified_isr_entries=None),
                physical_storage_peak_bytes=None, qualified_storage_successful_allocations=None,
                native_qualified=False,
                limitations=["requested bytes are not physical charges",
                             "return boundaries are not allocator commit/release points",
                             "declared owner evidence is not independently authenticated",
                             "capture completeness is not debugger/native coverage proof"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    args = parser.parse_args()
    events = []
    source = args.events.read_text()
    for index, line in enumerate(source.splitlines()):
        try:
            event = json.loads(line)
        except (ValueError, RecursionError) as exc:
            event = dict(seq=index, kind="loss", reason="invalid JSON: " + str(exc))
        events.append(event)
    result = analyze(events)
    if not source.endswith("\n"):
        result["integrity"] = "unknown"
        result["issues"].append(dict(code="incomplete-terminal-frame", seq=None, detail=None))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
