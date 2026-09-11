"""
ETF Shares Outstanding Collector
---------------------------------

Fetches daily Shares Outstanding for ETFs via:

    1. SSGA
    2. iShares
    3. TradingView

The first valid provider result is used.

Price is fetched separately via yfinance.

Estimated flow:

    estimated_flow = ΔShares × price

This is an estimated flow, NOT official ETF fund flow data.

Files:

    data/etf_shares.csv
    data/etf_flows.csv
    data/etf_aum.csv

Shares CSV:

    date,ticker,shares,price,price_date,source

Example:

    2026-09-12,IBIT,1387360000,43.68,2026-09-11,iShares

Run manually:

    python etf_scraper/collect.py

GitHub Actions:
scheduled daily after market close.
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


# ============================================================================
# ETF universe
# ============================================================================

ETF_TICKERS: list[str] = [

    # ============================================================
    # 🇺🇸 US EQUITY — US broad market / major indexes
    # ============================================================

    "SPY", "VOO", "IVV", "QQQ", "QQQM",
    "DIA", "IWM", "IWB", "VTI", "ITOT",

    # ============================================================
    # 🇺🇸 US EQUITY — Sectors
    # ============================================================

    "XLK", "XLF", "XLV", "XLE", "XLI",
    "XLY", "XLP", "XLC", "XLU", "XLRE", "XLB",

    # ============================================================
    # 🇺🇸 US EQUITY — Style / Size
    # ============================================================

    "VUG", "VTV", "IVW", "IVE",
    "IWF", "IWD", "IWO", "IWN", "IJH",

    # ============================================================
    # 🇺🇸 US EQUITY — Themes
    # ============================================================

    "SMH", "SOXX", "XSD",
    "AIQ", "BOTZ", "ROBO",
    "SKYY",
    "CIBR", "HACK",
    "ITA", "XAR", "PPA",
    "PAVE",
    "URA", "URNM",

    # ============================================================
    # 🌎 GLOBAL EQUITY
    # ============================================================

    "VT", "ACWI", "URTH",
    "VEU", "VXUS", "IXUS",

    # ============================================================
    # 🇪🇺 EUROPE
    # ============================================================

    "VGK", "EZU", "FEZ",
    "EWU",
    "EWG",
    "EWQ",
    "EWL",
    "EWI",
    "EWP",

    # ============================================================
    # 🇯🇵 JAPAN
    # ============================================================

    "EWJ", "DXJ", "HEWJ",

    # ============================================================
    # 🇨🇳 CHINA / 🇭🇰 HONG KONG
    # ============================================================

    "MCHI", "KWEB", "FXI", "ASHR", "KBA",
    "EWH",

    # ============================================================
    # 🇹🇼 TAIWAN
    # ============================================================

    "EWT",

    # ============================================================
    # 🇰🇷 SOUTH KOREA
    # ============================================================

    "EWY",

    # ============================================================
    # 🇮🇳 INDIA
    # ============================================================

    "INDA", "INDY", "EPI",

    # ============================================================
    # 🌏 ASEAN
    # ============================================================

    "VNM",
    "EIDO",
    "THD",
    "EWS",
    "EWM",

    # ============================================================
    # 🇧🇷 LATIN AMERICA
    # ============================================================

    "EWZ",
    "EWW",
    "ECH",
    "ILF",

    # ============================================================
    # 🌎 EMERGING MARKETS
    # ============================================================

    "EEM", "VWO", "IEMG", "EMXC",

    # ============================================================
    # 🌍 MIDDLE EAST
    # ============================================================

    "KSA",
    "UAE",

    # ============================================================
    # 🛢 COMMODITIES — Gold
    # ============================================================

    "GLD", "IAU", "GLDM",

    # ============================================================
    # 🥈 COMMODITIES — Silver
    # ============================================================

    "SLV", "SIVR",

    # ============================================================
    # 🛢 COMMODITIES — Oil
    # ============================================================

    "USO", "BNO",
    "XOP", "OIH",

    # ============================================================
    # 🔥 COMMODITIES — Natural Gas
    # ============================================================

    "UNG", "FCG",

    # ============================================================
    # 🟠 COMMODITIES — Copper
    # ============================================================

    "CPER", "COPX",

    # ============================================================
    # 🌾 COMMODITIES — Broad Commodity
    # ============================================================

    "DBC", "PDBC", "GSG",

    # ============================================================
    # 🏦 US TREASURY — Ultra Short
    # ============================================================

    "SGOV", "BIL",

    # ============================================================
    # 🏦 US TREASURY — Short / Intermediate
    # ============================================================

    "SHY", "IEI",

    # ============================================================
    # 🏦 US TREASURY — 7-10Y
    # ============================================================

    "IEF", "VGIT",

    # ============================================================
    # 🏦 US TREASURY — Long Duration
    # ============================================================

    "TLH", "TLT", "VGLT",

    # ============================================================
    # 💳 US CORPORATE BONDS — Investment Grade
    # ============================================================

    "LQD",
    "IGSB", "IGIB",
    "VCSH", "VCIT",

    # ============================================================
    # 💳 US CORPORATE BONDS — High Yield
    # ============================================================

    "HYG", "JNK", "USHY",

    # ============================================================
    # 🛡 US BONDS — TIPS
    # ============================================================

    "TIP", "VTIP", "SCHP",

    # ============================================================
    # 🏙 US BONDS — Municipal
    # ============================================================

    "MUB", "VTEB",

    # ============================================================
    # 🇺🇸 US BONDS — Aggregate
    # ============================================================

    "BND",

    # ============================================================
    # 🌍 GLOBAL BONDS
    # ============================================================

    "BNDX", "IAGG",
    "BWX", "IGOV",

    # ============================================================
    # 🌏 EMERGING MARKET BONDS
    # ============================================================

    "EMB", "VWOB", "EMLC",

    # ============================================================
    # ₿ CRYPTO — Bitcoin
    # ============================================================

    "IBIT", "FBTC", "GBTC", "ARKB", "BITB",

    # ============================================================
    # Ξ CRYPTO — Ethereum
    # ============================================================

    "ETHA", "FETH", "ETHE",

    # ============================================================
    # 🟣 CRYPTO — Solana
    # ============================================================

    "BSOL", "VSOL", "GSOL",

    # ============================================================
    # 🛡 CRYPTO — Zcash
    # ============================================================

    "ZCSH",
]


# ============================================================================
# Files
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent

DATA_FILE = REPO_ROOT / "data" / "etf_shares.csv"
FLOWS_FILE = REPO_ROOT / "data" / "etf_flows.csv"
AUM_FILE = REPO_ROOT / "data" / "etf_aum.csv"


# ============================================================================
# Historical configuration
# ============================================================================

BOOTSTRAP_DAYS = 400
OVERLAP_DAYS = 30


# ============================================================================
# Empty DataFrame schemas
# ============================================================================

SHARES_COLUMNS = [
    "date",
    "ticker",
    "shares",
    "price",
    "price_date",
    "source",
]

FLOW_COLUMNS = [
    "date",
    "ticker",
    "flow_usd",
    "flow_type",
]

AUM_COLUMNS = [
    "ticker",
    "aum_usd",
    "updated_date",
]


# ============================================================================
# Load existing Shares state
# ============================================================================

def load_existing() -> pd.DataFrame:
    """
    Load existing etf_shares.csv.

    Automatically upgrades old CSV files which may not contain
    price_date.
    """

    if not DATA_FILE.exists():

        log.info(
            "No existing CSV — "
            "will bootstrap from current Shares Outstanding"
        )

        return pd.DataFrame(
            columns=SHARES_COLUMNS
        )

    try:

        df = pd.read_csv(
            DATA_FILE,
            parse_dates=["date"],
        )

    except Exception as exc:

        log.warning(
            f"Could not read existing shares CSV: {exc}"
        )

        return pd.DataFrame(
            columns=SHARES_COLUMNS
        )

    # ------------------------------------------------------------------------
    # Upgrade old schema
    # ------------------------------------------------------------------------

    if "price" not in df.columns:
        df["price"] = pd.NA

    if "price_date" not in df.columns:
        df["price_date"] = pd.NaT

    if "source" not in df.columns:
        df["source"] = pd.NA

    # Make sure all required columns exist.
    for col in SHARES_COLUMNS:

        if col not in df.columns:
            df[col] = pd.NA

    df = df[SHARES_COLUMNS]

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    ).dt.normalize()

    df["price_date"] = pd.to_datetime(
        df["price_date"],
        errors="coerce",
    ).dt.normalize()

    log.info(
        f"Loaded existing CSV: "
        f"{len(df):,} rows, "
        f"{df['ticker'].nunique()} tickers, "
        f"latest {df['date'].max().date() if df['date'].notna().any() else 'N/A'}"
    )

    return df


# ============================================================================
# Fetch Shares Outstanding
# ============================================================================

def fetch_shares_today(
    tickers: list[str],
) -> pd.DataFrame:
    """
    Fetch current Shares Outstanding.

    Provider priority:

        1. SSGA
        2. iShares
        3. TradingView

    Returns:

        date
        ticker
        shares
        source

    Price is intentionally NOT fetched here.
    """

    from providers import (
        ishares,
        ssga,
        tradingview,
    )

    today = pd.Timestamp.today().normalize()

    records: list[dict] = []
    missing: list[str] = []

    log.info(
        f"Trying SSGA → iShares → TradingView "
        f"for all {len(tickers)} tickers …"
    )

    for ticker in tickers:

        shares = None
        source = None

        # --------------------------------------------------------------------
        # 1. SSGA
        # --------------------------------------------------------------------

        try:

            shares = ssga.fetch_shares(
                ticker
            )

            if shares is not None and shares > 0:
                source = "SSGA"

        except Exception as exc:

            log.debug(
                f"SSGA failed for {ticker}: {exc}"
            )

        # --------------------------------------------------------------------
        # 2. iShares
        # --------------------------------------------------------------------

        if shares is None:

            try:

                shares = ishares.fetch_shares(
                    ticker
                )

                if shares is not None and shares > 0:
                    source = "iShares"

            except Exception as exc:

                log.debug(
                    f"iShares failed for {ticker}: {exc}"
                )

        # --------------------------------------------------------------------
        # 3. TradingView
        # --------------------------------------------------------------------

        if shares is None:

            try:

                shares = tradingview.fetch_shares(
                    ticker
                )

                if shares is not None and shares > 0:
                    source = "TradingView"

            except Exception as exc:

                log.debug(
                    f"TradingView failed for {ticker}: {exc}"
                )

        # --------------------------------------------------------------------
        # Save result
        # --------------------------------------------------------------------

        if shares is not None and source is not None:

            records.append(
                {
                    "date": today,
                    "ticker": ticker,
                    "shares": int(shares),
                    "price": pd.NA,
                    "price_date": pd.NaT,
                    "source": source,
                }
            )

            log.info(
                f"  {ticker:6s} → "
                f"{int(shares):,} shares "
                f"({source})"
            )

        else:

            missing.append(ticker)

            log.warning(
                f"  {ticker:6s} → "
                f"shares outstanding NOT FOUND"
            )

    # ------------------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------------------

    coverage = (
        len(records) / len(tickers) * 100
        if tickers
        else 0
    )

    log.info(
        f"Shares coverage: "
        f"{len(records)}/{len(tickers)} "
        f"({coverage:.1f}%)"
    )

    if missing:

        log.warning(
            f"Missing shares data "
            f"({len(missing)}): "
            f"{', '.join(missing)}"
        )

    if not records:

        return pd.DataFrame(
            columns=SHARES_COLUMNS
        )

    return pd.DataFrame(
        records,
        columns=SHARES_COLUMNS,
    )


# ============================================================================
# Fetch prices
# ============================================================================

def fetch_prices(
    tickers: list[str],
    start: date,
) -> pd.DataFrame:
    """
    Download daily Close prices using yfinance.

    Returns:

        date
        ticker
        price

    There is deliberately no assumption that today's date
    is a trading day.

    Example:

        Today = Saturday 2026-09-12

        Latest available price:
        2026-09-11

    """

    if not tickers:

        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "price",
            ]
        )

    try:

        raw = yf.download(
            tickers,
            start=str(start),
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if raw.empty:

            log.warning(
                "yfinance returned no price data"
            )

            return pd.DataFrame(
                columns=[
                    "date",
                    "ticker",
                    "price",
                ]
            )

        # --------------------------------------------------------------------
        # Multi ticker result
        # --------------------------------------------------------------------

        if isinstance(
            raw.columns,
            pd.MultiIndex,
        ):

            if "Close" in raw.columns.get_level_values(0):

                close = raw["Close"]

            else:

                close = raw

        # --------------------------------------------------------------------
        # Single ticker result
        # --------------------------------------------------------------------

        else:

            if "Close" in raw.columns:

                close = raw["Close"]

            else:

                close = raw

        if isinstance(
            close,
            pd.Series,
        ):

            close = close.to_frame(
                name=tickers[0]
            )

        records = []

        for dt, row in close.iterrows():

            normalized_date = (
                pd.Timestamp(dt)
                .normalize()
            )

            for ticker in tickers:

                if ticker not in row.index:
                    continue

                value = row[ticker]

                if pd.isna(value):
                    continue

                try:
                    price = float(value)
                except (TypeError, ValueError):
                    continue

                if price <= 0:
                    continue

                records.append(
                    {
                        "date": normalized_date,
                        "ticker": ticker,
                        "price": price,
                    }
                )

        prices = pd.DataFrame(
            records,
            columns=[
                "date",
                "ticker",
                "price",
            ],
        )

        if not prices.empty:

            log.info(
                f"Prices downloaded: "
                f"{len(prices):,} rows, "
                f"{prices['ticker'].nunique()} tickers, "
                f"{prices['date'].min().date()} → "
                f"{prices['date'].max().date()}"
            )

        return prices

    except Exception as exc:

        log.warning(
            f"Price fetch error: {exc}"
        )

        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "price",
            ]
        )


# ============================================================================
# Get latest price for each ticker
# ============================================================================

def get_latest_prices(
    prices_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Get the latest available trading price for every ticker.

    Returns:

        ticker
        price
        price_date
    """

    if prices_df.empty:

        return pd.DataFrame(
            columns=[
                "ticker",
                "price",
                "price_date",
            ]
        )

    df = prices_df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    ).dt.normalize()

    df = df.dropna(
        subset=[
            "ticker",
            "date",
            "price",
        ]
    )

    df = df.sort_values(
        [
            "ticker",
            "date",
        ]
    )

    latest = (
        df.groupby(
            "ticker",
            as_index=False,
        )
        .tail(1)
        [["ticker", "price", "date"]]
        .rename(
            columns={
                "date": "price_date",
            }
        )
        .reset_index(drop=True)
    )

    return latest


