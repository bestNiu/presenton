import { ApiResponseHandler } from "@/app/(presentation-generator)/services/api/api-error-handler";
import { getApiUrl } from "@/utils/api";

export type WorkspaceType = "personal" | "team" | "department";
export type WorkspaceRole = "owner" | "admin" | "editor" | "reviewer" | "viewer";
export type ConfidentialityLevel = "L1" | "L2" | "L3" | "L4";

export interface WorkspaceResponse {
  id: string;
  owner_id: string;
  name: string;
  workspace_type: WorkspaceType;
  confidentiality: ConfidentialityLevel;
  is_archived: boolean;
  governance_policy: {
    review_mode: "none" | "single";
    quality_gate_enabled: boolean;
    require_numeric_citations: boolean;
    revoked_delivery_retention_days: number;
  };
  current_user_role: WorkspaceRole;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMemberResponse {
  id: string;
  user_id: string;
  username: string;
  role: WorkspaceRole;
  created_at: string;
}

export interface EnterpriseNotificationResponse {
  id: string;
  workspace_id: string | null;
  actor_id: string | null;
  notification_type: string;
  title: string;
  body: string;
  resource_type: string;
  resource_id: string;
  action_url: string | null;
  event_metadata: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface EnterpriseNotificationListResponse {
  unread_count: number;
  notifications: EnterpriseNotificationResponse[];
}

export interface SceneDefinitionResponse {
  id: string;
  scene_type: string;
  version: string;
  display_name: string;
  description: string | null;
  config: Record<string, unknown>;
  status: "active" | "inactive";
}

export interface SceneRuntimeResponse {
  scene_type: string;
  version: string;
  display_name: string;
  description: string | null;
  workspace_id: string;
  workspace_role: WorkspaceRole;
  entry_route: string;
  create_schema: string;
  navigation: Array<{ code: string; label: string; route: string }>;
  permissions: string[];
  capabilities: {
    direct_presentation_create: boolean;
    requires_scene_resource: boolean;
  };
  policies: Record<string, string>;
}

export type BidProjectRole = "bid_manager" | "contributor" | "reviewer" | "viewer";
export type BidProjectStatus =
  | "understanding"
  | "strategy_pending"
  | "strategy_confirmed"
  | "archived";

export interface BidProjectResponse {
  id: string;
  workspace_id: string;
  bid_code: string;
  name: string;
  sponsor_name: string | null;
  drug_name: string | null;
  indication: string | null;
  due_date: string | null;
  confidentiality: ConfidentialityLevel;
  status: BidProjectStatus;
  current_user_role: BidProjectRole | null;
  row_version: number;
  created_at: string;
  updated_at: string;
}

export interface BidDocumentResponse {
  id: string;
  logical_name: string;
  category: string;
  version_no: number;
  status: "active" | "superseded";
  created_at: string;
}

export interface BidProfileResponse {
  id: string;
  facts: Record<string, unknown>;
  conflicts: unknown[];
  status: "draft" | "confirmed" | "stale";
  row_version: number;
}

export interface BidRequirementResponse {
  id: string;
  category: string;
  original_text: string;
  mandatory: boolean;
  owner_department: string | null;
  target_module: string | null;
  response: string | null;
  status: "open" | "answered" | "verified";
  row_version: number;
}

export interface BidStrategyResponse {
  id: string;
  version_no: number;
  elements: Record<string, unknown>;
  status: "draft" | "confirmed" | "stale";
  row_version: number;
  confirmed_at: string | null;
}

export interface BidProjectDashboardResponse {
  project: BidProjectResponse;
  profile: BidProfileResponse;
  documents: BidDocumentResponse[];
  requirements: BidRequirementResponse[];
  strategy: BidStrategyResponse;
  mandatory_requirement_coverage: number;
  strategy_blockers: string[];
}

export interface BidModuleResponse {
  id: string;
  module_type: "medical" | "operations" | "statistics";
  version_no: number;
  content: Record<string, unknown>;
  status: "draft" | "in_review" | "approved" | "rejected" | "stale";
  row_version: number;
  updated_by: string | null;
  review_comment: string | null;
}

export interface BidCommitmentResponse {
  id: string;
  content: string;
  commitment_type: string;
  evidence_ref: string | null;
  risk_level: string;
  status: "candidate" | "pending" | "approved" | "rejected" | "revoked";
}

export interface BidGateResponse {
  id: string;
  gate_type: "gate_1" | "gate_2" | "gate_3";
  status: "locked" | "open" | "blocked" | "passed";
  issues: Array<{ id: string; title: string; status: "open" | "resolved" }>;
}

export interface BidCollaborationResponse {
  modules: BidModuleResponse[];
  commitments: BidCommitmentResponse[];
  gates: BidGateResponse[];
}

export interface BidReleaseResponse {
  id: string;
  project_id: string;
  presentation_entry_id: string;
  template_publication_id: string;
  release_type: string;
  version_no: number;
  manifest: Record<string, unknown> & { presentation_id?: string };
  manifest_hash: string;
  slide_snapshot_hash: string;
  status: "draft" | "frozen" | "archived";
  frozen_at: string | null;
  created_at: string;
}

export interface BidDeliveryArtifactResponse {
  id: string;
  release_id: string;
  derived_presentation_id: string | null;
  format: "pptx" | "pdf";
  watermark_text: string;
  file_name: string;
  sha256: string;
  size_bytes: number;
  status: "ready" | "revoked";
  created_at: string;
  revoked_at: string | null;
  purged_at: string | null;
}

export interface BidDownloadGrantResponse {
  grant_id: string;
  artifact_id: string;
  download_url: string;
  expires_at: string;
  max_downloads: number;
}

export type PresentationCreationMode =
  | "topic"
  | "document"
  | "template"
  | "blank"
  | "import";

export interface PresentationEntryResponse {
  id: string;
  workspace_id: string;
  folder_id: string | null;
  presentation_id: string;
  title: string | null;
  scene_type: string;
  creation_mode: PresentationCreationMode;
  status: "draft" | "in_review" | "approved" | "frozen" | "published" | "archived";
  can_open: boolean;
  updated_at: string;
}

export interface PresentationGovernanceResponse {
  entry: PresentationEntryResponse;
  reviews: Array<{
    id: string;
    submission_no: number;
    status: "pending" | "approved" | "rejected";
    submitted_by: string | null;
    decided_by: string | null;
    decision_comment: string | null;
    submitted_at: string;
    decided_at: string | null;
  }>;
  snapshots: Array<{
    id: string;
    version_no: number;
    manifest_hash: string;
    slide_snapshot_hash: string;
    frozen_at: string;
  }>;
}

export interface PresentationCommentThreadResponse {
  id: string;
  presentation_entry_id: string;
  slide_id: string | null;
  slide_index: number | null;
  element_ref: string | null;
  title: string;
  body: string;
  is_blocking: boolean;
  status: "open" | "resolved";
  assigned_to: string | null;
  due_at: string | null;
  slide_snapshot_hash: string;
  created_by: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  replies: Array<{
    id: string;
    body: string;
    created_by: string | null;
    created_at: string;
  }>;
}

export interface PresentationSnapshotDiffResponse {
  from_snapshot_id: string;
  from_version_no: number;
  to_snapshot_id: string;
  to_version_no: number;
  added: number;
  removed: number;
  changed: number;
  unchanged: number;
  slides: Array<{
    slide_id: string;
    before_index: number | null;
    after_index: number | null;
    change_type: "added" | "removed" | "changed" | "unchanged";
    changed_fields: string[];
  }>;
}

export interface PresentationReviewInboxResponse {
  summary: {
    open_count: number;
    blocking_count: number;
    overdue_count: number;
    assigned_to_me_count: number;
  };
  tasks: Array<PresentationCommentThreadResponse & {
    presentation_title: string;
    scene_type: string;
    presentation_status: PresentationEntryResponse["status"];
    assigned_to_username: string | null;
    reply_count: number;
    is_overdue: boolean;
  }>;
}

export interface PresentationQualityRunResponse {
  id: string;
  presentation_entry_id: string;
  slide_snapshot_hash: string;
  status: "passed" | "failed";
  blocking_count: number;
  warning_count: number;
  created_at: string;
  issues: Array<{
    id: string;
    rule_code: string;
    severity: "blocking" | "warning";
    slide_index: number | null;
    message: string;
  }>;
}

export interface PresentationDeliveryArtifactResponse {
  id: string;
  snapshot_id: string;
  format: "pptx" | "pdf";
  watermark_text: string;
  file_name: string;
  sha256: string;
  size_bytes: number;
  status: "ready" | "revoked";
  revoked_at: string | null;
  purged_at: string | null;
}

export interface TemplatePublicationResponse {
  id: string;
  publication_key: string;
  template_id: string;
  workspace_id: string | null;
  scope_type: "enterprise" | "workspace" | "scene";
  scene_type: string | null;
  version: number;
  status: "draft" | "in_review" | "published" | "offline" | "archived";
  display_name: string;
  description: string | null;
  compatibility: Record<string, unknown>;
  preview_url: string | null;
  is_default: boolean;
  recommended_order: number;
}

export interface TemplatePublicationCreateInput {
  template_id: string;
  publication_key: string;
  version: number;
  scope_type: "workspace" | "scene";
  workspace_id: string;
  scene_type?: string;
  display_name?: string;
  description?: string;
  compatibility: { pptx: boolean };
  recommended_order?: number;
}

export type AssetScopeType = "personal" | "workspace" | "enterprise";
export type AssetStatus = "draft" | "published" | "offline" | "archived";

export interface AssetItemResponse {
  id: string;
  version_group_id: string;
  version_no: number;
  is_latest: boolean;
  supersedes_asset_id: string | null;
  duplicate_of_asset_id: string | null;
  duplicate_status: "none" | "suspected" | "confirmed" | "distinct";
  workspace_id: string | null;
  created_by: string | null;
  scope_type: AssetScopeType;
  asset_type: "page" | "chart" | "image" | "logo" | "copy" | "component";
  name: string;
  description: string | null;
  scene_type: string | null;
  tags: string[];
  payload_hash: string;
  preview: {
    kind?: string;
    title?: string;
    subtitle?: string | null;
    layout?: string;
    element_count?: number;
    accent?: string;
  };
  preview_status: "structured" | "queued" | "rendering" | "ready" | "error";
  preview_task_id: string | null;
  preview_url: string | null;
  preview_error: string | null;
  source_presentation_entry_id: string | null;
  source_slide_id: string | null;
  parent_asset_id: string | null;
  authorization_status: "internal" | "authorized" | "revoked";
  expires_at: string | null;
  compatibility: Record<string, unknown>;
  status: AssetStatus;
  usage_count: number;
  published_by: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetPageInsertResponse {
  slide_id: string;
  slide_index: number;
  asset_id: string;
  compatibility: AssetCompatibilityResponse;
}

export interface AssetCompatibilityIssue {
  code: string;
  severity: "warning" | "blocked";
  message: string;
}

export interface AssetCompatibilityResponse {
  asset_id: string;
  presentation_entry_id: string;
  status: "compatible" | "warning" | "blocked";
  can_insert: boolean;
  strategy: "preserve_source";
  source_template_id: string | null;
  target_template_id: string | null;
  issues: AssetCompatibilityIssue[];
}

export interface AssetPreviewTaskResponse {
  asset_id: string;
  task_id: string;
  status: string;
}

export interface AssetElementInsertResponse {
  asset_id: string;
  slide_id: string;
  component_id: string;
  component_index: number;
  asset_type: string;
}

export type AssetPromotionStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface AssetPromotionResponse {
  id: string;
  source_asset_id: string;
  promoted_asset_id: string | null;
  target_scope_type: AssetScopeType;
  target_workspace_id: string | null;
  requested_by: string;
  asset_name_snapshot: string;
  justification: string;
  desensitization_notes: string;
  authorization_confirmed: boolean;
  status: AssetPromotionStatus;
  decided_by: string | null;
  decision_comment: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetAnalyticsResponse {
  total_assets: number;
  published_assets: number;
  expiring_within_7_days: number;
  expired_assets: number;
  total_reuses: number;
  reuses_last_30_days: number;
  unique_presentations: number;
  unique_users: number;
  by_scope: Record<string, number>;
  by_type: Record<string, number>;
  top_assets: Array<{
    asset_id: string;
    name: string;
    asset_type: string;
    scope_type: AssetScopeType;
    reuse_count: number;
  }>;
}

export interface AssetPersonalizedItemResponse {
  asset: AssetItemResponse;
  is_favorite: boolean;
  last_used_at: string | null;
  recommendation_score: number | null;
  recommendation_reasons: string[];
}

export interface AssetDiscoveryItemResponse {
  asset: AssetItemResponse;
  score: number;
  reasons: string[];
  exact_duplicate: boolean;
}

export class EnterpriseApi {
  static async ensurePersonalWorkspace(): Promise<WorkspaceResponse> {
    const response = await fetch(
      getApiUrl("/api/v1/enterprise/workspaces/personal"),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to initialize your personal workspace"
    );
  }

  static async getWorkspaces(): Promise<WorkspaceResponse[]> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/workspaces"), {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load workspaces"
    );
  }

