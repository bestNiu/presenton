"use client";

import { ReactNode } from "react";
import { Clock3, History, ShieldCheck, X } from "lucide-react";

export interface ResourceDetailField {
  label: string;
  value: ReactNode;
}

export interface ResourceVersionItem {
  id: string;
  label: string;
  detail: string;
  current?: boolean;
}

interface ResourceDetailDrawerProps {
  open: boolean;
  eyebrow: string;
  title: string;
  description?: string | null;
  status: string;
  fields: ResourceDetailField[];
  versions?: ResourceVersionItem[];
  governanceNote?: string;
  actions?: ReactNode;
  children?: ReactNode;
  onClose: () => void;
}

export default function ResourceDetailDrawer({
  open,
  eyebrow,
  title,
  description,
  status,
  fields,
  versions = [],
  governanceNote,
  actions,
  children,
  onClose,
}: ResourceDetailDrawerProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] bg-black/30" role="dialog" aria-modal="true" aria-labelledby="resource-detail-title">
      <button type="button" aria-label="关闭资源详情" onClick={onClose} className="absolute inset-0 cursor-default" />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-[#EAECF0] px-6 py-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[#635BFF]">{eyebrow}</p>
            <h2 id="resource-detail-title" className="mt-1 truncate text-xl font-semibold text-[#101828]">{title}</h2>
            {description && <p className="mt-2 text-sm leading-6 text-[#667085]">{description}</p>}
          </div>
          <button type="button" onClick={onClose} className="ml-4 rounded-lg p-2 text-[#667085] hover:bg-[#F2F4F7]" aria-label="关闭"><X className="h-5 w-5" /></button>
        </header>
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-6">
          <div className="flex items-center justify-between rounded-xl bg-[#F8F9FC] p-4">
            <span className="text-sm font-medium text-[#344054]">当前治理状态</span>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-[#4238CA] shadow-sm">{status}</span>
          </div>
          <dl className="grid gap-4 sm:grid-cols-2">
            {fields.map((field) => <div key={field.label}><dt className="text-xs text-[#98A2B3]">{field.label}</dt><dd className="mt-1 break-words text-sm text-[#344054]">{field.value}</dd></div>)}
          </dl>
          {children}
          {versions.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-[#101828]"><History className="h-4 w-4 text-[#635BFF]" />版本时间线</h3>
              <div className="mt-3 space-y-2 border-l-2 border-[#E4E1FF] pl-4">
                {versions.map((version) => <div key={version.id} className="rounded-xl border border-[#EAECF0] p-3"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium text-[#344054]">{version.label}</span>{version.current && <span className="rounded-full bg-[#ECFDF3] px-2 py-1 text-[10px] text-[#027A48]">当前版本</span>}</div><p className="mt-1 flex items-center gap-1 text-xs text-[#667085]"><Clock3 className="h-3 w-3" />{version.detail}</p></div>)}
              </div>
            </section>
          )}
          {governanceNote && <div className="flex items-start gap-2 rounded-xl bg-[#F0F9FF] p-4 text-xs leading-5 text-[#175CD3]"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />{governanceNote}</div>}
        </div>
        {actions && <footer className="flex flex-wrap justify-end gap-2 border-t border-[#EAECF0] px-6 py-4">{actions}</footer>}
      </aside>
    </div>
  );
}
