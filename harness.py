#!/usr/bin/env python3
"""Validate task packets and execution receipts; never executes task content."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

MAX_DOCUMENT_BYTES = 1_000_000
TASK_STATUSES = {"completed", "partial", "failed", "blocked"}
ACCEPTANCE_STATUSES = {"pending", "accepted", "rejected"}
CHECK_RESULTS = {"pass", "fail", "not_run"}


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _string_list(value):
    return isinstance(value, list) and all(_is_text(item) for item in value)


def validate_task(data):
    errors = []
    if not isinstance(data, dict):
        return ["task root must be an object"]
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    for field in ("task_id", "objective"):
        if not _is_text(data.get(field)):
            errors.append(f"{field} must be a non-empty string")
    target = data.get("target")
    if not isinstance(target, dict) or not all(_is_text(target.get(k)) for k in ("kind", "id")):
        errors.append("target must include non-empty kind and id")
    elif not _string_list(target.get("allowed_paths")) or not target["allowed_paths"]:
        errors.append("target.allowed_paths must be a non-empty list of strings")
    control = data.get("control")
    if not isinstance(control, dict) or not all(_is_text(control.get(k)) for k in ("primary_role", "executor_role", "single_writer")):
        errors.append("control must identify primary_role, executor_role, and single_writer")
    interfaces = data.get("interfaces")
    if not isinstance(interfaces, list) or not interfaces:
        errors.append("interfaces must be a non-empty list")
    elif any(not isinstance(item, dict) or not _is_text(item.get("kind")) or not _is_text(item.get("name")) or type(item.get("verified_for_task")) is not bool for item in interfaces):
        errors.append("each interface must include kind, name, and boolean verified_for_task")
    for field in ("allowed_actions", "prohibited_actions", "stop_conditions"):
        if not _string_list(data.get(field)):
            errors.append(f"{field} must be a list of non-empty strings")
    criteria = data.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("acceptance_criteria must be a non-empty list")
    elif any(not isinstance(item, dict) or not _is_text(item.get("id")) or not _is_text(item.get("description")) for item in criteria):
        errors.append("each acceptance criterion must include id and description")
    elif len({item["id"] for item in criteria}) != len(criteria):
        errors.append("acceptance criterion ids must be unique")
    attempts = data.get("max_attempts")
    if type(attempts) is not int or not 1 <= attempts <= 10:
        errors.append("max_attempts must be an integer from 1 to 10")
    return errors


def _valid_evidence(value):
    return isinstance(value, list) and all(
        isinstance(item, dict) and all(_is_text(item.get(k)) for k in ("kind", "reference", "establishes"))
        for item in value
    )


def validate_receipt(data, task=None):
    errors = []
    if not isinstance(data, dict):
        return {"errors": ["receipt root must be an object"], "outcome": "invalid", "accepted": False}
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if not _is_text(data.get("task_id")):
        errors.append("task_id must be a non-empty string")
    task_errors = []
    if task is not None:
        task_errors = validate_task(task)
        errors.extend(task_errors)
        if isinstance(task, dict) and data.get("task_id") != task.get("task_id"):
            errors.append("receipt task_id does not match task")
    executor = data.get("executor")
    if not isinstance(executor, dict) or not all(_is_text(executor.get(k)) for k in ("id", "route")):
        errors.append("executor must include non-empty id and route")
    reported = data.get("reported_status")
    if not isinstance(reported, str) or reported not in TASK_STATUSES:
        errors.append("reported_status must be completed, partial, failed, or blocked")
    if not _string_list(data.get("actions_reported")):
        errors.append("actions_reported must be a list of non-empty strings")
    if not isinstance(data.get("changes"), list):
        errors.append("changes must be a list")
    if not _valid_evidence(data.get("evidence")):
        errors.append("evidence must be a list of objects with kind, reference, and establishes")
    if not _string_list(data.get("limitations")):
        errors.append("limitations must be a list of non-empty strings")

    acceptance = data.get("independent_acceptance")
    if not isinstance(acceptance, dict):
        errors.append("independent_acceptance object is required; use pending until reviewed")
        acceptance = {}
    status = acceptance.get("status")
    if not isinstance(status, str) or status not in ACCEPTANCE_STATUSES:
        errors.append("independent_acceptance.status must be pending, accepted, or rejected")
        status = "pending"
    checks = acceptance.get("checks")
    if not isinstance(checks, list):
        errors.append("independent_acceptance.checks must be a list")
        checks = []
    check_ids = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or not _is_text(check.get("id")) or not isinstance(check.get("result"), str) or check.get("result") not in CHECK_RESULTS or not _valid_evidence(check.get("evidence")):
            errors.append(f"acceptance check {index + 1} must include id, result, and evidence list")
            continue
        if check["id"] in check_ids:
            errors.append("acceptance check ids must be unique")
        check_ids.add(check["id"])
    accepted_by = acceptance.get("accepted_by")
    if status == "accepted":
        if reported != "completed":
            errors.append("accepted requires reported_status completed")
        if not isinstance(accepted_by, dict) or accepted_by.get("role") != "primary" or not _is_text(accepted_by.get("id")):
            errors.append("accepted requires accepted_by with role primary and an id")
        elif isinstance(executor, dict) and accepted_by["id"] == executor.get("id"):
            errors.append("acceptance reviewer must be independent of the executor")
        if not checks:
            errors.append("accepted requires at least one acceptance check")
        for check in checks:
            if not isinstance(check, dict):
                continue
            if check.get("result") != "pass" or not check.get("evidence"):
                errors.append(f"accepted check {check.get('id', '<unknown>')} must pass and cite evidence")
        if task is not None and not task_errors:
            required = {item["id"] for item in task["acceptance_criteria"]}
            if required - check_ids:
                errors.append("accepted receipt is missing one or more task acceptance checks")
    elif status == "rejected" and not _is_text(acceptance.get("reason")):
        errors.append("rejected acceptance requires a reason")

    if errors:
        outcome = "invalid"
        accepted = False
    elif status == "accepted":
        outcome = "accepted"
        accepted = True
    elif reported == "completed" and status == "pending":
        outcome = "reported_completed_pending_acceptance"
        accepted = False
    elif reported == "completed" and status == "rejected":
        outcome = "reported_completed_rejected"
        accepted = False
    else:
        outcome = f"reported_{reported}"
        accepted = False
    return {"errors": errors, "outcome": outcome, "accepted": accepted}


def read_json(path):
    path = Path(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            return None, "document exceeds 1 MB limit"
        value = json.loads(raw.decode("utf-8"))
        return value, None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "document could not be read as JSON"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate task packets and receipts; never execute task content")
    sub = parser.add_subparsers(dest="command", required=True)
    task_parser = sub.add_parser("validate-task", help="Validate a task packet")
    task_parser.add_argument("path")
    receipt_parser = sub.add_parser("validate-receipt", help="Validate a receipt and independent acceptance")
    receipt_parser.add_argument("path")
    receipt_parser.add_argument("--task", help="Optional matching task packet")
    args = parser.parse_args(argv)
    data, error = read_json(args.path)
    if error:
        result = {"valid": False, "outcome": "invalid", "errors": [error]}
    elif args.command == "validate-task":
        errors = validate_task(data)
        result = {"valid": not errors, "outcome": "valid" if not errors else "invalid", "errors": errors}
    else:
        task = None
        if args.task:
            task, task_error = read_json(args.task)
            if task_error:
                result = {"valid": False, "outcome": "invalid", "accepted": False, "errors": ["task: " + task_error]}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
        result = validate_receipt(data, task)
        result["valid"] = not result["errors"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
