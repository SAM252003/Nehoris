"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from "recharts";

type AuditHistoryItem = {
  id: string;
  brandName: string;
  businessType: string;
  location: string;
  provider: string;
  model: string;
  date: string;
  mentionRate: number;
  totalMentions: number;
  promptsWithMention: number;
  totalPrompts: number;
  avgFirstIndex: number;
};

export default function HistoryPage() {
  const [auditHistory, setAuditHistory] = useState<AuditHistoryItem[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<string>("");
  const [dateRange, setDateRange] = useState<string>("30"); // derniers X jours

  useEffect(() => {
    loadAuditHistory();
  }, []);

  function loadAuditHistory() {
    const historyData = localStorage.getItem('auditHistory');
    if (historyData) {
      try {
        const history = JSON.parse(historyData);
        setAuditHistory(history);

        // Auto-sélectionner la première marque
        if (history.length > 0 && !selectedBrand) {
          setSelectedBrand(history[0].brandName);
        }
      } catch (error) {
        console.error('Erreur lors du chargement de l\'historique:', error);
      }
    }
  }

  function clearHistory() {
    localStorage.removeItem('auditHistory');
    setAuditHistory([]);
    setSelectedBrand("");
  }

  function exportHistory() {
    const exportData = {
      exportDate: new Date().toISOString(),
      totalAudits: auditHistory.length,
      brands: [...new Set(auditHistory.map(a => a.brandName))],
      history: auditHistory
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `historique-audits-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Filtrer par marque et date
  const filteredHistory = auditHistory.filter(audit => {
    const matchesBrand = !selectedBrand || audit.brandName === selectedBrand;
    const auditDate = new Date(audit.date);
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - parseInt(dateRange));
    const matchesDate = auditDate >= cutoffDate;

    return matchesBrand && matchesDate;
  }).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  // Données pour les graphiques
  const trendData = filteredHistory.map(audit => ({
    date: new Date(audit.date).toLocaleDateString('fr-FR', { month: 'short', day: 'numeric' }),
    mentionRate: audit.mentionRate,
    totalMentions: audit.totalMentions,
    provider: audit.provider
  }));

  // Comparaison par provider
  const providerComparison = auditHistory.reduce((acc, audit) => {
    if (!acc[audit.provider]) {
      acc[audit.provider] = [];
    }
    acc[audit.provider].push(audit.mentionRate);
    return acc;
  }, {} as Record<string, number[]>);

  const providerStats = Object.entries(providerComparison).map(([provider, rates]) => ({
    provider,
    avgRate: Math.round(rates.reduce((sum, rate) => sum + rate, 0) / rates.length),
    audits: rates.length,
    minRate: Math.min(...rates),
    maxRate: Math.max(...rates)
  }));

  // Marques uniques
  const uniqueBrands = [...new Set(auditHistory.map(a => a.brandName))];

  if (auditHistory.length === 0) {
    return (
      <main className="max-w-7xl mx-auto p-6">
        <div className="text-center py-20">
          <div className="mb-8">
            <div className="text-6xl mb-4">📈</div>
            <h1 className="text-3xl font-bold mb-4">Historique des audits</h1>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Aucun historique d'audit trouvé. Lancez quelques audits pour voir l'évolution de vos métriques dans le temps.
            </p>
          </div>
          <div className="bg-blue-50 rounded-xl p-6 max-w-lg mx-auto">
            <h3 className="font-semibold text-blue-900 mb-3">L'historique vous permettra de :</h3>
            <ul className="text-left text-blue-800 space-y-2">
              <li className="flex items-center gap-2">
                <span className="text-blue-600">📊</span>
                Suivre l'évolution de la visibilité dans le temps
              </li>
              <li className="flex items-center gap-2">
                <span className="text-blue-600">🔄</span>
                Comparer les performances entre différents providers
              </li>
              <li className="flex items-center gap-2">
                <span className="text-blue-600">📈</span>
                Identifier les tendances et améliorations
              </li>
              <li className="flex items-center gap-2">
                <span className="text-blue-600">💾</span>
                Exporter vos données pour analyse
              </li>
            </ul>
          </div>
          <div className="mt-8">
            <a
              href="/"
              className="bg-blue-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-blue-700 inline-flex items-center gap-2"
            >
              🚀 Lancer un audit
            </a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">📈 Historique des audits</h1>
          <p className="text-gray-600 mt-2">{auditHistory.length} audits • {uniqueBrands.length} marque(s)</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={exportHistory}
            className="bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700"
          >
            📥 Exporter
          </button>
          <button
            onClick={clearHistory}
            className="bg-red-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-red-700"
          >
            🗑️ Vider l'historique
          </button>
        </div>
      </div>

      {/* Filtres */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">🔍 Filtres</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Marque</label>
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
              className="w-full border rounded-lg p-2"
            >
              <option value="">Toutes les marques</option>
              {uniqueBrands.map(brand => (
                <option key={brand} value={brand}>{brand}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Période</label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full border rounded-lg p-2"
            >
              <option value="7">7 derniers jours</option>
              <option value="30">30 derniers jours</option>
              <option value="90">3 derniers mois</option>
              <option value="365">Année complète</option>
            </select>
          </div>
        </div>
      </div>

      {/* Évolution temporelle */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">📊 Évolution du taux de visibilité</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={trendData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis label={{ value: 'Taux (%)', angle: -90, position: 'insideLeft' }} />
            <Tooltip
              formatter={(value: any, name: any) => [`${value}%`, 'Taux de visibilité']}
              labelFormatter={(label) => `Date: ${label}`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="mentionRate"
              stroke="#8884d8"
              strokeWidth={3}
              dot={{ fill: '#8884d8', strokeWidth: 2, r: 6 }}
              name="Taux de visibilité (%)"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Comparaison providers */}
      {providerStats.length > 1 && (
        <div className="bg-white rounded-xl p-6 shadow-lg">
          <h2 className="text-xl font-bold mb-4">🔄 Performance par provider</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={providerStats}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="provider" />
              <YAxis label={{ value: 'Taux moyen (%)', angle: -90, position: 'insideLeft' }} />
              <Tooltip
                formatter={(value: any, name: any) => [`${value}%`, 'Taux moyen']}
              />
              <Bar dataKey="avgRate" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tableau détaillé */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h2 className="text-xl font-bold mb-4">📋 Détail des audits</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-3 pr-4 font-medium">Date</th>
                <th className="py-3 pr-4 font-medium">Marque</th>
                <th className="py-3 pr-4 font-medium">Provider</th>
                <th className="py-3 pr-4 font-medium">Taux</th>
                <th className="py-3 pr-4 font-medium">Mentions</th>
                <th className="py-3 pr-4 font-medium">Prompts</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((audit) => (
                <tr key={audit.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 pr-4">
                    {new Date(audit.date).toLocaleDateString('fr-FR', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </td>
                  <td className="py-3 pr-4 font-medium">{audit.brandName}</td>
                  <td className="py-3 pr-4">
                    <span className="inline-flex px-2 py-1 rounded text-xs bg-blue-100 text-blue-800">
                      {audit.provider}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <div className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                      audit.mentionRate >= 70 ? 'bg-green-100 text-green-800' :
                      audit.mentionRate >= 50 ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {audit.mentionRate}%
                    </div>
                  </td>
                  <td className="py-3 pr-4">{audit.totalMentions}</td>
                  <td className="py-3 pr-4">{audit.promptsWithMention}/{audit.totalPrompts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}