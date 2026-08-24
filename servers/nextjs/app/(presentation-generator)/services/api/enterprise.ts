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
    presentation_archive_retention_days: number;
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

export interface FolderResponse {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  created_by: string | null;
  name: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
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
  issues: Array<{
    id: string;
    title: string;
    description: string | null;
    severity: "blocking" | "warning";
    status: "open" | "resolved";
    owner_id: string | null;
    resolution: string | null;
    created_at: string;
    updated_at: string;
  }>;
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
  created_by: string | null;
  title: string | null;
  scene_type: string;
  creation_mode: PresentationCreationMode;
  status: "draft" | "in_review" | "approved" | "frozen" | "published" | "archived";
  can_open: boolean;
  updated_at: string;
}

export interface PresentationCatalogItemResponse
  extends PresentationEntryResponse {
  creator_username: string | null;
  archive_expires_at: string | null;
}

export interface PresentationCatalogResponse {
  items: PresentationCatalogItemResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  archive_retention_days: number;
}

export interface PresentationArchiveLifecycleResponse {
  mode: "dry_run" | "execute";
  retention_days: number;
  candidate_count: number;
  purged_count: number;
  candidates: Array<{
    id: string;
    presentation_id: string;
    title: string | null;
    archived_at: string;
    expires_at: string;
  }>;
}

