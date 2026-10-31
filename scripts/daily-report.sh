#!/bin/zsh
# Source 项目每日全量成果总结（launchd 定时任务入口）
# 由 ~/Library/LaunchAgents/com.source.daily-report.plist 在每天 21:07 触发。
# 日志：/Users/lute/Project/data_scrapy/tmp/daily-report.log

set -euo pipefail

PROJ=/Users/lute/Project/data_scrapy
LOG="$PROJ/tmp/daily-report.log"
TODAY=$(date +%Y%m%d)
OUTDIR="$PROJ/reports/achievements-$TODAY"

mkdir -p "$PROJ/tmp" "$OUTDIR"

{
  echo "===== $(date '+%F %T') start ====="
  cd "$PROJ"

  # launchd 环境缺 PATH 项，显式补齐
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

  PROMPT="生成 Source 项目（/Users/lute/Project/data_scrapy）的当日全量成果总结。要求：

1. 按 ASD-STE100 等效规则写中文（项目标准见 docs/standards/writing-standard-ste.md）。
2. 用 Workflow 工具跑多代理工作流：7 个并行读者覆盖七个成果域（平台能力与采集目录、生产部署与发布、交付时间线、VOC/报告管线、控制台前端、Agent 与飞书、治理测试文档），再加一个完整性批评者查漏与核对数字矛盾。
3. 关键数字必须定向核实，标注口径日期。已知易冲突口径：MCP 工具数（以 mcp_runtime/server.py 的 @_tool 计数为准，文档 25 已过期）、VOC 禁写清单（以 voc_pipeline/spec/forbidden_conclusions.json 的 12 条为准）、ABI 状态（已交付，方案文档头「待批准」滞后）、生产 B 状态（README「暂缓」过期，以 docs/【运维手册】生产环境基线.md 为准）、能力目录数（以生产实测日期口径为准）。
4. 报告结构：总结、数字总览（KPI + 图表）、交付时间线、成果明细、已知边界（固定状态词）、术语、证据口径。
5. 输出两份文件到 reports/achievements-$TODAY/：
   - Source-项目成果总结-$TODAY.md
   - Source-项目成果总结-$TODAY.html（沿用 reports/achievements-2026-10/Source-项目成果总结-20261031.html 的样式与图表规范：SVG 图表、hover 提示、表格视图切换、深浅色、打印样式；dataviz 调色板须先用 validate_palette.js 校验）
6. 提交 git（reports/ 需 git add -f），提交信息 docs(report): Source 项目成果总结 $TODAY。提交前跑 node .gitnexus/run.cjs detect-changes --scope all --repo .；对「not a clean tree（纯文档零符号）」分支可提交，对 partial/truncated 须先排查。
7. 完成后汇报：状态、改动文件、验证结果、待确认事项（写入下方日志即可，无交互读者）。"

  claude -p "$PROMPT" \
    --add-dir "$PROJ" \
    --permission-mode acceptEdits 2>&1 || echo "EXIT_CODE=$?"

  echo "===== $(date '+%F %T') end ====="
  echo
} >> "$LOG" 2>&1