  static async getAssets(
    workspaceId?: string,
    filters: { assetType?: string; status?: AssetStatus; q?: string } = {}
  ): Promise<AssetItemResponse[]> {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", workspaceId);
    if (filters.assetType) params.set("asset_type", filters.assetType);
    if (filters.status) params.set("status", filters.status);
    if (filters.q) params.set("q", filters.q);
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets?${params.toString()}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load assets");
  }

  static async getAssetAnalytics(workspaceId: string): Promise<AssetAnalyticsResponse> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/analytics?${params.toString()}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load asset analytics");
  }

  static async getPersonalizedAssets(
    workspaceId: string,
    view: "favorites" | "recent" | "recommended",
    options: { sceneType?: string; tags?: string[]; limit?: number } = {}
  ): Promise<AssetPersonalizedItemResponse[]> {
    const params = new URLSearchParams({
      workspace_id: workspaceId,
      view,
      limit: String(options.limit || 20),
    });
    if (options.sceneType) params.set("scene_type", options.sceneType);
    options.tags?.forEach((tag) => params.append("tags", tag));
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/personalized?${params.toString()}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load personalized assets");
  }

  static async searchAssets(workspaceId: string, query: string, assetType?: string): Promise<AssetDiscoveryItemResponse[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId, q: query });
    if (assetType) params.set("asset_type", assetType);
    const response = await fetch(getApiUrl(`/api/v1/enterprise/assets/search?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to search assets");
  }

  static async getSimilarAssets(assetId: string, workspaceId: string): Promise<AssetDiscoveryItemResponse[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    const response = await fetch(getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/similar?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to find similar assets");
  }

  static async decideAssetDuplicate(assetId: string, action: "confirm" | "distinct", canonicalAssetId?: string): Promise<{ asset_id: string; duplicate_status: string; duplicate_of_asset_id: string | null }> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/duplicate-decision`), {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, canonical_asset_id: canonicalAssetId || null }),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to resolve duplicate asset");
  }

  static async setAssetFavorite(assetId: string, favorite: boolean): Promise<{ asset_id: string; is_favorite: boolean }> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/favorite`),
      { method: favorite ? "POST" : "DELETE", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to update asset favorite");
  }

  static getAssetPreviewUrl(asset: AssetItemResponse): string | null {
    return asset.preview_url ? getApiUrl(asset.preview_url) : null;
  }

  static async requestAssetPreview(assetId: string): Promise<AssetPreviewTaskResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/preview-tasks`),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to render asset preview");
  }

  static async saveSlideAsAsset(
    workspaceId: string,
    entryId: string,
    slideId: string,
    input: {
      scope_type: "personal" | "workspace";
      name: string;
      description?: string;
      tags?: string[];
    }
  ): Promise<AssetItemResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/slides/${encodeURIComponent(slideId)}/assets`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to save slide as asset");
  }

  static async saveSlideElementAsAsset(
    workspaceId: string,
    entryId: string,
    slideId: string,
    input: {
      scope_type: "personal" | "workspace";
      name: string;
      tags: string[];
      asset_type: "chart" | "image" | "copy" | "component";
      component_index: number;
      element_index?: number;
    }
  ): Promise<AssetItemResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/slides/${encodeURIComponent(slideId)}/element-assets`),
      { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to save selected asset");
  }

  static async saveSlideAsAssetVersion(
    workspaceId: string,
    entryId: string,
    slideId: string,
    assetId: string
  ): Promise<AssetItemResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/slides/${encodeURIComponent(slideId)}/assets/${encodeURIComponent(assetId)}/versions`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to create asset version");
  }

  static async getAssetVersions(assetId: string): Promise<AssetItemResponse[]> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/versions`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load asset versions");
  }

  static async getAssetCompatibility(
    assetId: string,
    workspaceId: string,
    entryId: string
  ): Promise<AssetCompatibilityResponse> {
    const params = new URLSearchParams({
      workspace_id: workspaceId,
      presentation_entry_id: entryId,
    });
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/compatibility?${params.toString()}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to check asset compatibility");
  }

  static async transitionAsset(
    assetId: string,
    action: "publish" | "offline" | "archive"
  ): Promise<AssetItemResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/transitions/${action}`),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to update asset");
  }

  static async bulkTransitionAssets(
    assetIds: string[],
    action: "publish" | "offline" | "archive"
  ): Promise<AssetItemResponse[]> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/assets/bulk-transition"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_ids: assetIds, action }),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to bulk update assets");
  }

  static async insertAssetPage(
    assetId: string,
    workspaceId: string,
    entryId: string,
    afterIndex: number
  ): Promise<AssetPageInsertResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/insert-page`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          presentation_entry_id: entryId,
          after_index: afterIndex,
        }),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to insert asset page");
  }

  static async insertAssetElement(
    assetId: string,
    workspaceId: string,
    entryId: string,
    slideId: string
  ): Promise<AssetElementInsertResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/insert-element`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          presentation_entry_id: entryId,
          slide_id: slideId,
        }),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to insert asset element");
  }

  static async createAssetPromotionRequest(
    assetId: string,
    input: {
      target_scope_type: "workspace" | "enterprise";
      target_workspace_id?: string;
      justification: string;
      desensitization_notes: string;
      authorization_confirmed: boolean;
    }
  ): Promise<AssetPromotionResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/assets/${encodeURIComponent(assetId)}/promotion-requests`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to request asset promotion");
  }

  static async getAssetPromotionRequests(
    workspaceId: string | undefined,
    view: "mine" | "review"
  ): Promise<AssetPromotionResponse[]> {
    const params = new URLSearchParams({ view });
    if (workspaceId) params.set("workspace_id", workspaceId);
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/asset-promotion-requests?${params.toString()}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load asset promotion requests");
  }

  static async decideAssetPromotionRequest(
    requestId: string,
    action: "approve" | "reject",
    comment: string
  ): Promise<AssetPromotionResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/asset-promotion-requests/${encodeURIComponent(requestId)}/decision`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, comment }),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to decide asset promotion request");
  }

  static async getWorkspaceMembers(workspaceId: string): Promise<WorkspaceMemberResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/members`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load workspace members");
  }

  static async getNotifications(workspaceId?: string, unreadOnly = false): Promise<EnterpriseNotificationListResponse> {
    const params = new URLSearchParams({ unread_only: String(unreadOnly), limit: "30" });
    if (workspaceId) params.set("workspace_id", workspaceId);
    const response = await fetch(getApiUrl(`/api/v1/enterprise/notifications?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load notifications");
  }

  static async markNotificationRead(notificationId: string): Promise<EnterpriseNotificationResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/notifications/${encodeURIComponent(notificationId)}/read`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to mark notification as read");
  }

  static async markAllNotificationsRead(workspaceId?: string): Promise<{ updated_count: number }> {
    const suffix = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
    const response = await fetch(getApiUrl(`/api/v1/enterprise/notifications/read-all${suffix}`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to mark notifications as read");
  }

  static async createWorkspace(input: {
    name: string;
    workspace_type: "team" | "department";
    confidentiality: ConfidentialityLevel;
  }): Promise<WorkspaceResponse> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/workspaces"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to create workspace"
    );
  }

  static async getScenes(): Promise<SceneDefinitionResponse[]> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/scenes"), {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load professional workspaces"
    );
  }

  static async getSceneRuntime(
    sceneType: string,
    workspaceId: string
  ): Promise<SceneRuntimeResponse> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/scenes/${encodeURIComponent(sceneType)}/runtime?${params.toString()}`
      ),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load scene runtime"
    );
  }

  static async getPresentations(
    workspaceId: string
  ): Promise<PresentationEntryResponse[]> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations`
      ),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load workspace presentations"
    );
  }

  static async submitPresentationReview(workspaceId: string, entryId: string) {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/review/submit`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to submit presentation review");
  }

  static async decidePresentationReview(workspaceId: string, entryId: string, action: "approve" | "reject", comment?: string) {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/review/decision`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, comment }) });
    return ApiResponseHandler.handleResponse(response, "Failed to decide presentation review");
  }

  static async reopenPresentationReview(workspaceId: string, entryId: string): Promise<PresentationEntryResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/review/reopen`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to reopen presentation review");
  }

  static async freezePresentation(workspaceId: string, entryId: string) {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/freeze`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to freeze presentation");
  }

  static async getPresentationGovernance(workspaceId: string, entryId: string): Promise<PresentationGovernanceResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/governance`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load presentation governance");
  }

  static async getPresentationComments(workspaceId: string, entryId: string): Promise<PresentationCommentThreadResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/comment-threads`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load presentation comments");
  }

  static async getPresentationReviewInbox(workspaceId: string, options: { scope?: "all" | "mine"; taskStatus?: "all" | "open" | "resolved"; overdueOnly?: boolean } = {}): Promise<PresentationReviewInboxResponse> {
    const params = new URLSearchParams({ scope: options.scope || "all", task_status: options.taskStatus || "open", overdue_only: String(options.overdueOnly || false) });
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/review-inbox?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load presentation review inbox");
  }

  static async createPresentationComment(workspaceId: string, entryId: string, input: { slide_id?: string; slide_index?: number; title: string; body: string; is_blocking: boolean; assigned_to?: string; due_at?: string }): Promise<PresentationCommentThreadResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/comment-threads`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
    return ApiResponseHandler.handleResponse(response, "Failed to create presentation comment");
  }

  static async replyPresentationComment(workspaceId: string, entryId: string, threadId: string, body: string) {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/comment-threads/${encodeURIComponent(threadId)}/replies`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body }) });
    return ApiResponseHandler.handleResponse(response, "Failed to reply to presentation comment");
  }

  static async transitionPresentationComment(workspaceId: string, entryId: string, threadId: string, action: "resolve" | "reopen"): Promise<PresentationCommentThreadResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/comment-threads/${encodeURIComponent(threadId)}/${action}`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to update presentation comment");
  }

  static async comparePresentationSnapshots(workspaceId: string, entryId: string, fromSnapshotId: string, toSnapshotId: string): Promise<PresentationSnapshotDiffResponse> {
    const params = new URLSearchParams({ from_snapshot_id: fromSnapshotId, to_snapshot_id: toSnapshotId });
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/snapshot-diff?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to compare presentation snapshots");
  }

  static async runPresentationQuality(workspaceId: string, entryId: string): Promise<PresentationQualityRunResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/quality-runs`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to run presentation quality check");
  }

  static async getPresentationQualityReport(workspaceId: string, entryId: string): Promise<{ run: PresentationQualityRunResponse | null }> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/quality-report`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load presentation quality report");
  }

  static async updateWorkspaceGovernancePolicy(workspaceId: string, policy: WorkspaceResponse["governance_policy"]): Promise<WorkspaceResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/governance-policy`), { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(policy) });
    return ApiResponseHandler.handleResponse(response, "Failed to update workspace governance policy");
  }

  static async createPresentationDelivery(workspaceId: string, entryId: string, snapshotId: string, format: "pptx" | "pdf"): Promise<PresentationDeliveryArtifactResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ snapshot_id: snapshotId, format }) });
    return ApiResponseHandler.handleResponse(response, "Failed to export governed presentation");
  }

  static async issuePresentationDownloadGrant(workspaceId: string, entryId: string, artifactId: string): Promise<BidDownloadGrantResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/grants`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expires_in_minutes: 30, max_downloads: 1 }) });
    const grant = await ApiResponseHandler.handleResponse(response, "Failed to authorize governed download") as BidDownloadGrantResponse;
    return { ...grant, download_url: getApiUrl(grant.download_url) };
  }

  static async revokePresentationDelivery(workspaceId: string, entryId: string, artifactId: string): Promise<PresentationDeliveryArtifactResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/revoke`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to revoke governed delivery");
  }

  static async getPublishedTemplates(
    workspaceId: string
  ): Promise<TemplatePublicationResponse[]> {
    const params = new URLSearchParams({
      workspace_id: workspaceId,
      status: "published",
    });
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/template-publications?${params.toString()}`),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load published templates"
    );
  }

  static async getTemplatePublications(
    workspaceId: string
  ): Promise<TemplatePublicationResponse[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/template-publications?${params.toString()}`),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to load template publications"
    );
  }

  static async createTemplatePublication(
    input: TemplatePublicationCreateInput
  ): Promise<TemplatePublicationResponse> {
    const response = await fetch(
      getApiUrl("/api/v1/enterprise/template-publications"),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to register template publication"
    );
  }

  static async transitionTemplatePublication(
    publicationId: string,
    action: "submit" | "publish" | "reject" | "offline" | "archive" | "set-default"
  ): Promise<TemplatePublicationResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/template-publications/${encodeURIComponent(publicationId)}/${action}`
      ),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "Failed to update template publication"
    );
  }

  static async getBidProjects(workspaceId: string): Promise<BidProjectResponse[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects?${params.toString()}`),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load bid projects");
  }

  static async createBidProject(input: {
    workspace_id: string;
    bid_code: string;
    name: string;
    sponsor_name?: string;
    drug_name?: string;
    indication?: string;
    due_date?: string;
    confidentiality: ConfidentialityLevel;
  }): Promise<BidProjectResponse> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/bid/projects"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to create bid project");
  }

  static async getBidProject(projectId: string): Promise<BidProjectDashboardResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}`),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to load bid project");
  }

  static async registerBidDocument(
    projectId: string,
    input: {
      logical_name: string;
      category: string;
      version_no: number;
      file_ref: string;
      sha256?: string;
    }
  ): Promise<BidDocumentResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/documents`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to register bid document");
  }

  static async updateBidProfile(
    projectId: string,
    input: { facts: Record<string, unknown>; conflicts: unknown[]; row_version: number }
  ): Promise<BidProfileResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/profile`),
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to update bid profile");
  }

  static async confirmBidProfile(projectId: string): Promise<BidProfileResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/profile/confirm`),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to confirm bid profile");
  }

  static async createBidRequirement(
    projectId: string,
    input: {
      category: string;
      original_text: string;
      mandatory: boolean;
      score?: number;
      source_ref?: string;
      owner_department?: string;
      target_module?: string;
    }
  ): Promise<BidRequirementResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/requirements`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to create bid requirement");
  }

  static async updateBidRequirement(
    projectId: string,
    requirementId: string,
    input: {
      response: string | null;
      status: "open" | "answered" | "verified";
      owner_department: string | null;
      target_module: string | null;
      row_version: number;
    }
  ): Promise<BidRequirementResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/requirements/${encodeURIComponent(requirementId)}`
      ),
      {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to update bid requirement");
  }

  static async updateBidStrategy(
    projectId: string,
    input: { elements: Record<string, unknown>; row_version: number }
  ): Promise<BidStrategyResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/strategy`),
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to update bid strategy");
  }

  static async confirmBidStrategy(projectId: string): Promise<BidStrategyResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/strategy/confirm`),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "Failed to confirm bid strategy");
  }

  static async getBidCollaboration(projectId: string): Promise<BidCollaborationResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/collaboration`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load professional collaboration");
  }

  static async initializeBidModules(projectId: string): Promise<BidCollaborationResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/modules/initialize`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to initialize professional modules");
  }

  static async updateBidModule(projectId: string, moduleId: string, content: Record<string, unknown>, rowVersion: number): Promise<BidModuleResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/modules/${encodeURIComponent(moduleId)}`), { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content, row_version: rowVersion }) });
    return ApiResponseHandler.handleResponse(response, "Failed to update professional module");
  }

  static async submitBidModule(projectId: string, moduleId: string): Promise<BidModuleResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/modules/${encodeURIComponent(moduleId)}/submit`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to submit professional module");
  }

  static async reviewBidModule(projectId: string, moduleId: string, action: "approve" | "reject", comment?: string): Promise<BidModuleResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/modules/${encodeURIComponent(moduleId)}/review`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, comment }) });
    return ApiResponseHandler.handleResponse(response, "Failed to review professional module");
  }

  static async createBidCommitment(projectId: string, input: { content: string; commitment_type: string; evidence_ref?: string; risk_level: string }): Promise<BidCommitmentResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/commitments`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
    return ApiResponseHandler.handleResponse(response, "Failed to create commitment");
  }

  static async actOnBidCommitment(projectId: string, commitmentId: string, action: "submit" | "approve" | "reject" | "revoke"): Promise<BidCommitmentResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/commitments/${encodeURIComponent(commitmentId)}/action`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    return ApiResponseHandler.handleResponse(response, "Failed to update commitment");
  }

  static async actOnBidGate(projectId: string, gateType: "gate_1" | "gate_2" | "gate_3", action: "open" | "pass"): Promise<BidGateResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/gates/${gateType}/action`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    return ApiResponseHandler.handleResponse(response, "Failed to update review gate");
  }

  static async getBidReleases(projectId: string): Promise<BidReleaseResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load bid releases");
  }

  static async assembleBidRelease(projectId: string, templatePublicationId: string): Promise<BidReleaseResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases/assemble`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template_publication_id: templatePublicationId, release_type: "management-summary" }) });
    return ApiResponseHandler.handleResponse(response, "Failed to assemble bid summary");
  }

  static async freezeBidRelease(projectId: string, releaseId: string): Promise<BidReleaseResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases/${encodeURIComponent(releaseId)}/freeze`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to freeze bid release");
  }

  static async archiveBidRelease(projectId: string, releaseId: string): Promise<BidReleaseResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases/${encodeURIComponent(releaseId)}/archive`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to archive bid release");
  }

  static async getBidDeliveries(projectId: string, releaseId: string): Promise<BidDeliveryArtifactResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases/${encodeURIComponent(releaseId)}/deliveries`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load delivery artifacts");
  }

  static async createBidDelivery(projectId: string, releaseId: string, format: "pptx" | "pdf"): Promise<BidDeliveryArtifactResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/releases/${encodeURIComponent(releaseId)}/deliveries`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format }) });
    return ApiResponseHandler.handleResponse(response, "Failed to export delivery artifact");
  }

  static async issueBidDownloadGrant(projectId: string, artifactId: string): Promise<BidDownloadGrantResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/deliveries/${encodeURIComponent(artifactId)}/grants`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expires_in_minutes: 30, max_downloads: 1 }) });
    const grant = await ApiResponseHandler.handleResponse(response, "Failed to authorize delivery download") as BidDownloadGrantResponse;
    return { ...grant, download_url: getApiUrl(grant.download_url) };
  }

  static async revokeBidDelivery(projectId: string, artifactId: string): Promise<BidDeliveryArtifactResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/deliveries/${encodeURIComponent(artifactId)}/revoke`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to revoke delivery artifact");
  }
}
