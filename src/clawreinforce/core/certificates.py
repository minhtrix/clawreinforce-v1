from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from clawreinforce.core.models import CertificationReport


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_or_create_key(root: Path) -> Ed25519PrivateKey:
    store = root / ".clawreinforce"
    store.mkdir(parents=True, exist_ok=True)
    path = store / "signing-key.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def issue_certificate(report: CertificationReport, key: Ed25519PrivateKey) -> dict[str, Any]:
    body = {
        "schema": "clawreinforce.certificate.v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "skill": report.skill,
        "fingerprint": report.fingerprint,
        "tiers": [tier.to_dict() for tier in report.tiers],
    }
    return sign_envelope(body, key)


def sign_envelope(body: dict[str, Any], key: Ed25519PrivateKey) -> dict[str, Any]:
    public_raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "body": body,
        "public_key": base64.b64encode(public_raw).decode("ascii"),
        "signature": base64.b64encode(key.sign(_canonical(body))).decode("ascii"),
    }


def verify_certificate(certificate: dict[str, Any], fingerprint: str | None = None) -> tuple[bool, str]:
    valid, message = verify_envelope(certificate)
    if not valid:
        return valid, message
    body = certificate["body"]
    if fingerprint is not None and body.get("fingerprint") != fingerprint:
        return False, "skill fingerprint does not match certificate"
    return True, "valid"


def verify_envelope(certificate: dict[str, Any]) -> tuple[bool, str]:
    try:
        body = certificate["body"]
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(certificate["public_key"]))
        public.verify(base64.b64decode(certificate["signature"]), _canonical(body))
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        return False, f"signature invalid: {exc}"
    return True, "valid"