# ============================================================================
# Attach latest price to today's Shares
# ============================================================================

def attach_latest_prices(
    shares_df: pd.DataFrame,
    prices_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach the latest available trading price to today's Shares data.

    Example:

        Shares date:
            2026-09-12 Saturday

        Latest price:
            2026-09-11 Friday

    Result:

        date        ticker   shares       price   price_date
        2026-09-12  IBIT     1387360000   43.68   2026-09-11
    """

    if shares_df.empty:

        return shares_df.copy()

    latest = get_latest_prices(
        prices_df
    )

    result = shares_df.copy()

    # Remove possible old price fields.
    for col in [
        "price",
        "price_date",
    ]:

        if col in result.columns:
            result = result.drop(
                columns=[col]
            )

    result = result.merge(
        latest,
        on="ticker",
        how="left",
    )

    # Keep stable column order.
    for col in SHARES_COLUMNS:

        if col not in result.columns:
            result[col] = pd.NA

    result = result[
        SHARES_COLUMNS
    ]

    return result


# ============================================================================
# Find price valid for a particular date
# ============================================================================

def get_price_on_or_before(
    prices_df: pd.DataFrame,
    ticker: str,
    target_date: pd.Timestamp,
) -> tuple[float | None, pd.Timestamp | None]:
    """
    Return the latest available trading price on or before target_date.

    This is important for:

        weekends
        holidays
        delayed Shares Outstanding publication
    """

    if prices_df.empty:

        return None, None

    target_date = pd.Timestamp(
        target_date
    ).normalize()

    df = prices_df[
        prices_df["ticker"] == ticker
    ].copy()

    if df.empty:

        return None, None

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    ).dt.normalize()

    df = df[
        df["date"] <= target_date
    ].dropna(
        subset=[
            "date",
            "price",
        ]
    )

    if df.empty:

        return None, None

    row = (
        df.sort_values("date")
        .iloc[-1]
    )

    return (
        float(row["price"]),
        pd.Timestamp(
            row["date"]
        ).normalize(),
    )


# ============================================================================
# Compute estimated flows
# ============================================================================

def compute_flows(
    shares_state: pd.DataFrame,
    today_shares: pd.DataFrame,
    prices_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute estimated daily flow:

        estimated_flow = ΔShares × price

    Price selection:

        latest available trading price
        on or before the Shares date.

    IMPORTANT:

        This is NOT official ETF fund flow data.
    """

    rows = []

    if today_shares.empty:

        return pd.DataFrame(
            columns=FLOW_COLUMNS
        )

    for _, row in today_shares.iterrows():

        ticker = row["ticker"]

        today = pd.Timestamp(
            row["date"]
        ).normalize()

        # --------------------------------------------------------------------
        # Find price corresponding to Shares date
        # --------------------------------------------------------------------

        price, price_date = get_price_on_or_before(
            prices_df,
            ticker,
            today,
        )

        if price is None:

            rows.append(
                {
                    "date": today,
                    "ticker": ticker,
                    "flow_usd": float("nan"),
                    "flow_type": "estimated",
                }
            )

            log.debug(
                f"{ticker}: no valid price "
                f"on/before {today.date()}"
            )

            continue

        # --------------------------------------------------------------------
        # Find previous Shares Outstanding
        # --------------------------------------------------------------------

        prev = shares_state[
            shares_state["ticker"] == ticker
        ].copy()

        if prev.empty:

            rows.append(
                {
                    "date": today,
                    "ticker": ticker,
                    "flow_usd": float("nan"),
                    "flow_type": "estimated",
                }
            )

            log.debug(
                f"{ticker}: no previous Shares"
            )

            continue

        prev["date"] = pd.to_datetime(
            prev["date"],
            errors="coerce",
        ).dt.normalize()

        prev = prev[
            prev["date"] < today
        ].sort_values("date")

        if prev.empty:

            rows.append(
                {
                    "date": today,
                    "ticker": ticker,
                    "flow_usd": float("nan"),
                    "flow_type": "estimated",
                }
            )

            continue

        previous_row = prev.iloc[-1]

        try:

            prev_shares = int(
                previous_row["shares"]
            )

            curr_shares = int(
                row["shares"]
            )

        except (
            TypeError,
            ValueError,
        ):

            rows.append(
                {
                    "date": today,
                    "ticker": ticker,
                    "flow_usd": float("nan"),
                    "flow_type": "estimated",
                }
            )

            continue

        delta_shares = (
            curr_shares - prev_shares
        )

        flow_usd = (
            delta_shares * price
        )

        rows.append(
            {
                "date": today,
                "ticker": ticker,
                "flow_usd": flow_usd,
                "flow_type": "estimated",
            }
        )

        sign = "+" if flow_usd >= 0 else ""

        log.info(
            f"  {ticker:6s}: "
            f"{sign}{flow_usd / 1e6:.1f}M "
            f"(price ${price:.2f}, "
            f"price date {price_date.date()})"
        )

    return pd.DataFrame(
        rows,
        columns=FLOW_COLUMNS,
    )


# ============================================================================
# Compute AUM
# ============================================================================

def compute_aum(
    shares_df: pd.DataFrame,
    latest_prices: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute:

        AUM = Shares Outstanding × latest price

    Returns:

        ticker
        aum_usd
        updated_date
    """

    if shares_df.empty:

        return pd.DataFrame(
            columns=AUM_COLUMNS
        )

    today = pd.Timestamp.today().normalize()

    merged = shares_df.merge(
        latest_prices,
        on="ticker",
        how="left",
        suffixes=(
            "",
            "_latest",
        ),
    )

    records = []

    for _, row in merged.iterrows():

        shares = row.get(
            "shares"
        )

        price = row.get(
            "price"
        )

        if (
            pd.notna(shares)
            and pd.notna(price)
            and float(price) > 0
        ):

            aum = (
                float(shares)
                * float(price)
            )

            records.append(
                {
                    "ticker": row["ticker"],
                    "aum_usd": aum,
                    "updated_date": today,
                }
            )

            log.info(
                f"  AUM {row['ticker']}: "
                f"${aum / 1e9:.2f}B"
            )

    if not records:

        return pd.DataFrame(
            columns=AUM_COLUMNS
        )

    return pd.DataFrame(
        records,
        columns=AUM_COLUMNS,
    )


# ============================================================================
# Main
# ============================================================================

def main() -> None:

    # =========================================================================
    # 1. Load previous Shares Outstanding state
    # =========================================================================

    existing = load_existing()

    log.info(
        f"Scraping today's Shares Outstanding "
        f"for {len(ETF_TICKERS)} tickers …"
    )

    today_shares = fetch_shares_today(
        ETF_TICKERS
    )

    if today_shares.empty:

        log.warning(
            "No Shares Outstanding data returned — "
            "nothing to save"
        )

        sys.exit(0)

    active_tickers = (
        today_shares["ticker"]
        .unique()
        .tolist()
    )

    # =========================================================================
    # 2. Fetch prices
    # =========================================================================

    log.info(
        f"Fetching prices for "
        f"{len(active_tickers)} tickers …"
    )

    prices_df = fetch_prices(
        active_tickers,
        date.today() - timedelta(days=10),
    )

    if prices_df.empty:

        log.warning(
            "No prices returned"
        )

        latest_prices = pd.DataFrame(
            columns=[
                "ticker",
                "price",
                "price_date",
            ]
        )

    else:

        latest_prices = get_latest_prices(
            prices_df
        )

    # =========================================================================
    # 3. Attach price + price_date to today's Shares
    # =========================================================================

    today_shares = attach_latest_prices(
        today_shares,
        prices_df,
    )

    # Log price coverage
    price_count = (
        today_shares["price"]
        .notna()
        .sum()
    )

    price_coverage = (
        price_count / len(today_shares) * 100
        if len(today_shares) > 0
        else 0
    )

    log.info(
        f"Price coverage: "
        f"{price_count}/{len(today_shares)} "
        f"({price_coverage:.1f}%)"
    )

    # =========================================================================
    # 4. Update Shares state
    # =========================================================================

    combined_state = pd.concat(
        [
            existing,
            today_shares,
        ],
        ignore_index=True,
    )

    # Ensure columns exist.
    for col in SHARES_COLUMNS:

        if col not in combined_state.columns:
            combined_state[col] = pd.NA

    combined_state["date"] = pd.to_datetime(
        combined_state["date"],
        errors="coerce",
    ).dt.normalize()

    combined_state["price_date"] = pd.to_datetime(
        combined_state["price_date"],
        errors="coerce",
    ).dt.normalize()

    combined_state = combined_state[
        SHARES_COLUMNS
    ]

    # -------------------------------------------------------------------------
    # One row per ticker per Shares date.
    # -------------------------------------------------------------------------

    combined_state = (
        combined_state
        .drop_duplicates(
            subset=[
                "date",
                "ticker",
            ],
            keep="last",
        )
        .sort_values(
            [
                "ticker",
                "date",
            ]
        )
        .reset_index(drop=True)
    )

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined_state.to_csv(
        DATA_FILE,
        index=False,
        date_format="%Y-%m-%d",
    )

    log.info(
        f"Shares state: "
        f"{len(combined_state):,} rows "
        f"→ {DATA_FILE}"
    )

    # =========================================================================
    # 5. Compute estimated flows
    # =========================================================================

    new_flows = compute_flows(
        existing,
        today_shares,
        prices_df,
    )

    if new_flows.empty:

        log.info(
            "No new flows computed "
            "(first run or no previous state)"
        )

    else:

        if FLOWS_FILE.exists():

            try:

                flows_existing = pd.read_csv(
                    FLOWS_FILE,
                    parse_dates=["date"],
                )

            except Exception as exc:

                log.warning(
                    f"Could not read existing flows CSV: "
                    f"{exc}"
                )

                flows_existing = pd.DataFrame(
                    columns=FLOW_COLUMNS
                )

        else:

            flows_existing = pd.DataFrame(
                columns=FLOW_COLUMNS
            )

        # Make sure schema exists.
        for col in FLOW_COLUMNS:

            if col not in flows_existing.columns:
                flows_existing[col] = pd.NA

        flows_existing = flows_existing[
            FLOW_COLUMNS
        ]

        combined_flows = pd.concat(
            [
                flows_existing,
                new_flows,
            ],
            ignore_index=True,
        )

        combined_flows["date"] = pd.to_datetime(
            combined_flows["date"],
            errors="coerce",
        ).dt.normalize()

        combined_flows = (
            combined_flows
            .drop_duplicates(
                subset=[
                    "date",
                    "ticker",
                ],
                keep="last",
            )
            .sort_values(
                [
                    "ticker",
                    "date",
                ]
            )
            .reset_index(drop=True)
        )

        FLOWS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        combined_flows.to_csv(
            FLOWS_FILE,
            index=False,
            date_format="%Y-%m-%d",
        )

        log.info(
            f"Flows: "
            f"+{len(new_flows)} new rows "
            f"→ {FLOWS_FILE}"
        )

    # =========================================================================
    # 6. Compute AUM
    # =========================================================================

    log.info(
        "Computing AUM from "
        "Shares × latest price …"
    )

    aum_df = compute_aum(
        today_shares,
        latest_prices,
    )

    if not aum_df.empty:

        AUM_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        aum_df.to_csv(
            AUM_FILE,
            index=False,
            date_format="%Y-%m-%d",
        )

        log.info(
            f"AUM: "
            f"{len(aum_df)} tickers "
            f"→ {AUM_FILE}"
        )

    else:

        log.warning(
            "No AUM data generated"
        )

    # =========================================================================
    # 7. Summary
    # =========================================================================

    log.info("=" * 70)
    log.info("COLLECTION COMPLETE")
    log.info("=" * 70)

    log.info(
        f"Shares: "
        f"{len(today_shares)}/{len(ETF_TICKERS)}"
    )

    log.info(
        f"Prices: "
        f"{price_count}/{len(today_shares)}"
    )

    log.info(
        f"Flows: "
        f"{len(new_flows)}"
    )

    log.info(
        f"AUM: "
        f"{len(aum_df)}"
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    main()
