from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def previous_business_day(base: date | None = None) -> date:
    """Return the previous weekday (Mon-Fri)."""
    if base is None:
        base = datetime.now().date()

    target = base - timedelta(days=1)
    while target.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        target -= timedelta(days=1)

    return target


def _latest_two_closes(symbol: str, target_day: date) -> tuple[float, float] | None:
    """
    Fetch close prices and return (current_close, previous_close).
    Uses a buffered date range to handle holidays.
    Returns None when the remote API is unavailable for a symbol.
    """
    start = target_day - timedelta(days=14)
    end = target_day + timedelta(days=1)

    try:
        df = fdr.DataReader(symbol, start, end)
    except Exception as exc:  # network/provider errors
        print(f"[WARN] failed to fetch {symbol}: {exc}")
        return None

    if df.empty:
        print(f"[WARN] no data returned for symbol: {symbol}")
        return None

    df = df.sort_index()
    closes = df["Close"].dropna()
    if closes.empty:
        print(f"[WARN] close data missing for symbol: {symbol}")
        return None

    if len(closes) < 2:
        current = float(closes.iloc[-1])
        return current, current

    current = float(closes.iloc[-1])
    previous = float(closes.iloc[-2])
    return current, previous


def build_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    report_day = previous_business_day()

    index_symbols = {
        "KOSPI": "KS11",
        "KOSDAQ": "KQ11",
        "S&P 500": "US500",
        "NASDAQ": "IXIC",
        "DOW": "DJI",
    }

    fx_symbols = {
        "USD/KRW": "USD/KRW",
        "USD/JPY": "USD/JPY",
        "EUR/USD": "EUR/USD",
    }

    warnings: list[str] = []

    index_rows: list[dict[str, float | str]] = []
    for name, symbol in index_symbols.items():
        closes = _latest_two_closes(symbol, report_day)
        if closes is None:
            warnings.append(f"지수 데이터 수집 실패: {name}({symbol})")
            continue

        current, previous = closes
        change = current - previous
        pct = (change / previous * 100) if previous else 0.0
        index_rows.append(
            {
                "구분": name,
                "종가": round(current, 2),
                "등락": round(change, 2),
                "등락률(%)": round(pct, 2),
            }
        )

    fx_rows: list[dict[str, float | str]] = []
    for name, symbol in fx_symbols.items():
        closes = _latest_two_closes(symbol, report_day)
        if closes is None:
            warnings.append(f"환율 데이터 수집 실패: {name}({symbol})")
            continue

        current, previous = closes
        change = current - previous
        pct = (change / previous * 100) if previous else 0.0
        fx_rows.append(
            {
                "구분": name,
                "종가": round(current, 4),
                "등락": round(change, 4),
                "등락률(%)": round(pct, 2),
            }
        )

    return pd.DataFrame(index_rows), pd.DataFrame(fx_rows), warnings


def _table_or_empty_message(df: pd.DataFrame, empty_message: str) -> str:
    if df.empty:
        return f"<p>{empty_message}</p>"
    return df.to_html(index=False, border=0, classes="tbl")


def render_html(
    index_df: pd.DataFrame,
    fx_df: pd.DataFrame,
    report_day: date,
    warnings: list[str],
) -> str:
    index_html = _table_or_empty_message(index_df, "지수 데이터가 없습니다.")
    fx_html = _table_or_empty_message(fx_df, "환율 데이터가 없습니다.")

    warning_html = ""
    if warnings:
        warning_items = "".join(f"<li>{w}</li>" for w in warnings)
        warning_html = f"""
  <h2>수집 경고</h2>
  <ul>{warning_items}</ul>
"""

    return f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <title>전일 시장 요약 - {report_day}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    h1 {{ font-size: 24px; margin-bottom: 8px; }}
    .sub {{ color: #666; margin-bottom: 20px; }}
    h2 {{ margin-top: 24px; font-size: 18px; border-left: 4px solid #2b6cb0; padding-left: 8px; }}
    table.tbl {{ border-collapse: collapse; width: 100%; max-width: 860px; }}
    .tbl th, .tbl td {{ border: 1px solid #ddd; padding: 8px 10px; text-align: center; }}
    .tbl th {{ background: #f5f7fa; }}
  </style>
</head>
<body>
  <h1>전일 시장 요약</h1>
  <div class=\"sub\">기준일: {report_day} / 생성시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

  <h2>주요 지수</h2>
  {index_html}

  <h2>환율</h2>
  {fx_html}
  {warning_html}
</body>
</html>
"""


def save_report() -> Path:
    report_day = previous_business_day()
    index_df, fx_df, warnings = build_snapshot()
    html = render_html(index_df, fx_df, report_day, warnings)

    out_path = REPORT_DIR / f"market_{report_day}.html"
    out_path.write_text(html, encoding="utf-8")

    latest_path = REPORT_DIR / "latest.html"
    latest_path.write_text(html, encoding="utf-8")

    return out_path


if __name__ == "__main__":
    saved = save_report()
    print(f"[OK] report saved: {saved}")
