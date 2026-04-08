# harden-runner 検証: GitHub API 可視化

## 概要

harden-runner の GitHub API 可視化機能を検証した。
ワークフロー実行中に行われた GitHub API 呼び出しの HTTPメソッドとエンドポイントパスが記録されるか確認した。

## 検証内容

以下の API 呼び出しを composite action でテストした。

```yaml
# github-api-test-action
- GET  /repos/{owner}/{repo}                     # リポジトリ情報取得
- GET  /repos/{owner}/{repo}/branches            # ブランチ一覧取得
- GET  /repos/{owner}/{repo}/actions/runs        # workflow runs 取得
- POST /repos/{owner}/{repo}/issues              # Issue 作成
- PATCH /repos/{owner}/{repo}/issues/{number}    # Issue クローズ
```

## 結果

### `api.github.com`（REST API 呼び出し）

| 項目 | 表示内容 |
|------|---------|
| Destination | `api.github.com` |
| Port | `443` |
| Status | `Allowed` |
| Process | `gh` |
| **Method / Path** | **表示されない** |

### `github.com`（git 操作）

| 項目 | 表示内容 |
|------|---------|
| Destination | `github.com` |
| Port | `443` |
| Process | `git-remote-http` |
| **Method / Path** | **`GET /jjchange10/test-actions/info/refs?service=git-upload-pack`** |

## 結論

**REST API の詳細（HTTPメソッド＋パス）は Enterprise 限定機能。**

コミュニティ版では：
- `api.github.com` への通信が発生したこと・プロセス名は記録される
- しかし「どのエンドポイントに何のメソッドで呼んだか」は不明

git 操作（`github.com` への HTTPS git プロトコル）は Method/Path が表示されるが、
これは REST API 可視化とは別の仕組みによるもの。

## コミュニティ版 vs Enterprise 版 まとめ（全機能）

| 機能 | コミュニティ版 | Enterprise版 |
|------|-------------|-------------|
| ネットワーク監視（audit/block） | ○ | ○ |
| ファイル整合性監視 | ○（GitHub App 要） | ○ |
| コード改ざん検知 | ○（GitHub App 要） | ○ |
| ベースライン自動生成・推奨ポリシー | ○ | ○ |
| プロセス監視・プロセスツリー | ✗ | ○ |
| GitHub API 可視化（Method/Path） | ✗（通信先のみ） | ○ |
