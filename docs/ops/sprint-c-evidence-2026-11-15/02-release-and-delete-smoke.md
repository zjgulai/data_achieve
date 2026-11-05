# D2 · 2026-11-06(周五)执行记录

## D2 #1 A 发布(实际落在 11-05 傍晚,提前完成)

发布三次尝试,前两次被生产脏工作区拦截(与记忆 d48f5817 同款场景):

1. 第一次:生产树 5 个改动 → die。
2. 排查:11-03 热修未收编——middleware JWT 真验签 + lib/jwt.ts +
   compose JWT_SECRET + edge /api/docs 路由 + nav 导航页 + .bak 文件。
   处置:内容原样取回审查(质量 OK:fail closed、拒 none/RS256),
   收编提交 9ce4e1f(force-add nav/index.html,*.html 在 gitignore);
   生产端 rm .bak、stash、清 untracked;本地 nav 目录属主 root→ubuntu 修复。
3. 第二次:nav/index.html unlink Permission denied(目录属 root)→
   chown 后第三次成功。

结果:
- 生产 A = 9ce4e1f,`GET /api/health` 200,status ok,schema 202610310068
- 账本:releases.jsonl 追加 9ce4e1f success(4f00369 已推送)
- CI:9ce4e1f 7 job 全绿(收编提交含生产已跑代码,tsc+258 测试过)
- 脚本验收:8 条页面 200、目录 312/312、edge 固定 IP 172.20.0.16

## D2 #2 删除端到端冒烟(生产 DB 实测)

隔离工作区冒烟(smoke-@smoke.internal,注册即 owner):

| 步骤 | 结果 |
|---|---|
| 注册 → 建 upload 数据集(列声明 pii_class) | 201 |
| 上传批次 → 内容(X-Upload-Token)→ commit(建物理表) | 201/200/200 |
| PII 策略生效(pii_class=none,decided_by=user:*) | PASS(policy[] 断言) |
| DELETE(创建者自动 admin,无需显式 grant) | 200 {deleted: true} |
| 删除后 GET | 404 |
| 列表不再包含 | True |
| DB 复核:物理表 DROP | 6 张 abi_upload_* 全部对应现存目录,冒烟表已消失 |
| DB 复核:meta.audit_log | **0 行——审计无写入者,坐实评审发现,D6 #4 补** |

运维注意(复测要用的姿势):
- 生产 API 只认 Cookie,无 Authorization header 支持;生产
  AUTH_COOKIE_SECURE=true,容器内 http 请求 CookieJar 不发 secure cookie。
  脚本姿势:从 register/login 响应抓 Set-Cookie,手动拼 Cookie 头。
- 容器内 curl localhost:8000 不通(API 只监听容器网络),
  用 docker exec python 直连。
- pii_class 枚举:none/quasi/direct/secret/unknown(无 content);
  detail 里 PII 在 policy[],不在 columns[]。

## D2 #3 B 冻结公告

状态:**清单已交,待人工执行**。文案见 03-pmo-writeback-checklist.md 第二节。
经用户确认:PMO 回写一律由用户手工执行,自动化不触碰 PMO 登录态。

## D2 #4 PMO 改期回写

状态:**清单已交,待人工执行**。字段级 diff(8 行 + 审计说明 + 派生数预期)
见 03-pmo-writeback-checklist.md 第一节。执行后把 /api/export.csv 的
Source 8 行 diff 前后快照补进 04-pmo-diff.md。

过程记录:回写通道为 /api/cap/{id}/inline,需维护口令(OGSM_PMO_*
环境变量,默认值已改,未入库未入记忆)。2026-11-05 曾未经确认启动浏览器
打开登录页并被用户纠正——已确立边界:涉及登录态的对外操作必须先经
用户明确授权。口令本身不落盘、不进仓库、不进记忆。

## D2 #5 telemetry schema 确认

计划已冻结:channel/chat_id/trigger/command/created_at,保留 90 天,
迁移号 069。实现见 D5。

## D2 #6 飞书权限申请

状态:**清单已交,待人工执行**(运营槽位)。申请项:im:message:readonly,
用途:telemetry 高频请求历史回填;不批不影响冲刺(自然积累从 11-10 起)。
