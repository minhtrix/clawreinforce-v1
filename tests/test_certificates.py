from copy import deepcopy

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from clawreinforce.core.certificates import issue_certificate, verify_certificate
from clawreinforce.core.models import CertificationReport, TierReport


def _report() -> CertificationReport:
    tier = TierReport("openai:gpt-5.6-sol", "completed", 1.0, {"completed": 1, "expected": 1, "passed": 1}, [])
    return CertificationReport("demo", "sha256:abc", [tier])


def test_certificate_signature_and_fingerprint() -> None:
    certificate = issue_certificate(_report(), Ed25519PrivateKey.generate())
    assert verify_certificate(certificate, "sha256:abc") == (True, "valid")
    assert not verify_certificate(certificate, "sha256:other")[0]


def test_certificate_detects_tamper() -> None:
    certificate = issue_certificate(_report(), Ed25519PrivateKey.generate())
    tampered = deepcopy(certificate)
    tampered["body"]["tiers"][0]["pass_rate"] = 0.0
    assert not verify_certificate(tampered)[0]

