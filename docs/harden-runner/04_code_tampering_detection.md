# harden-runner 検証: コード改ざん検知

## 概要

harden-runner のコード改ざん検知機能を検証した。
ビルド中にファイルが書き換えられた場合、種別に応じて分類・記録される。

## 重要: GitHub App の必要性

**StepSecurity GitHub App をインストールしないと File Write Events の情報が不完全になる。**
App なしでは一部のファイル書き込みが表示されず、誤った結論を導く可能性がある。
パブリックリポジトリでは無料で利用可能。

## 設定

ネットワーク監視と同じ設定で有効。ファイル監視専用の設定項目はない。

```yaml
- uses: step-security/harden-runner@0634a2670c59f64b4a01f0f96f84700a4088b9f0  # v2.12.0
  with:
    egress-policy: audit
```

## 検証内容

以下の操作を composite action でテストした。

| 操作 | ファイル |
|------|---------|
| 既存ソースファイルの上書き | `modules/apps/main.tf` |
| workflow YAML の上書き | `.github/workflows/auto-tag-v2.yml` |
| composite action ファイルの上書き | `.github/actions/suspicious-action/action.yml` |
| `.github/actions/` 内の非 action.yml 上書き | `.github/actions/suspicious-action/README.md` |
| `action.yml` という名前のファイルを `.github/` 外で上書き | `modules/apps/action.yml` |
| 新規ファイルの作成 | `generated-artifact.txt`、`new-file.txt` |
| workspace 外への書き込み | `/tmp/test-tamper.txt` |

## 結果

| ファイル | 分類 |
|---------|------|
| `modules/apps/main.tf` | **Source Code Overwritten** |
| `.github/workflows/auto-tag-v2.yml` | **Source Code Overwritten** |
| `.github/actions/suspicious-action/action.yml` | **Source Code Overwritten** |
| `.github/actions/suspicious-action/README.md` | **Source Code Overwritten** |
| `modules/apps/action.yml` | **Overwritten file** |
| `.git/HEAD`、`.git/config`、`.git/index` 等 | **Overwritten file** |
| `generated-artifact.txt`（新規作成） | 検知されるが分類なし |
| `new-file.txt`（新規作成） | 検知されるが分類なし |
| `/tmp/test-tamper.txt` | **検知されず** |

## 検知の3分類

### Source Code Overwritten
- `.github/` 配下の既存ファイル（パスを問わず）
- `modules/` 等のソースファイル
- **ソースコードとして管理されているファイルの上書き**を意味する

### Overwritten file
- `.git/` 内部ファイル（git 操作の副作用として記録）
- `.github/` 外の `action.yml` という名前のファイル
- ソースコードとは分類されないが書き換えは検知する

### 分類なし（空白）
- workspace 内の**新規ファイル作成**（上書きでないため）

### 検知されない
- **workspace 外**（`/tmp` 等）への書き込み

## 当初の誤解について

当初 `action.yml` の書き換えが検知されなかった原因は、ファイル名やパスの除外ではなく
**GitHub App 未インストールによる表示の不完全さ**だった。
GitHub App をインストールすることで全件表示される。

## まとめ

- GitHub App のインストールが完全な可視化に必須
- workspace 内の既存ファイルへの書き込みはほぼすべて検知される
- `/tmp` 等 workspace 外は対象外
- 新規ファイル作成は検知されるが「改ざん」とは分類されない
- ブロック機能はなく、検知・記録・アラートのみ
