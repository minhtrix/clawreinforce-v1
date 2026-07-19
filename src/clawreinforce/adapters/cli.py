from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clawreinforce.adapters.providers import ProviderHub
from clawreinforce.core.badges import badge_svg
from clawreinforce.core.arena import load_task, run_bench, task_health
from clawreinforce.core.certificates import issue_certificate, load_or_create_key, sign_envelope, verify_certificate
from clawreinforce.core.certify import certify_skill
from clawreinforce.core.fetch import fetched_skill
from clawreinforce.core.fingerprint import skill_fingerprint
from clawreinforce.core.guard import guard_skill
from clawreinforce.core.exports import export_csv, export_png
from clawreinforce.core.ledger import append_event
from clawreinforce.core.scan import scan_skill
from clawreinforce.core.skill import load_skill
from clawreinforce.core.task_source import fetched_task
from clawreinforce.errors import ClawError


GPT56_TIER = "openai:gpt-5.6-sol"


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _save_certificate(root: Path, certificate: dict[str, Any]) -> Path:
    store = root / ".clawreinforce" / "certificates"
    store.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = store / f"certificate-{stamp}.json"
    path.write_text(json.dumps(certificate, indent=2, ensure_ascii=False), encoding="utf-8")
    append_event(root, "certificates", {"certificate": certificate, "path": str(path.relative_to(root))})
    return path


def _cmd_scan(args: argparse.Namespace) -> int:
    skill = load_skill(args.path)
    findings = scan_skill(skill)
    _print({"skill": skill.name, "fingerprint": skill_fingerprint(skill.root), "findings": [asdict(row) for row in findings]})
    return 1 if any(row.severity == "high" for row in findings) else 0


def _cmd_certify(args: argparse.Namespace) -> int:
    skill = load_skill(args.path)
    hub = ProviderHub(skill.root)
    tiers = args.tier or [GPT56_TIER]
    report = certify_skill(skill, tiers, args.samples, hub.execute, dry_run=args.dry_run)
    payload: dict[str, Any] = {"report": report.to_dict(), "certificate_path": None}
    if not args.dry_run:
        certificate = issue_certificate(report, load_or_create_key(skill.root))
        payload["certificate_path"] = str(_save_certificate(skill.root, certificate))
    _print(payload)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.certificate)
    certificate = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = None
    if args.skill:
        fingerprint = skill_fingerprint(load_skill(args.skill).root)
    valid, message = verify_certificate(certificate, fingerprint)
    _print({"valid": valid, "message": message, "certificate": str(path)})
    return 0 if valid else 1


def _cmd_badge(args: argparse.Namespace) -> int:
    certificate = json.loads(Path(args.certificate).read_text(encoding="utf-8"))
    valid, message = verify_certificate(certificate)
    if not valid:
        raise ClawError("certificate.invalid", "security", message)
    tiers = certificate["body"].get("tiers", [])
    rates = [row["pass_rate"] for row in tiers if row.get("pass_rate") is not None]
    if not rates:
        raise ClawError("badge.no_score", "validation", "certificate has no completed coverage")
    names = [row["tier"] for row in tiers]
    scope = ", ".join(names)
    gpt56 = any("gpt-5.6" in name for name in names)
    output = Path(args.output) if args.output else Path(args.certificate).parent.parent / "badge.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(badge_svg(scope, sum(rates) / len(rates), gpt56=gpt56), encoding="utf-8")
    _print({"badge": str(output), "scope": scope, "gpt56": gpt56})
    return 0


def _cmd_guard(args: argparse.Namespace) -> int:
    with fetched_skill(args.source) as fetched:
        skill = load_skill(fetched)
        hub = ProviderHub(Path.cwd())
        result = guard_skill(skill, args.tier or [GPT56_TIER], args.samples, hub.execute, threshold=args.threshold)
        result["source"] = args.source
        result["skill"] = skill.name
        result["fingerprint"] = skill_fingerprint(skill.root)
        _print(result)
        return {"install": 0, "reject": 1, "review": 2}[result["verdict"]]


def _cmd_models(args: argparse.Namespace) -> int:
    hub = ProviderHub(Path(args.project).resolve())
    payload: dict[str, Any] = {"providers": hub.status(), "preset": GPT56_TIER, "gpt56_preset": GPT56_TIER}
    if args.discover:
        result = hub.discover(args.discover)
        discovered = json.loads(result.output) if result.output else None
        payload["discovery"] = {"status": result.status, "models": discovered, "last_error": result.error}
        if discovered:
            payload["preset"] = f"{args.discover}:{discovered[0]}"
    if args.probe:
        result = hub.execute(args.probe, "Follow the user instruction exactly.", "Reply with exactly: OLLAMA_CLOUD_OK")
        payload["probe"] = {"status": result.status, "output": result.output, "last_error": result.error}
    _print(payload)
    return 0 if not args.probe or payload["probe"]["status"] == "completed" else 1


def _cmd_task_check(args: argparse.Namespace) -> int:
    with fetched_task(args.path) as fetched:
        task = load_task(fetched)
        health = task_health(task)
        _print({"task": task.name, "source": task.source, "difficulty": task.difficulty, **health})
        return 0 if health["healthy"] is not False else 1


