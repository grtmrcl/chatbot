# chatbot

Discord 上で動作する Python 製チャットボット。

## 必要なもの

- Docker / Docker Compose
- Discord Bot Token（[Discord Developer Portal](https://discord.com/developers/applications) で取得）

## セットアップ

`.env-sample` をコピーして `.env` を作成し、各値を設定する。

```bash
cp .env-sample .env
```

| 変数名 | 説明 |
|---|---|
| `token` | Discord Bot のトークン |
| `DISCORD_SERVERS` | 応答するチャンネルの設定（JSON） |
| `BRAVE_SEARCH_API_KEY` | Brave Search API キー |
| `OPENAI_API_KEY` | OpenAI API キー |
| `SSS_SPREADSHEETS` | `sss` / `ss-omikuji` コマンドで使用するスプレッドシートの識別子→ID マップ（JSON） |
| `EVENTS_SPREADSHEETS` | `event-register` / `event-remind` コマンドで使用するスプレッドシートの識別子→ID マップ（JSON） |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud プロジェクト ID（sss コマンド用 ADC） |

### DISCORD_SERVERS の設定例

```
DISCORD_SERVERS={"チャンネルID": {"response_type": "default"}}
```

キーにはチャンネルIDとサーバー（ギルド）IDを混在させることができる。チャンネルIDが優先される。

```
DISCORD_SERVERS={"サーバーID": {"response_type": "default"}, "特定チャンネルID": {"response_type": "special"}}
```

| フィールド | 説明 |
|---|---|
| `response_type` | レスポンス形式（省略時は `default`） |
| `event_remind_label` | 毎日10時（JST）に自動実行する `event-remind` の識別子。文字列または配列で複数指定可。省略するとそのチャンネルでは実行されない |
| `opebirth_label` | 毎日0時（JST）に自動実行する `opebirth` の識別子。文字列または配列で複数指定可。省略するとそのチャンネルでは実行されない |

```
DISCORD_SERVERS={"チャンネルID": {"response_type": "default", "event_remind_label": ["ak", "bk"], "opebirth_label": ["ak", "bk"]}}
```

チャンネル ID・サーバー ID は Discord の URL `https://discord.com/channels/サーバーID/チャンネルID` から確認できる。

## 起動

```bash
docker compose up -d
```

ログの確認:

```bash
docker compose logs -f chatbot
```

停止:

```bash
docker compose down
```

## テンプレートのカスタマイズ

`template.yml` でおみくじ・天気予報の応答テンプレートを編集できる。
テンプレートは [Jinja2](https://jinja.palletsprojects.com/) 形式。

## コマンド一覧

### Web 検索（Brave Search）

```
google <キーワード>
brave <キーワード>
g <キーワード>
```

#### 画像検索

```
image <キーワード>
i <キーワード>
```

#### サイト指定検索

| コマンド | エイリアス | 検索対象 |
|---|---|---|
| `wiki <キーワード>` | — | Wikipedia（Web検索） |
| `youtube <キーワード>` | `yt <キーワード>` | YouTube（動画検索） |
| `nicovideo <キーワード>` | `nico <キーワード>` | ニコニコ動画（動画検索） |

---

### 天気予報

[weather.tsukumijima.net](https://weather.tsukumijima.net/) から今日・明日の天気を取得する。

```
weather <地名>
```

```
weather 東京
```

#### エリア一覧

指定できる地名は都道府県ごとに確認できる。

```
weatherarea <都道府県名>
```

```
weatherarea 東京都
→ 東京, 大島, 八丈島, 父島
```

---
### 乗換案内

Yahoo!路線情報から経路を検索する。

```
route <出発地> <目的地> [オプション]
乗換 <出発地> <目的地> [オプション]
乗り換え <出発地> <目的地> [オプション]
乗換え <出発地> <目的地> [オプション]
```

```
route 新宿 渋谷
乗換 東京 新大阪 着
```

#### オプション

| オプション | 説明 |
|---|---|
| `発`（省略時のデフォルト） | 現在時刻出発 |
| `着` | 現在時刻到着 |
| `始発` | 始発 |
| `終電` | 終電 |
| `YYYYMMDD` | 日付指定（例: `20260401`） |
| `HHMM` | 時刻指定（例: `0930`）。`始発`・`終電`と同時指定不可 |

オプションは組み合わせて指定可能。

```
乗換 新宿 渋谷 1800 着
乗換 東京 新大阪 20260401 0930 発
```

---

### おみくじ

```
omikuji <タイプ>
```

`template.yml` に定義されたタイプを指定する。タイプを省略すると `unsei` が使われる。

```
omikuji unsei
omikuji
```

---

### ダイス

メッセージ中の `[NdM]` 記法をダイスロール結果に置換する。複数記述も可。

```
[NdM]        # N個のM面ダイスを振る
[NdM+K]      # 結果に K を加算
[NdM-K]      # 結果から K を減算
```

```
[2d6]
[1d20+5] で攻撃！
[3d6] [2d8-1]
```

制限: ダイス数は最大 100、面数は最大 10000。

---

### メッセージ削除

bot 自身の直前の発言を指定件数削除する。コマンド自体も削除される。

```
purge <件数>
```

```
purge 5
```

- チャンネルの履歴（最大500件）を遡って bot 自身のメッセージを新しい順に削除する
- コマンドメッセージも同時に削除される

---

### ChatGPT（現在無効）

ChatGPT との会話機能は現在コメントアウトされている。
有効化するには [lib/message_processer.py](lib/message_processer.py) の該当箇所のコメントを解除し、`.env` に `OPENAI_API_KEY` を設定する。

有効化後のコマンド:

| コマンド | 説明 |
|---|---|
| `gpt <メッセージ>` | ChatGPT に送信 |
| `gpt system <プロンプト>` | システムプロンプトを設定 |
| `gpt list` | 会話履歴の一覧 |
| `gpt detail <ID>` | 指定 ID の会話詳細 |
| `gpt id <ID>` | 使用する会話 ID を切替 |
| `gpt delete <ID>` | 指定 ID の会話を削除 |
| `gpt clear` | 全会話履歴を削除 |

---

### スプレッドシート検索

Google スプレッドシートから条件指定で検索し、一致した行の1列目の値を返す。
認証は Application Default Credentials (ADC) を使用する。

```
sss <識別子> <条件>...
```

```
sss ak 陣営=ライン生命　性別=女
sss ak 陣営=ライン生命、バベル　性別=女　職業=先鋒
```

#### 識別子の設定

`.env` の `SSS_SPREADSHEETS` に JSON 形式で定義する。

```
SSS_SPREADSHEETS={"ak": {"id": "スプレッドシートID", "sheet": "シート名"}}
```

- スプレッドシート ID は URL の `/d/{ID}/` の部分
- `sheet` を省略すると1枚目のシートを使用
- 複数シートを指定する場合は識別子ごとに `sheet` を変える

#### 検索条件の書式

| 書式 | 説明 |
|---|---|
| `列名=値` | 指定列に値が部分一致する行を絞り込む |
| `列名=値1,値2` | 全角・半角カンマで区切るとOR条件 |
| 複数条件をスペースで区切る | 全角・半角スペースで区切るとAND条件 |

#### 動作

- 1行目をヘッダー行として列名に使用する
- 条件に一致した行の1列目の値を `, ` で連結して返す

#### スプレッドシートおみくじ

`SSS_SPREADSHEETS` で定義したシートからランダムで1行取得して返す。条件を指定すると絞り込んだ中からランダム取得する。

```
ss-omikuji <識別子> [条件]...
opekuji [条件]...          # ss-omikuji ak のエイリアス
```

```
ss-omikuji ak
ss-omikuji ak 陣営=ライン生命　性別=女
opekuji
opekuji 陣営=ライン生命　性別=女
```

条件の書式は `sss` コマンドと同じ。

---

### イベント管理

`EVENTS_SPREADSHEETS` で定義したシートにイベントを登録・リマインドする。
シートの1行目はヘッダー行（列名）として使用する。

#### イベント登録

```
event-register <識別子> <イベント名> <開始日> <終了日>
```

```
event-register ak イベント名 20260301 20260326
event-register ak イベント名 2026-03-01 2026-03-26
```

- 日付は `yyyymmdd` または `yyyy-mm-dd` 形式
- 登録先の列1〜3に、イベント名・開始日（yyyy/mm/dd）・終了日（yyyy/mm/dd）を書き込む
- イベント名が重複する場合は登録せずにその旨を返す

#### イベントリマインダー

翌日に終了するイベントを通知する。「終了日」列を参照する。

```
event-remind <識別子> [日付]
```

```
event-remind ak
event-remind ak 20260325
```

- 日付を省略すると現在日を基準に翌日を検索
- 日付は `yyyymmdd` または `yyyy-mm-dd` 形式（テスト用）
- `DISCORD_SERVERS` の `event_remind_label` を設定すると毎日10時（JST）に自動実行。複数識別子の結果はまとめて通知

#### イベント削除

```
event-delete <識別子> <イベント名>
```

```
event-delete ak イベント名
```

- 1列目がイベント名と一致する行を削除する
- 該当するイベントがない場合はその旨を返す

---

### 誕生日通知

`SSS_SPREADSHEETS` で定義したシートの「誕生日」列を検索し、本日が誕生日のコードネームを返す。

```
opebirth [識別子] [日付]
```

```
opebirth
opebirth 0326
opebirth ak
opebirth ak 0326
```

- 識別子を省略すると `SSS_SPREADSHEETS` に定義されたすべての識別子に対して実行する
- 「誕生日」列の `M月D日` 形式（例: `3月26日`）、`yyyy/m/d` 形式（例: `2000/3/26`）、`m/d` 形式（例: `3/26`）に対応
- 日付を省略すると現在日を使用
- 日付は `mmdd` または `mm-dd` 形式（テスト用）
- `DISCORD_SERVERS` の `opebirth_label` を設定すると毎日0時（JST）に自動実行。複数識別子の結果はまとめて通知
