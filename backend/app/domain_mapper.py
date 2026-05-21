"""
Domain mapping - assigns risk domains to signals based on keyword matching.

Intentionally simple for V1: keyword sets over text fields.
This will be replaced or augmented with LLM-based classification once we
have enough real signals to evaluate quality, but keyword matching gives us
deterministic, auditable results during early development.

Signals can belong to multiple domains - a credential CVE is both
identity_credential and vulnerability_patch.
"""

from app.models.enums import RiskDomain

# Keywords are matched case-insensitively against title + summary text.
# Each tuple is (domain, frozenset_of_keywords).
# Order matters: more specific patterns should appear before generic ones
# so that a specialist domain wins where there's overlap.
_DOMAIN_KEYWORDS: list[tuple[RiskDomain, frozenset[str]]] = [
    (
        RiskDomain.RANSOMWARE_EXTORTION,
        frozenset([
            "ransomware", "extortion", "lockbit", "blackcat", "revil",
            "double extortion", "triple extortion", "data leak site",
        ]),
    ),
    (
        RiskDomain.IDENTITY_CREDENTIAL,
        frozenset([
            "authentication", "credential", "oauth", "mfa", "multi-factor",
            "privilege", "identity", "session", "token", "ldap", "kerberos",
            "password", "phishing", "account takeover", "aitm",
            "adversary-in-the-middle", "passkey", "fido",
            "social engineering", "business email compromise", "bec",
            "spear phishing", "smishing", "vishing", "impersonation",
            "pretexting", "deepfake", "fraud", "wire transfer", "invoice fraud",
        ]),
    ),
    (
        RiskDomain.SUPPLY_CHAIN,
        frozenset([
            "supply chain", "dependency", "third party", "third-party",
            "vendor", "npm", "pypi", "open source", "open-source",
            "package manager", "software bill of materials", "sbom",
        ]),
    ),
    (
        RiskDomain.DETECTION_RESPONSE,
        frozenset([
            "detection", "edr", "siem", "logging", "monitoring", "dwell",
            "alert fatigue", "incident response", "forensic",
            "threat hunting", "coverage gap",
        ]),
    ),
    (
        RiskDomain.CLOUD_SECURITY,
        frozenset([
            "aws", "azure", "google cloud", "gcp", "cloud provider",
            "kubernetes", "k8s", "container", "docker", "eks", "aks", "gke",
            "terraform", "infrastructure as code", "iac", "serverless", "lambda",
            "cloud misconfiguration", "cloud iam", "service account", "iam role",
            "ec2", "blob storage", "cloud storage", "s3 bucket",
            "cloud native", "cloudtrail", "secret manager", "key vault",
        ]),
    ),
    (
        RiskDomain.DATA_EXPOSURE,
        frozenset([
            "data breach", "misconfiguration", "storage",
            "exfiltration", "data leak", "exposure", "pii", "gdpr",
            "publicly accessible",
        ]),
    ),
    (
        RiskDomain.VULNERABILITY_PATCH,
        frozenset([
            "cve", "patch", "unpatched", "eol", "end-of-life", "end of life",
            "remote code execution", "rce", "exploit", "zero-day", "zero day",
            "critical vulnerability", "buffer overflow", "injection",
        ]),
    ),
]


def map_domains(title: str, summary: str | None, tags: list[str] | None = None) -> list[RiskDomain]:
    """
    Return a deduplicated list of risk domains for a signal.

    We match against the combined text of title, summary, and tags so that
    rich source metadata (e.g. CISA advisory categories) improves accuracy
    without needing a separate classification step.
    """
    corpus = " ".join(filter(None, [title, summary, " ".join(tags or [])])).lower()

    matched: list[RiskDomain] = [
        domain
        for domain, keywords in _DOMAIN_KEYWORDS
        if any(kw in corpus for kw in keywords)
    ]

    # Every signal with a CVE ID should land in vulnerability_patch at minimum,
    # even if no other keywords match. CVE-prefixed source IDs are the clearest
    # indicator we have without parsing the full advisory.
    if not matched or (
        "cve-" in corpus and RiskDomain.VULNERABILITY_PATCH not in matched
    ):
        matched.append(RiskDomain.VULNERABILITY_PATCH)

    # Preserve insertion order while deduplicating
    seen: set[RiskDomain] = set()
    return [d for d in matched if not (d in seen or seen.add(d))]  # type: ignore[func-returns-value]
