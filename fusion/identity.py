"""Interface for AUTHENTICATED SOURCE IDENTITY. WP4 defines the seam only.
HONEST STATUS: no cryptographic verification and no replay protection are implemented anywhere in this repository. CRC-32 (comm/) detects ACCIDENTAL corruption only.
The default verifier therefore reports `allowlist-only`; a policy that REQUIRES `authenticated` fails closed (every remote estimate is refused)."""
from __future__ import annotations
from typing import Protocol

ALLOWLIST_ONLY = "allowlist-only"
AUTHENTICATED = "authenticated"
LOCAL = "local"


class SourceIdentityVerifier(Protocol):
    def assurance(self, source_id: str, evidence: tuple) -> str:
        """Return AUTHENTICATED only if a cryptographic check bound to source_id AND replay protection for this evidence succeeded; otherwise ALLOWLIST_ONLY."""


class UnauthenticatedVerifier:
    """The only verifier shipped. Never returns AUTHENTICATED."""
    def assurance(self, source_id: str, evidence: tuple) -> str:
        return ALLOWLIST_ONLY


class _UnsafeTestOnlyAcceptAllVerifier:
    """TEST DOUBLE ONLY: claims every source is authenticated WITHOUT verifying anything. Exists to test the policy plumbing; must never be used in an experiment or report."""
    def assurance(self, source_id: str, evidence: tuple) -> str:
        return AUTHENTICATED
