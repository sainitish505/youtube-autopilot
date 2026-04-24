"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import AppShell from "@/components/AppShell";
import { jobs, Job } from "@/lib/api";
import { formatCost, formatDateTime } from "@/lib/utils";
import {
  RefreshCw, CheckCircle, XCircle, Clock, Zap, Brain,
  FileText, Image, Mic, Film, Search, Upload, AlertCircle,
  ExternalLink, PlusCircle,
} from "lucide-react";
import Link from "next/link";

// ── Agent metadata ────────────────────────────────────────────────────────────
const AGENTS = [
  { name: "CEO",             label: "Research",  icon: Brain,       desc: "Picks trending topic & plans scenes" },
  { name: "ScriptPolisher",  label: "Script",    icon: FileText,    desc: "Writes & polishes the script"        },
  { name: "VisualGenerator", label: "Visuals",   icon: Image,       desc: "Generates clips with Sora + DALL-E"  },
  { name: "AudioEngineer",   label: "Audio",     icon: Mic,         desc: "Creates voiceover with TTS"         },
  { name: "VideoEditor",     label: "Edit",      icon: Film,        desc: "Assembles clips & audio"            },
  { name: "SEOOptimizer",    label: "SEO",       icon: Search,      desc: "Writes title, tags & description"   },
  { name: "Uploader",        label: "Upload",    icon: Upload,      desc: "Uploads to YouTube"                 },
];

// ── Elapsed timer hook ─────────────────────────────────────────────────────────
function useElapsed(startedAt?: string) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return elapsed;
}

function formatElapsed(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  if (m === 0) return `${sec}s`;
  return `${m}m ${sec.toString().padStart(2, "0")}s`;
}

