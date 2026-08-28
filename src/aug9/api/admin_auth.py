import hashlib
import hmac
import os


class AdminAuthenticationError(ValueError):
    pass


class AdminAuthenticationConfigurationError(RuntimeError):
    pass


def verify_admin_api_key(supplied_key: str | None) -> None:
    configured_key = os.getenv("AUG9_ADMIN_API_KEY", "")
    if len(configured_key) < 32:
        raise AdminAuthenticationConfigurationError(
            "AUG9_ADMIN_API_KEY must contain at least 32 characters"
        )
    if supplied_key is None:
        raise AdminAuthenticationError("Admin credentials are required")

    supplied_digest = hashlib.sha256(supplied_key.encode()).digest()
    configured_digest = hashlib.sha256(configured_key.encode()).digest()
    if not hmac.compare_digest(supplied_digest, configured_digest):
        raise AdminAuthenticationError("Invalid admin credentials")
