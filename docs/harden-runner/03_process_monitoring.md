# harden-runner 検証: プロセス監視

## 概要

harden-runner のプロセス監視機能を検証した。
ビルド中に起動されたプロセス（PID・引数・プロセスツリー）を記録する機能。

## 検証内容

以下の操作を行う composite action を作成してテストした。

```yaml
# process-monitor-action
- name: Spawn child processes
  run: |
    bash -c "echo 'child process 1'"
    bash -c "sleep 1 & echo 'background process spawned'"

- name: Run process with sensitive-looking arguments
  run: |
    python3 -c "import os; print('python process:', os.getpid())"
    node -e "console.log('node process:', process.pid)" || true

- name: Simulate build tool execution
  run: |
    env SECRET_TOKEN=dummy-token bash -c "echo 'process with env vars'"
```

## 結果

StepSecurity ダッシュボードにプロセス監視用のタブ自体が存在しなかった。

## 結論

**プロセス監視はEnterprise限定機能。**
コミュニティ版（無料・パブリックリポジトリ）では利用不可。

## コミュニティ版で利用可能な機能との比較

| 機能 | コミュニティ版 | Enterprise版 |
|------|-------------|-------------|
| ネットワーク監視（audit/block） | ○ | ○ |
| ファイル整合性監視 | ○ | ○ |
| プロセス監視・プロセスツリー | ✗ | ○ |
