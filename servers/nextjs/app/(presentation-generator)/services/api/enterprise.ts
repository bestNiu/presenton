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
}
