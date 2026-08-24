"use client";

import { useCallback, useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type { EcosystemHealth, EcosystemHealthSiteRow, SiteRecommendations } from '@/lib/types';

type Site = { id: number; location_name: string };

const PRIORITY_STYLES: Record<string, string> = {
  high: 'bg-rose-100 text-rose-700 border-rose-200',
  medium: 'bg-amber-100 text-amber-800 border-amber-200',
  low: 'bg-slate-100 text-slate-600 border-slate-200',
};

const CATEGORY_LABELS: Record<string, string> = {
  conservation_priority: 'Conservation Priority',
  habitat_restoration: 'Habitat Restoration',
  wildlife_protection: 'Wildlife Protection',
  monitoring_allocation: 'Monitoring Allocation',
};

const BAND_STYLES: Record<string, string> = {
  Good: 'text-emerald-700',
  Fair: 'text-amber-700',
  Poor: 'text-orange-700',
  Critical: 'text-rose-700',
};

export default function ConservationPage() {
  const { logout } = useAuth();

  const [scope, setScope] = useState('');
  const [sites, setSites] = useState<Site[]>([]);
  const [health, setHealth] = useState<EcosystemHealth | null>(null);
  const [rankedSites, setRankedSites] = useState<EcosystemHealthSiteRow[]>([]);
  const [recommendationSites, setRecommendationSites] = useState<SiteRecommendations[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/monitoring/sites')
      .then((res) => setSites(res.data))
      .catch(() => setError('Could not load monitoring sites.'));
    api.get('/ecosystem/health/sites')
      .then((res) => setRankedSites(res.data.sites))
      .catch(() => setError('Could not load ecosystem health rankings.'));
  }, []);

  const fetchScoped = useCallback(async (siteId: string) => {
    const params = siteId ? { site_id: Number(siteId) } : {};
    try {
      const [healthRes, recommendationsRes] = await Promise.all([
        api.get('/ecosystem/health', { params }),
        api.get('/conservation/recommendations', { params }),
      ]);
      setHealth(healthRes.data);
      setRecommendationSites(recommendationsRes.data.sites);
    } catch {
      setError('Could not load conservation insights.');
    }
  }, []);

  useEffect(() => {
    fetchScoped(scope);
  }, [scope, fetchScoped]);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
                Conservation Insights
              </h1>
              <p className="text-slate-500 mt-1">
                Ecosystem health scores and rule-based recommendations
              </p>
            </div>
            <div className="flex gap-3">
              <a href="/" className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors">
                Dashboard
              </a>
              <button onClick={logout} className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors">
                Sign Out
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">{error}</div>
          )}

          {/* Scope selector */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <label className="block text-sm font-medium text-slate-700 mb-2">Scope</label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              className="w-full sm:w-1/2 px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
            >
              <option value="">All monitoring sites</option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>{site.location_name}</option>
              ))}
            </select>
          </div>

          {/* Ecosystem health */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Ecosystem Health</h2>
            {health && (
              <>
                <p className="text-sm text-slate-500 mb-6">{health.note}</p>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                  <ScoreCard label="Biodiversity" value={health.biodiversity_score} />
                  <ScoreCard label="Habitat quality" value={health.habitat_quality_score} />
                  <ScoreCard label="Population stability" value={health.population_stability_score} />
                  <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
                    <p className="text-3xl font-bold text-slate-800">
                      {health.overall_ecosystem_health_score ?? '—'}
                    </p>
                    <p className="text-sm font-medium text-slate-700 mt-1">Overall</p>
                    {health.band && (
                      <p className={`text-xs mt-0.5 font-semibold ${BAND_STYLES[health.band] ?? 'text-slate-500'}`}>
                        {health.band}
                      </p>
                    )}
                  </div>
                </div>
                <p className="text-xs text-slate-400">
                  {health.overall_ecosystem_health_score != null
                    ? `Computed from: ${health.computed_from.join(', ')}`
                    : 'Not enough component scores available yet to compute an overall figure.'}
                </p>
              </>
            )}
          </div>

          {/* Site ranking */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Sites Ranked by Ecosystem Health</h2>
            {rankedSites.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Site</th>
                      <th className="py-3 px-4 font-medium">Overall</th>
                      <th className="py-3 px-4 font-medium">Band</th>
                      <th className="py-3 px-4 font-medium">Species richness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankedSites.map((row) => (
                      <tr key={row.site_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                        <td className="py-3 px-4 text-slate-900 font-medium">{row.location_name}</td>
                        <td className="py-3 px-4 text-slate-600">
                          {row.overall_ecosystem_health_score ?? 'n/a'}
                        </td>
                        <td className="py-3 px-4">
                          {row.band ? (
                            <span className={`text-sm font-semibold ${BAND_STYLES[row.band] ?? 'text-slate-500'}`}>
                              {row.band}
                            </span>
                          ) : 'n/a'}
                        </td>
                        <td className="py-3 px-4 text-slate-600">{row.inputs.species_richness}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No monitoring sites yet.</p>
            )}
          </div>

          {/* Recommendations */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Recommendations</h2>
            <p className="text-sm text-slate-500 mb-6">
              Deterministic rule-based recommendations, not AI-generated. Each rationale cites
              the number that triggered it.
            </p>
            {recommendationSites.length > 0 ? (
              <div className="space-y-6">
                {recommendationSites.map((siteEntry) => (
                  <div key={siteEntry.site_id}>
                    <h3 className="font-semibold text-slate-800 mb-3">{siteEntry.location_name}</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {siteEntry.recommendations.map((rec, index) => (
                        <div
                          key={index}
                          className={`p-4 rounded-xl border ${PRIORITY_STYLES[rec.priority] ?? 'bg-slate-50 border-slate-100'}`}
                        >
                          <div className="flex justify-between items-start mb-2">
                            <span className="text-xs font-semibold uppercase tracking-wide opacity-70">
                              {CATEGORY_LABELS[rec.category] ?? rec.category}
                            </span>
                            <span className="text-xs font-bold uppercase">{rec.priority}</span>
                          </div>
                          <p className="font-medium text-slate-800 mb-1">{rec.title}</p>
                          <p className="text-sm text-slate-600">{rec.rationale}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">
                No recommendations triggered for this scope — either the data looks healthy, or
                there isn&apos;t enough data yet to trigger any rule.
              </p>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function ScoreCard({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
      <p className="text-3xl font-bold text-slate-800">{value ?? 'n/a'}</p>
      <p className="text-sm font-medium text-slate-700 mt-1">{label}</p>
    </div>
  );
}
