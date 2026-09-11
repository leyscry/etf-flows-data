"""
iShares (BlackRock) ETF shares outstanding scraper.

Fetches current Shares Outstanding from official iShares fund pages.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_BASE = "https://www.ishares.com/us/products"


# Ticker -> (product_id, slug)
ISHARES_FUNDS: dict[str, tuple[str, str]] = {

    # =========================
    # US Equity
    # =========================
    "IWM": ("239710", "ishares-russell-2000-etf"),
    "IVV": ("239726", "ishares-core-sp-500-etf"),

    # =========================
    # International
    # =========================
    "EFA":  ("239623", "ishares-msci-eafe-etf"),
    "EEM":  ("239637", "ishares-msci-emerging-markets-etf"),
    "IEMG": ("244049", "ishares-core-msci-emerging-markets-etf"),
    "EWJ":  ("239665", "ishares-msci-japan-etf"),
    "FXI":  ("239536", "ishares-china-large-cap-etf"),
    "EWZ":  ("239612", "ishares-msci-brazil-etf"),
    "INDA": ("239758", "ishares-msci-india-etf"),

    # =========================
    # Fixed Income
    # =========================
    "TLT": ("239454", "ishares-20-year-treasury-bond-etf"),
    "IEF": ("239456", "ishares-7-10-year-treasury-bond-etf"),
    "SHY": ("239452", "ishares-1-3-year-treasury-bond-etf"),
    "AGG": ("239458", "ishares-core-total-us-bond-market-etf"),
    "HYG": ("239565", "ishares-iboxx-high-yield-corporate-bond-etf"),
    "LQD": ("239566", "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "TIP": ("239467", "ishares-tips-bond-etf"),
    "EMB": ("239572", "ishares-jp-morgan-usd-emerging-markets-bond-etf"),

    # =========================
    # Commodities
    # =========================
    "SLV": ("239855", "ishares-silver-trust"),
    "GSG": ("239757", "ishares-sp-gsci-commodity-indexed-trust"),

    # =========================
    # Crypto
    # =========================
    "IBIT": ("333011", "ishares-bitcoin-trust-etf"),

    # =========================
    # Thematic
    # =========================
    "SOXX": ("239705", "ishares-phlx-semiconductor-etf"),
    "ICLN": ("239738", "ishares-global-clean-energy-etf"),
    "IBB":  ("239699", "ishares-nasdaq-biotechnology-etf"),
}


def _parse_shares(soup: BeautifulSoup) -> int | None:
    """
    Extract Shares Outstanding from an iShares product page.
    """

    # Method 1:
    # Find exact "Shares Outstanding" label and inspect nearby text.
    tag = soup.find(
        string=lambda t: t and t.strip().lower() == "shares outstanding"
    )

    if tag:
        parent = tag.parent

        # Check parent and a few ancestors because iShares HTML
        # structure can vary.
        nodes = [
            parent,
            parent.parent if parent else None,
            parent.parent.parent if parent and parent.parent else None,
        ]

        for node in nodes:
            if node is None:
                continue

            text = node.get_text(" ", strip=True)

            # Examples:
            # "Shares Outstanding 1,234,567"
            # "Shares Outstanding 1234.5M"
            m = re.search(
                r"Shares\s+Outstanding\s+([\d,.]+)\s*([MB])?",
                text,
                re.IGNORECASE,
            )

            if m:
                value = float(m.group(1).replace(",", ""))
                unit = (m.group(2) or "").upper()

                if unit == "M":
                    value *= 1_000_000
                elif unit == "B":
                    value *= 1_000_000_000

                return int(value)

    # Method 2:
    # Search the complete page text as fallback.
    page_text = soup.get_text(" ", strip=True)

    m = re.search(
        r"Shares\s+Outstanding\s*[:\-]?\s*([\d,.]+)\s*([MB])?",
        page_text,
        re.IGNORECASE,
    )

    if m:
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").upper()

        if unit == "M":
            value *= 1_000_000
        elif unit == "B":
            value *= 1_000_000_000

        return int(value)

    return None


def fetch_shares(
    ticker: str,
    session: requests.Session | None = None,
) -> int | None:
    """
    Fetch current Shares Outstanding for an iShares ETF.

    Returns:
        int  -> shares outstanding
        None -> unavailable
    """

    fund = ISHARES_FUNDS.get(ticker)

    if not fund:
        log.debug(f"ishares: {ticker} not in ISHARES_FUNDS")
        return None

    product_id, slug = fund
    url = f"{_BASE}/{product_id}/{slug}"

    sess = session or requests.Session()

    try:
        r = sess.get(
            url,
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()

    except Exception as exc:
        log.warning(
            f"ishares: {ticker} fetch error — {exc}"
        )
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    shares = _parse_shares(soup)

    if shares is not None and shares > 0:
        log.info(
            f"ishares: {ticker} shares outstanding = "
            f"{shares:,}"
        )
        return shares

    log.warning(
        f"ishares: {ticker} — "
        f"Shares Outstanding not found"
    )

    return None


def fetch_all(
    tickers: list[str],
) -> dict[str, int]:
    """
    Fetch Shares Outstanding for all iShares tickers.

    Returns:
        {
            "IWM": 123456789,
            "IVV": 987654321,
        }
    """

    sess = requests.Session()

    results: dict[str, int] = {}

    for ticker in tickers:

        if ticker not in ISHARES_FUNDS:
            continue

        shares = fetch_shares(
            ticker,
            session=sess,
        )

        if shares is not None:
            results[ticker] = shares

    return results
