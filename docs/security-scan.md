# GitHub Actions Security Scanner

GitHub Actions ワークフロー内のセキュリティリスクを自動検出する仕組み。
組織配下の全リポジトリを動的に取得し、2 つのスキャナー（zizmor / semgrep）で並列スキャンを実行する。

## 全体構成

```
.
├── .github/
│   ├── workflows/
│   │   └── security-scan.yml        # ワークフロー本体
│   ├── semgrep-rules/
│   │   └── npm-unpinned.yml         # semgrep カスタムルール定義
│   └── zizmor.yml                   # zizmor ルール設定（unpinned-uses のみ有効化）
└── tests/
    ├── run-scan.sh                  # ローカルテストランナー
    └── fixtures/                    # テスト用フィクスチャ
        ├── bad-unpinned-actions.yml
        ├── bad-npm-latest.yml
        ├── bad-npm-no-version.yml
        └── good-workflow.yml
```

## ワークフロー（security-scan.yml）

### トリガー

| イベント | 条件 |
|---------|------|
| `push` | `main` ブランチ & `.github/workflows/**`, `.github/actions/**`, `.github/semgrep-rules/**` の変更時 |
| `pull_request` | 同上のパス変更時 |
| `schedule` | 毎週月曜 02:00 UTC |
| `workflow_dispatch` | 手動実行 |

### Job 1: setup — スキャン対象リポジトリの動的取得

`gh repo list` で組織（またはユーザー）配下のリポジトリ一覧を取得し、matrix を生成する。

```
gh repo list "<owner>" --json nameWithOwner --no-archived --limit 1000
```

- `--no-archived` でアーカイブ済みリポジトリを除外
- `--limit 1000` で最大 1000 リポジトリまで取得
- 出力を `jq` で `{"repo": ["owner/repo-a", "owner/repo-b", ...]}` 形式に変換し、後続ジョブの matrix として渡す

#### トークンについて

| 対象 | 必要なトークン |
|------|---------------|
| パブリックリポジトリのみ | `GITHUB_TOKEN`（デフォルト） |
| プライベートリポジトリを含む | `SCAN_TOKEN`（PAT: `repo` + `read:org` スコープ） |

ワークフローでは `secrets.SCAN_TOKEN || secrets.GITHUB_TOKEN` のフォールバックを使用している。

### Job 2: scan — 並列セキュリティスキャン

matrix で生成されたリポジトリごとに独立した runner が起動し、以下の 2 ステップを実行する。
`fail-fast: false` により、1 つのリポジトリで問題が見つかっても残りのスキャンは継続する。

各 runner は 2 つのリポジトリをチェックアウトする:

| ディレクトリ | 内容 |
|-------------|------|
| `scanner/` | 本リポジトリ（semgrep ルール・zizmor 設定の取得用） |
| `target/` | スキャン対象リポジトリ |

#### ステップ 1: zizmor — Action Hash Pinning

Actions の `uses:` 参照がコミットハッシュでピン留めされているかを検査する。

```bash
zizmor --no-online-audits --config scanner/.github/zizmor.yml --format plain <対象ディレクトリ>
```

- `--no-online-audits`: ネットワーク不要の監査のみ実行
- `--config scanner/.github/zizmor.yml`: `unpinned-uses` ルールのみ有効化
- 対象: `target/.github/workflows/` と `target/.github/actions/`

**検出例:**

```yaml
# NG: タグ指定（サプライチェーン攻撃のリスク）
- uses: actions/checkout@v4

# OK: コミットハッシュでピン留め
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

#### ステップ 2: semgrep — npm Version Pinning

ワークフロー内の `npm install` 等でパッケージバージョンが固定されているかを検査する。

```bash
semgrep --config scanner/.github/semgrep-rules/npm-unpinned.yml --error --include="*.yml" --include="*.yaml" target/.github/
```

---

## zizmor 設定（zizmor.yml）

zizmor は 34 個の監査ルールを持つが、本スキャナーでは **`unpinned-uses` のみ有効化** している。
他の 33 ルールはすべて `disable: true` で無効化されている。

```yaml
rules:
  artipacked:
    disable: true
  cache-poisoning:
    disable: true
  # ... 他 31 ルール省略
  # unpinned-uses のみ有効（記載なし = 有効）
```

全ルール一覧: https://docs.zizmor.sh/audits/

---

## semgrep カスタムルール（npm-unpinned.yml）

### Rule 1: `forbid-dynamic-version-in-actions`（ERROR）

`@latest`, `@main`, `@next` など動的タグによるバージョン指定を検出する。

```yaml
regex: "(?s).*(npm|pnpm|yarn|pip|pip3)\\s+(install|i|add).*(@|==)(?:latest|main|next|beta|alpha|canary).*"
```

- `(?s)`: `.` が改行にもマッチ（複数行スクリプト全体を走査）
- npm/pnpm/yarn に加えて pip/pip3 の `==latest` 等も検出対象

| 入力 | 結果 |
|------|------|
| `npm install lodash@latest` | ERROR |
| `pip install requests==main` | ERROR |
| `npm install lodash@4.17.21` | OK |

### Rule 2: `forbid-unversioned-install-in-actions`（WARNING）

パッケージ名はあるがバージョン指定（`@X.Y.Z`）が無い install を検出する。

```yaml
regex: >-
  (?m)^\s*(npm|pnpm|yarn)\s+(install|i|add)\s+(?!.*@)\S.*$
```

- `(?m)`: `^` `$` が各行にマッチ
- `(?!.*@)`: 否定先読みで「その行に `@` が含まれない」ことを確認
- `\S.*$`: パッケージ名が 1 文字以上存在する

| 入力 | 結果 |
|------|------|
| `npm install lodash` | WARNING |
| `npm install -g typescript` | WARNING |
| `npm install @types/node` | WARNING |
| `npm install lodash@4.17.21` | OK |
| `npm ci` | OK（サブコマンドが対象外） |
| `npm install` | OK（パッケージ名なし） |

---

## ローカルテスト（tests/run-scan.sh）

フィクスチャに対してスキャナーを実行し、期待通りの検出/非検出を検証する。

```bash
bash tests/run-scan.sh
```

### テストケース

| ツール | フィクスチャ | 期待結果 |
|--------|------------|---------|
| zizmor | `bad-unpinned-actions.yml` | FAIL（タグ指定を検出） |
| zizmor | `good-workflow.yml` | PASS（hash ピン留め済み） |
| semgrep | `bad-npm-latest.yml` | FAIL（`@latest` を検出） |
| semgrep | `bad-npm-no-version.yml` | FAIL（バージョン未指定を検出） |
| semgrep | `good-workflow.yml` | PASS（厳密バージョン指定済み） |

加えて、`gh repo list` の JSON 出力を jq で matrix に変換するパイプラインもモックデータで検証している。

---

## 検出対象まとめ

| リスク | ツール | ルール | 重要度 |
|--------|--------|--------|--------|
| Action がハッシュ未固定 | zizmor | `unpinned-uses` | HIGH |
| npm 等で `@latest` / `@main` 指定 | semgrep | `forbid-dynamic-version-in-actions` | ERROR |
| npm 等でバージョン未指定 | semgrep | `forbid-unversioned-install-in-actions` | WARNING |
