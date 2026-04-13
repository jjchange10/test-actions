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
  for tool in zizmor semgrep; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      log_info "${tool} が見つかりません。pip でインストールします..."
      pip install "${tool}" --quiet || {
        echo -e "${RED}[ERROR]${NC} ${tool} のインストールに失敗しました"
        missing=$((missing + 1))
      }
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