// ── Live pipeline card (for queued/running jobs) ───────────────────────────────
function LiveJobCard({ job }: { job: Job }) {
  const [detail, setDetail] = useState<Job | null>(null);
  const elapsed = useElapsed(job.started_at);
  const isRunning = job.status === "running";

  const loadDetail = useCallback(async () => {
    try { setDetail(await jobs.get(job.id)); } catch {}
  }, [job.id]);

  useEffect(() => {
    loadDetail();
    const id = setInterval(loadDetail, 4000); // faster refresh for active jobs
    return () => clearInterval(id);
  }, [loadDetail]);

  const agentStatuses = detail?.agents || [];
  const doneCount = agentStatuses.filter((a) => a.status === "done").length;
  const progressPct = AGENTS.length > 0 ? Math.round((doneCount / AGENTS.length) * 100) : 0;

  // ETA: assume ~10 min total; scale remaining by progress
  const avgTotalSec = 10 * 60;
  const etaSec = doneCount > 0
    ? Math.max(0, Math.round((avgTotalSec - elapsed) * ((AGENTS.length - doneCount) / AGENTS.length)))
    : null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl overflow-hidden shadow-lg shadow-black/20">
      {/* Animated top bar */}
      {isRunning && (
        <div className="h-1 bg-gray-800 relative overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-600 to-orange-500 transition-all duration-1000"
            style={{ width: `${Math.max(progressPct, 5)}%` }}
          />
          {/* shimmer */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-[shimmer_2s_infinite]" />
        </div>
      )}
      {job.status === "queued" && (
        <div className="h-1 bg-yellow-500/40 animate-pulse" />
      )}

      <div className="p-6">
        {/* Header row */}
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              {/* Pulsing live badge */}
              {isRunning && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                  LIVE
                </span>
              )}
              {job.status === "queued" && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
                  QUEUED
                </span>
              )}
              <span className="text-xs text-gray-500">{formatDateTime(job.created_at)}</span>
            </div>
            <h3 className="text-lg font-bold text-white truncate">
              {job.title || job.niche || "Generating video…"}
            </h3>
          </div>

          {/* Timer & cost */}
          <div className="flex items-center gap-4 flex-shrink-0 text-right">
            {isRunning && (
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Elapsed</p>
                <p className="text-sm font-bold text-white tabular-nums">{formatElapsed(elapsed)}</p>
              </div>
            )}
            {etaSec !== null && etaSec > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-0.5">~ETA</p>
                <p className="text-sm font-bold text-orange-400 tabular-nums">{formatElapsed(etaSec)}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Cost</p>
              <p className="text-sm font-bold text-white">{formatCost(job.total_cost_usd)}</p>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {agentStatuses.length > 0 && (
          <div className="mb-5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-gray-500">Pipeline progress</span>
              <span className="text-xs font-medium text-gray-400">{doneCount} / {AGENTS.length} agents</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-red-600 to-orange-500 rounded-full transition-all duration-700"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}

        {/* Agent pipeline steps — horizontally scrollable on small screens */}
        <div className="overflow-x-auto -mx-1 pb-1">
        <div className="grid grid-cols-7 gap-1.5 min-w-[380px] px-1">
          {AGENTS.map(({ name, label, icon: Icon, desc }, i) => {
            const a = agentStatuses.find((x) => x.agent_name === name);
            const status = a?.status || "pending";
            const isDone = status === "done";
            const isActive = status === "running";
            const isFailed = status === "failed";

            return (
              <div key={name} className="flex flex-col items-center gap-1.5 group relative">
                {/* Connector line */}
                {i < AGENTS.length - 1 && (
                  <div className="absolute left-1/2 top-5 w-full h-0.5 -z-0">
                    <div className={`h-full transition-colors duration-500 ${isDone ? "bg-green-500/40" : "bg-gray-800"}`} />
                  </div>
                )}

                {/* Icon circle */}
                <div className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                  isDone    ? "bg-green-500/20 border-green-500 text-green-400" :
                  isActive  ? "bg-red-500/20 border-red-500 text-red-400 shadow-lg shadow-red-500/20" :
                  isFailed  ? "bg-red-900/30 border-red-700 text-red-500" :
                  "bg-gray-800 border-gray-700 text-gray-600"
                }`}>
                  {isDone ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : isActive ? (
                    <Icon className="w-4 h-4 animate-pulse" />
                  ) : isFailed ? (
                    <XCircle className="w-4 h-4" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                  {/* Spinning ring for active */}
                  {isActive && (
                    <div className="absolute inset-0 rounded-full border-2 border-red-500 border-t-transparent animate-spin" />
                  )}
                </div>

                {/* Label */}
                <span className={`text-xs font-medium text-center leading-tight ${
                  isDone ? "text-green-400" : isActive ? "text-red-400" : "text-gray-600"
                }`}>{label}</span>

                {/* Tooltip on hover */}
                <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 bg-gray-800 text-gray-300 text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none border border-gray-700">
                  {desc}
                </div>
              </div>
            );
          })}
        </div>
        </div>{/* end overflow-x-auto */}

        {/* Loading state when detail not yet fetched */}
        {agentStatuses.length === 0 && (
          <div className="flex items-center gap-3 py-4">
            <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <span className="text-sm text-gray-500">Initialising pipeline…</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Compact card for completed/failed jobs ─────────────────────────────────────
function CompactJobCard({ job }: { job: Job }) {
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed" || job.status === "cancelled";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition flex items-center gap-4">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        isCompleted ? "bg-green-500/20" : isFailed ? "bg-red-900/30" : "bg-gray-800"
      }`}>
        {isCompleted ? <CheckCircle className="w-4 h-4 text-green-400" /> :
         isFailed    ? <XCircle className="w-4 h-4 text-red-400" /> :
                       <Clock className="w-4 h-4 text-gray-500" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{job.title || job.niche || "Untitled"}</p>
        <p className="text-xs text-gray-500">{formatDateTime(job.created_at)}</p>
        {job.error_message && <p className="text-xs text-red-400 truncate mt-0.5">{job.error_message}</p>}
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="text-right">
          <p className="text-xs text-gray-500">Cost</p>
          <p className="text-xs font-medium text-white">{formatCost(job.total_cost_usd)}</p>
        </div>
        {job.video_url && job.video_url.startsWith("https://") && (
          <a
            href={job.video_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2.5 py-1.5 bg-red-600 hover:bg-red-700 rounded-lg text-xs text-white font-medium transition"
          >
            <ExternalLink className="w-3 h-3" /> Watch
          </a>
        )}
      </div>
    </div>
  );
}

// ── Main dashboard ─────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [allJobs, setAllJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await jobs.list();
      setAllJobs(data.jobs);
      setLastUpdated(new Date());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 6000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [load]);

  const active  = allJobs.filter((j) => ["queued", "running"].includes(j.status));
  const history = allJobs.filter((j) => !["queued", "running"].includes(j.status)).slice(0, 8);

  const stats = [
    { label: "Total",     value: allJobs.length,                                               color: "text-white",      bg: "bg-gray-800" },
    { label: "Completed", value: allJobs.filter((j) => j.status === "completed").length,        color: "text-green-400",  bg: "bg-green-500/10" },
    { label: "Active",    value: active.length,                                                 color: "text-red-400",    bg: "bg-red-500/10" },
    { label: "Failed",    value: allJobs.filter((j) => j.status === "failed").length,           color: "text-gray-400",   bg: "bg-gray-800" },
  ];

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            <div className="flex items-center gap-2 mt-1">
              {active.length > 0 ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-sm text-gray-400">{active.length} job{active.length > 1 ? "s" : ""} running · auto-refreshing</span>
                </>
              ) : (
                <span className="text-sm text-gray-500">
                  {lastUpdated ? `Updated ${formatElapsed(Math.floor((Date.now() - lastUpdated.getTime()) / 1000))} ago` : "Loading…"}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => load()}
              className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <Link
              href="/new-video"
              className="flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm text-white font-medium transition"
            >
              <PlusCircle className="w-4 h-4" /> New Video
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {stats.map(({ label, value, color, bg }) => (
            <div key={label} className={`${bg} border border-gray-800 rounded-xl p-4`}>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">{label}</p>
              <p className={`text-3xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Active jobs — full live cards */}
        {active.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
                Active  ({active.length})
              </h2>
            </div>
            <div className="space-y-4">
              {active.map((j) => <LiveJobCard key={j.id} job={j} />)}
            </div>
          </div>
        )}

        {/* Empty state */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : allJobs.length === 0 ? (
          <div className="text-center py-24 bg-gray-900 border border-gray-800 rounded-2xl">
            <Zap className="w-12 h-12 text-gray-700 mx-auto mb-4" />
            <p className="text-white font-semibold mb-1">No videos yet</p>
            <p className="text-gray-500 text-sm mb-6">Generate your first AI video in under 10 minutes</p>
            <Link
              href="/new-video"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 rounded-lg text-white font-medium transition text-sm"
            >
              <PlusCircle className="w-4 h-4" /> Generate First Video
            </Link>
          </div>
        ) : (
          /* History */
          history.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">History</h2>
              <div className="space-y-2">
                {history.map((j) => <CompactJobCard key={j.id} job={j} />)}
              </div>
              {allJobs.length > 8 && (
                <Link href="/my-videos" className="block text-center text-sm text-red-400 hover:text-red-300 mt-4 transition">
                  View all {allJobs.length} videos →
                </Link>
              )}
            </div>
          )
        )}
      </div>
    </AppShell>
  );
}
