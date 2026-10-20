/**
 * 采集放行判定。
 *
 * 设计约束：前端不持有策略名单。
 * 四类 collector（offline / guarded_http / provider_api / unsupported）
 * 的唯一来源是后端 `collectors/outbound_policy.py`。
 * 目录接口按行投影 `policy_block_reason`，前端只读该字段。
 *
 * 理由：名单复制到前端会漂移，且前端无法知道运行时 grant 是否配置。
 * 一致性由后端契约测试保障（tests/unit/test_outbound_policy_contract.py）。
 */

type CollectionPolicyState = {
  status: string;
  policy_block_reason?: string | null;
};

export function canStartCollection(endpoint: CollectionPolicyState): boolean {
  return endpoint.status === "verified" && !endpoint.policy_block_reason;
}
