# ツール一覧

## get_events.py

イベント一覧ページから開催中のイベント情報を取得し、スプレッドシートに上書き書き込みするツール。

取得元に応じて以下のセクションを対象とする。

| ソースキー | 対象サイト | 取得セクション |
|---|---|---|
| `ak` | arknights.wikiru.jp | 左サイドの「イベント」内（「終了」および折りたたみ項目を除く） |
| `ef` | arknights-endfield.wikiru.jp | 左サイドの「開催中イベント」内（折りたたみ項目を除く） |

取得項目: イベント名 / 開始日 / 終了日

スプレッドシートは `EVENTS_SPREADSHEETS` 環境変数の識別子 `ak` / `ef` を使用する。実行のたびに自動取得分を上書きする。

**手動登録イベントの保持:** D列（手動登録）が `TRUE` の行はバッチ実行時に削除されず保持される。手動登録と同名のイベントが自動取得された場合は手動登録側が優先される。

### 実行

```bash
docker compose --profile batch build --no-cache

# AK・EF 両方を実行
docker compose --profile batch run --rm events

# アークナイツのみ
docker compose --profile batch run --rm ak-events

# アークナイツ エンドフィールドのみ
docker compose --profile batch run --rm ef-events
```

---

## get_operators.py

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
docker compose --profile batch build --no-cache

# AK・EF 両方を実行
docker compose --profile batch run --rm operators

# アークナイツのみ
docker compose --profile batch run --rm ak-operators

# アークナイツ エンドフィールドのみ
docker compose --profile batch run --rm ef-operators
```


## バッチ処理

スプレッドシートへのデータ書き込みバッチ。詳細は [batch/README.md](batch/README.md) を参照。

| バッチ | コマンド | 説明 |
|---|---|---|
| オペレーター情報更新 | `docker compose --profile batch run --rm operators` | AK・EF 両方のオペレーター情報を取得してスプレッドシートに書き込む |
| イベント情報更新 | `docker compose --profile batch run --rm events` | AK・EF 両方の開催中イベントを取得してスプレッドシートに上書きする |

### スケジュール実行（crontab）

`crontab.example` を参考に `crontab -e` で設定する。

```cron
# オペレーター情報更新: 毎週木曜 11:15
15 11 * * 4 cd /path/to/chatbot && docker compose --profile batch run --rm operators >> /var/log/chatbot-batch.log 2>&1

# イベント情報更新: 毎日 11:45
45 11 * * * cd /path/to/chatbot && docker compose --profile batch run --rm events >> /var/log/chatbot-batch.log 2>&1
```

`/path/to/chatbot` はリポジトリの絶対パスに置き換えること。

---
