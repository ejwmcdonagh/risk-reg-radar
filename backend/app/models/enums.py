from enum import Enum


class SignalSource(str, Enum):
    CISA_KEV = "cisa_kev"
    CISA_ADVISORY = "cisa_advisory"
    NCSC = "ncsc"
    NVD = "nvd"
    # Dynamic value used for all custom RSS sources added via the profile API.
    # The actual source name is stored in signal.tags as "source:<name>".
    CUSTOM = "custom"


class SignalType(str, Enum):
    VULNERABILITY = "vulnerability"
    ADVISORY = "advisory"
    THREAT_INTEL = "threat_intel"
    REGULATORY = "regulatory"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskDomain(str, Enum):
    IDENTITY_CREDENTIAL = "identity_credential"
    VULNERABILITY_PATCH = "vulnerability_patch"
    SUPPLY_CHAIN = "supply_chain"
    DETECTION_RESPONSE = "detection_response"
    DATA_EXPOSURE = "data_exposure"
    RANSOMWARE_EXTORTION = "ransomware_extortion"
