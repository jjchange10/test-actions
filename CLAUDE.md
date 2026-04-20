# CVE 脆弱性分析 — プロジェクトコンテキスト

このリポジトリには、**Claude Code** 上に構築された AI による CVE トリアージ自動化システムが含まれています。

## 目的

CVE ID と対象 GitHub リポジトリが与えられた際、本システムは:
1. **NVD**（CVSS、CWE、説明）、**OSV**（パッケージエコシステム、バージョン範囲）、**GitHub Security Advisories**（パッチ済みバージョン、エコシステム固有情報）から脆弱性情報を取得する
2. GitHub API 経由で対象リポジトリの依存マニフェストとソースコードを検査する
3. コードベースがその脆弱性に致命的に晒されているかを判定する
4. リスクレベルと実行可能な是正策を含む、構造化された Markdown セキュリティレポートを生成する

## アーキテクチャ

```
.claude/
  skills/cve-analyze/          ← 正本となるスキル（SKILL.md を参照）
    SKILL.md                   · 実行手順 + YAML フロントマター
    REPORT_TEMPLATE.md         · Markdown レポートのひな形
    RISK_LEVELS.md             · リスクレベル判定ルーブリック
    scripts/                   · 検証済みヘルパー（NVD、OSV、GHSA、GitHub API）
  commands/cve-analyze.md      ← スキルを読み込む薄いスラッシュコマンドラッパー

prompts/
  cve-security-analyst-system.md  · システムプロンプトのペルソナ（シニア appsec アナリスト）

.github/workflows/
  cve-vulnerability-analysis.yml  · 手動ディスパッチの CI ランナー
```

`.claude/skills/cve-analyze/SKILL.md` の **スキル** が分析ロジックの唯一の真実（single source of truth）です。スラッシュコマンドとワークフローはいずれもこのスキルに処理を委譲します。

## 利用可能なスキル

### `/cve-analyze <CVE_ID> <owner/repo> [branch]`

完全なセキュリティ分析を実行し、カレントディレクトリに `cve-report-<CVE_ID>.md` を書き出します。

```
/cve-analyze CVE-2021-44228 apache/logging-log4j2
/cve-analyze CVE-2023-44487 nginx/nginx main
/cve-analyze CVE-2024-3094  owner/myapp develop
```

ヘルパースクリプトは `.claude/skills/cve-analyze/scripts/` 配下に配置されており、スキル本体では生の `curl` より優先して使用してください — リトライ、レート制限、404 フォールバックが実装済みです。

## リスクレベルスケール

| レベル | 意味 |
|-------|---------|
| 🔴 CRITICAL | 脆弱なバージョン利用 + 脆弱な機能を能動的に呼び出し + 信頼できない入力から到達可能 |
| 🟠 HIGH | 脆弱なバージョン + 機能呼び出しあり、但し露出が間接的または部分的緩和策あり |
| 🟡 MEDIUM | 脆弱なバージョン宣言 + パッケージ使用ありだが、特定の脆弱パスの発動が不明確 |
| 🟢 LOW | 脆弱なパッケージを宣言しているが、脆弱な機能のコード中での使用は未検出 |
| ✅ SAFE | 影響なし、バージョンが脆弱範囲外、または修正が既適用 |

完全なルーブリック: `.claude/skills/cve-analyze/RISK_LEVELS.md`。

## GitHub Actions 経由での実行

Actions タブから `.github/workflows/cve-vulnerability-analysis.yml` を手動ディスパッチで起動します。

**必要なシークレット（Workload Identity Federation 経由の Vertex AI）:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`

ワークフローの処理:
1. `cve_id`, `target_repo`, `target_branch` 入力を検証（シェルインジェクション形式の値は即座に失敗）。
2. Claude Code CLI をインストール。
3. `--append-system-prompt` 経由で `prompts/cve-security-analyst-system.md` を注入し、アナリストペルソナを保証。
4. `/cve-analyze` スキルを非対話モードで実行。
5. レポートをビルドアーティファクトとしてアップロードし、ジョブサマリーへ投稿。
6. 任意で GitHub Issue を作成（ただし同一 CVE + 対象リポジトリのオープン Issue が既に存在しない場合のみ）。

## 振る舞いのガイドライン

このプロジェクトで CVE 分析を行う際は:
- 完全なセキュリティスペシャリストのペルソナとレポート構造は `prompts/cve-security-analyst-system.md` に従う。
- すべての findings について具体的なファイルパスとコードスニペットを引用する — 裏付けのない主張は禁止。
- データが入手できない、またはトランケートされている場合は確信度への影響を明示する。
- リスクレベルで迷った場合は引き上げる方向に寄せ、理由を説明する。
- すべての是正ステップは、正確なバージョン番号とコマンドを伴い、即座に実行可能であること。
- スキルのヘルパースクリプトを生の `curl` より優先する — リトライ、レート制限、404 フォールバックが実装済み。
