# Terraform Module リリース自動化パターン

GitHub Actions を使って Terraform モジュールのタグ作成・リリースを自動化する 3 つのパターンをまとめる。

---

## 背景

現在、Terraform モジュールのリリースは GitHub タグを手動で作成して管理している。モジュールディレクトリ配下に変更が入るたびに、担当者がタグを作成し、GitHub Release を作成する運用となっている。

この手動運用には以下の課題がある。

- **ヒューマンエラーのリスク**: タグの付け忘れ、バージョン番号の誤り、リリースノートの記載漏れなどが発生しやすい
- **手間とリードタイムの増大**: モジュール変更のたびにタグ作成・リリース作成・Slack での周知といった定型作業が発生し、開発者の負担となっている
- **環境ごとのリリース戦略の不在**: dev / stg / prod 環境に対して、どのバージョンをいつ反映するかの仕組みが整っておらず、意図しないバージョンが本番に入るリスクがある

## 目的

本ドキュメントでは、上記の課題を解決するために以下を目指す。

- モジュールディレクトリの変更を検知し、**タグ作成・GitHub Release 作成を自動化**する
- dev 環境で事前検証を行い、stg / prod にはタグ経由で安全にリリースする**段階的デプロイの仕組み**を構築する
- リリース時の **Slack 通知を自動化**し、チームへの周知を確実にする

以下、これらを実現するための 3 つのパターンを比較・整理する。

---

## 1. タグ作成 + リリース作成をセットにするパターン

2 つのアクションを組み合わせて、タグの自動作成とGitHub Release の作成を行う。

### 使用アクション

| アクション | 役割 |
|---|---|
| `anothrNick/github-tag-action` | コミット時にセマンティックバージョニングのタグを自動作成 |
| `softprops/action-gh-release` | タグに基づいて GitHub Release を作成 |

### ワークフロー例

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'modules/**'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # タグ作成
      - uses: anothrNick/github-tag-action@v1
        id: tag
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          DEFAULT_BUMP: patch
          WITH_V: true

      # リリース作成
      - uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.tag.outputs.new_tag }}
          name: ${{ steps.tag.outputs.new_tag }}
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### バージョン制御

コミットメッセージに以下を含めることでバンプの種類を制御する。

- `#major` → メジャーバージョンアップ
- `#minor` → マイナーバージョンアップ
- `#patch`（またはデフォルト）→ パッチバージョンアップ

### 特徴

- **シンプルな構成**: 2 つのアクションを繋ぐだけで完結する
- **即時リリース**: main への push で即座にタグとリリースが作成される
- **リリースノート**: `generate_release_notes: true` で前回タグからの差分が自動生成される
- **リリース前の確認ステップがない**: push 即リリースなので、事前テストを挟む場合は別途ジョブを追加する必要がある

### `mathieudutour/github-tag-action` を使う代替構成

Conventional Commits（`feat:`, `fix:` など）を使っている場合は `mathieudutour/github-tag-action` を使うと、コミットメッセージからバージョンを自動判定し、changelog も生成できる。

```yaml
      - uses: mathieudutour/github-tag-action@v6
        id: tag
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.tag.outputs.new_tag }}
          body: ${{ steps.tag.outputs.changelog }}
```

---

## 2. release-please-action を使うパターン

Google 製の `release-please-action` を使い、タグ・リリース・CHANGELOG の更新を 1 つのアクションで完結させる。リリース前に PR ベースの確認ステップがある点が最大の特徴。

### 使用アクション

| アクション | 役割 |
|---|---|
| `googleapis/release-please-action` | Conventional Commits を解析し、リリース PR の作成・タグ・リリース・CHANGELOG 更新をすべて自動化 |

### ワークフロー例

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'modules/**'

permissions:
  contents: write
  pull-requests: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          release-type: simple
          token: ${{ secrets.GITHUB_TOKEN }}
```

### リリースフロー

```
feat: / fix: コミットを main に push
  → release-please がリリース用 PR を自動作成
  → PR に追加コミットがあれば自動更新
  → PR をマージするとタグ + リリースが作成される
