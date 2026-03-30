#!/usr/bin/env python3
"""
イベント一覧 スプレッドシート書き込みツール

usage:
    python batch/get_events.py --source ak
    python batch/get_events.py --source ef

環境変数(.env):
    EVENTS_SPREADSHEETS : イベント書き込み先（JSON: {"ak": {"id": "...", "sheet": "..."}, "ef": {...}}）

認証:
    Application Default Credentials (ADC) を使用します。
    - ローカル実行時:
        gcloud auth application-default login \\
            --client-id-file=~/client_secret.json \\
            --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets
"""
import argparse
import json
import logging
import os
import re

import google.auth
import gspread
import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = ["イベント名", "開始日", "終了日"]

DATE_FULL_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
DATE_SHORT_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
DATE_RANGE_SEP_RE = re.compile(r"[〜～]")
DATE_RANGE_RE = re.compile(r"[（(](.+?[〜～].+?)[）)]")
TITLE_NOISE_RE = re.compile(r"\?+$")  # span.noexists 内 <a>?</a> 由来の末尾 ?
CATEGORY_PREFIXES = ("期間限定イベント",)

SOURCES: dict[str, dict] = {
    "ak": {
        "url": "https://arknights.wikiru.jp/",
        "strategy": "ak",
    },
    "ef": {
        "url": "https://arknights-endfield.wikiru.jp/",
        "strategy": "ef",
    },
}


def _is_in_collapsed_region(tag: Tag) -> bool:
    """タグが折りたたまれた領域（rgn-content display:none）の内側にあるかを判定する"""
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        if "rgn-content" in parent.get("class", []):
            style = parent.get("style", "")
            if re.search(r"display\s*:\s*none", style, re.IGNORECASE):
                return True
    return False


def _parse_date_range(text: str) -> tuple[str, str]:
    """
    日付範囲テキストから（開始日, 終了日）を YYYY/MM/DD 形式で返す。
    取得できない場合は空文字を返す。
    """
    parts = DATE_RANGE_SEP_RE.split(text, maxsplit=1)
    if len(parts) != 2:
        return "", ""

    start_text, end_text = parts[0].strip(), parts[1].strip()

    sm = DATE_FULL_RE.search(start_text)
    if not sm:
        return "", ""
    start_year = int(sm.group(1))
    start_month = int(sm.group(2))
    start_date = f"{start_year}/{start_month:02d}/{int(sm.group(3)):02d}"

    em = DATE_FULL_RE.search(end_text)
    if em:
        end_year, end_month = int(em.group(1)), int(em.group(2))
        end_date = f"{end_year}/{end_month:02d}/{int(em.group(3)):02d}"
    else:
        em2 = DATE_SHORT_RE.search(end_text)
        if em2:
            end_month = int(em2.group(1))
            end_day = int(em2.group(2))
            end_year = start_year if end_month >= start_month else start_year + 1
            end_date = f"{end_year}/{end_month:02d}/{end_day:02d}"
        else:
            end_date = ""

    return start_date, end_date


def _extract_events_from_p(p: Tag) -> list[dict]:
    """
    p タグのテキストからイベント情報を抽出する。
    get_text() で平文化し、日付範囲パターンを軸に直前テキストをタイトルとして取得する。
    """
    text = p.get_text(strip=True)
    events = []
    prev_end = 0
    for m in DATE_RANGE_RE.finditer(text):
        title = text[prev_end: m.start()].strip()
        title = TITLE_NOISE_RE.sub("", title).strip()
        for prefix in CATEGORY_PREFIXES:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
                break
        logger.debug("  タイトル: %s, 日付: %s", title, m.group(1))
        if title:
            start_date, end_date = _parse_date_range(m.group(1))
            logger.debug("  パース結果: start=%s end=%s", start_date, end_date)
            if start_date:
                events.append({"title": title, "start": start_date, "end": end_date})
        prev_end = m.end()
    return events


def _fetch_ak_events(url: str) -> list[dict]:
    """
    AK wiki からイベントを取得する。
    - 「イベント一覧」リンクを含む hr 区切り内の p タグを走査
    - 次の hr タグ（次セクション境界）が来たら終了
    - 「終了」セクションに到達したら以降をスキップ
    - 折りたたみ領域（rgn-container / rgn-content display:none）はスキップ
    """
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    menubar = soup.find("td", class_="menubar")
    if menubar is None:
        logger.error("td.menubar が見つかりません")
        return []
    logger.debug("AK: td.menubar を検出しました")

    event_heading_p = None
    for p in menubar.find_all("p"):
        if p.find("a", title="イベント一覧"):
            event_heading_p = p
            break

    if event_heading_p is None:
        logger.error("AK: イベント見出しが見つかりません")
        return []
    logger.debug("AK: イベント見出し段落を検出: %s", event_heading_p.get_text(strip=True)[:80])

    events: list[dict] = []
    hit_end_section = False

    for sibling in event_heading_p.find_next_siblings():
        if not isinstance(sibling, Tag):
            continue

        # hr タグ（次セクション境界）が来たら終了
        if sibling.name == "hr":
            logger.debug("AK: hr タグに到達 → セクション終了")
            break

        # 折りたたみ領域はスキップ
        if "rgn-container" in sibling.get("class", []):
            logger.debug("AK: rgn-container をスキップ")
            continue

        if sibling.name != "p":
            logger.debug("AK: p 以外のタグをスキップ: <%s>", sibling.name)
            continue

        if _is_in_collapsed_region(sibling):
            logger.debug("AK: 折りたたみ領域内の p をスキップ: %s", sibling.get_text(strip=True)[:40])
            continue

        # 「終了」セクションに到達したら以降をスキップ
        strong = sibling.find("strong")
        if strong and strong.get_text(strip=True) == "終了":
            logger.debug("AK: 「終了」セクション検出 → 以降スキップ")
            hit_end_section = True
            continue

        if hit_end_section:
            continue

        # 常設イベント（期限なし）はスキップ
        if sibling.get_text(strip=True).startswith("長期探索（常設）"):
            logger.debug("AK: 常設イベントをスキップ")
            continue

        logger.debug("AK: p タグを処理: %s", sibling.get_text(strip=True)[:80])
        logger.debug("AK: p タグ HTML: %s", str(sibling)[:300])
        before = len(events)
        events.extend(_extract_events_from_p(sibling))
        after = len(events)
        if after > before:
            logger.debug("AK: %d 件追加 (累計 %d 件)", after - before, after)

    return events


