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

# Gitブランチ運用ルール

- **開発は必ず `develop` ブランチをベースとすること**
- `main` ブランチには直接コミット・プッシュしないこと
- 新機能・修正はすべて `develop` から派生したブランチで作業し、`develop` へマージすること
- `main` へのマージは `develop` からのPRを通じてのみ行うこと
