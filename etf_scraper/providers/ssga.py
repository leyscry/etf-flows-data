"""
SSGA (State Street) ETF Shares Outstanding scraper.

Fetches current Shares Outstanding from official SSGA ETF pages.

Provider priority in collect.py:

    SSGA
      ↓
    iShares
      ↓
    TradingView

This module only provides Shares Outstanding.
It does NOT calculate ETF fund flows.
"""

import json
import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# SSGA ETF mapping
# ---------------------------------------------------------------------------
#
# ticker -> official SSGA URL slug
#
# SSGA has changed its URL structure over time.
# Current product pages generally use:
#
#   https://www.ssga.com/us/en/intermediary/etfs/{slug}
#
# ---------------------------------------------------------------------------

SSGA_FUNDS: dict[str, str] = {

    # -----------------------------------------------------------------------
    # Core / Index
    # -----------------------------------------------------------------------

    "SPY": "spdr-sp-500-etf-trust-spy",
    "DIA": "spdr-dow-jones-industrial-average-etf-trust-dia",

    # -----------------------------------------------------------------------
    # S&P 500 sectors
    # -----------------------------------------------------------------------

    "XLK": "the-technology-select-sector-spdr-fund-xlk",
    "XLF": "the-financial-select-sector-spdr-fund-xlf",
    "XLE": "the-energy-select-sector-spdr-fund-xle",
    "XLV": "the-health-care-select-sector-spdr-fund-xlv",
    "XLI": "the-industrial-select-sector-spdr-fund-xli",
    "XLY": "the-consumer-discretionary-select-sector-spdr-fund-xly",
    "XLP": "the-consumer-staples-select-sector-spdr-fund-xlp",
    "XLC": "the-communication-services-select-sector-spdr-fund-xlc",
    "XLU": "the-utilities-select-sector-spdr-fund-xlu",
    "XLRE": "the-real-estate-select-sector-spdr-fund-xlre",
    "XLB": "the-materials-select-sector-spdr-fund-xlb",

    # -----------------------------------------------------------------------
    # Commodities
    # -----------------------------------------------------------------------

    "GLD": "spdr-gold-shares-gld",
    "GLDM": "spdr-gold-minishares-trust-gldm",

    # -----------------------------------------------------------------------
    # Thematic
    # -----------------------------------------------------------------------

    "XAR": "state-street-spdr-sp-aerospace-defense-etf-xar",
    "XME": "state-street-spdr-sp-metals-mining-etf-xme",
    "XBI": "state-street-spdr-sp-biotech-etf-xbi",

    # -----------------------------------------------------------------------
    # Credit
    # -----------------------------------------------------------------------

    "SRLN": "spdr-blackstone-senior-loan-etf-srln",
}


# ---------------------------------------------------------------------------
# URL configuration
# ---------------------------------------------------------------------------

_BASE_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/{slug}"
)

# Some older SSGA pages used /funds/.
# Keep it as a fallback.
_OLD_BASE_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/funds/{slug}"
)


# ---------------------------------------------------------------------------
# Utility: parse numeric values
# ---------------------------------------------------------------------------

def _parse_number_with_unit(
    value: str,
    unit: str | None = None,
) -> int | None:
    """
    Parse values such as:

        69
        69.00
        69M
        69.00 M
        1.2B
        1,042.58M

    Returns an integer number of shares.
    """

    if not value:
        return None

    cleaned = value.strip().replace(",", "")

    # Remove common formatting characters.
    cleaned = cleaned.replace("$", "")
    cleaned = cleaned.replace("≈", "")
    cleaned = cleaned.strip()

    # Extract numeric component.
    match = re.search(
        r"([-+]?\d+(?:\.\d+)?)",
        cleaned,
    )

    if not match:
        return None

    try:
        number = float(match.group(1))
    except ValueError:
        return None

    # Unit can either be explicitly passed or included in value.
    detected_unit = (
        unit
        or re.search(
            r"\b([KMBT])\b",
            cleaned,
            re.IGNORECASE,
        )
    )

    if hasattr(detected_unit, "group"):
        detected_unit = detected_unit.group(1)

    if detected_unit:
        detected_unit = str(detected_unit).upper()

    multiplier = 1

    if detected_unit == "K":
        multiplier = 1_000

    elif detected_unit == "M":
        multiplier = 1_000_000

    elif detected_unit == "B":
        multiplier = 1_000_000_000

    elif detected_unit == "T":
        multiplier = 1_000_000_000_000

    result = int(number * multiplier)

    return result if result > 0 else None