export interface EnterpriseDocumentResponse {
  id: string;
  version_group_id: string;
  version_no: number;
  is_latest: boolean;
  supersedes_document_id: string | null;
  workspace_id: string | null;
  project_id: string | null;
  scope_type: "enterprise" | "workspace" | "project";
  logical_name: string;
  category: string;
  file_name: string;
  mime_type: string;
  sha256: string;
  size_bytes: number;
  authorization_status: "internal" | "authorized" | "revoked";
  confidentiality: ConfidentialityLevel;
  status: string;
  parse_status: "queued" | "parsing" | "ready" | "error";
  parse_task_id: string | null;
  parse_error: string | null;
  extracted_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EnterpriseKnowledgeSearchItemResponse {
  chunk_id: string;
  document_id: string;
  document_version: number;
  logical_name: string;
  category: string;
  heading: string | null;
  excerpt: string;
  locator: Record<string, unknown>;
  score: number;
  retrieval_mode: "lexical" | "hybrid";
  score_components: { lexical: number; semantic: number };
  matched_terms: string[];
  citation: {
    source_type: string;
    source_id: string;
    source_version: string;
    locator: string;
    excerpt: string;
  };
}

export interface PresentationSourceCitationResponse {
  id: string;
  presentation_entry_id: string;
  slide_id: string | null;
  element_ref: string | null;
  source_type: string;
  source_id: string;
  source_version: string | null;
  locator: string | null;
  excerpt: string | null;
  created_by: string | null;
  created_at: string;
  status: "valid" | "missing" | "revoked" | "archived" | "expired" | "unavailable" | "source_updated" | "locator_changed" | "excerpt_changed";
  status_message: string;
  source_name: string | null;
  source_category: string | null;
  current_version: string | null;
  source_available: boolean;
}

export interface PresentationSourceCitationSummaryResponse {
  total_citations: number;
  valid_citations: number;
  invalid_citations: number;
  cited_slide_ids: string[];
  invalid_citation_ids: string[];
}

export interface PresentationSourceCitationPreviewResponse {
  citation: PresentationSourceCitationResponse;
  heading: string | null;
  content: string | null;
}

export interface EnterpriseKnowledgeOutlineResponse {
  id: string;
  workspace_id: string | null;
  project_id: string | null;
  presentation_entry_id: string | null;
  scope_type: "enterprise" | "workspace" | "project";
  topic: string;
  audience: string | null;
  language: string;
  n_slides: number;
  status: "queued" | "generating" | "ready" | "error";
  task_id: string | null;
  query: string;
  document_ids: string[];
  context_manifest: Array<Record<string, unknown>>;
  outline: { slides?: Array<{ content: string; citation_refs: string[] }> };
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnterpriseKnowledgePresentationResponse {
  presentation_id: string;
  presentation_entry_id: string;
  outline: EnterpriseKnowledgeOutlineResponse;
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

export interface PresentationFreezePreflightResponse {
  can_freeze: boolean;
  slide_snapshot_hash: string;
  checks: Array<{ code: string; label: string; passed: boolean; message: string; count: number }>;
}

export interface PresentationSnapshotEvidenceResponse {
  snapshot_id: string;
  version_no: number;
  frozen_at: string;
  manifest_hash: string;
  manifest_integrity: boolean;
  citation_manifest_hash: string | null;
  citation_integrity: boolean;
  citations: Array<{ id: string; slide_id: string | null; source_type: string; source_id: string; source_version: string | null; locator: string | null; excerpt: string | null; status: string; source_name: string | null; current_version: string | null }>;
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

export interface PresentationDeliveryEvidenceResponse {
  artifact: PresentationDeliveryArtifactResponse;
  snapshot_id: string;
  snapshot_version: number;
  snapshot_manifest_hash: string;
  citation_manifest_hash: string | null;
  citation_count: number;
  file_integrity: boolean;
  snapshot_integrity: boolean;
  citation_integrity: boolean;
  credential_hash: string;
}

export interface AuditEventResponse {
  id: string;
  actor_id: string | null;
  workspace_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  result: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface PresentationDeliveryEvidenceVerifyResponse {
  valid: boolean;
  package_integrity: boolean;
  issued_by_platform: boolean;
  artifact_match: boolean;
  current_file_integrity: boolean;
  current_snapshot_integrity: boolean;
  current_citation_integrity: boolean;
  package_hash: string | null;
}

export interface DeliveryCenterResponse {
  summary: { total: number; ready: number; revoked: number; integrity_failed: number; downloads: number; active_grants: number };
  items: Array<{
    artifact_id: string;
    scene_type: "general" | "bid";
    resource_id: string;
    resource_title: string;
    resource_code: string | null;
    version_no: number;
    format: "pptx" | "pdf";
    file_name: string;
    sha256: string;
    size_bytes: number;
    watermark_text: string;
    status: "ready" | "revoked";
    integrity_status: "passed" | "failed";
    file_integrity: boolean;
    snapshot_integrity: boolean;
    citation_integrity: boolean | null;
    citation_count: number;
    grant_count: number;
    active_grant_count: number;
    download_count: number;
    created_at: string;
    revoked_at: string | null;
    purged_at: string | null;
    detail_url: string;
  }>;
}

export interface DeliveryIntegrityScanResponse {
  id: string;
  workspace_id: string;
  total: number;
  integrity_failed: number;
  anomaly_ids: string[];
  new_anomaly_ids: string[];
  opened_incident_ids: string[];
  resolved_incident_ids: string[];
  revoked_grant_count: number;
  created_at: string;
}

export interface DeliveryIntegrityIncidentResponse {
  id: string;
  workspace_id: string;
  workspace_name: string;
  scene_type: "general" | "bid";
  artifact_id: string;
  resource_id: string;
  resource_title: string;
  detail_url: string;
  anomaly_types: Array<"file_integrity" | "snapshot_integrity" | "citation_integrity">;
  severity: "high" | "medium" | "low";
  status: "open" | "in_progress" | "resolved" | "accepted_risk" | "false_positive";
  authorization_paused: boolean;
  assigned_to: string | null;
  assigned_to_username: string | null;
  occurrence_count: number;
  resolution_note: string | null;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  updated_at: string;
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
      "个人工作空间初始化失败，请稍后重试"
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
      "工作空间加载失败，请稍后重试"
    );
  }

  static async getDocuments(workspaceId: string, includeVersions = false): Promise<EnterpriseDocumentResponse[]> {
    const params = new URLSearchParams({ scope_type: "workspace", workspace_id: workspaceId });
    if (includeVersions) params.set("include_versions", "true");
    const response = await fetch(getApiUrl(`/api/v1/enterprise/documents?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load enterprise documents");
  }

  static async uploadDocument(workspaceId: string, file: File, input: { logicalName: string; category: string; confidentiality: ConfidentialityLevel }): Promise<EnterpriseDocumentResponse> {
    const data = new FormData();
    data.set("file", file);
    data.set("scope_type", "workspace");
    data.set("workspace_id", workspaceId);
    data.set("logical_name", input.logicalName);
    data.set("category", input.category);
    data.set("confidentiality", input.confidentiality);
    const response = await fetch(getApiUrl("/api/v1/enterprise/documents"), { method: "POST", credentials: "include", body: data });
    return ApiResponseHandler.handleResponse(response, "Failed to upload enterprise document");
  }

  static async retryDocumentParse(documentId: string): Promise<{ document_id: string; task_id: string; status: string }> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/documents/${encodeURIComponent(documentId)}/parse-tasks`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to retry document parsing");
  }

  static async searchKnowledge(workspaceId: string, query: string, documentIds: string[] = []): Promise<EnterpriseKnowledgeSearchItemResponse[]> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/knowledge/search"), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, scope_type: "workspace", workspace_id: workspaceId, document_ids: documentIds, retrieval_mode: "hybrid", latest_only: true, limit: 20 }) });
    return ApiResponseHandler.handleResponse(response, "Failed to search enterprise knowledge");
  }

  static async createKnowledgeOutline(workspaceId: string, input: { topic: string; query?: string; audience?: string; nSlides: number; documentIds: string[] }): Promise<EnterpriseKnowledgeOutlineResponse> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/knowledge/outlines"), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: input.topic, query: input.query || input.topic, audience: input.audience || undefined, n_slides: input.nSlides, document_ids: input.documentIds, scope_type: "workspace", workspace_id: workspaceId, language: "Chinese" }) });
    return ApiResponseHandler.handleResponse(response, "Failed to create knowledge outline");
  }

  static async createKnowledgePresentation(
    workspaceId: string,
    input: {
      topic: string;
      query?: string;
      audience?: string;
      nSlides: number;
      documentIds: string[];
      instructions?: string;
      folderId?: string;
      language?: string;
    },
    idempotencyKey: string
  ): Promise<EnterpriseKnowledgePresentationResponse> {
    const response = await fetch(getApiUrl("/api/v1/enterprise/knowledge/presentations"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        topic: input.topic,
        query: input.query || input.topic,
        audience: input.audience || undefined,
        n_slides: input.nSlides,
        document_ids: input.documentIds,
        workspace_id: workspaceId,
        language: input.language || "Chinese",
        instructions: input.instructions || undefined,
        folder_id: input.folderId || undefined,
      }),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to create knowledge presentation");
  }

  static async getKnowledgeOutline(outlineId: string): Promise<EnterpriseKnowledgeOutlineResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/knowledge/outlines/${encodeURIComponent(outlineId)}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load knowledge outline");
  }

  static async applyKnowledgeOutline(outlineId: string, workspaceId: string, entryId: string): Promise<EnterpriseKnowledgeOutlineResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/knowledge/outlines/${encodeURIComponent(outlineId)}/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/apply`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to apply knowledge outline");
  }

  static async materializeKnowledgeCitations(outlineId: string, workspaceId: string, entryId: string): Promise<unknown[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/knowledge/outlines/${encodeURIComponent(outlineId)}/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to materialize knowledge citations");
  }

  static async getPresentationCitations(workspaceId: string, entryId: string): Promise<PresentationSourceCitationResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load presentation citations");
  }

  static async getPresentationCitationSummary(workspaceId: string, entryId: string): Promise<PresentationSourceCitationSummaryResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations/summary`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load citation summary");
  }

