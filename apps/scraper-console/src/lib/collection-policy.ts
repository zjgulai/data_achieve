type CollectionPolicyState = {
  status: string;
  policy_block_reason?: string | null;
};

export function canStartCollection(endpoint: CollectionPolicyState): boolean {
  return endpoint.status === "verified" && !endpoint.policy_block_reason;
}
