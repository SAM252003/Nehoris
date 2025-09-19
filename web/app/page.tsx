"use client";

import { useState, useEffect } from "react";
import { askDetectBatch, generatePrompts } from "@/lib/api";

type Brand = { name: string; aliases?: string[] };

export default function AuditPage() {
  const [provider, setProvider] = useState<"openai" | "anthropic" | "gemini" | "ollama" | "perplexity">("openai");
  const [model, setModel] = useState("gpt-5-mini");
  const [brandName, setBrandName] = useState("Seven Seventy");
  const [brandAliases, setBrandAliases] = useState("770, seven seventy");
  const [businessType, setBusinessType] = useState("restaurant");
  const [customBusinessType, setCustomBusinessType] = useState("");
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("Charenton");
  const [promptsText, setPromptsText] = useState("");
  const [promptCount, setPromptCount] = useState(20);
  const [compareMode, setCompareMode] = useState(false);
  const [compareProviders, setCompareProviders] = useState<string[]>(["openai", "perplexity"]);

  const [loading, setLoading] = useState(false);
  const [generatingPrompts, setGeneratingPrompts] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [comparisonResults, setComparisonResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Charger les données sauvegardées au démarrage
  useEffect(() => {
    const savedResults = localStorage.getItem('lastAuditResults');
    const savedFormData = localStorage.getItem('lastAuditFormData');

    if (savedResults) {
      try {
        setResults(JSON.parse(savedResults));
      } catch (error) {
        console.error('Erreur lors du chargement des résultats:', error);
      }
    }

    if (savedFormData) {
      try {
        const formData = JSON.parse(savedFormData);
        setBrandName(formData.brandName || "Seven Seventy");
        setBrandAliases(formData.brandAliases || "770, seven seventy");
        setBusinessType(formData.businessType || "restaurant");
        setLocation(formData.location || "Charenton");
        setPromptCount(formData.promptCount || 20);
        setPromptsText(formData.promptsText || "");
        setProvider(formData.provider || "openai");
        setModel(formData.model || "gpt-5-mini");
      } catch (error) {
        console.error('Erreur lors du chargement des données du formulaire:', error);
      }
    }
  }, []);

  // Sauvegarder les données du formulaire à chaque modification
  useEffect(() => {
    const formData = {
      brandName,
      brandAliases,
      businessType,
      location,
      promptCount,
      promptsText,
      provider,
      model
    };
    localStorage.setItem('lastAuditFormData', JSON.stringify(formData));
  }, [brandName, brandAliases, businessType, customBusinessType, keywords, location, promptCount, promptsText, provider, model]);

  async function generateAutoPrompts() {
    setGeneratingPrompts(true);
    try {
      const finalBusinessType = businessType === "autre" ? customBusinessType : businessType;
      const data = await generatePrompts(finalBusinessType, location, promptCount, keywords);
      setPromptsText(data.prompts.join("\n"));
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setGeneratingPrompts(false);
    }
  }

  function downloadPDF() {
    if (!results) return;

    // Import dynamique pour éviter les erreurs SSR
    import('jspdf').then(({ default: jsPDF }) => {
      import('jspdf-autotable').then(() => {
        const doc = new jsPDF();
        const currentDate = new Date().toLocaleDateString('fr-FR');

        // Header
        doc.setFontSize(20);
        doc.text('🎯 Rapport d\'Audit GEO', 20, 30);

        doc.setFontSize(12);
        doc.text(`Généré le ${currentDate}`, 20, 40);
        doc.text(`Marque: ${brandName}`, 20, 50);
        doc.text(`Secteur: ${businessType} - ${location}`, 20, 60);
        doc.text(`Provider: ${provider.toUpperCase()} (${model})`, 20, 70);

        // KPIs principaux
        doc.setFontSize(16);
        doc.text('📊 Métriques principales', 20, 90);

        const metrics = results.metrics.by_brand[brandName];
        const mentionRate = Math.round((metrics?.mention_rate || 0) * 100);

        doc.setFontSize(12);
        doc.text(`• Taux de visibilité: ${mentionRate}%`, 25, 105);
        doc.text(`• Total mentions: ${metrics?.total_mentions || 0}`, 25, 115);
        doc.text(`• Prompts avec mention: ${metrics?.prompts_with_mention || 0}`, 25, 125);
        doc.text(`• Total prompts testés: ${results.metrics.n_prompts}`, 25, 135);
        doc.text(`• Position moyenne: ${(metrics?.avg_first_index || 0).toFixed(1)}`, 25, 145);

        // Tableau détaillé des prompts
        doc.setFontSize(16);
        doc.text('📝 Résultats détaillés par prompt', 20, 165);

        const tableData = results.per_prompt.map((item: any, index: number) => {
          const hasMention = Object.keys(item.summary).length > 0;
          const mentionCount = hasMention ? item.summary[brandName]?.total || 0 : 0;

          return [
            (index + 1).toString(),
            item.prompt.substring(0, 50) + '...',
            hasMention ? '✓' : '✗',
            mentionCount.toString()
          ];
        });

        (doc as any).autoTable({
          startY: 175,
          head: [['#', 'Prompt', 'Mention', 'Nb']],
          body: tableData,
          styles: { fontSize: 8 },
          headStyles: { fillColor: [59, 130, 246] },
          columnStyles: {
            0: { cellWidth: 15 },
            1: { cellWidth: 110 },
            2: { cellWidth: 25 },
            3: { cellWidth: 20 }
          }
        });

        // Footer
        const pageCount = doc.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
          doc.setPage(i);
          doc.setFontSize(8);
          doc.text(
            `Nehoris GEO Audit - Page ${i}/${pageCount}`,
            20,
            doc.internal.pageSize.height - 10
          );
        }

        // Télécharger
        doc.save(`audit-geo-${brandName.replace(/\s+/g, '-').toLowerCase()}-${new Date().toISOString().split('T')[0]}.pdf`);
      });
    });
  }

  function downloadResults() {
    if (!results) return;

    // Créer le contenu du fichier
    const reportData = {
      metadata: {
        brandName,
        brandAliases,
        businessType,
        location,
        provider,
        model,
        generatedAt: new Date().toISOString(),
        totalPrompts: results.metrics.n_prompts
      },
      summary: {
        mentionRate: `${Math.round((results.metrics.by_brand[brandName]?.mention_rate || 0) * 100)}%`,
        totalMentions: results.metrics.by_brand[brandName]?.total_mentions || 0,
        promptsWithMention: results.metrics.by_brand[brandName]?.prompts_with_mention || 0,
        avgFirstIndex: results.metrics.by_brand[brandName]?.avg_first_index || 0
      },
      detailedResults: results.per_prompt.map((item: any, index: number) => ({
        promptNumber: index + 1,
        prompt: item.prompt,
        hasMention: Object.keys(item.summary).length > 0,
        mentionCount: item.summary[brandName]?.total || 0,
        answer: item.answer_text,
        summary: item.summary
      }))
    };

    // Créer et télécharger le fichier JSON
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-geo-${brandName.replace(/\s+/g, '-').toLowerCase()}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function runAudit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setResults(null);
    setComparisonResults(null);

    try {
      const prompts = promptsText.split("\n").filter(p => p.trim());
      const aliases = brandAliases.split(",").map(a => a.trim()).filter(Boolean);
      const brands: Brand[] = [{
        name: brandName,
        aliases: [brandName, ...aliases]
      }];

      if (compareMode) {
        // Mode comparaison : tester plusieurs providers
        const comparisonData: any = {};

        for (const providerName of compareProviders) {
          try {
            const payload = {
              provider: providerName,
              model: getDefaultModel(providerName),
              prompts,
              brands,
              match_mode: "exact_only"
            };

            const data = await askDetectBatch(payload);
            comparisonData[providerName] = data;
            console.log(`✅ ${providerName} terminé avec succès`);
          } catch (providerError: any) {
            console.error(`❌ Erreur avec ${providerName}:`, providerError);
            comparisonData[providerName] = {
              error: true,
              message: `Erreur ${providerName}: ${providerError?.message || String(providerError)}`,
              metrics: { n_prompts: prompts.length, by_brand: {} }
            };
          }
        }

        setComparisonResults(comparisonData);
        localStorage.setItem('lastComparisonResults', JSON.stringify(comparisonData));

        // Émettre un événement pour notifier les autres pages
        window.dispatchEvent(new CustomEvent('auditComplete', { detail: comparisonData }));

        // Sauvegarder chaque provider dans l'historique
        for (const [providerName, data] of Object.entries(comparisonData)) {
          saveToHistory(data, providerName, getDefaultModel(providerName));
        }
      } else {
        // Mode normal : un seul provider
        const payload = {
          provider,
          model,
          prompts,
          brands,
          match_mode: "exact_only"
        };

        const data = await askDetectBatch(payload);
        setResults(data);
        localStorage.setItem('lastAuditResults', JSON.stringify(data));

        // Émettre un événement pour notifier les autres pages
        window.dispatchEvent(new CustomEvent('auditComplete', { detail: data }));

        // Sauvegarder dans l'historique
        saveToHistory(data, provider, model);
      }
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }

  function getDefaultModel(providerName: string): string {
    switch (providerName) {
      case "openai": return "gpt-5-mini";
      case "anthropic": return "claude-3-5-sonnet-20241022";
      case "gemini": return "gemini-1.5-pro";
      case "ollama": return "llama3.2:1b-instruct-fp16";
      case "perplexity": return "sonar-pro";
      default: return "gpt-5-mini";
    }
  }

  function saveToHistory(auditData: any, usedProvider: string, usedModel: string) {
    try {
      const historyItem = {
        id: Date.now().toString(),
        brandName,
        businessType,
        location,
        provider: usedProvider,
        model: usedModel,
        date: new Date().toISOString(),
        mentionRate: Math.round((auditData.metrics.by_brand[brandName]?.mention_rate || 0) * 100),
        totalMentions: auditData.metrics.by_brand[brandName]?.total_mentions || 0,
        promptsWithMention: auditData.metrics.by_brand[brandName]?.prompts_with_mention || 0,
        totalPrompts: auditData.metrics.n_prompts,
        avgFirstIndex: auditData.metrics.by_brand[brandName]?.avg_first_index || 0
      };

      // Récupérer l'historique existant
      const existingHistory = localStorage.getItem('auditHistory');
      const history = existingHistory ? JSON.parse(existingHistory) : [];

      // Ajouter le nouvel audit
      history.push(historyItem);

      // Limiter à 100 audits max (pour éviter que localStorage devienne trop gros)
      if (history.length > 100) {
        history.splice(0, history.length - 100);
      }

      // Sauvegarder
      localStorage.setItem('auditHistory', JSON.stringify(history));
    } catch (error) {
      console.error('Erreur lors de la sauvegarde dans l\'historique:', error);
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
              onChange={(e) => {
                const newProvider = e.target.value as typeof provider;
                setProvider(newProvider);
                // Auto-sélectionner le bon modèle par défaut
                if (newProvider === "openai") setModel("gpt-5-mini");
                else if (newProvider === "anthropic") setModel("claude-3-5-sonnet-20241022");
                else if (newProvider === "gemini") setModel("gemini-1.5-pro");
                else if (newProvider === "ollama") setModel("llama3.2:1b-instruct-fp16");
                else if (newProvider === "perplexity") setModel("sonar-pro");
              }}
              className="w-full border rounded-lg p-2"
            >
              <option value="openai">🤖 OpenAI (GPT-5)</option>
              <option value="perplexity">🔍 Perplexity (Web Search)</option>
              <option value="anthropic">🧠 Anthropic (Claude)</option>
              <option value="gemini">💎 Google (Gemini)</option>
              <option value="ollama">🦙 Ollama (Local)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Modèle</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border rounded-lg p-2"
            >
              {provider === "openai" && (
                <>
                  <option value="gpt-5-mini">GPT-5 Mini (Rapide + Web)</option>
                  <option value="gpt-5">GPT-5 (Précis + Web)</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                </>
              )}
              {provider === "anthropic" && (
                <>
                  <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                  <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku</option>
                  <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                </>
              )}
              {provider === "gemini" && (
                <>
                  <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                  <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                  <option value="gemini-1.0-pro">Gemini 1.0 Pro</option>
                </>
              )}
              {provider === "perplexity" && (
                <>
                  <option value="sonar-pro">Sonar Pro (Web Search)</option>
                  <option value="sonar">Sonar (Web Search)</option>
                  <option value="sonar-small">Sonar Small (Web Search)</option>
                </>
              )}
              {provider === "ollama" && (
                <>
                  <option value="llama3.2:1b-instruct-fp16">Llama 3.2 1B</option>
                  <option value="llama3.2:3b-instruct-q4_K_M">Llama 3.2 3B</option>
                  <option value="llama3.1:8b-instruct-q4_0">Llama 3.1 8B</option>
                </>
              )}
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

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
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
            <select
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              className="w-full border rounded-lg p-2"
            >
              <option value="restaurant">🍽️ Restaurant</option>
              <option value="restaurant-vegan">🌱 Restaurant végétarien/vegan</option>
              <option value="boulangerie">🥖 Boulangerie</option>
              <option value="coiffeur">✂️ Coiffeur</option>
              <option value="garage">🚗 Garage / Mécanicien</option>
              <option value="dentiste">🦷 Dentiste</option>
              <option value="avocat">⚖️ Avocat</option>
              <option value="banque">🏦 Banque</option>
              <option value="hotel">🏨 Hôtel</option>
              <option value="pharmacie">💊 Pharmacie</option>
              <option value="immobilier">🏠 Agence immobilière</option>
              <option value="artisan">🔨 Artisan</option>
              <option value="commerce">🛒 Commerce / Magasin</option>
              <option value="service">💼 Service professionnel</option>
              <option value="autre">🔧 Autre (personnalisé)</option>
            </select>
            {businessType === "autre" && (
              <input
                value={customBusinessType}
                onChange={(e) => setCustomBusinessType(e.target.value)}
                className="w-full border rounded-lg p-2 mt-2"
                placeholder="Décrivez votre activité (ex: restaurant de sushi, coiffeur afro, etc.)"
              />
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Mots-clés spécifiques (optionnel)</label>
            <input
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full border rounded-lg p-2"
              placeholder="bio, local, terroir, artisanal, premium..."
            />
            <p className="text-xs text-gray-500 mt-1">Séparés par virgules. Ces mots enrichiront les prompts générés.</p>
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

          <div>
            <label className="block text-sm font-medium mb-2">Nombre de prompts</label>
            <select
              value={promptCount}
              onChange={(e) => setPromptCount(Number(e.target.value))}
              className="w-full border rounded-lg p-2"
            >
              <option value={10}>10 prompts</option>
              <option value={15}>15 prompts</option>
              <option value={20}>20 prompts</option>
              <option value={30}>30 prompts</option>
              <option value={50}>50 prompts</option>
            </select>
          </div>
        </div>

        {/* Mode comparaison */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="compareMode"
                checked={compareMode}
                onChange={(e) => setCompareMode(e.target.checked)}
                className="w-4 h-4 text-blue-600"
              />
              <label htmlFor="compareMode" className="text-sm font-medium">
                🔄 Mode comparaison multi-providers
              </label>
            </div>
            {compareMode && (
              <span className="text-xs text-amber-600 bg-amber-100 px-2 py-1 rounded">
                ⚠️ Prendra plus de temps
              </span>
            )}
          </div>

          {compareMode && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { id: "openai", name: "🤖 OpenAI", model: "GPT-5" },
                { id: "perplexity", name: "🔍 Perplexity", model: "Sonar Online" },
                { id: "anthropic", name: "🧠 Claude", model: "3.5 Sonnet" },
                { id: "gemini", name: "💎 Gemini", model: "1.5 Pro" },
                { id: "ollama", name: "🦙 Ollama", model: "Llama 3.2" }
              ].map((provider) => (
                <label key={provider.id} className="flex items-center gap-2 p-2 bg-white rounded border cursor-pointer hover:bg-blue-50">
                  <input
                    type="checkbox"
                    checked={compareProviders.includes(provider.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCompareProviders([...compareProviders, provider.id]);
                      } else {
                        setCompareProviders(compareProviders.filter(p => p !== provider.id));
                      }
                    }}
                    className="w-4 h-4 text-blue-600"
                  />
                  <div className="text-xs">
                    <div className="font-medium">{provider.name}</div>
                    <div className="text-gray-500">{provider.model}</div>
                  </div>
                </label>
              ))}
            </div>
          )}
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
            disabled={loading || (compareMode && compareProviders.length < 2)}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700"
          >
            {loading ?
              (compareMode ? `🔄 Comparaison en cours (${compareProviders.length} providers)...` : "🔍 Analyse en cours...") :
              (compareMode ? `🔄 Comparer ${compareProviders.length} providers` : "🚀 Lancer l'audit")
            }
          </button>
          {compareMode && compareProviders.length < 2 && (
            <span className="text-amber-600 text-sm">Sélectionnez au moins 2 providers</span>
          )}
          {error && <span className="text-red-600 text-sm">{error}</span>}
        </div>
      </form>

      {results && (
        <div className="space-y-6">
          {/* Bouton pour vider les résultats */}
          <div className="text-center">
            <button
              onClick={() => {
                setResults(null);
                localStorage.removeItem('lastAuditResults');
                localStorage.removeItem('lastAuditFormData');
              }}
              className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700"
            >
              🗑️ Vider les résultats
            </button>
          </div>

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

            {/* Boutons de téléchargement */}
            <div className="mt-6 text-center">
              <div className="flex gap-4 justify-center">
                <button
                  onClick={downloadPDF}
                  className="bg-red-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-red-700 flex items-center gap-2"
                >
                  📄 Télécharger PDF
                </button>
                <button
                  onClick={downloadResults}
                  className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 flex items-center gap-2"
                >
                  📥 Télécharger JSON
                </button>
              </div>
              <p className="text-sm text-gray-500 mt-2">
                PDF pour présentation • JSON pour analyse détaillée
              </p>
            </div>
          </div>

        </div>
      )}

      {/* Résultats de comparaison */}
      {comparisonResults && (
        <div className="space-y-6">
          <div className="text-center">
            <button
              onClick={() => {
                setComparisonResults(null);
                localStorage.removeItem('lastComparisonResults');
              }}
              className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700"
            >
              🗑️ Vider la comparaison
            </button>
          </div>

          {/* Tableau de comparaison */}
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h2 className="text-2xl font-bold mb-4">📊 Comparaison des providers</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-3 pr-4 font-medium">Provider</th>
                    <th className="py-3 pr-4 font-medium">Taux de visibilité</th>
                    <th className="py-3 pr-4 font-medium">Mentions totales</th>
                    <th className="py-3 pr-4 font-medium">Prompts avec mention</th>
                    <th className="py-3 pr-4 font-medium">Position moyenne</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(comparisonResults).map(([providerName, data]: [string, any]) => {
                    const metrics = data.metrics.by_brand[brandName];
                    const mentionRate = Math.round(metrics.mention_rate * 100);

                    return (
                      <tr key={providerName} className="border-b hover:bg-gray-50">
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            <span>
                              {providerName === "openai" && "🤖 OpenAI"}
                              {providerName === "perplexity" && "🔍 Perplexity"}
                              {providerName === "anthropic" && "🧠 Claude"}
                              {providerName === "gemini" && "💎 Gemini"}
                              {providerName === "ollama" && "🦙 Ollama"}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          <div className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                            mentionRate >= 70 ? 'bg-green-100 text-green-800' :
                            mentionRate >= 50 ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {mentionRate}%
                          </div>
                        </td>
                        <td className="py-3 pr-4 font-medium">{metrics.total_mentions}</td>
                        <td className="py-3 pr-4">{metrics.prompts_with_mention}</td>
                        <td className="py-3 pr-4">{(metrics.avg_first_index || 0).toFixed(1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Téléchargement comparaison */}
            <div className="mt-6 text-center">
              <button
                onClick={() => {
                  const comparisonData = {
                    metadata: {
                      brandName,
                      brandAliases,
                      businessType,
                      location,
                      generatedAt: new Date().toISOString(),
                      providers: Object.keys(comparisonResults)
                    },
                    comparison: Object.entries(comparisonResults).map(([providerName, data]: [string, any]) => ({
                      provider: providerName,
                      mentionRate: Math.round((data.metrics.by_brand[brandName]?.mention_rate || 0) * 100),
                      totalMentions: data.metrics.by_brand[brandName]?.total_mentions || 0,
                      promptsWithMention: data.metrics.by_brand[brandName]?.prompts_with_mention || 0,
                      avgFirstIndex: data.metrics.by_brand[brandName]?.avg_first_index || 0
                    })),
                    detailedResults: comparisonResults
                  };

                  const blob = new Blob([JSON.stringify(comparisonData, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `comparaison-providers-${brandName.replace(/\s+/g, '-').toLowerCase()}-${new Date().toISOString().split('T')[0]}.json`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }}
                className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 flex items-center gap-2 mx-auto"
              >
                📥 Télécharger la comparaison (JSON)
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
