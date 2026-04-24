"use client";

import { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/AppShell";
import { analytics, AnalyticsSummary } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { TrendingUp, DollarSign, Video, CheckCircle } from "lucide-react";

const SERVICE_COLORS: Record<string, string> = {
  sora_generate: "#ef4444",
  tts_generate: "#3b82f6",
  dalle_generate: "#a855f7",
  gpt4o_call: "#22c55e",
};

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await analytics.summary());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </AppShell>
    );
  }

  if (error || !data) {
    return (
      <AppShell>
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-white">Analytics</h1>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
            <p className="text-gray-500 text-sm">{error || "No data yet. Generate your first video to see stats here."}</p>
          </div>
        </div>
      </AppShell>
    );
  }

  // Build chart-ready arrays from the API response
  const costByServiceData = Object.entries(data.cost_by_type || {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: k.replace(/_/g, " "), cost: v, key: k }));

  const nicheData = Object.entries(data.videos_by_niche || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([niche, count]) => ({ niche: niche || "Auto", count }));

  const maxNicheCount = nicheData[0]?.count || 1;

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-gray-400 text-sm mt-1">Cost breakdown and usage stats</p>
        </div>

        {/* Top metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            {
              label: "Videos This Month",
              value: data.videos_this_month,
              icon: Video,
              color: "text-blue-400",
            },
            {
              label: "Cost This Month",
              value: formatCost(data.cost_this_month_usd),
              icon: DollarSign,
              color: "text-green-400",
            },
            {
              label: "Total Videos",
              value: data.total_videos,
              icon: TrendingUp,
              color: "text-purple-400",
            },
            {
              label: "Success Rate",
              value: `${data.success_rate.toFixed(0)}%`,
              icon: CheckCircle,
              color: data.success_rate >= 80 ? "text-green-400" : "text-yellow-400",
            },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  {label}
                </span>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <p className="text-2xl font-bold text-white">{value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Cost by service */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-5">
              Cost by Service
            </h2>
            {costByServiceData.length === 0 ? (
              <div className="flex items-center justify-center h-48 text-gray-600 text-sm">
                No API usage recorded yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={costByServiceData} barSize={32}>
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#9ca3af" }} />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                    tickFormatter={(v) => `$${(v as number).toFixed(2)}`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#1f2937",
                      border: "1px solid #374151",
                      borderRadius: 8,
                    }}
                    labelStyle={{ color: "#f9fafb" }}
                    formatter={(v) => [`$${(v as number).toFixed(3)}`, "Cost"]}
                  />
                  <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                    {costByServiceData.map((entry) => (
                      <Cell
                        key={entry.key}
                        fill={SERVICE_COLORS[entry.key] || "#6b7280"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* All-time summary */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-5">
              All-time Summary
            </h2>
            <div className="space-y-4">
              {[
                { label: "Total Videos Generated", value: data.total_videos },
                { label: "Total Spend", value: formatCost(data.total_cost_usd) },
                { label: "Avg Cost per Video", value: formatCost(data.avg_cost_per_video) },
                { label: "Success Rate", value: `${data.success_rate.toFixed(1)}%` },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
                >
                  <span className="text-sm text-gray-400">{label}</span>
                  <span className="text-sm font-semibold text-white">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Top niches */}
        {nicheData.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-4">
              Top Niches
            </h2>
            <div className="space-y-3">
              {nicheData.map(({ niche, count }) => {
                const pct = Math.round((count / maxNicheCount) * 100);
                return (
                  <div key={niche} className="flex items-center gap-3">
                    <div className="w-40 text-sm text-gray-300 truncate">{niche}</div>
                    <div className="flex-1 bg-gray-800 rounded-full h-2">
                      <div
                        className="bg-red-500 h-2 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="w-8 text-xs text-gray-500 text-right">{count}x</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty niches message */}
        {nicheData.length === 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
            <p className="text-gray-600 text-sm">Generate videos to see niche breakdown here.</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
