# harden-runner 検証: ネットワーク監視

## 概要

harden-runner のネットワーク監視機能を検証した。

## 設定

```yaml
- uses: step-security/harden-runner@0634a2670c59f64b4a01f0f96f84700a4088b9f0  # v2.12.0
  with:
    egress-policy: block          # audit or block
    allowed-endpoints: >
      github.com:443
      api.github.com:443
      results-receiver.actions.githubusercontent.com:443
      example.com:443             # 許可するドメインを追加
```

## egress-policy の挙動

| policy | 挙動 |
|--------|------|
| `audit` | 外部通信を記録するが、通信はブロックしない |
| `block` | `allowed-endpoints` に含まれないドメインへの通信をブロックする |

## 検証内容

### 1. ネスト構造での検知

composite action が別の composite action を呼び出す3階層構造でテストした。

```
workflow
└── suspicious-action (L1) → example.com
    └── nested-action-l2 (L2) → httpbin.org
        └── nested-action-l3 (L3) → icanhazip.com
```

**結果**: 全階層の外部通信を検知できた。ネスト階層の深さに関わらず harden-runner は通信を捕捉する。

### 2. block モードでのブロック

`allowed-endpoints` に `example.com` のみを許可した状態でテスト。

| 階層 | ドメイン | 結果 |
|------|---------|------|
| L1 | example.com | 通信成功 |
| L2 | httpbin.org | ブロック |
| L3 | icanhazip.com | ブロック |

**結果**: 許可リスト外のドメインへの通信は正常にブロックされた。

### 3. ブロック時のCIへの影響

| コマンド | ブロック時の挙動 |
|---------|----------------|
| `curl -s https://httpbin.org/get \|\| true` | curl は失敗するが `\|\| true` でステップは成功 |
| `curl -s https://httpbin.org/get` | curl が失敗し、ステップ・CIも失敗 |

**結果**: `|| true` の有無でブロック時のCI結果が変わる。不審なアクションが `|| true` を使っている場合、CIは成功しつつも外部通信が発生する点に注意が必要。

## まとめ

- `audit` モードは通信の可視化・ベースライン学習に使う
- 運用時は `block` モード + `allowed-endpoints` の明示が推奨
- ネストされた composite action 内の通信も検知・ブロック可能
- `|| true` によってブロックが隠蔽されるリスクがある
