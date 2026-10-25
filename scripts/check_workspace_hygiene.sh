#!/usr/bin/env bash
#
# 工作区卫生巡检。只读，不改任何状态。
#
# 回答四个问题：
#   1. 有没有工作树位于主仓之外（应全部收敛到 .worktrees/）？
#   2. 有没有工作树带着未提交改动（可能丢东西）？
#   3. 有没有分支其实已经把补丁全部合进 main（可安全删除）？
#   4. 有没有分支在 main 之外仍有真实新增提交（未发布工作）？
#
# 用法：
#   bash scripts/check_workspace_hygiene.sh          # 人读报告
#   bash scripts/check_workspace_hygiene.sh --quiet   # 只输出异常，无异常则静默
#
# 退出码：
#   0  无硬性违规（有可清理项也返回 0，清理是建议不是失败）
#   1  存在硬性违规：工作树位于主仓之外，或工作树有未提交改动
#
set -euo pipefail

MAIN_BRANCH="${MAIN_BRANCH:-main}"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

ROOT="$(git rev-parse --show-toplevel)"
ALLOWED_PREFIX="$ROOT/.worktrees/"

say() { [ "$QUIET" -eq 1 ] || printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*"; }

hard_violations=0
outside=()
dirty=()
redundant=()
active=()

# 逐个工作树分类。只解析 porcelain，避免依赖 subshell 里的 PATH。
while IFS= read -r line; do
  case "$line" in
    "worktree "*) wt_path="${line#worktree }"; wt_branch="" ;;
    "branch "*)    wt_branch="${line#branch refs/heads/}"
                   [ "$wt_path" = "$ROOT" ] && continue

                   # 1) 位置是否在允许范围内
                   case "$wt_path" in
                     "$ALLOWED_PREFIX"*|"$ROOT"|/private/tmp/*) ;;
                     *) outside+=("$wt_path ($wt_branch)"); hard_violations=1 ;;
                   esac

                   # 2) 是否带未提交改动
                   if [ -n "$(git -C "$wt_path" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
                     dirty+=("$wt_path ($wt_branch)"); hard_violations=1
                   fi

                   # 3) 是否补丁已全部在 main（可删）
                   new_commits="$(git cherry "$MAIN_BRANCH" "$wt_branch" 2>/dev/null | grep -c '^+' || true)"
                   if [ "${new_commits:-0}" -eq 0 ]; then
                     redundant+=("$wt_branch")
                   else
                     active+=("$wt_branch ($new_commits 个真实新增提交)")
                   fi
                   ;;
    "detached")    [ -d "$wt_path" ] && case "$wt_path" in
                     /private/tmp/*) ;;
                     *) outside+=("$wt_path (detached)"); hard_violations=1 ;;
                   esac ;;
  esac
done <<< "$(git worktree list --porcelain)"

say "=== 工作区卫生报告 ==="
say "主仓：$ROOT"
say "工作树总数：$(git worktree list | wc -l | tr -d ' ')"

if [ "$QUIET" -eq 0 ]; then
  say ""
  say "── 仍持有未发布工作的分支"
  if [ ${#active[@]} -eq 0 ]; then say "   （无）"; else printf '   %s\n' "${active[@]}"; fi
fi

if [ ${#redundant[@]} -gt 0 ]; then
  warn ""
  warn "⚠ 补丁已全部在 $MAIN_BRANCH、可安全删除的分支："
  printf '   %s\n' "${redundant[@]}"
  warn "   删除方式：git worktree remove <路径> && git branch -d <分支>"
fi

if [ ${#outside[@]} -gt 0 ]; then
  warn ""
  warn "✗ 工作树不在 $ALLOWED_PREFIX 之下："
  printf '   %s\n' "${outside[@]}"
  warn "   处置：git worktree move <旧路径> \"$ALLOWED_PREFIX<短名>\""
fi

if [ ${#dirty[@]} -gt 0 ]; then
  warn ""
  warn "✗ 工作树有未提交改动："
  printf '   %s\n' "${dirty[@]}"
fi

[ "$QUIET" -eq 0 ] && say ""
if [ "$hard_violations" -eq 1 ]; then
  warn "结论：存在需要处理的问题（见上）。"
  exit 1
fi
say "结论：无硬性违规。"
exit 0
