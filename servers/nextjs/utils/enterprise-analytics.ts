"use client";

import { track } from "@/utils/mixpanel";

export const EnterpriseAnalyticsEvent = {
  WorkspacePageViewed: "Enterprise Workspace Page Viewed",
  WorkspaceSwitched: "Enterprise Workspace Switched",
  WorkspaceLoadFailed: "Enterprise Workspace Load Failed",
  RuntimeError: "Enterprise Workspace Runtime Error",
  CreationWizardOpened: "Enterprise Creation Wizard Opened",
  CreationRequested: "Enterprise Presentation Creation Requested",
  CreationAccepted: "Enterprise Presentation Creation Accepted",
  CreationFailed: "Enterprise Presentation Creation Failed",
  CreationResourceLoadFailed: "Enterprise Creation Resource Load Failed",
} as const;

export type EnterpriseAnalyticsEventName =
  (typeof EnterpriseAnalyticsEvent)[keyof typeof EnterpriseAnalyticsEvent];

type SafeEnterpriseAnalyticsProps = Record<
  string,
  string | number | boolean | null | undefined
>;

/**
 * Enterprise analytics must only contain bounded operational dimensions. Do
 * not pass workspace names, document text, prompts, user names or identifiers.
 */
export function trackEnterpriseEvent(
  event: EnterpriseAnalyticsEventName,
  props: SafeEnterpriseAnalyticsProps = {}
) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("enterprise:telemetry", { detail: { event, props } })
    );
  }
  track(event, props);
}

export function classifyEnterpriseError(cause: unknown): string {
  if (cause instanceof DOMException) return "DOMException";
  if (cause instanceof TypeError) return "TypeError";
  if (cause instanceof Error) return cause.name || "Error";
  return typeof cause === "string" ? "StringError" : "UnknownError";
}
