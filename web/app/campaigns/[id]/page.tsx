"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Campaign = { id: number; status: string; total_prompts: number; completed_runs: number };

export default function CampaignPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [status, setStatus] = useState<Campaign["status"]>("queued");
  const [completed, setCompleted] = useState(0);
  const [totalRuns, setTotalRuns] = useState(0);
  const [pct, setPct] = useState(0);
  const [exportPath, setExportPath] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Poll status once at mount (in case SSE arrives late)
  async function fetchStatus() {
    try {
      const res = await fetch(`${API}/campaigns/${id}`);
      if (!res.ok) throw new Error("Status error");
      const d = (await res.json()) as Campaign;
      setStatus(d.status);
      // total_runs = total_prompts * runs_per_query (non exposé ici)
      // On lira la valeur exacte via SSE; ce fallback reste utile
    } catch (e: any) {
      setErr(e?.message || "Erreur statut");
    }
  }

  useEffect(() => {
    fetchStatus();
    const es = new EventSource(`${API}/campaigns/${id}/events`);
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        setStatus(d.status || "running");
        setCompleted(d.completed_runs || 0);
        setTotalRuns(d.total_runs || 0);
        setPct(d.pct || 0);
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => {
      // auto-close to avoid noisy console if backend restarts
      es.close();
    };
    return () => es.close();
  }, [id]);

  async function doExport() {
    setErr(null);
    try {
      const res = await fetch(`${API}/exports/campaign/${id}`, { method: "POST" });
      if (!res.ok) throw new Error("Export failed");
      const d = await res.json();
      setExportPath(d.path);
    } catch (e: any) {
      setErr(e?.message || "Erreur export");
    }
  }

  return (
    <main className="max-w-2xl mx-auto p-8 space-y-6">
      <h1 className="text-xl font-semibold">Campagne #{id}</h1>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-800 p-3 rounded">
          {err}
        </div>
      )}

      <div className="space-y-2">
        <div className="text-sm">Statut : <b>{status}</b></div>
        <div className="w-full bg-gray-200 rounded h-3">
          <div className="bg-green-600 h-3 rounded" style={{ width: `${pct}%` }} />
        </div>
        <div className="text-xs text-gray-600">{completed}/{totalRuns} runs — {pct}%</div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={doExport}
          disabled={status !== "done"}
          className={`px-3 py-2 rounded text-white ${status === "done" ? "bg-black" : "bg-gray-400 cursor-not-allowed"}`}
          title={status === "done" ? "Exporter les résultats (CSV)" : "Disponible une fois terminé"}
        >
          Export CSV
        </button>
        {exportPath && (
          <a className="text-blue-600 underline" href={exportPath} target="_blank" rel="noreferrer">
            Télécharger
          </a>
        )}
      </div>

      <p className="text-sm text-gray-600">
        Cette page se met à jour en temps réel via <em>Server-Sent Events</em>. L’export devient cliquable une fois la
        campagne terminée.
      </p>
    </main>
  );
}
