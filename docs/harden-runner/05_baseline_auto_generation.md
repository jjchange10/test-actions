# harden-runner 検証: ベースライン自動生成

## 概要

harden-runner のベースライン自動生成・推奨ポリシー機能を検証した。
過去のワークフロー実行を学習し、実際にアクセスされたエンドポイントから `block` モード用の推奨ポリシーを自動生成する。

## 検証手順

1. `egress-policy: audit` でワークフローを実行し、全通信を記録
2. StepSecurity ダッシュボードの Recommended Policy タブを確認
3. 生成されたポリシーを検証

## 結果

以下の推奨ポリシーが自動生成された。

```yaml
- name: Harden Runner
  uses: step-security/harden-runner@fa2e9d605c4eeb9fcad4c99c224cee0c6c7f3594 # v2.16.0
  with:
    egress-policy: block
    allowed-endpoints: >
      api.github.com:443
      example.com:443
      github.com:443
      httpbin.org:443
      icanhazip.com:443
```

## 重要な特性

### 全通信先を漏れなく学習

`block` モードでブロックされた通信（`httpbin.org`・`icanhazip.com`）も含め、
実際にアクセスを試みた全エンドポイントが推奨ポリシーに含まれる。
ネストされた composite action 内の通信も正しく学習されている。

### block モードを推奨

`audit` で実行しても、推奨ポリシーは `egress-policy: block` として生成される。
より安全な設定を自動的に提案する設計になっている。

### バージョンアップも提案

推奨ポリシーには harden-runner 自身の最新バージョンも含まれる。
（検証時: `v2.12.0` → `v2.16.0`）

## 活用方法

1. 最初は `egress-policy: audit` で数回実行してベースラインを蓄積
2. ダッシュボードの推奨ポリシーをそのまま workflow にコピー
3. `egress-policy: block` に切り替えて運用開始

手動で `allowed-endpoints` を洗い出す作業が不要になる。

## まとめ

- 実行履歴から全通信先を自動学習し、`block` 用ポリシーを生成
- ブロックされた通信も含めてすべて学習対象になる
- harden-runner のバージョン更新も合わせて提案される
- `audit` → 推奨ポリシー適用 → `block` の流れが推奨ワークフロー