# ---------------------------------------------------------------------------
# Utility: extract Shares Outstanding from visible text
# ---------------------------------------------------------------------------

def _parse_shares_from_text(
    text: str,
) -> int | None:
    """
    Extract Shares Outstanding from page text.

    Handles examples such as:

        Shares Outstanding 69.00 M

        Shares Outstanding
        69.00M

        Shares Outstanding: 69,000,000

        Shares Outstanding 69 Million
    """

    if not text:
        return None

    # Normalize whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    patterns = [

        # 69.00 M
        r"Shares\s+Outstanding\s*[:\-]?\s*"
        r"([\d,.]+)\s*([KMBT])\b",

        # 69 Million / 69 Billion
        r"Shares\s+Outstanding\s*[:\-]?\s*"
        r"([\d,.]+)\s*"
        r"(Thousand|Million|Billion|Trillion)\b",

        # Plain number
        r"Shares\s+Outstanding\s*[:\-]?\s*"
        r"([\d,.]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        number = match.group(1)

        unit = None

        if match.lastindex and match.lastindex >= 2:
            unit = match.group(2)

        if unit:

            unit_lower = unit.lower()

            if unit_lower == "thousand":
                unit = "K"

            elif unit_lower == "million":
                unit = "M"

            elif unit_lower == "billion":
                unit = "B"

            elif unit_lower == "trillion":
                unit = "T"

        shares = _parse_number_with_unit(
            number,
            unit,
        )

        if shares:
            return shares

    return None


# ---------------------------------------------------------------------------
# Utility: extract Shares Outstanding from raw HTML / JSON
# ---------------------------------------------------------------------------

