# harden-runner 検証: コード改ざん検知

## 概要

harden-runner のコード改ざん検知機能を検証した。
ビルド中にソースファイルが書き換えられた場合、`Source Code Overwritten` として分類・記録される。

## 検証内容

以下の操作を行う composite action を作成してテストした。

```yaml
# code-tamper-action
- Terraform ソースファイル (.tf) の上書き       → workspace/modules/apps/main.tf
- workflow YAMLファイル (.yml) の上書き          → workspace/.github/workflows/auto-tag-v2.yml
- action ファイル (action.yml) の上書き          → workspace/.github/actions/suspicious-action/action.yml
- 新規ファイルの作成                             → workspace/new-file.txt
- workspace外へのファイル書き込み               → /tmp/test-tamper.txt
```

## 結果

| 操作 | ファイル | 検知 | 分類 |
|------|---------|------|------|
| `.tf` 上書き（file-write-action） | `modules/apps/main.tf` | ○ | Source Code Overwritten |
| `.tf` 上書き（code-tamper-action） | `modules/apps/main.tf` | ○ | Source Code Overwritten |
| workflow `.yml` 上書き | `.github/workflows/auto-tag-v2.yml` | ○ | Source Code Overwritten |
| `action.yml` 上書き | `.github/actions/suspicious-action/action.yml` | **✗** | — |
| 新規ファイル作成 | `new-file.txt` | **✗** | — |
| `/tmp` への書き込み | `/tmp/test-tamper.txt` | **✗** | — |

## 重要な特性

### 検知される条件

- **workspaceに存在する既存ファイルの上書き** → `Source Code Overwritten` として検知
- 拡張子は問わない（`.tf`・`.yml` ともに検知）

### 検知されない条件

- **新規ファイルの作成**（上書きでないため）
- **workspace外（`/tmp` 等）への書き込み**
- **実行中の composite action 自身の `action.yml`** の書き換え（理由は不明。実行中ファイルは除外されている可能性）

### ブロックはしない

ファイル整合性監視と同様、検知・記録のみ。書き込みそのものは防げない。

### 重複検知

同じファイルが複数のステップで書き換えられた場合、それぞれ独立して記録される。
（`main.tf` が file-write-action と code-tamper-action の両方で検知された）

## まとめ

- workspace内の**既存ファイルへの上書き**が `Source Code Overwritten` として記録される
- 新規作成・/tmp・実行中アクションファイルは対象外
- 改ざん検知はあくまで可視化・アラート目的であり、ブロック機能はない
