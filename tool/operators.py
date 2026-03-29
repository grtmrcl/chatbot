#!/usr/bin/env python3
"""
オペレーター プロフィール一覧 スプレッドシート書き込みツール

usage:
    python tool/operators.py --source ak
    python tool/operators.py --source ef

環境変数(.env):
    AK_OPERATORS_SPREADSHEET  : AK 書き込み先（JSON: {"id": "...", "sheet": "..."} または スプレッドシートID文字列）
    EF_OPERATORS_SPREADSHEET  : EF 書き込み先（同上）

認証:
    Application Default Credentials (ADC) を使用します。
    - ローカル実行時:
        gcloud auth application-default login \\
            --client-id-file=~/client_secret.json \\
            --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets
    - GCP 環境 / Workload Identity 連携:
        環境に紐づいた認証情報が自動的に使用されます。
"""
import argparse
import json
import logging
import os
import time
from urllib.parse import urljoin, unquote

import google.auth
import gspread
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER_FIXED = ["コードネーム", "URL"]

# サーバー負荷軽減のためのリクエスト間隔（秒）
REQUEST_INTERVAL = 1.0

SOURCES: dict[str, dict] = {
    "ak": {
        "list_url": "https://arknights.wikiru.jp/?キャラクター一覧",
        "base_url": "https://arknights.wikiru.jp/",
        "sections": ["sixstar", "fivestar", "fourstar", "threestar", "twostar", "onestar"],
        "section_end": "scenariocharacter",
        "link_prefix": "./?",
        "spreadsheet_env": "AK_OPERATORS_SPREADSHEET",
    },
    "ef": {
        "list_url": "https://arknights-endfield.wikiru.jp/?オペレーター一覧",
        "base_url": "https://arknights-endfield.wikiru.jp/",
        "sections": ["sixstar", "fivestar", "fourstar"],
        "section_end": "comment",
        "link_prefix": "./?",
        "spreadsheet_env": "EF_OPERATORS_SPREADSHEET",
    },
}


def _is_hidden(tag) -> bool:
    """タグまたはその祖先がデフォルトで非表示かどうかを判定する"""
    for el in [tag, *tag.parents]:
        style = el.get("style", "") if hasattr(el, "get") else ""
        normalized = style.replace(" ", "").lower()
        if "display:none" in normalized or "visibility:hidden" in normalized:
            return True
    return False


