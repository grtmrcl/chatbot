#!/usr/bin/env python3
"""
アークナイツ キャラクタープロフィール一覧 スプレッドシート書き込みツール

usage:
    python tool/ak_operators.py

環境変数(.env):
    AK_OPERATORS_SPREADSHEET_ID  : 書き込み先スプレッドシートのID

認証:
    Application Default Credentials (ADC) を使用します。
    - ローカル実行時:
        gcloud auth application-default login \\
            --client-id-file=~/client_secret.json \\
            --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets
    - GCP 環境 / Workload Identity 連携:
        環境に紐づいた認証情報が自動的に使用されます。
"""
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

# キャラクター一覧ページ
LIST_URL = "https://arknights.wikiru.jp/?キャラクター一覧"
BASE_URL = "https://arknights.wikiru.jp/"

# 取得対象セクション（順序通り）
SECTIONS = ["sixstar", "fivestar", "fourstar", "threestar", "twostar", "onestar"]

# セクション終端の区切りID（#onestar の終わりを示す）
SECTION_END = "scenariocharacter"


def fetch_operator_urls() -> list[str]:
    """一覧ページの各セクション（#sixstar〜#onestar）からオペレーターURLを取得する"""
    res = requests.get(LIST_URL, timeout=15)
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    stop_ids = set(SECTIONS) | {SECTION_END}

    urls: list[str] = []
    for section_id in SECTIONS:
        heading = soup.find(id=section_id)
        if heading is None:
            logger.warning("セクションが見つかりません: #%s", section_id)
            continue

        # 次のセクション見出し（または終端）までの範囲でリンクを収集
        section_urls: list[str] = []
        for sibling in heading.find_all_next():
            if sibling.get("id") in stop_ids and sibling.get("id") != section_id:
                break
            if sibling.name == "a":
                href = sibling.get("href", "")
                if href and href.startswith("?") and not any(c in href for c in ["#", "="]):
                    full_url = urljoin(BASE_URL, href)
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

    # プロフィールテーブルを特定する
    # 「コードネーム」を含む th を持つテーブルを優先
    profile_table = None
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        if "コードネーム" in ths or "氏名" in ths:
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
    spreadsheet_id = os.environ.get("AK_OPERATORS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("環境変数 AK_OPERATORS_SPREADSHEET_ID が設定されていません")

    urls = fetch_operator_urls()
    if not urls:
        raise SystemExit("URLが1件も取得できませんでした")

    creds, _ = google.auth.default(scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id).sheet1

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

            # 「氏名」はコードネームとして扱う
            if "氏名" in profile and "コードネーム" not in profile:
                profile["コードネーム"] = profile.pop("氏名")

            logger.info("profile: %s", profile)

            # コードネームが重複する場合はスキップ
            codename = profile.get("コードネーム", "")
            if codename and codename in seen_codenames:
                logger.info("スキップ（重複）: %s", codename)
                time.sleep(REQUEST_INTERVAL)
                continue
            if codename:
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
