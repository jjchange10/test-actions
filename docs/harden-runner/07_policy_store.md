# harden-runner 検証: ポリシーストア

## 概要

harden-runner のポリシーストア機能を検証した。
ワークフロー YAML に直接 `egress-policy` や `allowed-endpoints` を書く代わりに、
StepSecurity ダッシュボード上で一元管理したポリシーを参照する機能。

## 設定方法

### ワークフロー側

```yaml
permissions:
  id-token: write  # StepSecurity API 認証に必要

steps:
  - uses: step-security/harden-runner@...
    with:
      policy: new  # ポリシーストアのポリシー名
```

インラインの `egress-policy`・`allowed-endpoints` は不要。

### ポリシーストア側（StepSecurity ダッシュボード）

`https://app.stepsecurity.io/github/{org}/actions/policies` で定義。

```yaml
egress-policy: block
allowed-endpoints: >
  github.com:443
  example.com:443
  httpbin.org:443
  icanhazip.com:443
```

## 結果

ポリシーストアで定義した通りのエンドポイントが適用された。

| ドメイン | ステータス |
|---------|----------|
| `github.com` | Allowed |
| `api.github.com` | Allowed |
| `example.com` | Allowed |
| `httpbin.org` | Allowed |
| `icanhazip.com` | Allowed |

## インライン設定との比較

| | インライン設定 | ポリシーストア |
|--|-------------|-------------|
| 設定場所 | ワークフロー YAML | StepSecurity ダッシュボード |
| 変更方法 | コードの PR が必要 | ダッシュボードから即時変更 |
| 複数リポジトリへの適用 | リポジトリごとに設定 | 1つのポリシーを共有可能 |
| セキュリティチームによる管理 | 開発者と混在 | ポリシーを独立管理できる |

## 複数ポリシーの指定

`policy:` パラメータは**単一の文字列のみ**対応しており、複数のポリシーを同時に指定することはできない。

```yaml
# NG: 複数指定は非対応
with:
  policy: policy-a, policy-b
```

複数の設定を適用したい場合の選択肢：

1. **ポリシーストア側で統合する**: 複数のルールを1つのポリシーにまとめる
2. **インライン設定と併用する**: `policy:` とインラインの `allowed-endpoints` を同時に指定することが可能。ポリシーストアの設定がインライン設定とマージされる（ポリシーストア側が優先）

```yaml
# インライン設定との併用例
- uses: step-security/harden-runner@...
  with:
    policy: new
    egress-policy: audit          # ポリシーストアに egress-policy があれば上書きされる
    allowed-endpoints: >
      extra-endpoint.example.com:443  # ポリシーストアの設定とマージされる
```

## まとめ

- `policy:` パラメータと `id-token: write` を追加するだけで利用可能
- ポリシーの変更がワークフロー YAML のコミットなしに行える
- 複数リポジトリに同一ポリシーを適用しやすい
- セキュリティチームが開発者のワークフロー変更を待たずにポリシーを更新できる
- `policy:` に指定できるのは1つのポリシー名のみ。複数適用はポリシー統合か併用で対応する
