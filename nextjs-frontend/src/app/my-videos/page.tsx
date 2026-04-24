"use client";

import { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/AppShell";
import { jobs, Job } from "@/lib/api";
import { formatCost, formatDateTime, STATUS_COLORS, STATUS_ICONS } from "@/lib/utils";
import { ExternalLink, X } from "lucide-react";

type TabKey = "all" | "completed" | "running" | "failed";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "completed", label: "✅ Completed" },
  { key: "running", label: "🔄 In Progress" },
  { key: "failed", label: "❌ Failed" },
];

function filterJobs(all: Job[], tab: TabKey): Job[] {
  if (tab === "all") return all;
  if (tab === "completed") return all.filter((j) => j.status === "completed");
  if (tab === "running") return all.filter((j) => ["queued", "running"].includes(j.status));
  return all.filter((j) => ["failed", "cancelled"].includes(j.status));
}

function JobRow({ job, onCancel }: { job: Job; onCancel: (id: string) => void }) {
  const [detail, setDetail] = useState<Job | null>(null);
  const [open, setOpen] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!open) return;
    try { const d = await jobs.get(job.id); setDetail(d); } catch {}
  }, [open, job.id]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  return (
    <>
      <tr
        className="border-t border-gray-800 hover:bg-gray-800/50 cursor-pointer transition"
        onClick={() => setOpen((o) => !o)}
      >
        <td className="px-4 py-3">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[job.status]}`}>
            {STATUS_ICONS[job.status]} {job.status}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-white font-medium max-w-xs truncate">
          {job.title || job.niche || "Untitled"}
        </td>
        <td className="px-4 py-3 text-sm text-gray-400">{formatDateTime(job.created_at)}</td>
        <td className="px-4 py-3 text-sm text-gray-400">{job.scenes_count ?? "—"}</td>
        <td className="px-4 py-3 text-sm text-gray-400">{formatCost(job.total_cost_usd)}</td>
        <td className="px-4 py-3 text-sm">
          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            {job.video_url && (
              <a
                href={job.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-red-400 hover:text-red-300 text-xs"
              >
                <ExternalLink className="w-3 h-3" /> YouTube
              </a>
            )}
            {["queued", "running"].includes(job.status) && (
              <button
                onClick={() => onCancel(job.id)}
                className="flex items-center gap-1 text-gray-400 hover:text-red-400 text-xs transition"
              >
                <X className="w-3 h-3" /> Cancel
              </button>
            )}
          </div>
        </td>
      </tr>

      {open && (
        <tr className="border-t border-gray-800 bg-gray-900">
          <td colSpan={6} className="px-4 py-4">
            {job.error_message && (
              <p className="text-sm text-red-400 mb-3">{job.error_message}</p>
            )}
            {detail ? (
              <>
                {detail.agents && detail.agents.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Agent Pipeline</p>
                    <div className="flex flex-wrap gap-2">
                      {detail.agents.map((a) => (
                        <span
                          key={a.agent_name}
                          className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[a.status]}`}
                        >
                          {STATUS_ICONS[a.status]} {a.agent_name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {detail.assets && detail.assets.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Assets</p>
                    <div className="flex flex-wrap gap-2">
                      {detail.assets.map((a, i) => (
                        <span key={i} className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded">
                          {a.type}{a.url?.startsWith("http") ? " ✓" : " (local)"}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-gray-500">Loading details...</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function MyVideosPage() {
  const [allJobs, setAllJobs] = useState<Job[]>([]);
  const [tab, setTab] = useState<TabKey>("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try { const d = await jobs.list(); setAllJobs(d.jobs); } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCancel = async (id: string) => {
    await jobs.cancel(id);
    load();
  };

  const visible = filterJobs(allJobs, tab);

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">My Videos</h1>
          <p className="text-gray-400 text-sm mt-1">All your generated videos and job history</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-gray-900 p-1 rounded-lg border border-gray-800 w-fit">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                tab === key ? "bg-red-600 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              {label}
              <span className="ml-1.5 text-xs opacity-70">
                ({filterJobs(allJobs, key).length})
              </span>
            </button>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : visible.length === 0 ? (
            <div className="text-center py-20 text-gray-500">No jobs in this category.</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Title / Niche</th>
                  <th className="px-4 py-3 text-left">Created</th>
                  <th className="px-4 py-3 text-left">Scenes</th>
                  <th className="px-4 py-3 text-left">Cost</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((j) => (
                  <JobRow key={j.id} job={j} onCancel={handleCancel} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
