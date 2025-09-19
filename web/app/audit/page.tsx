"use client";

import { useState } from "react";
import { askDetectBatch, generatePrompts } from "@/lib/api";

type Brand = { name: string; aliases?: string[] };

export default function AuditPage() {
  const [provider, setProvider] = useState<"openai">("openai");
  const [model, setModel] = useState("gpt-5-mini");
  const [brandName, setBrandName] = useState("Seven Seventy");
  const [brandAliases, setBrandAliases] = useState("770, seven seventy");
  const [businessType, setBusinessType] = useState("restaurant");
  const [location, setLocation] = useState("Charenton");
  const [promptsText, setPromptsText] = useState("");

  const [loading, setLoading] = useState(false);
  const [generatingPrompts, setGeneratingPrompts] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function generateAutoPrompts() {
    setGeneratingPrompts(true);
    try {
      const data = await generatePrompts(businessType, location, 20);
      setPromptsText(data.prompts.join("\n"));
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setGeneratingPrompts(false);
    }
  }

  async function runAudit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setResults(null);

    try {
      const prompts = promptsText.split("\n").filter(p => p.trim());
      const aliases = brandAliases.split(",").map(a => a.trim()).filter(Boolean);
      const brands: Brand[] = [{
        name: brandName,
        aliases: [brandName, ...aliases]
      }];

      const payload = {
        provider,
        model,
        prompts,
        brands,
        match_mode: "exact_only"
      };

      const data = await askDetectBatch(payload);
      setResults(data);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }

  const metrics = results?.metrics?.by_brand?.[brandName];
  const mentionRate = metrics ? Math.round(metrics.mention_rate * 100) : 0;

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold">🎯 Audit GEO</h1>
        <p className="text-gray-600 mt-2">Testez la visibilité de votre marque avec GPT-5 + recherche web</p>
      </div>

      <form onSubmit={runAudit} className="bg-white rounded-xl p-6 shadow-lg">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as any)}
              className="w-full border rounded-lg p-2"
            >
              <option value="openai">OpenAI (GPT-5)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Modèle</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border rounded-lg p-2"
            >
              <option value="gpt-5-mini">GPT-5 Mini (Rapide)</option>
              <option value="gpt-5">GPT-5 (Précis)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Marque à tester</label>
            <input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              className="w-full border rounded-lg p-2"
              placeholder="Seven Seventy"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-2">Aliases (séparés par virgules)</label>
            <input
              value={brandAliases}
              onChange={(e) => setBrandAliases(e.target.value)}
              className="w-full border rounded-lg p-2"
              placeholder="770, seven seventy"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Type d'activité</label>
            <input
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              className="w-full border rounded-lg p-2"
              placeholder="restaurant, banque, artisan..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Localisation</label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full border rounded-lg p-2"
              placeholder="Paris, Marseille, Nice..."
            />
          </div>
        </div>

        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium">
              Prompts de test ({promptsText.split('\n').filter(p => p.trim()).length} prompts)
            </label>
            <button
              type="button"
              onClick={generateAutoPrompts}
              disabled={generatingPrompts || !businessType}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-green-700"
            >
              {generatingPrompts ? "🔄 Génération..." : "🎯 Générer les prompts"}
            </button>
          </div>
          <textarea
            value={promptsText}
            onChange={(e) => setPromptsText(e.target.value)}
            className="w-full border rounded-lg p-3 font-mono text-sm"
            rows={8}
            placeholder="Cliquez sur 'Générer les prompts' ou écrivez un prompt par ligne..."
          />
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700"
          >
            {loading ? "🔍 Analyse en cours..." : "🚀 Lancer l'audit"}
          </button>
          {error && <span className="text-red-600 text-sm">{error}</span>}
        </div>
      </form>

      {results && (
        <div className="space-y-6">
          {/* Résultats principaux */}
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h2 className="text-2xl font-bold mb-4">📊 Résultats de l'audit</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-blue-600">{mentionRate}%</div>
                <div className="text-sm text-gray-600">Taux de visibilité</div>
              </div>
              <div className="bg-green-50 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-green-600">{metrics?.prompts_with_mention || 0}</div>
                <div className="text-sm text-gray-600">Prompts avec mention</div>
              </div>
              <div className="bg-purple-50 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-purple-600">{metrics?.total_mentions || 0}</div>
                <div className="text-sm text-gray-600">Total mentions</div>
              </div>
              <div className="bg-orange-50 rounded-lg p-4 text-center">
                <div className="text-3xl font-bold text-orange-600">{results.metrics.n_prompts}</div>
                <div className="text-sm text-gray-600">Prompts testés</div>
              </div>
            </div>
          </div>

          {/* Détail par prompt */}
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-xl font-bold mb-4">📝 Détail par prompt</h3>
            <div className="space-y-3">
              {results.per_prompt.map((item: any, idx: number) => {
                const hasMention = Object.keys(item.summary).length > 0;
                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg border-l-4 ${
                      hasMention ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold ${
                        hasMention ? 'bg-green-500 text-white' : 'bg-gray-400 text-white'
                      }`}>
                        {hasMention ? '✓' : '✗'}
                      </span>
                      <span className="font-medium">{item.prompt}</span>
                      {hasMention && (
                        <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">
                          {item.summary[brandName]?.total} mention(s)
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 ml-9 line-clamp-2">
                      {item.answer_text.substring(0, 200)}...
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}