def _cmd_bench(args: argparse.Namespace) -> int:
    project_root = Path.cwd()
    with fetched_skill(args.skill) as skill_root, fetched_task(args.task) as task_root:
        skill = load_skill(skill_root)
        task = load_task(task_root)
        hub = ProviderHub(project_root)
        report = run_bench(task, skill, args.tier or [GPT56_TIER], args.trials, hub.execute)
    store = project_root / ".clawreinforce" / "bench"
    store.mkdir(parents=True, exist_ok=True)
    report_path = store / f"{report.run_id}.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    append_event(project_root, "bench-runs", {"run_id": report.run_id, "report_path": str(report_path.relative_to(project_root)), "summary": report.summary})
    outputs: dict[str, str] = {"report": str(report_path)}
    if args.csv:
        outputs["csv"] = str(export_csv(report, Path(args.csv)))
    if args.png:
        outputs["png"] = str(export_png(report, Path(args.png)))
    _print({"report": report.to_dict(), "outputs": outputs})
    return 0


def _cmd_bench_certify(args: argparse.Namespace) -> int:
    report_path = Path(args.report).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    root = Path(args.project).resolve()
    digest = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
    body = {
        "schema": "clawreinforce.bench-certificate.v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "ledger_ref": str(report_path),
        "report_digest": digest,
        "run_id": report["run_id"],
        "skill_fingerprint": report["fingerprint"],
        "summary": report["summary"],
    }
    certificate = sign_envelope(body, load_or_create_key(root))
    output = Path(args.output) if args.output else report_path.with_name(report_path.stem + ".certificate.json")
    output.write_text(json.dumps(certificate, indent=2, ensure_ascii=False), encoding="utf-8")
    append_event(root, "bench-certificates", {"run_id": report["run_id"], "certificate_path": str(output)})
    _print({"certificate": str(output), "report_digest": digest})
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from clawreinforce.adapters.http import serve

    serve(Path(args.project), args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clawreinforce",
        description="CI for agent skills",
        epilog=(
            "Check kinds: equals, contains, not_contains, regex, property, exec, task, "
            "and agent. The agent check is single-shot (no tool loop yet)."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="statically inspect a skill")
    scan.add_argument("path")
    scan.set_defaults(func=_cmd_scan)
    certify = commands.add_parser("certify", help="run deterministic golden certification")
    certify.add_argument("path")
    certify.add_argument("--tier", action="append", help=f"provider:model (default: {GPT56_TIER})")
    certify.add_argument("--samples", type=int, default=1)
    certify.add_argument("--dry-run", action="store_true")
    certify.set_defaults(func=_cmd_certify)
    verify = commands.add_parser("cert-verify", help="verify an Ed25519 certificate")
    verify.add_argument("certificate")
    verify.add_argument("--skill")
    verify.set_defaults(func=_cmd_verify)
    badge = commands.add_parser("badge", help="render a scope-bearing SVG badge")
    badge.add_argument("certificate")
    badge.add_argument("--output")
    badge.set_defaults(func=_cmd_badge)
    guard = commands.add_parser("guard", help="fetch, scan, certify, and decide before install")
    guard.add_argument("source", help="local path, GitHub URL, or ClawHub slug")
    guard.add_argument("--tier", action="append")
    guard.add_argument("--samples", type=int, default=1)
    guard.add_argument("--threshold", type=float, default=0.8)
    guard.set_defaults(func=_cmd_guard)
    models = commands.add_parser("models", help="show provider configuration without secrets")
    models.add_argument("--project", default=".")
    models.add_argument("--discover")
    models.add_argument("--probe", help="provider:model connectivity test")
    models.set_defaults(func=_cmd_models)
    task_check = commands.add_parser("task-check", help="smoke-run a task's hidden grader against its oracle")
    task_check.add_argument("path")
    task_check.set_defaults(func=_cmd_task_check)
    bench = commands.add_parser("bench", help="measure model scores with and without a skill")
    bench.add_argument("task")
    bench.add_argument("skill")
    bench.add_argument("--tier", action="append")
    bench.add_argument("--trials", type=int, default=1)
    bench.add_argument("--csv")
    bench.add_argument("--png")
    bench.set_defaults(func=_cmd_bench)
    bench_certify = commands.add_parser("bench-certify", help="sign a persisted bench result")
    bench_certify.add_argument("report")
    bench_certify.add_argument("--project", default=".")
    bench_certify.add_argument("--output")
    bench_certify.set_defaults(func=_cmd_bench_certify)
    server = commands.add_parser("serve", help="serve the HTTP API and four-tab GUI")
    server.add_argument("--project", default=".")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8788)
    server.set_defaults(func=_cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if getattr(args, "samples", 1) < 1 or getattr(args, "trials", 1) < 1:
            raise ClawError("count.invalid", "validation", "samples/trials must be >= 1")
        return int(args.func(args))
    except ClawError as exc:
        _print({"error": exc.detail.to_dict()})
        return 1
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        _print({"error": {"code": "cli.failed", "kind": "runtime", "message": str(exc), "context": {}}})
        return 1


if __name__ == "__main__":
    sys.exit(main())
