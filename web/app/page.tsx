"use client";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Company = { id: number; name: string };

export default function Home() {
  const [name, setName] = useState("");
  const [variants, setVariants] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [prompts, setPrompts] = useState("");
  const [runs, setRuns] = useState(1);
  const [model, setModel] = useState("perplexity:sonar");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const canSubmit = name && variants && prompts && !loading;

  async function createCompany(): Promise<Company> {
    const body = {
      name,
      variants: variants.split(",").map((s) => s.trim()).filter(Boolean),
      competitors: competitors
        ? competitors.split(",").map((s) => s.trim()).filter(Boolean)
        : [],
    };
    const res = await fetch(`${API}/companies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Company creation failed");
    return res.json();
  }

  async function createCampaign(companyId: number) {
    const promptList = prompts.split("\n").map((s) => s.trim()).filter(Boolean);
    const res = await fetch(`${API}/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_id: companyId,
        model,
        runs_per_query: runs,
        temperature: 0.1,
        prompts: promptList,
      }),
    });
    if (!res.ok) throw new Error("Campaign creation failed");
    return res.json() as Promise<{ id: number }>;
  }

  async function onLaunch() {
    try {
      setLoading(true);
      setErr(null);
      const company = await createCompany();
      const camp = await createCampaign(company.id);
      window.location.href = `/campaigns/${camp.id}`;
    } catch (e: any) {
      setErr(e?.message || "Unexpected error");
      setLoading(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-8 space-y-6">
      <h1 className="text-2xl font-semibold">GEO — Lancer une campagne</h1>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-800 p-3 rounded">
          {err}
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm">Nom de la société</label>
        <input
          className="w-full border p-2 rounded"
          placeholder="Pizza del Mama"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm">Variantes (séparées par des virgules)</label>
          <input
            className="w-full border p-2 rounded"
            placeholder="Pizza del Mama, pizzadelmama.com"
            value={variants}
            onChange={(e) => setVariants(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm">Concurrents (optionnel)</label>
          <input
            className="w-full border p-2 rounded"
            placeholder="Domino's, Pizza Hut"
            value={competitors}
            onChange={(e) => setCompetitors(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm">Prompts (un par ligne)</label>
        <textarea
          className="w-full border p-2 rounded h-40"
          placeholder={"best pizza in Paris\npizza delivery near me\npizzeria open late"}
          value={prompts}
          onChange={(e) => setPrompts(e.target.value)}
        />
      </div>

      <div className="grid md:grid-cols-3 gap-6 items-end">
        <div className="space-y-2">
          <label className="text-sm">Modèle</label>
          <select
            className="border p-2 rounded w-full"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            <option value="perplexity:sonar">Perplexity (web)</option>
            <option value="openai:gpt-5">GPT-5 (API)</option>
            <option value="ollama:llama3.2:1b-instruct-fp16">Llama 3.2 1B (local)</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm">Runs par prompt</label>
          <input
            type="number"
            min={1}
            className="border p-2 rounded w-full"
            value={runs}
            onChange={(e) => setRuns(parseInt(e.target.value || "1", 10))}
          />
        </div>
        <button
          disabled={!canSubmit}
          onClick={onLaunch}
          className={`px-4 py-2 rounded text-white ${canSubmit ? "bg-black" : "bg-gray-400 cursor-not-allowed"}`}
        >
          {loading ? "Démarrage…" : "Lancer"}
        </button>
      </div>
    </main>
  );
}

