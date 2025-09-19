"use client";

import { useState, useEffect } from "react";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line, ResponsiveContainer } from "recharts";
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

// Types pour les données d'analytics
type AnalyticsData = {
  brandName: string;
  totalPrompts: number;
  mentionRate: number;
  totalMentions: number;
  promptsWithMention: number;
  avgFirstIndex: number;
  per_prompt: Array<{
    prompt: string;
    answer_text: string;
    summary: any;
  }>;
};

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export default function AnalyticsPage() {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [debugInfo, setDebugInfo] = useState<string>('');

  // Fonction pour charger les vraies données depuis le localStorage
  const loadRealData = () => {
    const savedResults = localStorage.getItem('lastAuditResults');
    const timestamp = new Date().toLocaleTimeString();

    console.log('[Analytics] Tentative de chargement des données à', timestamp);
    console.log('[Analytics] Données localStorage:', savedResults ? 'Données présentes' : 'Aucune donnée');

    if (savedResults) {
      try {
        const results = JSON.parse(savedResults);
        console.log('[Analytics] Structure complète des résultats:', results);
        console.log('[Analytics] results.metrics:', results.metrics);
        console.log('[Analytics] results.metrics?.by_brand:', results.metrics?.by_brand);

        // Essayons différentes structures possibles
        console.log('[Analytics] by_brand brut:', results.metrics.by_brand);
        console.log('[Analytics] type de by_brand:', typeof results.metrics.by_brand);
        console.log('[Analytics] by_brand est null?', results.metrics.by_brand === null);

        let brandNames = Object.keys(results.metrics?.by_brand || {});
        console.log('[Analytics] Marques trouvées dans by_brand:', brandNames);

        // Si by_brand est vide, regardons s'il y a des données directement dans metrics
        if (brandNames.length === 0 && results.metrics) {
          console.log('[Analytics] by_brand est vide, regardons la structure metrics:', Object.keys(results.metrics));

          // Peut-être que les données sont dans une autre structure
          if (results.per_prompt && results.per_prompt.length > 0) {
            // Essayons d'extraire le nom de marque du premier prompt
            const firstPrompt = results.per_prompt[0];
            console.log('[Analytics] Premier prompt:', firstPrompt);
            console.log('[Analytics] Summary du premier prompt:', firstPrompt.summary);

            if (firstPrompt.summary && Object.keys(firstPrompt.summary).length > 0) {
              brandNames = Object.keys(firstPrompt.summary);
              console.log('[Analytics] Marques trouvées dans le summary des prompts:', brandNames);
            }
          }
        }

        // Si on a un audit avec des prompts mais pas de marque détectée,
        // essayons de récupérer la marque depuis le localStorage du formulaire
        if (brandNames.length === 0 && results.per_prompt && results.per_prompt.length > 0) {
          console.log('[Analytics] Aucune marque détectée, essayons de récupérer depuis le formulaire...');

          const savedFormData = localStorage.getItem('lastAuditFormData');
          if (savedFormData) {
            try {
              const formData = JSON.parse(savedFormData);
              if (formData.brandName) {
                brandNames = [formData.brandName];
                console.log('[Analytics] Marque récupérée depuis le formulaire:', formData.brandName);
              }
            } catch (error) {
              console.error('[Analytics] Erreur lors de la récupération de la marque du formulaire:', error);
            }
          }
        }

        setDebugInfo(`${timestamp} - Audit trouvé avec ${results.per_prompt?.length || 0} prompts, ${brandNames.length} marque(s): ${brandNames.join(', ')}`);

        if (brandNames.length === 0 && (!results.per_prompt || results.per_prompt.length === 0)) {
          console.warn('[Analytics] Aucune donnée d\'audit trouvée');
          setDebugInfo(`${timestamp} - ERREUR: Aucune donnée d'audit. Structure metrics: ${Object.keys(results.metrics || {})}, Structure générale: ${Object.keys(results)}`);
          setAnalyticsData(null);
          return;
        }

        const brandName = brandNames[0];
        let metrics = results.metrics?.by_brand?.[brandName];

        // Si les metrics by_brand n'existent pas, calculons-les à partir des prompts
        if (!metrics && results.per_prompt) {
          console.log('[Analytics] Calcul des métriques à partir des prompts...');

          let totalMentions = 0;
          let promptsWithMention = 0;
          let firstIndexSum = 0;
          let firstIndexCount = 0;

          results.per_prompt.forEach((prompt: any) => {
            if (prompt.summary && prompt.summary[brandName]) {
              const brandData = prompt.summary[brandName];
              totalMentions += brandData.total || 0;
              if (brandData.total > 0) {
                promptsWithMention++;
                if (brandData.first_index) {
                  firstIndexSum += brandData.first_index;
                  firstIndexCount++;
                }
              }
            }
          });

          metrics = {
            mention_rate: promptsWithMention / results.per_prompt.length,
            total_mentions: totalMentions,
            prompts_with_mention: promptsWithMention,
            avg_first_index: firstIndexCount > 0 ? firstIndexSum / firstIndexCount : 0
          };

          console.log('[Analytics] Métriques calculées:', metrics);
        }

        const analyticsData: AnalyticsData = {
          brandName,
          totalPrompts: results.per_prompt?.length || results.metrics?.n_prompts || 0,
          mentionRate: Math.round((metrics?.mention_rate || 0) * 100),
          totalMentions: metrics?.total_mentions || 0,
          promptsWithMention: metrics?.prompts_with_mention || 0,
          avgFirstIndex: metrics?.avg_first_index || 0,
          per_prompt: results.per_prompt || []
        };

        console.log('[Analytics] Données analytics créées:', analyticsData);
        setAnalyticsData(analyticsData);
        setLastUpdate(timestamp);
      } catch (error) {
        console.error('[Analytics] Erreur lors du chargement des données:', error);
        setDebugInfo(`Erreur: ${error}`);
        setAnalyticsData(null);
      }
    } else {
      console.log('[Analytics] Aucune donnée dans localStorage');
      setAnalyticsData(null);
    }
  };

  // Fonction pour générer et télécharger le PDF
  const generatePDF = () => {
    if (!analyticsData) return;

    const doc = new jsPDF();
    const currentDate = new Date().toLocaleDateString('fr-FR');
    const currentTime = new Date().toLocaleTimeString('fr-FR');

    // En-tête
    doc.setFontSize(20);
    doc.setTextColor(51, 65, 85); // text-gray-800
    doc.text('📊 Analytics GEO - Rapport d\'audit', 20, 25);

    doc.setFontSize(12);
    doc.setTextColor(107, 114, 128); // text-gray-500
    doc.text(`Marque: ${analyticsData.brandName}`, 20, 35);
    doc.text(`Généré le: ${currentDate} à ${currentTime}`, 20, 42);

    // KPIs principaux
    doc.setFontSize(16);
    doc.setTextColor(51, 65, 85);
    doc.text('📈 Métriques principales', 20, 60);

    const kpiData = [
      ['Métrique', 'Valeur'],
      ['Taux de visibilité', `${analyticsData.mentionRate}%`],
      ['Total mentions', analyticsData.totalMentions.toString()],
      ['Prompts performants', analyticsData.promptsWithMention.toString()],
      ['Total prompts testés', analyticsData.totalPrompts.toString()],
      ['Position moyenne', analyticsData.avgFirstIndex.toFixed(1)]
    ];

    autoTable(doc, {
      startY: 70,
      head: [kpiData[0]],
      body: kpiData.slice(1),
      theme: 'grid',
      headStyles: { fillColor: [59, 130, 246] }, // bg-blue-500
      alternateRowStyles: { fillColor: [248, 250, 252] }, // bg-slate-50
      margin: { left: 20, right: 20 }
    });

    // Performance par prompt
    const finalY = (doc as any).lastAutoTable.finalY || 120;

    doc.setFontSize(16);
    doc.text('🎯 Performance détaillée par prompt', 20, finalY + 20);

    const promptData = [
      ['#', 'Prompt', 'Mentions', 'Performance']
    ];

    analyticsData.per_prompt.forEach((prompt, index) => {
      const mentionCount = Object.keys(prompt.summary).length > 0
        ? prompt.summary[analyticsData.brandName]?.total || 0
        : 0;
      const performance = mentionCount > 0 ? '✅ Performant' : '❌ Aucune mention';

      promptData.push([
        (index + 1).toString(),
        prompt.prompt.length > 60 ? prompt.prompt.substring(0, 60) + '...' : prompt.prompt,
        mentionCount.toString(),
        performance
      ]);
    });

    autoTable(doc, {
      startY: finalY + 30,
      head: [promptData[0]],
      body: promptData.slice(1),
      theme: 'grid',
      headStyles: { fillColor: [34, 197, 94] }, // bg-green-500
      alternateRowStyles: { fillColor: [248, 250, 252] },
      columnStyles: {
        0: { cellWidth: 15 },
        1: { cellWidth: 80 },
        2: { cellWidth: 25 },
        3: { cellWidth: 35 }
      },
      margin: { left: 20, right: 20 }
    });

    // Recommandations
    const finalY2 = (doc as any).lastAutoTable.finalY || 200;

    if (finalY2 > 250) {
      doc.addPage();
      doc.setFontSize(16);
      doc.text('💡 Recommandations', 20, 30);

      doc.setFontSize(11);
      doc.setTextColor(107, 114, 128);

      if (analyticsData.mentionRate === 0) {
        doc.text('• Aucune mention détectée. Considérez tester avec une marque plus connue.', 25, 45);
        doc.text('• Vérifiez que les aliases de marque sont correctement configurés.', 25, 52);
        doc.text('• Essayez d\'ajuster les termes de recherche pour inclure des variantes.', 25, 59);
      } else if (analyticsData.mentionRate < 30) {
        doc.text('• Visibilité faible. Optimisez votre stratégie de contenu.', 25, 45);
        doc.text('• Renforcez votre présence sur les plateformes de recherche.', 25, 52);
      } else if (analyticsData.mentionRate < 70) {
        doc.text('• Visibilité modérée. Continuez vos efforts d\'optimisation.', 25, 45);
        doc.text('• Identifiez les prompts performants pour reproduire leur succès.', 25, 52);
      } else {
        doc.text('• Excellente visibilité ! Maintenez cette performance.', 25, 45);
        doc.text('• Analysez les prompts les plus performants pour optimiser davantage.', 25, 52);
      }
    } else {
      doc.setFontSize(16);
      doc.text('💡 Recommandations', 20, finalY2 + 20);

      doc.setFontSize(11);
      doc.setTextColor(107, 114, 128);

      if (analyticsData.mentionRate === 0) {
        doc.text('• Aucune mention détectée. Considérez tester avec une marque plus connue.', 25, finalY2 + 35);
        doc.text('• Vérifiez que les aliases de marque sont correctement configurés.', 25, finalY2 + 42);
      } else if (analyticsData.mentionRate < 30) {
        doc.text('• Visibilité faible. Optimisez votre stratégie de contenu.', 25, finalY2 + 35);
      } else {
        doc.text('• Performance satisfaisante. Continuez vos efforts !', 25, finalY2 + 35);
      }
    }

    // Pied de page
    const pageCount = doc.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(9);
      doc.setTextColor(156, 163, 175); // text-gray-400
      doc.text(`Rapport généré par GEO Analytics - Page ${i}/${pageCount}`, 20, 285);
      doc.text(`🤖 Généré avec Claude Code - ${currentDate}`, 140, 285);
    }

    // Télécharger le PDF
    const fileName = `analytics-geo-${analyticsData.brandName.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}.pdf`;
    doc.save(fileName);
  };

  useEffect(() => {
    loadRealData();

    // Écouter les changements dans localStorage
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'lastAuditResults') {
        loadRealData();
      }
    };

    // Écouter les événements customisés pour les mises à jour
    const handleAuditComplete = () => {
      loadRealData();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('auditComplete', handleAuditComplete);

    // Polling pour détecter les changements (fallback)
    const interval = setInterval(() => {
      const currentData = localStorage.getItem('lastAuditResults');
      if (currentData && !analyticsData) {
        loadRealData();
      }
    }, 5000);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('auditComplete', handleAuditComplete);
      clearInterval(interval);
    };
  }, [analyticsData]);

  if (loading) {
    return (
      <main className="max-w-7xl mx-auto p-6">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Chargement des analytics...</p>
        </div>
      </main>
    );
  }

  if (!analyticsData) {
    return (
      <main className="max-w-7xl mx-auto p-6">
        <div className="text-center py-20">
          <div className="mb-8">
            <div className="text-6xl mb-4">📊</div>
            <h1 className="text-3xl font-bold mb-4">Analytics GEO</h1>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Aucun audit n'a encore été effectué. Lancez d'abord un audit pour voir vos analytics et graphiques détaillés.
            </p>
          </div>
          <div className="bg-blue-50 rounded-xl p-6 max-w-lg mx-auto">
            <h3 className="font-semibold text-blue-900 mb-3">Comment procéder :</h3>
            <ol className="text-left text-blue-800 space-y-2">
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">1</span>
                Allez sur la page d'audit principale
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">2</span>
                Configurez votre marque et type d'activité
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">3</span>
                Générez et lancez votre audit GEO
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">4</span>
                Revenez ici pour voir vos analytics
              </li>
            </ol>
          </div>

          {/* Debug info */}
          {debugInfo && (
            <div className="mt-4 p-3 bg-gray-100 rounded text-xs text-gray-700">
              <strong>Debug:</strong> {debugInfo}
            </div>
          )}

          <div className="mt-8">
            <a
              href="/"
              className="bg-blue-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-blue-700 inline-flex items-center gap-2"
            >
              🚀 Lancer un audit GEO
            </a>
          </div>
        </div>
      </main>
    );
  }

  // Données pour le graphique en camembert
  const pieData = [
    { name: 'Avec mention', value: analyticsData.promptsWithMention, color: '#00C49F' },
    { name: 'Sans mention', value: analyticsData.totalPrompts - analyticsData.promptsWithMention, color: '#FF8042' }
  ];

  // Données pour le graphique en barres (performance par type de prompt)
  const barData = analyticsData.per_prompt.map((item, index) => ({
    name: `P${index + 1}`,
    mentions: Object.keys(item.summary).length > 0 ? item.summary[analyticsData.brandName]?.total || 1 : 0,
    prompt: item.prompt.substring(0, 30) + "..."
  }));

  // Données pour la courbe de tendance
  const lineData = analyticsData.per_prompt.map((item, index) => ({
    prompt: index + 1,
    mentions: Object.keys(item.summary).length > 0 ? item.summary[analyticsData.brandName]?.total || 1 : 0
  }));

  // Top 5 des meilleurs prompts
  const topPrompts = analyticsData.per_prompt
    .map((item, index) => ({
      ...item,
      index,
      mentionCount: Object.keys(item.summary).length > 0 ? item.summary[analyticsData.brandName]?.total || 1 : 0
    }))
    .filter(item => item.mentionCount > 0)
    .sort((a, b) => b.mentionCount - a.mentionCount)
    .slice(0, 5);

  return (
    <main className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold">📊 Analytics GEO</h1>
        <p className="text-gray-600 mt-2">Analyse détaillée de la visibilité de <span className="font-semibold text-blue-600">{analyticsData.brandName}</span></p>
        {lastUpdate && (
          <p className="text-xs text-gray-400 mt-1">Dernière mise à jour: {lastUpdate}</p>
        )}
        {debugInfo && (
          <div className="mt-2 p-2 bg-gray-100 rounded text-xs text-gray-700">
            <strong>Debug:</strong> {debugInfo}
          </div>
        )}
      </div>

      {/* KPIs principaux */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl p-6 text-white">
          <div className="text-3xl font-bold">{analyticsData.mentionRate}%</div>
          <div className="text-blue-100">Taux de visibilité</div>
        </div>
        <div className="bg-gradient-to-r from-green-500 to-green-600 rounded-xl p-6 text-white">
          <div className="text-3xl font-bold">{analyticsData.totalMentions}</div>
          <div className="text-green-100">Total mentions</div>
        </div>
        <div className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-xl p-6 text-white">
          <div className="text-3xl font-bold">{analyticsData.promptsWithMention}</div>
          <div className="text-purple-100">Prompts performants</div>
        </div>
        <div className="bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl p-6 text-white">
          <div className="text-3xl font-bold">{analyticsData.avgFirstIndex.toFixed(1)}</div>
          <div className="text-orange-100">Position moyenne</div>
        </div>
      </div>

      {/* Graphiques principaux */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Graphique en camembert */}
        <div className="bg-white rounded-xl p-6 shadow-lg">
          <h3 className="text-xl font-bold mb-4">Répartition des mentions</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Graphique en barres */}
        <div className="bg-white rounded-xl p-6 shadow-lg">
          <h3 className="text-xl font-bold mb-4">Performance par prompt</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip
                labelFormatter={(label) => `Prompt ${label}`}
                formatter={(value: any, name: any) => [value, 'Mentions']}
              />
              <Bar dataKey="mentions" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Courbe de tendance */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-bold mb-4">Tendance des mentions</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={lineData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="prompt" label={{ value: 'Numéro de prompt', position: 'insideBottom', offset: -10 }} />
            <YAxis label={{ value: 'Mentions', angle: -90, position: 'insideLeft' }} />
            <Tooltip
              labelFormatter={(label) => `Prompt ${label}`}
              formatter={(value: any) => [value, 'Mentions']}
            />
            <Line type="monotone" dataKey="mentions" stroke="#8884d8" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Top 5 des meilleurs prompts */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-bold mb-4">🏆 Top 5 des prompts les plus performants</h3>
        <div className="space-y-3">
          {topPrompts.length > 0 ? (
            topPrompts.map((prompt, index) => (
              <div key={prompt.index} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                    index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : index === 2 ? 'bg-amber-600' : 'bg-blue-500'
                  }`}>
                    {index + 1}
                  </div>
                  <div>
                    <p className="font-medium">{prompt.prompt.substring(0, 60)}...</p>
                    <p className="text-sm text-gray-600">{prompt.mentionCount} mention(s)</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-green-600">{prompt.mentionCount}</div>
                  <div className="text-xs text-gray-500">mentions</div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8">
              <div className="text-gray-400 text-4xl mb-2">📊</div>
              <p className="text-gray-600 font-medium">Aucune mention trouvée</p>
              <p className="text-gray-500 text-sm mt-1">
                La marque "{analyticsData.brandName}" n'a été mentionnée dans aucun des {analyticsData.totalPrompts} prompts testés.
              </p>
              <div className="mt-4 p-4 bg-amber-50 rounded-lg">
                <p className="text-amber-800 text-sm">
                  💡 <strong>Conseil :</strong> Essayez avec une marque plus connue ou ajustez les termes de recherche (aliases).
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-xl p-6 shadow-lg">
        <h3 className="text-xl font-bold mb-4">🔄 Actions</h3>
        <div className="flex flex-wrap gap-4">
          <button
            onClick={loadRealData}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 inline-flex items-center gap-2"
          >
            🔄 Actualiser les données
          </button>
          <button
            onClick={generatePDF}
            className="bg-red-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-red-700 inline-flex items-center gap-2"
          >
            📄 Télécharger PDF
          </button>
          <a
            href="/"
            className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 inline-flex items-center gap-2"
          >
            🚀 Nouvel audit
          </a>
        </div>
      </div>
    </main>
  );
}