"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import { jobs } from "@/lib/api";
import { Zap, Sparkles, DollarSign, Clock } from "lucide-react";

const NICHE_SUGGESTIONS = [
  "personal finance tips", "AI tools for beginners", "fitness motivation",
  "travel hacks", "passive income ideas", "crypto explained",
  "healthy recipes", "productivity tips", "web development tutorials",
];

export default function NewVideoPage() {
  const router = useRouter();
  const [niche, setNiche] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await jobs.create(niche.trim());
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create job");
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">New Video</h1>
          <p className="text-gray-400 text-sm mt-1">
            Let the AI pipeline generate a complete YouTube video
          </p>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { icon: Sparkles, label: "7 AI agents", desc: "Script → visuals → audio → edit → upload", color: "text-purple-400" },
            { icon: DollarSign, label: "~$2–5/video", desc: "GPT-4o, Sora, DALL-E, TTS costs combined", color: "text-green-400" },
            { icon: Clock, label: "8–15 minutes", desc: "Fully automated from niche to live video", color: "text-blue-400" },
          ].map(({ icon: Icon, label, desc, color }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <Icon className={`w-5 h-5 ${color} mb-2`} />
              <p className="text-white font-medium text-sm">{label}</p>
              <p className="text-gray-500 text-xs mt-1">{desc}</p>
            </div>
          ))}
        </div>

        {/* Form */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <form onSubmit={create} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Video Niche
                <span className="text-gray-500 font-normal ml-2">(leave blank for AI to choose)</span>
              </label>
              <input
                type="text"
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                placeholder="e.g. personal finance tips for Gen Z"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition"
              />
            </div>

            {/* Suggestions */}
            <div>
              <p className="text-xs text-gray-500 mb-2">Quick picks:</p>
              <div className="flex flex-wrap gap-2">
                {NICHE_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setNiche(s)}
                    className={`text-xs px-3 py-1.5 rounded-full border transition ${
                      niche === s
                        ? "bg-red-600 border-red-600 text-white"
                        : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-3 text-red-300 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Zap className="w-5 h-5" />
                  Generate Video
                </>
              )}
            </button>

            {loading && (
              <p className="text-center text-gray-400 text-sm">
                Job queued! Redirecting to dashboard...
              </p>
            )}
          </form>
        </div>

        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Pipeline steps</h3>
          <div className="space-y-2">
            {[
              ["CEO Agent", "Picks trending topic, creates video plan"],
              ["Script Polisher", "Refines script with hooks and CTAs"],
              ["Visual Generator", "Creates scenes with Sora + DALL-E"],
              ["Audio Engineer", "Generates voiceover with OpenAI TTS"],
              ["Video Editor", "Assembles clips + audio with ffmpeg"],
              ["SEO Optimizer", "Writes title, description, and tags"],
              ["Uploader", "Uploads to YouTube via API"],
            ].map(([name, desc], i) => (
              <div key={name} className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-gray-800 text-gray-400 text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <div>
                  <span className="text-sm text-white font-medium">{name}</span>
                  <span className="text-xs text-gray-500 ml-2">{desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
