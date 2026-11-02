#!/bin/zsh
# Source 项目每日全量成果总结（launchd 定时任务入口）
# 由 ~/Library/LaunchAgents/com.source.daily-report.plist 在每天 21:07 触发。
# 日志：/Users/lute/Project/data_scrapy/tmp/daily-report.log
#
# 2026-11-02 加固：
#   1. 生成后校验 md 与 html 都存在且非空；缺失即失败，不再留下空目录。
#   2. 由本脚本提交报告。headless 的 acceptEdits 模式没有 git commit 权限，
#      此前把提交写进提示词只会失败。
#   3. 把 RUN_STATUS 写进日志，便于下一次运行和人工巡检发现失败。

set -euo pipefail

PROJ=/Users/lute/Project/data_scrapy
LOG="$PROJ/tmp/daily-report.log"
TODAY=$(date +%Y%m%d)
OUTDIR="$PROJ/reports/achievements-$TODAY"
MD="$OUTDIR/Source-项目成果总结-$TODAY.md"
HTML="$OUTDIR/Source-项目成果总结-$TODAY.html"

mkdir -p "$PROJ/tmp" "$OUTDIR"

{
  echo "===== $(date '+%F %T') start ====="
  cd "$PROJ"

  # launchd 环境缺 PATH 项，显式补齐
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

  PROMPT="生成 Source 项目（/Users/lute/Project/data_scrapy）的当日全量成果总结。要求：

1. 按 ASD-STE100 等效规则写中文（项目标准见 docs/standards/writing-standard-ste.md）。避免报告术语：口径、归因、维度、层面、颗粒度、赋能、抓手、闭环、沉淀、建议关注；改用统计范围、原因、项目、具体动作等读者能懂的话。
2. 用 Workflow 工具跑多代理工作流：7 个并行读者覆盖七个成果域（平台能力与采集目录、生产部署与发布、交付时间线、VOC/报告管线、控制台前端、Agent 与飞书、治理测试文档），再加一个完整性批评者查漏与核对数字矛盾。若运行环境不允许 Workflow 工具，改用同等结构的并行 Agent，并在报告末尾说明。
3. 关键数字必须定向核实，标注统计范围日期。已知易冲突的统计范围：MCP 工具数（以 mcp_runtime/server.py 的 @_tool 计数为准，文档 25 已过期）、VOC 禁写清单（以 voc_pipeline/spec/forbidden_conclusions.json 的 12 条为准）、ABI 状态（只能说「应用侧查询/上传/导出代码路径与本地测试已打通；生产异步导出终态、T-1 入仓、看板真实数据未验收；外部仓是 PG18.6 本地快照」，不得写「已交付」）、生产 B 状态（以 /api/health 与实际分支为准，注明 B 相对 main 是否祖先）、能力目录数（以生产实测日期为准）。
4. 报告结构：总结、数字总览（KPI + 图表）、交付时间线、成果明细、已知边界（固定状态词）、术语、证据与统计范围。报告开头写「本报告为内部成果总结，属描述性归档」。
5. 输出两份文件到 reports/achievements-$TODAY/：
   - Source-项目成果总结-$TODAY.md
   - Source-项目成果总结-$TODAY.html（沿用 reports/achievements-2026-10/Source-项目成果总结-20261031.html 的样式与图表规范：SVG 图表、hover 提示、表格视图切换、深浅色、打印样式；dataviz 调色板须先用 validate_palette.js 校验）
6. 不要运行 git add 或 git commit。外层脚本负责提交。
7. 完成后汇报：状态、改动文件、验证结果、待确认事项（写入下方日志即可，无交互读者）。"

  STATUS=success
  claude -p "$PROMPT" \
    --add-dir "$PROJ" \
    --permission-mode acceptEdits 2>&1 || { STATUS=failed; echo "EXIT_CODE=$?"; }

  if [[ ! -s "$MD" || ! -s "$HTML" ]]; then
    STATUS=failed
    echo "REPORT_MISSING md=$([[ -s "$MD" ]] && echo ok || echo missing) html=$([[ -s "$HTML" ]] && echo ok || echo missing)"
  fi

  # 日报是内部成果总结，语言闸门只记录不阻断。业务报告在导入与 CI 中 fail-closed。
  if [[ -s "$HTML" ]]; then
    if GATE_OUT=$(python3 "$PROJ/scripts/check_report_language.py" --html "$HTML" --strict 2>&1); then
      echo "REPORT_LANGUAGE_GATE=pass"
    else
      echo "REPORT_LANGUAGE_GATE=fail"
    fi
    printf '%s\n' "$GATE_OUT" | head -20
  fi

  if [[ "$STATUS" == "success" ]]; then
    if git -C "$PROJ" add -f "$OUTDIR"; then
      if git -C "$PROJ" diff --cached --quiet; then
        echo "GIT_COMMIT skipped: nothing staged"
      elif git -C "$PROJ" commit -m "docs(report): Source 项目成果总结 $TODAY"; then
        echo "GIT_COMMIT ok"
      else
        STATUS=commit_failed
        echo "GIT_COMMIT failed"
      fi
    else
      STATUS=commit_failed
      echo "GIT_ADD failed"
    fi
  fi

  echo "RUN_STATUS=$STATUS md_bytes=$(stat -f%z "$MD" 2>/dev/null || echo 0) html_bytes=$(stat -f%z "$HTML" 2>/dev/null || echo 0)"
  echo "===== $(date '+%F %T') end ====="
  echo

  [[ "$STATUS" == "success" ]] || exit 1
} >> "$LOG" 2>&1
