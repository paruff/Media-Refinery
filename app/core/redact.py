"""Log-safe descriptions of provider errors (R-SAFE-6).

httpx exception text embeds the full request URL, which carries API keys and
audio fingerprints in the query string, so log this summary instead of `str(e)`.
"""

import logging

# httpx logs every request URL at INFO; importing this module (done by every
# provider client) keeps those lines out of the logs.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def http_error_summary(error: Exception) -> str:
    status = getattr(getattr(error, "response", None), "status_code", None)
    name = type(error).__name__
    return f"{name} (HTTP {status})" if status else name