```

### モノレポ対応

`release-please-config.json` にパッケージごとのパスを定義する。

```json
{
  "packages": {
    "modules/vpc": {
      "release-type": "simple",
      "component": "vpc"
    },
    "modules/ecs": {
      "release-type": "simple",
      "component": "ecs"
    }
  }
}
```

これにより `vpc-v1.2.0`、`ecs-v1.0.1` のようにモジュール別のタグ・リリースが作られる。全モジュールを同一タグで管理する場合は、ルートに単一パッケージとして設定すればよい。

### 特徴

- **PR ベースの確認**: リリース前に PR で内容を確認できるため、意図しないリリースを防げる
- **CHANGELOG 自動生成**: `CHANGELOG.md` が自動で更新される
- **言語非依存**: `release-type: simple` で Terraform など非 npm プロジェクトにも対応
- **リリース PR の自動更新**: 追加コミットがあれば PR が自動的に更新される
- **テストとの親和性**: リリース PR に対して CI テスト（静的解析・セキュリティスキャン等）を実行でき、Branch Protection と組み合わせればテスト通過を必須にできる

### dev/stg/prod 環境での運用例

dev はパス参照（常に最新）、stg/prod はタグ参照という構成が実用的。

```hcl
# envs/dev/main.tf
module "vpc" {
  source = "../../modules/vpc"  # パス参照
}

# envs/stg/main.tf, envs/prod/main.tf
module "vpc" {
  source = "git::https://github.com/your-org/infra.git//modules/vpc?ref=v1.2.0"  # タグ参照
}
```

フロー:

```
modules/ 変更 → main merge
  → dev apply（パス参照なので即反映）
  → smoke test
  → release-please → リリース PR 作成
  → PR マージ → タグ作成
  → Renovate が stg/prod の ref 更新 PR を作成
  → stg: automerge → apply
  → prod: レビュー承認 → apply
```

---

## 3. semantic-release-action を使うパターン

`semantic-release` を GitHub Actions で使うためのラッパーアクション。Conventional Commits に基づいてタグ・リリース・リリースノートを全自動で作成する。

### 使用アクション

| アクション | 役割 |
|---|---|
| `cycjimmy/semantic-release-action` | semantic-release を GitHub Actions で実行するラッパー |

### ワークフロー例

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'modules/**'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: cycjimmy/semantic-release-action@v4
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### リリースノートのカスタマイズ

`.releaserc.json` でプラグインを指定してカスタマイズする。

```json
{
  "branches": ["main"],
  "plugins": [
    ["@semantic-release/commit-analyzer", {
      "preset": "conventionalcommits"
    }],
    ["@semantic-release/release-notes-generator", {
      "preset": "conventionalcommits",
      "presetConfig": {
        "types": [
          { "type": "feat", "section": "Features" },
          { "type": "fix", "section": "Bug Fixes" },
          { "type": "refactor", "section": "Refactoring", "hidden": false }
        ]
      }
    }],
    "@semantic-release/changelog",
    "@semantic-release/github"
  ]
}
```

- `release-notes-generator`: セクション名や表示するコミットタイプを制御
- `@semantic-release/changelog`: CHANGELOG.md の自動更新
- Handlebars テンプレートによる完全カスタムも可能

### モノレポ対応

`semantic-release-monorepo` パッケージを使い、各モジュールごとに `.releaserc.json` を配置する。

```json
{
  "extends": "semantic-release-monorepo"
}
```

```yaml
jobs:
  release:
    strategy:
      matrix:
        module: [module-a, module-b]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: cycjimmy/semantic-release-action@v4
        with:
          working_directory: modules/${{ matrix.module }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 特徴

- **即時リリース**: push 即リリースで、自動化を最大限にしたい場合に向いている
- **豊富なプラグイン**: npm, changelog, git, GitHub 等のプラグインで柔軟にカスタマイズ可能
- **リリースノートのカスタマイズ性が高い**: プラグインの組み合わせやテンプレートで自由にカスタマイズできる
- **PR ベースの確認ステップがない**: release-please と異なり、push 即リリースが基本動作

---

## 3 パターンの比較

| 観点 | タグ + リリースセット | release-please | semantic-release |
|---|---|---|---|
| リリースフロー | push 即リリース | PR 経由で確認後リリース | push 即リリース |
| 設定の簡単さ | ◎（ほぼ設定不要） | ○（config ファイル必要） | ○（`.releaserc.json`） |
| CHANGELOG 自動生成 | △（別途対応が必要） | ◎（組み込み） | ◎（プラグイン） |
| リリースノートカスタマイズ | △ | ○ | ◎（プラグインで柔軟） |
| モノレポ対応 | △（自前で構成が必要） | ◎（config で簡単） | ○（別パッケージが必要） |
| リリース前テストとの親和性 | △（別途ジョブ追加） | ◎（PR にテストを実行） | △（別途ジョブ追加） |
| Terraform との相性 | ○ | ◎（言語非依存） | ○（npm 前提の部分あり） |

### 選定の目安

- **シンプルに始めたい** → タグ + リリースセット
- **リリース前に確認したい / Terraform モノレポ** → release-please
- **カスタマイズ性を重視 / 完全自動化したい** → semantic-release