def _fetch_ef_events(url: str) -> list[dict]:
    """
    EF wiki からイベントを取得する。
    - 「開催中イベント」見出し段落以降の p タグを走査
    - hr タグ（次セクション境界）または次の大見出し段落が現れたら停止
    - 折りたたみ領域（rgn-container / rgn-content display:none）はスキップ
    """
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    menubar = soup.find("td", class_="menubar")
    if menubar is None:
        logger.error("td.menubar が見つかりません")
        return []
    logger.debug("EF: td.menubar を検出しました")

    event_heading_p = None
    for p in menubar.find_all("p"):
        strong = p.find("strong")
        if strong and "開催中イベント" in strong.get_text():
            event_heading_p = p
            break

    if event_heading_p is None:
        logger.error("EF: 開催中イベント見出しが見つかりません")
        return []
    logger.debug("EF: 開催中イベント見出し段落を検出: %s", event_heading_p.get_text(strip=True)[:80])

    events: list[dict] = []

    for sibling in event_heading_p.find_next_siblings():
        if not isinstance(sibling, Tag):
            continue

        # hr タグ（次セクション境界）が来たら終了
        if sibling.name == "hr":
            logger.debug("EF: hr タグに到達 → セクション終了")
            break

        # 折りたたみ領域はスキップ
        if "rgn-container" in sibling.get("class", []):
            logger.debug("EF: rgn-container をスキップ")
            continue

        if sibling.name != "p":
            logger.debug("EF: p 以外のタグをスキップ: <%s>", sibling.name)
            continue

        if _is_in_collapsed_region(sibling):
            logger.debug("EF: 折りたたみ領域内の p をスキップ: %s", sibling.get_text(strip=True)[:40])
            continue

        # 次の大見出し段落（font-size:16px の span を含む）が来たら終了
        span = sibling.find("span", style=True)
        if span:
            style = span.get("style", "").replace(" ", "").lower()
            if "font-size:16px" in style and "display:inline-block" in style:
                logger.debug("EF: 次の大見出し段落を検出 → セクション終了: %s", sibling.get_text(strip=True)[:40])
                break

        logger.debug("EF: p タグを処理: %s", sibling.get_text(strip=True)[:80])
        before = len(events)
        events.extend(_extract_events_from_p(sibling))
        after = len(events)
        if after > before:
            logger.debug("EF: %d 件追加 (累計 %d 件)", after - before, after)

    return events


def fetch_events(source: dict) -> list[dict]:
    strategy = source["strategy"]
    url = source["url"]
    logger.info("イベント取得開始: %s (%s)", strategy, url)

    if strategy == "ak":
        events = _fetch_ak_events(url)
    elif strategy == "ef":
        events = _fetch_ef_events(url)
    else:
        raise ValueError(f"不明なストラテジー: {strategy}")

    logger.info("%d 件のイベントを取得しました", len(events))
    return events


def _open_sheet(entry: str | dict) -> gspread.Worksheet:
    if isinstance(entry, str):
        spreadsheet_id, sheet_name = entry, None
    else:
        spreadsheet_id = entry.get("id", "")
        sheet_name = entry.get("sheet")

    if not spreadsheet_id:
        raise ValueError("スプレッドシートIDが設定されていません")

    creds, _ = google.auth.default(scopes=SCOPES)
    client = gspread.authorize(creds)
    wb = client.open_by_key(spreadsheet_id)
    return wb.worksheet(sheet_name) if sheet_name else wb.sheet1


def write_to_sheet(sheet: gspread.Worksheet, events: list[dict]) -> None:
    """イベント一覧をスプレッドシートに上書き書き込みする"""
    rows = [HEADER] + [[e["title"], e["start"], e["end"]] for e in events]
    sheet.clear()
    sheet.update("A1", rows, value_input_option="RAW")
    logger.info("%d 件をスプレッドシートに書き込みました", len(events))


def main() -> None:
    parser = argparse.ArgumentParser(description="イベント情報をスプレッドシートに書き込む")
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        required=True,
        help="取得元ソース（ak: アークナイツ / ef: エンドフィールド）",
    )
    args = parser.parse_args()

    spreadsheets_val = os.environ.get("EVENTS_SPREADSHEETS")
    if not spreadsheets_val:
        raise SystemExit("環境変数 EVENTS_SPREADSHEETS が設定されていません")

    try:
        spreadsheets = json.loads(spreadsheets_val)
    except json.JSONDecodeError as e:
        raise SystemExit(f"EVENTS_SPREADSHEETS のJSON解析に失敗しました: {e}") from e

    entry = spreadsheets.get(args.source)
    if not entry:
        raise SystemExit(f"EVENTS_SPREADSHEETS に '{args.source}' が設定されていません")

    source = SOURCES[args.source]
    events = fetch_events(source)
    if not events:
        logger.warning("イベントが取得できませんでした")

    sheet = _open_sheet(entry)
    write_to_sheet(sheet, events)


if __name__ == "__main__":
    main()
