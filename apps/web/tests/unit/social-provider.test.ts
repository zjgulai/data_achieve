import { describe, expect, it } from "vitest";

import { mapSocialExecutionDryRunResponse } from "@/lib/api/social-provider";
import type { SocialExecutionDryRunResponseDto } from "@/types/social-provider";

const response: SocialExecutionDryRunResponseDto = {
  schema_version: "social_execution_dry_run.v1",
  platform: "reddit",
  provider_id: "reddit.praw",
  endpoint: "comments.new",
  fixture_only: true,
  provider_call_allowed: false,
  provider_call_attempted: false,
  credential_read_attempted: false,
  source_create_allowed: false,
  task_create_allowed: false,
  task_run_allowed: false,
  dataset_write_allowed: false,
  export_allowed: false,
  production_write_allowed: false,
  live_comparison_available: false,
  blocked_reasons: ["credential_missing:oauth_token"],
  execution_plan: [
    {
      stage: "readiness",
      status: "blocked",
      blocked_reasons: ["credential_missing:oauth_token"],
      provider_call: false,
      credential_read: false,
      production_write: false,
      details: {
        missing_credentials: ["oauth_token"],
      },
    },
    {
      stage: "dataset_preview",
      status: "previewed",
      blocked_reasons: [],
      provider_call: false,
      credential_read: false,
      production_write: false,
      details: {
        row_count: 2,
      },
    },
  ],
  readiness: {
    readiness: false,
    missing_credentials: ["oauth_token"],
    missing_scope: [],
    blocked_reasons: ["credential_missing:oauth_token"],
    provider_call_allowed: false,
    provider_call_attempted: false,
  },
  raw_preview: {
    records: [
      {
        schema_version: "social_raw.v1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
      },
    ],
  },
  normalization_preview: {
    normalized_items: [
      {
        schema_version: "social_comment.v1",
        item_id: "social_comment:reddit.praw:1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
      },
    ],
  },
  dataset_preview: {
    dataset_name: "Reddit comments VOC fixture",
    row_count: 2,
    source_item_count: 2,
    truncated: false,
    rows: [
      {
        row_id: "social_dataset_row:reddit.praw:1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
        source_schema_version: "social_voc_item.v1",
        payload: {
          text_excerpt: "Reddit fixture post 1",
          provider_call: false,
          llm_call_attempted: false,
        },
      },
    ],
  },
  source_template: {
    source_create_allowed: false,
    source_created: false,
    task_created: false,
    source_create_payload: {
      name: "Reddit comments fixture source",
      type: "manual_json",
    },
  },
  task_run_approval_template: {
    task_run_allowed: false,
    dataset_write_allowed: false,
    approval_packet: {
      schema_version: "social_task_run_l4_approval_packet.v1",
      provider_call: false,
      task_run: false,
      dataset_save: false,
    },
  },
  next_required_authorization: "L4_social_execution_authorization_required",
};

describe("mapSocialExecutionDryRunResponse", () => {
  it("maps social execution dry-run response and preserves no-write flags", () => {
    const mapped = mapSocialExecutionDryRunResponse(response);

    expect(mapped.schemaVersion).toBe("social_execution_dry_run.v1");
    expect(mapped.providerId).toBe("reddit.praw");
    expect(mapped.fixtureOnly).toBe(true);
    expect(mapped.providerCallAllowed).toBe(false);
    expect(mapped.providerCallAttempted).toBe(false);
    expect(mapped.credentialReadAttempted).toBe(false);
    expect(mapped.sourceCreateAllowed).toBe(false);
    expect(mapped.taskRunAllowed).toBe(false);
    expect(mapped.datasetWriteAllowed).toBe(false);
    expect(mapped.exportAllowed).toBe(false);
    expect(mapped.productionWriteAllowed).toBe(false);
    expect(mapped.blockedReasons).toEqual(["credential_missing:oauth_token"]);
    expect(mapped.executionPlan.map((stage) => stage.stage)).toEqual([
      "readiness",
      "dataset_preview",
    ]);
    expect(mapped.executionPlan.every((stage) => !stage.providerCall)).toBe(true);
    expect(mapped.datasetPreview.rowCount).toBe(2);
    expect(mapped.datasetPreview.rows[0]?.textExcerpt).toBe("Reddit fixture post 1");
    expect(mapped.taskRunApprovalTemplate.approvalPacket.task_run).toBe(false);
  });
});
