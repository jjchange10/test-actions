#!/usr/bin/env bash
# ============================================================
# tests/run-scan.sh
# zizmor / semgrep をフィクスチャに対して実行し、
# 期待通りに検出・スルーされるかを検証するテストランナー
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_DIR="${REPO_ROOT}/tests/fixtures"
SEMGREP_RULES="${REPO_ROOT}/.github/semgrep-rules/npm-unpinned.yml"

PASS=0
FAIL=0

# ─── カラー出力 ─────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $*"; PASS=$((PASS + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL + 1)); }
log_info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

# ─── ツールの確認 ───────────────────────────────────────────
check_tools() {
  local missing=0
  for tool in zizmor semgrep jq; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      if [[ "${tool}" == "jq" ]]; then
        echo -e "${RED}[ERROR]${NC} jq が見つかりません。apt install jq などでインストールしてください"
        missing=$((missing + 1))
      else
        log_info "${tool} が見つかりません。pip でインストールします..."
        pip install "${tool}" --quiet || {
          echo -e "${RED}[ERROR]${NC} ${tool} のインストールに失敗しました"
          missing=$((missing + 1))
        }
      fi
    fi
  done
  [ "${missing}" -eq 0 ] || { echo "必要なツールのインストールに失敗しました"; exit 1; }
}

# ─── ヘルパー ───────────────────────────────────────────────
# expect_fail: ツールがエラー (exit != 0) を返すことを期待
expect_fail() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_fail "${label} – 問題を検出すべきでしたが、スキャンが通過しました"
  else
    log_pass "${label} – 期待通り問題を検出しました"
  fi
}

# expect_pass: ツールが正常終了 (exit 0) することを期待
expect_pass() {
  local label="$1"; shift
  if "$@" 2>&1; then
    log_pass "${label} – 期待通りスキャンが通過しました"
  else
    log_fail "${label} – 問題なしのはずですが、スキャンが失敗しました"
  fi
}

# ─── メイン ─────────────────────────────────────────────────
main() {
  echo "========================================"
  echo " GitHub Actions Security Scanner テスト"
  echo "========================================"
  echo ""

  check_tools

  log_info "zizmor $(zizmor --version 2>/dev/null | head -1)"
  log_info "semgrep $(semgrep --version 2>/dev/null | head -1)"
  echo ""

  # ── zizmor テスト ─────────────────────────────────────────
  echo "── zizmor: Action hash ピン留め ──"

  expect_fail \
    "zizmor / bad-unpinned-actions.yml (タグ指定 → FAIL 期待)" \
    zizmor --no-online-audits \
           --format plain \
           "${FIXTURES_DIR}/bad-unpinned-actions.yml"

  expect_pass \
    "zizmor / good-workflow.yml (hash ピン済み → PASS 期待)" \
    zizmor --no-online-audits \
           --format plain \
           "${FIXTURES_DIR}/good-workflow.yml"

  echo ""

  # ── semgrep テスト ────────────────────────────────────────
  echo "── semgrep: npm バージョン固定 ──"

  expect_fail \
    "semgrep / bad-npm-latest.yml (@latest → ERROR 期待)" \
    semgrep \
      --config "${SEMGREP_RULES}" \
      --error \
      --include="*.yml" \
      "${FIXTURES_DIR}/bad-npm-latest.yml"

  expect_fail \
    "semgrep / bad-npm-no-version.yml (バージョン未指定 → WARNING/ERROR 期待)" \
    semgrep \
      --config "${SEMGREP_RULES}" \
      --error \
      --include="*.yml" \
      "${FIXTURES_DIR}/bad-npm-no-version.yml"

  expect_pass \
    "semgrep / good-workflow.yml (厳密バージョン指定 → PASS 期待)" \
    semgrep \
      --config "${SEMGREP_RULES}" \
      --error \
      --include="*.yml" \
      "${FIXTURES_DIR}/good-workflow.yml"

  echo ""

  # ── gh repo list マトリクス生成パイプラインの検証 ─────────
  # 実際の API 呼び出しは行わず、gh が返す JSON 形式をモックして
  # jq パイプラインが正しく matrix を生成することを確認する
  echo "── gh repo list: matrix 生成パイプライン ──"

  # gh コマンドの存在確認（ローカルにない場合はスキップ、CI では必須）
  if command -v gh >/dev/null 2>&1; then
    log_pass "gh CLI がインストールされています ($(gh --version | head -1))"

    # --no-archived オプションが gh に存在するか確認
    if gh repo list --help 2>&1 | grep -q -- "--no-archived"; then
      log_pass "gh repo list / --no-archived オプションが利用可能"
    else
      log_fail "gh repo list / --no-archived オプションが見つかりません"
    fi
  else
    log_info "gh CLI 未インストール – gh オプション確認はスキップ (GitHub Actions ランナーには標準搭載)"
  fi

  # gh repo list が返す JSON 形式をモックして jq パイプラインを検証
  # ネットワークアクセス不要のため常に実行する
  mock_gh_output='[
    {"nameWithOwner":"org/repo-a"},
    {"nameWithOwner":"org/repo-b"},
    {"nameWithOwner":"org/repo-c"}
  ]'

  repos_json=$(echo "${mock_gh_output}" | jq -c '[.[].nameWithOwner]')
  count=$(echo "${repos_json}" | jq 'length')
  matrix=$(echo "${repos_json}" | jq -c '{repo: .}')
  matrix_count=$(echo "${matrix}" | jq '.repo | length')

  if [ "${count}" -eq 3 ]; then
    log_pass "gh mock / nameWithOwner 抽出: ${count} 件 → ${repos_json}"
  else
    log_fail "gh mock / nameWithOwner 抽出: 期待 3 件, 実際 ${count} 件"
  fi

  if [ "${matrix_count}" -eq "${count}" ]; then
    log_pass "gh mock / matrix 生成: ${matrix_count} エントリ → ${matrix}"
  else
    log_fail "gh mock / matrix 生成: エントリ数不一致 (${matrix_count} vs ${count})"
  fi

  echo ""

  # ── 結果サマリー ─────────────────────────────────────────
  echo "========================================"
  echo " 結果: ${PASS} PASS / $((PASS + FAIL)) テスト"
  if [ "${FAIL}" -gt 0 ]; then
    echo -e " ${RED}${FAIL} FAIL${NC}"
    echo "========================================"
    exit 1
  else
    echo -e " ${GREEN}全テスト通過${NC}"
    echo "========================================"
    exit 0
  fi
}

main "$@"
