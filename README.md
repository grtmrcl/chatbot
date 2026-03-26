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

### DISCORD_SERVERS の設定例

```
DISCORD_SERVERS={"チャンネルID": {"response_type": "default"}}
```

チャンネル ID は Discord の URL `https://discord.com/channels/サーバーID/チャンネルID` の末尾の数字。

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
tenki <地名>
weather <地名>
```

```
tenki 東京
weather 大阪
```

#### エリア一覧

指定できる地名は都道府県ごとに確認できる。

```
tenkiarea <都道府県名>
```

```
tenkiarea 東京都
→ 東京, 大島, 八丈島, 父島
```

---

### 乗換案内

Navitime から経路を検索する。

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