def _parse_shares_from_html(
    html: str,
) -> int | None:
    """
    Search raw HTML and embedded JavaScript/JSON.

    This is useful when the value exists in the page source
    but is not rendered as a normal HTML table cell.
    """

    if not html:
        return None

    patterns = [

        # ---------------------------------------------------------------
        # JSON camelCase
        # ---------------------------------------------------------------

        r'"sharesOutstanding"\s*:\s*"([^"]+)"',
        r'"sharesOutstanding"\s*:\s*([0-9.,]+)',

        # ---------------------------------------------------------------
        # JSON snake_case
        # ---------------------------------------------------------------

        r'"shares_outstanding"\s*:\s*"([^"]+)"',
        r'"shares_outstanding"\s*:\s*([0-9.,]+)',

        # ---------------------------------------------------------------
        # Human-readable HTML / JS
        # ---------------------------------------------------------------

        r"Shares\s+Outstanding"
        r".{0,300}?"
        r"([\d,.]+)\s*([KMBT])\b",

        r"Shares\s+Outstanding"
        r".{0,300}?"
        r"([\d,.]+)\s*"
        r"(Million|Billion|Thousand|Trillion)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            continue

        number = match.group(1)

        unit = None

        if match.lastindex and match.lastindex >= 2:
            unit = match.group(2)

        if unit:

            unit_lower = unit.lower()

            if unit_lower == "thousand":
                unit = "K"

            elif unit_lower == "million":
                unit = "M"

            elif unit_lower == "billion":
                unit = "B"

            elif unit_lower == "trillion":
                unit = "T"

        shares = _parse_number_with_unit(
            number,
            unit,
        )

        if shares:
            return shares

    return None


# ---------------------------------------------------------------------------
# Utility: search embedded JSON scripts
# ---------------------------------------------------------------------------

def _parse_shares_from_json_scripts(
    soup: BeautifulSoup,
) -> int | None:
    """
    Inspect JSON script blocks.

    Some modern web pages embed product information
    inside <script type="application/json">.
    """

    scripts = soup.find_all(
        "script"
    )

    for script in scripts:

        content = script.string

        if not content:
            content = script.get_text()

        if not content:
            continue

        if (
            "sharesOutstanding" not in content
            and "shares_outstanding" not in content
            and "Shares Outstanding" not in content
        ):
            continue

        # ---------------------------------------------------------------
        # Direct regex first
        # ---------------------------------------------------------------

        shares = _parse_shares_from_html(
            content
        )

        if shares:
            return shares

        # ---------------------------------------------------------------
        # Try JSON parsing
        # ---------------------------------------------------------------

        try:

            data = json.loads(
                content
            )

        except Exception:
            continue

        shares = _find_shares_recursive(
            data
        )

        if shares:
            return shares

    return None


def _find_shares_recursive(
    obj: Any,
) -> int | None:
    """
    Recursively search a JSON object for keys related to
    Shares Outstanding.
    """

    if isinstance(obj, dict):

        for key, value in obj.items():

            normalized = (
                str(key)
                .lower()
                .replace("_", "")
                .replace("-", "")
                .replace(" ", "")
            )

            if normalized in {
                "sharesoutstanding",
                "sharesoutstandingvalue",
            }:

                if isinstance(value, (int, float)):

                    if value > 0:
                        return int(value)

                if isinstance(value, str):

                    shares = _parse_number_with_unit(
                        value
                    )

                    if shares:
                        return shares

            result = _find_shares_recursive(
                value
            )

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = _find_shares_recursive(
                item
            )

            if result:
                return result

    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def _parse_shares(
    soup: BeautifulSoup,
    html: str,
) -> int | None:
    """
    Multi-layer Shares Outstanding parser.

    Priority:

        1. visible page text
        2. raw HTML / JavaScript
        3. embedded JSON
    """

    # -----------------------------------------------------------------------
    # Method 1: visible text
    # -----------------------------------------------------------------------

    text = soup.get_text(
        " ",
        strip=True,
    )

    shares = _parse_shares_from_text(
        text
    )

    if shares:
        return shares

    # -----------------------------------------------------------------------
    # Method 2: raw HTML / JavaScript
    # -----------------------------------------------------------------------

    shares = _parse_shares_from_html(
        html
    )

    if shares:
        return shares

    # -----------------------------------------------------------------------
    # Method 3: embedded JSON
    # -----------------------------------------------------------------------

    shares = _parse_shares_from_json_scripts(
        soup
    )

    if shares:
        return shares

    return None


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch_page(
    ticker: str,
    slug: str,
    session: requests.Session,
) -> tuple[str, str] | None:
    """
    Fetch current SSGA product page.

    Returns:
        (url, html)
    """

    urls = [
        _BASE_URL.format(slug=slug),
        _OLD_BASE_URL.format(slug=slug),
    ]

    for url in urls:

        try:

            log.debug(
                f"ssga: {ticker} requesting {url}"
            )

            response = session.get(
                url,
                headers=_HEADERS,
                timeout=20,
                allow_redirects=True,
            )

            if response.status_code == 404:
                continue

            response.raise_for_status()

            html = response.text

            if not html:
                continue

            return (
                response.url,
                html,
            )

        except requests.RequestException as exc:

            log.debug(
                f"ssga: {ticker} "
                f"request failed for {url}: {exc}"
            )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_shares(
    ticker: str,
    session: requests.Session | None = None,
) -> int | None:
    """
    Fetch current Shares Outstanding for an SSGA ETF.

    Returns:
        int  -> Shares Outstanding
        None -> unavailable
    """

    ticker = ticker.upper().strip()

    slug = SSGA_FUNDS.get(
        ticker
    )

    if not slug:

        log.debug(
            f"ssga: {ticker} not in SSGA_FUNDS"
        )

        return None

    sess = session or requests.Session()

    result = _fetch_page(
        ticker,
        slug,
        sess,
    )

    if result is None:

        log.warning(
            f"ssga: {ticker} — "
            f"unable to fetch SSGA page"
        )

        return None

    url, html = result

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    shares = _parse_shares(
        soup,
        html,
    )

    if shares is not None and shares > 0:

        log.info(
            f"ssga: {ticker} "
            f"shares outstanding = "
            f"{shares:,}"
        )

        return shares

    # -----------------------------------------------------------------------
    # Diagnostic information
    # -----------------------------------------------------------------------

    if "Shares Outstanding" in html:

        log.warning(
            f"ssga: {ticker} — "
            f"'Shares Outstanding' exists in page "
            f"but parser could not extract value"
        )

    else:

        log.warning(
            f"ssga: {ticker} — "
            f"'Shares Outstanding' not found in page"
        )

    log.debug(
        f"ssga: {ticker} URL = {url}"
    )

    return None


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------

def fetch_all(
    tickers: list[str],
) -> dict[str, int]:
    """
    Fetch Shares Outstanding for all SSGA ETFs.

    Returns:

        {
            "SPY": 1000000000,
            "GLD": 300000000,
        }
    """

    session = requests.Session()

    results: dict[str, int] = {}

    for ticker in tickers:

        if ticker not in SSGA_FUNDS:
            continue

        shares = fetch_shares(
            ticker,
            session=session,
        )

        if shares is not None:

            results[ticker] = shares

    return results
