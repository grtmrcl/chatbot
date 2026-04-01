# 概要
Discord上で動作するチャットボット

## アーキテクチャ
- docker
- Python3

# must do
paths: lib/*
- update README.md

paths: batch/*
- update batch/README.md

# 実装手順

1. developブランチから作業ブランチを作成する
2. 実装の計画を立てる
3. 実装する
4. code-revier エージェントでレビューし、必要に応じて修正する
5. testを書いて実行し、必要に応じて修正する
6. developへマージし、mainへPRを出す

# Gitブランチ運用ルール

- **開発は必ず `develop` ブランチをベースとすること**
- `main` ブランチには直接コミット・プッシュしないこと
- 新機能・修正はすべて `develop` から派生したブランチで作業し、`develop` へマージすること
- `main` へのマージは `develop` からのPRを通じてのみ行うこと
