"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { keys, settings, youtube, UserSettings, KeyStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Check, Trash2, ExternalLink, PlayCircle as Youtube } from "lucide-react";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-5">{title}</h2>
      {children}
    </div>
  );
}

function SettingsPageInner() {
  const { email, userId } = useAuth();
  const searchParams = useSearchParams();
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null);
  const [prefs, setPrefs] = useState<UserSettings | null>(null);
  const [openaiKey, setOpenaiKey] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [ytUrl, setYtUrl] = useState("");

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 4000); };

  const load = useCallback(async () => {
    try {
      const [ks, ps] = await Promise.all([keys.status(), settings.get()]);
      setKeyStatus(ks);
      setPrefs(ps);
    } catch {}
    try { const yt = await youtube.connectUrl(); setYtUrl(yt.auth_url || ""); } catch {}
  }, []);

  // Handle OAuth callback redirect (?youtube_connected=1)
  useEffect(() => {
    if (searchParams.get("youtube_connected") === "1") {
      showToast("✅ YouTube channel connected successfully!");
      window.history.replaceState({}, "", "/settings");
      load();
    }
  }, [searchParams, load]);

  useEffect(() => { load(); }, [load]);

  const saveKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!openaiKey.startsWith("sk-")) { showToast("Key must start with sk-"); return; }
    setSaving("key");
    try { await keys.saveOpenAI(openaiKey); setOpenaiKey(""); await load(); showToast("✅ OpenAI key saved"); } catch (err: unknown) { showToast(err instanceof Error ? err.message : "Failed"); }
    setSaving(null);
  };

  const deleteKey = async () => {
    setSaving("del");
    try { await keys.deleteOpenAI(); await load(); showToast("Key removed"); } catch {}
    setSaving(null);
  };

  const disconnectYT = async () => {
    setSaving("yt");
    try { await youtube.disconnect(); await load(); showToast("YouTube disconnected"); } catch {}
    setSaving(null);
  };

  const savePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prefs) return;
    setSaving("prefs");
    try { await settings.update(prefs); showToast("✅ Preferences saved"); } catch {}
    setSaving(null);
  };

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-gray-400 text-sm mt-1">Manage your API keys, YouTube channel, and preferences</p>
        </div>

        {/* Toast */}
        {toast && (
          <div className="fixed top-4 right-4 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-white shadow-xl z-50 flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" /> {toast}
          </div>
        )}

        {/* OpenAI Key */}
        <Section title="🔑 OpenAI API Key">
          {keyStatus?.has_openai_key ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 p-3 bg-green-900/20 border border-green-800 rounded-lg">
                <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-green-300 font-medium">OpenAI key connected</p>
                  {keyStatus.openai_added_at && (
                    <p className="text-xs text-green-600 mt-0.5">
                      Added {new Date(keyStatus.openai_added_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={deleteKey}
                  disabled={saving === "del"}
                  className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition"
                >
                  <Trash2 className="w-3 h-3" />
                  {saving === "del" ? "Removing..." : "Remove"}
                </button>
              </div>
              <form onSubmit={saveKey} className="flex gap-2">
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="Update key: sk-..."
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition"
                />
                <button
                  type="submit"
                  disabled={saving === "key"}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition"
                >
                  {saving === "key" ? "..." : "Update"}
                </button>
              </form>
            </div>
          ) : (
            <form onSubmit={saveKey} className="space-y-3">
              <p className="text-sm text-gray-400">
                Your key is stored encrypted and never shown in plain text.{" "}
                <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-red-400 hover:text-red-300">
                  Get a key →
                </a>
              </p>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="sk-proj-..."
                  required
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition"
                />
                <button
                  type="submit"
                  disabled={saving === "key"}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition"
                >
                  {saving === "key" ? "Saving..." : "Save Key"}
                </button>
              </div>
            </form>
          )}
        </Section>

        {/* YouTube */}
        <Section title="📺 YouTube Channel">
          {keyStatus?.has_youtube_token ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-3 bg-green-900/20 border border-green-800 rounded-lg">
                <Youtube className="w-5 h-5 text-red-400" />
                <div className="flex-1">
                  <p className="text-sm text-green-300 font-medium">
                    {keyStatus.youtube_channel_name || "YouTube Channel"} connected
                  </p>
                  {keyStatus.youtube_channel_id && (
                    <p className="text-xs text-green-600 mt-0.5">ID: {keyStatus.youtube_channel_id}</p>
                  )}
                </div>
                <button onClick={disconnectYT} disabled={saving === "yt"} className="text-xs text-red-400 hover:text-red-300 transition">
                  {saving === "yt" ? "..." : "Disconnect"}
                </button>
              </div>
              {ytUrl && (
                <a href={ytUrl} className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300">
                  <ExternalLink className="w-4 h-4" /> Reconnect YouTube
                </a>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-400">
                Connect your YouTube channel so the agent can upload videos automatically.
                Your OAuth token is stored encrypted.
              </p>
              {ytUrl ? (
                <a
                  href={ytUrl}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition"
                >
                  <Youtube className="w-4 h-4" /> Connect YouTube Channel
                </a>
              ) : (
                <p className="text-sm text-yellow-600">
                  YouTube OAuth not configured. Set YOUTUBE_CLIENT_ID in .env
                </p>
              )}
            </div>
          )}
        </Section>

        {/* Video Preferences */}
        {prefs && (
          <Section title="🎬 Video Preferences">
            <form onSubmit={savePrefs} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Default Niche</label>
                  <input
                    type="text"
                    value={prefs.default_niche}
                    onChange={(e) => setPrefs({ ...prefs, default_niche: e.target.value })}
                    placeholder="e.g. personal finance"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Max Video Length: {prefs.max_video_minutes} min
                  </label>
                  <input
                    type="range" min={3} max={20}
                    value={prefs.max_video_minutes}
                    onChange={(e) => setPrefs({ ...prefs, max_video_minutes: +e.target.value })}
                    className="w-full accent-red-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Upload Privacy</label>
                  <select
                    value={prefs.upload_privacy}
                    onChange={(e) => setPrefs({ ...prefs, upload_privacy: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500 transition"
                  >
                    {["public", "unlisted", "private"].map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">TTS Voice</label>
                  <select
                    value={prefs.tts_voice}
                    onChange={(e) => setPrefs({ ...prefs, tts_voice: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500 transition"
                  >
                    {["alloy", "echo", "fable", "onyx", "nova", "shimmer"].map((v) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Auto-Approve Under ($): {prefs.auto_approve_under_dollars.toFixed(1)}
                  </label>
                  <input
                    type="range" min={0} max={50} step={0.5}
                    value={prefs.auto_approve_under_dollars}
                    onChange={(e) => setPrefs({ ...prefs, auto_approve_under_dollars: +e.target.value })}
                    className="w-full accent-red-500"
                  />
                </div>
                <div className="flex items-center gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setPrefs({ ...prefs, autonomous_mode: !prefs.autonomous_mode })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${prefs.autonomous_mode ? "bg-red-600" : "bg-gray-700"}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${prefs.autonomous_mode ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                  <label className="text-sm text-gray-300">Autonomous Mode</label>
                </div>
              </div>

              <button
                type="submit"
                disabled={saving === "prefs"}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition"
              >
                {saving === "prefs" ? "Saving..." : "💾 Save Preferences"}
              </button>
            </form>
          </Section>
        )}

        {/* Account */}
        <Section title="👤 Account">
          <div className="space-y-2">
            <div className="flex items-center justify-between py-2 border-b border-gray-800">
              <span className="text-sm text-gray-400">Email</span>
              <span className="text-sm text-white">{email}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-400">User ID</span>
              <span className="text-xs text-gray-500 font-mono">{userId}</span>
            </div>
          </div>
        </Section>
      </div>
    </AppShell>
  );
}

// useSearchParams requires a Suspense boundary in Next.js App Router
export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <SettingsPageInner />
    </Suspense>
  );
}
