---
name: retro
description: "Use when the user asks for a retrospective, weekly review, or lessons-learned pass. Reviews recent commits, incidents, docs, and memory, then turns each lesson into a durable environment asset."
---

# DIH Retrospective

## When to Use

- "复盘近一周"
- "做一次 retro"
- "把这次事故沉淀下来"
- After a production incident, a long migration, or a week of multi-session work

## Inputs

1. Time range. Default: last 7 days.
2. Scope. Default: current repository and its production environments.
3. Evidence sources:
   - `git log --since=<date> --oneline --decorate`
   - `docs/architecture/*` and `docs/retro/*`
   - `.claude/projects/*/memory/MEMORY.md` and linked memory files
   - Production read-only checks (`scripts/preflight-production.sh`)
   - Session incidents, deploy failures, test failures

## Procedure

1. **Collect**: list commits by theme, not by author.
2. **Reconstruct**: for each incident record symptom, root cause, fix, and evidence.
3. **Classify**: knowledge gap, process gap, code gap, or collaboration gap.
4. **Convert**: every lesson must map to at least one asset:
   - memory entry
   - checklist
   - script
   - unit or integration test
   - fixture
   - architecture doc
5. **Write**: create `docs/retro/YYYY-MM-DD-<topic>.md` with sections:
   - 范围与方法
   - 关键事件
   - 根因分类
   - 经验转环境资产机制
   - 已落地资产
   - 复盘产生的待办
   - 度量
6. **Ticket**: if the lesson exposes product work, add a ticket to `docs/tickets/` and the current tracking table.
7. **Verify**: run the assets you created. A retro that only writes prose is incomplete.

## Rules

- Do not blame people. Name the system condition.
- Do not write a lesson without an asset.
- Do not duplicate a memory that already exists. Update it instead.
- Cite exact commits, files, dates, and commands.
- Keep the retro under 200 lines unless the incident is a major outage.

## Output

- `docs/retro/YYYY-MM-DD-<topic>.md`
- Updated `MEMORY.md` entries when the lesson is durable
- New or updated scripts/tests/fixtures
- Linked tickets when product work is implied