def fetch_operator_urls(source: dict) -> list[str]:
    """一覧ページの各セクションからオペレーターURLを取得する"""
    res = requests.get(source["list_url"], timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    sections: list[str] = source["sections"]
    section_end: str = source["section_end"]
    base_url: str = source["base_url"]
    link_prefix: str = source["link_prefix"]

    stop_ids = set(sections)
    if section_end:
        stop_ids.add(section_end)

    urls: list[str] = []
    for section_id in sections:
        heading = soup.find(id=section_id)
        if heading is None:
            logger.warning("セクションが見つかりません: #%s", section_id)
            continue

        # 次のセクション見出し（または終端）までの範囲でリンクを収集
        section_urls: list[str] = []
        for sibling in heading.find_all_next():
            if sibling.get("id") in stop_ids and sibling.get("id") != section_id:
                break
            if sibling.name == "a" and not _is_hidden(sibling):
                href = sibling.get("href", "")
                if href and href.startswith(link_prefix) and not any(c in href for c in ["#", "="]):
                    full_url = urljoin(base_url, href)
                    if full_url not in urls and full_url not in section_urls:
                        section_urls.append(full_url)

        logger.info("#%s: %d 件", section_id, len(section_urls))
        urls.extend(section_urls)

    logger.info("合計 %d 件のURLを取得しました", len(urls))
    return urls


def fetch_profile(url: str) -> dict[str, str]:
    """オペレーターページからプロフィールテーブルの各項目を取得する"""
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    profile: dict[str, str] = {}

    # 「コードネーム」「氏名」「名前」のいずれかを含む th を持つテーブルを特定する
    profile_table = None
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        if "コードネーム" in ths or "氏名" in ths or "名前" in ths:
            profile_table = table
            break

    if profile_table is None:
        logger.warning("プロフィールテーブルが見つかりません: %s", url)
        return profile

    for row in profile_table.find_all("tr"):
        th = row.find("th")
        td = th.find_next_sibling("td") if th else None
        if th and td and "width:100px" in th.get("style", ""):
            key = th.get_text(strip=True)
            value = td.get_text(strip=True)
            if key:
                profile[key] = value

    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="オペレーター情報をスプレッドシートに書き込む")
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        required=True,
        help="取得元ソース（ak: アークナイツ / ef: エンドフィールド）",
    )
    args = parser.parse_args()

    logger.info("source: %s", args.source)
    source = SOURCES[args.source]
    spreadsheet_env = source["spreadsheet_env"]
    spreadsheet_val = os.environ.get(spreadsheet_env)
    if not spreadsheet_val:
        raise SystemExit(f"環境変数 {spreadsheet_env} が設定されていません")

    try:
        spreadsheet_entry = json.loads(spreadsheet_val)
    except json.JSONDecodeError:
        spreadsheet_entry = spreadsheet_val

    if isinstance(spreadsheet_entry, str):
        spreadsheet_id = spreadsheet_entry
        sheet_name = None
    else:
        spreadsheet_id = spreadsheet_entry.get("id", "")
        sheet_name = spreadsheet_entry.get("sheet")

    if not spreadsheet_id:
        raise SystemExit(f"環境変数 {spreadsheet_env} にスプレッドシートIDが設定されていません")

    urls = fetch_operator_urls(source)
    if not urls:
        raise SystemExit("URLが1件も取得できませんでした")

    creds, _ = google.auth.default(scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    sheet = spreadsheet.worksheet(sheet_name) if sheet_name else spreadsheet.sheet1

    # 既存ヘッダーを取得（未記入の場合は固定ヘッダーで初期化）
    headers: list[str] = sheet.row_values(1) or list(HEADER_FIXED)
    header_index: dict[str, int] = {h: i for i, h in enumerate(headers)}

    # 既存データのコードネーム一覧を取得（重複スキップ用）
    existing_rows = sheet.get_all_values()
    codename_col = header_index.get("コードネーム")
    seen_codenames: set[str] = set()
    if codename_col is not None:
        for row_vals in existing_rows[1:]:  # ヘッダー行を除く
            if codename_col < len(row_vals) and row_vals[codename_col]:
                seen_codenames.add(row_vals[codename_col])

    for i, url in enumerate(urls, start=1):
        logger.info("[%d/%d] %s", i, len(urls), url)
        try:
            # URLからキャラ名を取得し、登録済みであればページ取得前にスキップ
            url_name = unquote(url.split("?", 1)[-1])
            if url_name in seen_codenames:
                logger.info("スキップ（登録済み）: %s", url_name)
                continue

            profile = fetch_profile(url)

            # 「氏名」「名前」はコードネームとして扱う
            for name_key in ("氏名", "名前"):
                if name_key in profile and "コードネーム" not in profile:
                    profile["コードネーム"] = profile.pop(name_key)
                    break

            logger.info("profile: %s", profile)

            # コードネームが取得できない場合はスキップ（一覧ページ等）
            codename = profile.get("コードネーム", "")
            if not codename:
                logger.info("スキップ（コードネームなし）: %s", url)
                time.sleep(REQUEST_INTERVAL)
                continue

            # コードネームが重複する場合はスキップ
            if codename in seen_codenames:
                logger.info("スキップ（重複）: %s", codename)
                time.sleep(REQUEST_INTERVAL)
                continue
            seen_codenames.add(codename)

            # 新規キーがあればヘッダーを拡張
            new_keys = [k for k in profile if k not in header_index]
            if new_keys:
                for key in new_keys:
                    header_index[key] = len(headers)
                    headers.append(key)
                sheet.update("A1", [headers])

            # データ行を構築して追記
            row = [""] * len(headers)
            row[header_index["URL"]] = url
            for key, value in profile.items():
                row[header_index[key]] = value
            sheet.append_row(row, value_input_option="RAW")

            logger.info("書き込み完了: %s", url)
        except Exception:
            logger.exception("失敗: %s", url)
        time.sleep(REQUEST_INTERVAL)


if __name__ == "__main__":
    main()
