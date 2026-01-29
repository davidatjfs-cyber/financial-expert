from __future__ import annotations

import os


_PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "WS_PROXY",
    "WSS_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "ftp_proxy",
    "ws_proxy",
    "wss_proxy",
    "NO_PROXY",
    "no_proxy",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
]


def disable_proxies_for_process() -> None:
    """Disable common proxy env vars for current process.

    AkShare (and its underlying requests usage) respects environment proxy variables.
    In some local environments these can cause ProxyError. We disable them to
    prefer direct connection for this local app.
    """

    for k in _PROXY_ENV_KEYS:
        if k in os.environ:
            os.environ.pop(k, None)

    # requests/urllib may also consult platform proxy settings.
    # Force bypass by setting NO_PROXY to wildcard.
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"

    # Some libraries check this flag to decide whether to read env proxies
    os.environ["REQUESTS_USE_ENVIRONMENT"] = "0"
