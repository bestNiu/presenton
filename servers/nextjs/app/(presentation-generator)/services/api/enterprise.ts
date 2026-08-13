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
  current_user_role: WorkspaceRole;
  created_at: string;
  updated_at: string;
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
  gate_type: "gate_1" | "gate_2";
  status: "locked" | "open" | "blocked" | "passed";
  issues: Array<{ id: string; title: string; status: "open" | "resolved" }>;
}

export interface BidCollaborationResponse {
  modules: BidModuleResponse[];
  commitments: BidCommitmentResponse[];
  gates: BidGateResponse[];
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
  status: string;
  can_open: boolean;
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

  static async actOnBidGate(projectId: string, gateType: "gate_1" | "gate_2", action: "open" | "pass"): Promise<BidGateResponse> {
    const response = await fetch(getApiUrl(`/api/v1/enterprise/bid/projects/${encodeURIComponent(projectId)}/gates/${gateType}/action`), { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    return ApiResponseHandler.handleResponse(response, "Failed to update review gate");
  }
}
