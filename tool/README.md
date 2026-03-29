# ツール一覧

## operators.py

オペレーター一覧ページからプロフィール情報を取得し、スプレッドシートに書き込むツール。

`display:none` / `visibility:hidden` が付いたデフォルト非表示の要素は取得対象から除外する。

`--source` オプションで取得元を切り替えられる。

| ソースキー | 対象 | 環境変数 |
|---|---|---|
| `ak` | アークナイツ (arknights.wikiru.jp) | `AK_OPERATORS_SPREADSHEET` |
| `ef` | アークナイツ エンドフィールド (arknights-endfield.wikiru.jp) | `EF_OPERATORS_SPREADSHEET` |

### 事前準備

#### 1. Google Cloud の設定

[Google Cloud Console](https://console.cloud.google.com/) で以下を有効化する。

- Google Sheets API

#### 2. OAuth クライアントID の作成

gcloud のデフォルトクライアントID では Google Sheets API のスコープが使用できないため、独自の OAuth クライアントID が必要。

[Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > 認証情報 > 「認証情報を作成」> 「OAuth クライアントID」

- アプリケーションの種類: **デスクトップアプリ**
- JSON ファイルをダウンロードし、任意の場所に保存（例: `~/client_secret.json`）

#### 3. 認証（初回のみ）

```bash
gcloud auth application-default login \
    --no-browser \
    --client-id-file=~/client_secret.json \
    --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets
```

クォータプロジェクトを設定する（警告が出た場合）。

```bash
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

または `.env` に以下を追記する。

```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_QUOTA_PROJECT=your-project-id
```

#### 4. スプレッドシートの準備

1. Google スプレッドシートを新規作成する
2. URLの `/d/{ID}/` の部分をコピーする
3. `.env` に設定する

```
# JSON形式でIDとシート名を同時に指定（sheet を省略すると1枚目のシートを使用）
AK_OPERATORS_SPREADSHEET={"id": "SpreadsheetID", "sheet": "シート名"}
EF_OPERATORS_SPREADSHEET={"id": "SpreadsheetID", "sheet": "シート名"}
```

### 実行

```bash
docker compose --profile tools build --no-cache

# AK・EF 両方を実行
docker compose --profile tools run --rm operators

# アークナイツのみ
docker compose --profile tools run --rm ak-operators

# アークナイツ エンドフィールドのみ
docker compose --profile tools run --rm ef-operators
```
