# ABI 备份与恢复（2026-11-03）

## 本机备份

生产 A 的备份脚本：`scripts/backup-abi.sh`。

- 备份目录：`/opt/data-achieve-scrapy/abi-backups`
- 加密口令文件：`/opt/data-achieve-scrapy/.abi-backup.env`，权限 600
- 格式：`pg_dump --format=custom` 后用 `openssl enc -aes-256-cbc -pbkdf2 -iter 200000` 加密
- 校验：同名 `.sha256`
- 保留：默认 14 天

首次实测（2026-11-03）：`abi-20261102T180203Z.dump.enc`，69 MB。

## 远端副本

`backup-abi.sh` 支持：

```bash
ABI_BACKUP_REMOTE=user@host:/path bash scripts/backup-abi.sh --run
ABI_BACKUP_REQUIRE_REMOTE=1   # 未配置远端时失败
```

远端复制后用 `sha256sum` 比对；不一致退出 1。

2026-11-03 实测：同一份加密备份复制到本机 `~/data/abi-backups/a/` 和生产 B `/opt/backups/abi-from-a/`，两处 sha256 与 A 一致。

**待办：** 持久 cron 目标未定。当前 cron 仍是本机备份；需要用户提供独立主机或对象存储，再设置 `ABI_BACKUP_REMOTE`。

## 恢复演练（2026-11-03）

在临时 Postgres 16 容器中执行，不碰生产库：

```bash
ssh A 'set -a; . /opt/data-achieve-scrapy/.env.production; \
  . /opt/data-achieve-scrapy/.abi-backup.env; set +a; \
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in /opt/data-achieve-scrapy/abi-backups/abi-20261102T180203Z.dump.enc \
    -pass env:<PASS_VAR>' \
| docker exec -i abi-restore-drill \
    pg_restore -U postgres -d abi_restore --no-owner --no-privileges
```

验收 SQL：

```sql
select c.slug, c.row_count,
       (xpath('/row/c/text()',
         query_to_xml(format(
           'select count(*) as c from raw.%I where __abi_version = (select max(__abi_version) from raw.%I)',
           'abi_upload_' || replace(c.id::text,'-',''),
           'abi_upload_' || replace(c.id::text,'-','')), false, true, '')))[1]::text::bigint
from abi.catalog_dataset c
where c.slug like 'si_%'
order by c.slug;
```

结果：5 张表 current-version 计数与 catalog 一致，合计 186,352 行。

## RTO / RPO

- RPO：每日一次，最坏 24 小时。
- RTO：本次演练从启动临时库到校验完成约 5 分钟；生产恢复还要加解密与网络传输时间，按 15-30 分钟估算。
- 恢复前先校验 `.sha256`，再解密。不要把解密后的 dump 留在临时目录。

## 待办

- 配置持久远端目标并写入 cron。
- 把加密口令存入独立密码管理器；当前只存在 A 的 600 文件中。
- 每月做一次恢复演练，记录日期与行数。