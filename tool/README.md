# ツール一覧

## ak_operators.py

アークナイツ キャラクター一覧ページからプロフィール情報を取得し、スプレッドシートに書き込むツール。

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
AK_OPERATORS_SPREADSHEET_ID=コピーしたID
```

### 実行

```bash
docker compose --profile tools build --no-cache
docker compose --profile tools run --rm ak-operators
```
