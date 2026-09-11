"""
TradingView ETF shares outstanding scraper.
Tries common US exchanges automatically.
"""

import logging
import re
import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_BASE = "https://www.tradingview.com/symbols"

_EXCHANGES = (
    "AMEX",
    "NASDAQ",
    "NYSE",
)


def _extract_shares(text: str) -> int | None:
    """
    Extract shares_outstanding from TradingView embedded JSON.
    """

    patterns = [
        r'"shares_outstanding"\s*:\s*(\d+(?:\.\d+)?)',
        r'"sharesOutstanding"\s*:\s*(\d+(?:\.\d+)?)',
    ]

    for pattern in patterns:
        m = re.search(pattern, text)

        if m:
            try:
                value = float(m.group(1))

                if value > 0:
                    return int(value)

            except ValueError:
                pass

    return None


def fetch_shares(
    ticker: str,
    session: requests.Session | None = None,
) -> int | None:

    sess = session or requests.Session()

    ticker = ticker.upper().strip()

    for exchange in _EXCHANGES:

        url = f"{_BASE}/{exchange}-{ticker}/"

        try:
            r = sess.get(
                url,
                headers=_HEADERS,
                timeout=15,
            )

            if r.status_code == 404:
                continue

            r.raise_for_status()

        except Exception as exc:
            log.debug(
                "tradingview: %s %s fetch error — %s",
                exchange,
                ticker,
                exc,
            )
            continue

        shares = _extract_shares(r.text)

        if shares is not None:

            log.info(
                "tradingview: %s shares outstanding = %s "
                "(exchange=%s)",
                ticker,
                f"{shares:,}",
                exchange,
            )

            return shares

    log.debug(
        "tradingview: %s shares_outstanding not found",
        ticker,
    )

    return None


def fetch_all(tickers: list[str]) -> dict[str, int]:

    sess = requests.Session()

    results: dict[str, int] = {}

    for ticker in tickers:

        shares = fetch_shares(
            ticker,
            session=sess,
        )

        if shares is not None:
            results[ticker] = shares

    return results