  static async getPresentationCitationPreview(workspaceId: string, entryId: string, citationId: string): Promise<PresentationSourceCitationPreviewResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations/${encodeURIComponent(citationId)}/source`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load citation source");
  }

  static async createPresentationCitation(workspaceId: string, entryId: string, input: { slide_id?: string; element_ref?: string; source_type: string; source_id: string; source_version?: string; locator?: string; excerpt?: string }): Promise<PresentationSourceCitationResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
    return ApiResponseHandler.handleResponse(response, "Failed to create citation");
  }

  static async deletePresentationCitation(workspaceId: string, entryId: string, citationId: string): Promise<void> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/citations/${encodeURIComponent(citationId)}`), { method: "DELETE", credentials: "include" });
    if (!response.ok) await ApiResponseHandler.handleResponse(response, "Failed to delete citation");
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
    return ApiResponseHandler.handleResponse(response, "工作空间成员加载失败，请稍后重试");
  }

  static async updateWorkspace(
    workspaceId: string,
    input: { name: string; confidentiality: ConfidentialityLevel }
  ): Promise<WorkspaceResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}`),
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(response, "工作空间基本信息保存失败");
  }

  static async inviteWorkspaceMember(
    workspaceId: string,
    username: string,
    role: Exclude<WorkspaceRole, "owner">
  ): Promise<WorkspaceMemberResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/members`),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, role }),
      }
    );
    return ApiResponseHandler.handleResponse(response, "成员添加失败，请检查用户名和权限");
  }

  static async updateWorkspaceMember(
    workspaceId: string,
    userId: string,
    role: Exclude<WorkspaceRole, "owner">
  ): Promise<WorkspaceMemberResponse> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`),
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, role }),
      }
    );
    return ApiResponseHandler.handleResponse(response, "成员角色更新失败");
  }

  static async removeWorkspaceMember(
    workspaceId: string,
    userId: string
  ): Promise<boolean> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`),
      { method: "DELETE", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(response, "成员移除失败");
  }

  static async getWorkspaceAuditEvents(
    workspaceId: string,
    limit = 50
  ): Promise<AuditEventResponse[]> {
    const response = await fetch(
      getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/audit-events?limit=${limit}`),
      { credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(response, "审计记录加载失败");
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
      "团队工作空间创建失败，请稍后重试"
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
      "专业场景加载失败，其他工作台功能仍可继续使用"
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
      "工作空间文稿加载失败，请稍后重试"
    );
  }

  static async getPresentationCatalog(
    workspaceId: string,
    filters: {
      query?: string;
      folder_id?: string;
      unfiled_only?: boolean;
      presentation_status?: PresentationEntryResponse["status"];
      creation_mode?: PresentationCreationMode;
      mine_only?: boolean;
      sort_by?:
        | "updated_desc"
        | "updated_asc"
        | "title_asc"
        | "title_desc"
        | "created_desc";
      page?: number;
      page_size?: number;
    }
  ): Promise<PresentationCatalogResponse> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") params.set(key, String(value));
    });
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/search?${params.toString()}`
      ),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿目录加载失败，请稍后重试"
    );
  }

  static async archivePresentation(
    workspaceId: string,
    entryId: string
  ): Promise<PresentationEntryResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/archive`
      ),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿归档失败，请确认文稿仍处于草稿状态"
    );
  }

  static async restorePresentation(
    workspaceId: string,
    entryId: string
  ): Promise<PresentationEntryResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/restore`
      ),
      { method: "POST", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿恢复失败，请稍后重试"
    );
  }

  static async bulkUpdatePresentationLifecycle(
    workspaceId: string,
    entryIds: string[],
    action: "archive" | "restore"
  ): Promise<PresentationEntryResponse[]> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/lifecycle`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_ids: entryIds, action }),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      action === "archive"
        ? "批量归档失败，请确认所选文稿均为草稿"
        : "批量恢复失败，请确认所选文稿均已归档"
    );
  }

  static async copyPresentation(
    workspaceId: string,
    entryId: string,
    input: {
      target_workspace_id: string;
      target_folder_id: string | null;
      title?: string;
    }
  ): Promise<PresentationEntryResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/copy`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿复制失败，请检查目标工作空间权限"
    );
  }

  static async purgePresentation(
    workspaceId: string,
    entryId: string,
    confirmTitle: string
  ): Promise<void> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/purge`
      ),
      {
        method: "DELETE",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_title: confirmTitle }),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿彻底删除失败，请确认名称和管理员权限"
    );
  }

  static async runPresentationArchiveLifecycle(
    workspaceId: string,
    execute: boolean,
    maxDelete = 100
  ): Promise<PresentationArchiveLifecycleResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentation-archive-lifecycle-runs`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ execute, max_delete: maxDelete }),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "归档清理任务执行失败，请稍后重试"
    );
  }

  static async getFolders(workspaceId: string): Promise<FolderResponse[]> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/folders`
      ),
      { method: "GET", credentials: "include", cache: "no-store" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "工作空间文件夹加载失败，请稍后重试"
    );
  }

  static async createFolder(
    workspaceId: string,
    input: { name: string; parent_id: string | null }
  ): Promise<FolderResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/folders`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文件夹创建失败，请稍后重试"
    );
  }

  static async updateFolder(
    workspaceId: string,
    folderId: string,
    input: { name: string; parent_id: string | null }
  ): Promise<FolderResponse> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/folders/${encodeURIComponent(folderId)}`
      ),
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文件夹更新失败，请稍后重试"
    );
  }

  static async archiveFolder(
    workspaceId: string,
    folderId: string
  ): Promise<void> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/folders/${encodeURIComponent(folderId)}`
      ),
      { method: "DELETE", credentials: "include" }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文件夹归档失败，请先移出其中的文稿和子文件夹"
    );
  }

  static async movePresentations(
    workspaceId: string,
    entryIds: string[],
    folderId: string | null
  ): Promise<PresentationEntryResponse[]> {
    const response = await fetch(
      getApiUrl(
        `/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/move`
      ),
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_ids: entryIds, folder_id: folderId }),
      }
    );
    return ApiResponseHandler.handleResponse(
      response,
      "文稿移动失败，请稍后重试"
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

  static async getPresentationFreezePreflight(workspaceId: string, entryId: string): Promise<PresentationFreezePreflightResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/freeze-preflight`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load freeze preflight");
  }

  static async getPresentationSnapshotEvidence(workspaceId: string, entryId: string, snapshotId: string): Promise<PresentationSnapshotEvidenceResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/snapshots/${encodeURIComponent(snapshotId)}/evidence`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load snapshot evidence");
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

  static async bulkUpdatePresentationReviewTasks(
    workspaceId: string,
    input: {
      thread_ids: string[];
      assigned_to?: string | null;
      due_at?: string | null;
      update_assignee: boolean;
      update_due_at: boolean;
    }
  ): Promise<{ updated_count: number }> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/review-inbox/bulk-update`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to update review task assignments");
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

  static async getPresentationDeliveries(workspaceId: string, entryId: string): Promise<PresentationDeliveryArtifactResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load governed deliveries");
  }

  static async getPresentationDeliveryEvidence(workspaceId: string, entryId: string, artifactId: string): Promise<PresentationDeliveryEvidenceResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/evidence`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to verify delivery evidence");
  }

  static async getPresentationDeliveryActivity(workspaceId: string, entryId: string, artifactId: string): Promise<AuditEventResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/activity`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load delivery activity");
  }

  static async downloadPresentationDeliveryEvidencePackage(workspaceId: string, entryId: string, artifactId: string): Promise<void> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/evidence-package`), { credentials: "include", cache: "no-store" });
    if (!response.ok) await ApiResponseHandler.handleResponse(response, "Failed to export delivery evidence package");
    const blobUrl = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = `presentation-delivery-${artifactId}-evidence.json`;
    anchor.click();
    URL.revokeObjectURL(blobUrl);
  }

  static async verifyPresentationDeliveryEvidencePackage(workspaceId: string, entryId: string, artifactId: string, evidencePackage: Record<string, unknown>): Promise<PresentationDeliveryEvidenceVerifyResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/presentations/${encodeURIComponent(entryId)}/deliveries/${encodeURIComponent(artifactId)}/evidence-package/verify`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ package: evidencePackage }) });
    return ApiResponseHandler.handleResponse(response, "Failed to verify delivery evidence package");
  }

  static async getDeliveryCenter(workspaceId: string, filters: { sceneType?: string; status?: string; integrity?: string; q?: string } = {}): Promise<DeliveryCenterResponse> {
    const params = new URLSearchParams();
    if (filters.sceneType) params.set("scene_type", filters.sceneType);
    if (filters.status) params.set("delivery_status", filters.status);
    if (filters.integrity) params.set("integrity_status", filters.integrity);
    if (filters.q) params.set("q", filters.q);
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-center?${params.toString()}`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load delivery center");
  }

  static async runDeliveryIntegrityScan(workspaceId: string): Promise<DeliveryIntegrityScanResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-center/integrity-runs`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to run delivery integrity scan");
  }

  static async getDeliveryIntegrityScans(workspaceId: string): Promise<DeliveryIntegrityScanResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-center/integrity-runs`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load delivery integrity scans");
  }

  static async getDeliveryIntegrityIncidents(workspaceId: string): Promise<DeliveryIntegrityIncidentResponse[]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-integrity-incidents`), { credentials: "include", cache: "no-store" });
    return ApiResponseHandler.handleResponse(response, "Failed to load delivery integrity incidents");
  }

  static async updateDeliveryIntegrityIncident(workspaceId: string, incidentId: string, input: { status: DeliveryIntegrityIncidentResponse["status"]; resolution_note?: string }): Promise<DeliveryIntegrityIncidentResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-integrity-incidents/${encodeURIComponent(incidentId)}`), { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
    return ApiResponseHandler.handleResponse(response, "Failed to update delivery integrity incident");
  }

  static async recheckDeliveryIntegrityIncident(workspaceId: string, incidentId: string): Promise<DeliveryIntegrityIncidentResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/workspaces/${encodeURIComponent(workspaceId)}/delivery-integrity-incidents/${encodeURIComponent(incidentId)}/recheck`), { method: "POST", credentials: "include" });
    return ApiResponseHandler.handleResponse(response, "Failed to recheck delivery integrity incident");
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

  static async createBidGateIssue(
    projectId: string,
    gateType: "gate_1" | "gate_2" | "gate_3",
    input: { title: string; description?: string; severity: "blocking" | "warning"; owner_id?: string }
  ): Promise<BidGateResponse["issues"][number]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/gates/${gateType}/issues`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to create gate issue");
  }

  static async resolveBidGateIssue(
    projectId: string,
    issueId: string,
    resolution: string
  ): Promise<BidGateResponse["issues"][number]> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/gate-issues/${encodeURIComponent(issueId)}/resolve`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution }),
    });
    return ApiResponseHandler.handleResponse(response, "Failed to resolve gate issue");
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
