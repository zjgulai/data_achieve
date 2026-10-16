/**
 * 端点行的稳定标识。
 *
 * 目录有 286 行，但只有 258 个唯一 endpoint_type。
 * `public_feed` 出现 23 行、`generic_web` 出现 7 行。
 * 只用 endpoint_type 会产生重复 React key，也会让同一类型的多行串选。
 *
 * 本模块提供行级标识。目录尚未提供稳定的行 id，
 * 故用 (endpoint_type, label) 组合。该组合在全部 286 行中唯一。
 */

/** 端点行的标识来源。 */
export type EndpointIdentity = {
  endpoint_type: string;
  label: string;
};

/** 行的 React key 与选择集键。 */
export function endpointRowKey(endpoint: EndpointIdentity): string {
  return `${endpoint.endpoint_type}:${endpoint.label}`;
}
