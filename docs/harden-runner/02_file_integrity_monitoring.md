# harden-runner 検証: ファイル整合性監視

## 概要

harden-runner のファイル整合性監視機能を検証した。
ビルド中にファイルが書き込まれた・改ざんされた場合に、何が・いつ・どのプロセスによって変更されたかを記録する。

## 設定

ネットワーク監視と同じ設定で有効になる。ファイル監視専用の設定項目はない。

```yaml
- uses: step-security/harden-runner@0634a2670c59f64b4a01f0f96f84700a4088b9f0  # v2.12.0
  with:
    egress-policy: audit  # or block（ファイル監視に影響しない）
```

## 検証内容

以下の操作を行う composite action を作成してテストした。

```yaml
# file-write-action
- name: Write a new file (build artifact simulation)
  run: |
    echo "build artifact content" > /tmp/artifact.txt
    echo "build artifact content" > "$GITHUB_WORKSPACE/generated-artifact.txt"

- name: Modify existing source file (code tampering simulation)
  run: |
    echo "# tampered by CI step" >> "$GITHUB_WORKSPACE/modules/apps/main.tf"

- name: Restore tampered file
  run: |
    git checkout "$GITHUB_WORKSPACE/modules/apps/main.tf"
```

## 結果

StepSecurity ダッシュボードの **File Write Events** タブに以下が記録された。

| ファイルパス | イベント種別 | 検知時刻 |
|-------------|------------|---------|
| `/home/runner/work/test-actions/test-actions/modules/apps/main.tf` | Source Code Overwritten | 2026-04-08 10:03:18 |

## 重要な特性

### ブロックはしない

ネットワーク監視（`egress-policy: block`）と異なり、**ファイル整合性監視はブロック機能を持たない**。
検知・記録・アラートのみ。ファイルの書き込みそのものは防げない。

| 機能 | 監視 | ブロック |
|------|------|---------|
| ネットワーク監視 | ○ | ○（block モード時） |
| ファイル整合性監視 | ○ | ✗ |

### Source Code Overwritten の検知

ワークスペース内のソースファイルが書き換えられると `Source Code Overwritten` として分類される。
サプライチェーン攻撃の一形態（ビルド中にコードを差し替える）を検知するための分類と思われる。

## まとめ

- ファイル整合性監視は設定不要で自動的に有効
- ソースファイルの改ざんを `Source Code Overwritten` として記録する
- あくまで可視化・アラートが目的であり、ブロックはできない
- インシデント発生時のフォレンジック（いつ・何が・どのプロセスで書き換えられたか）に有用
