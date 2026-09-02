"use client";

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type {
  DiversityIndices, EcosystemHealthSiteRow, HabitatSiteSummary, PopulationTrendRow, SitePriorityRow,
} from '@/lib/types';
import type { MapSite } from '@/components/SiteMap';

const SiteMap = dynamic(() => import('@/components/SiteMap'), { ssr: false });

const BAND_STYLES: Record<string, string> = {
  Good: 'text-emerald-700', Fair: 'text-amber-700', Poor: 'text-orange-700', Critical: 'text-rose-700',
};

export default function ExecutiveDashboard() {
  const { user, logout } = useAuth();

  const [rankedSites, setRankedSites] = useState<EcosystemHealthSiteRow[]>([]);
  const [priorities, setPriorities] = useState<SitePriorityRow[]>([]);
  const [biodiversity, setBiodiversity] = useState<DiversityIndices | null>(null);
  const [trends, setTrends] = useState<PopulationTrendRow[]>([]);
  const [mapSites, setMapSites] = useState<MapSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.get('/ecosystem/health/sites'),
      api.get('/conservation/priorities'),
      api.get('/biodiversity/indices'),
      api.get('/population/trends'),
      api.get('/monitoring/sites'),
      api.get('/habitat/sites'),
    ])
      .then(([healthRes, prioritiesRes, biodiversityRes, trendsRes, sitesRes, habitatRes]) => {
        setRankedSites(healthRes.data.sites);
        setPriorities(prioritiesRes.data.sites);
        setBiodiversity(biodiversityRes.data);
        setTrends(trendsRes.data.species);

        const healthBySite = new Map<number, EcosystemHealthSiteRow>(
          healthRes.data.sites.map((h: EcosystemHealthSiteRow) => [h.site_id as number, h])
        );
        const habitatBySite = new Map<number, HabitatSiteSummary>(
          habitatRes.data.sites.map((h: HabitatSiteSummary) => [h.site_id, h])
        );
        const priorityBySite = new Map<number, SitePriorityRow>(
          prioritiesRes.data.sites.map((p: SitePriorityRow) => [p.site_id, p])
        );
        setMapSites(
          (sitesRes.data as { id: number; location_name: string; habitat_type: string | null; latitude: number | null; longitude: number | null }[]).map((s) => {
            const health = healthBySite.get(s.id);
            const habitat = habitatBySite.get(s.id);
            const priority = priorityBySite.get(s.id);
            return {
              site_id: s.id,
              location_name: s.location_name,
              habitat_type: s.habitat_type,
              latitude: s.latitude,
              longitude: s.longitude,
              health_score: health?.overall_ecosystem_health_score ?? null,
              health_band: health?.band ?? null,
              degradation_flag: habitat?.degradation_flag ?? false,
              high_priority_flags: priority?.high_priority_flags ?? 0,
            };
          })
        );
      })
      .catch(() => setError('Could not load executive overview data.'))
      .finally(() => setLoading(false));
  }, []);

  const topPriorities = priorities
    .filter((p) => p.high_priority_flags > 0)
    .sort((a, b) => b.high_priority_flags - a.high_priority_flags)
    .slice(0, 5);

  const increasing = trends.filter((t) => t.trend.significant && t.trend.direction === 'increasing');
  const decreasing = trends.filter((t) => t.trend.significant && t.trend.direction === 'decreasing');

  return (
    <ProtectedRoute allowedRoles={['Conservation Officer', 'Forest Department Officer', 'Administrator']}>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Executive Overview</h1>
              <p className="text-slate-500 mt-1">
                Platform-wide synthesis for {user?.name} — every figure here already exists on a
                dedicated page; this view combines them for a management-level read.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a href="/" className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors">
                Dashboard
              </a>
              <a href="/map" className="px-5 py-2.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-xl font-medium transition-colors">
                Map View
              </a>
              <button onClick={logout} className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors">
                Sign Out
              </button>
            </div>
          </div>

          {error && <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">{error}</div>}
          {loading && <p className="text-slate-500">Loading…</p>}

          {/* Platform biodiversity snapshot */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Platform Biodiversity Snapshot</h2>
            <p className="text-sm text-slate-500 mb-6">Across every monitoring site combined.</p>
            {biodiversity && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard label="Species richness" value={biodiversity.species_richness} />
                <StatCard label="Total detections" value={biodiversity.total_detections} />
                <StatCard label="Shannon index" value={biodiversity.shannon_index} />
                <StatCard label="Pielou evenness" value={biodiversity.pielou_evenness} />
              </div>
            )}
          </div>

          {/* Ecosystem health ranking + map preview */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Ecosystem Health Ranking</h2>
              {rankedSites.length > 0 ? (
                <div className="overflow-x-auto max-h-96 overflow-y-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                        <th className="py-3 px-4 font-medium">Site</th>
                        <th className="py-3 px-4 font-medium">Overall</th>
                        <th className="py-3 px-4 font-medium">Band</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rankedSites.map((row) => (
                        <tr key={row.site_id} className="border-b border-slate-100">
                          <td className="py-3 px-4 text-slate-900 font-medium">{row.location_name}</td>
                          <td className="py-3 px-4 text-slate-600">{row.overall_ecosystem_health_score ?? 'n/a'}</td>
                          <td className="py-3 px-4">
                            {row.band ? (
                              <span className={`text-sm font-semibold ${BAND_STYLES[row.band] ?? 'text-slate-500'}`}>{row.band}</span>
                            ) : 'n/a'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="py-8 text-center text-slate-500">No sites scored yet.</p>
              )}
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Site Map Preview</h2>
              {mapSites.filter((s) => s.latitude != null).length > 0 ? (
                <SiteMap sites={mapSites} height={300} />
              ) : (
                <p className="py-8 text-center text-slate-500">No located sites yet.</p>
              )}
              <a href="/map" className="block text-center mt-4 text-indigo-700 underline text-sm">
                Open full Map View
              </a>
            </div>
          </div>

          {/* Top conservation priorities */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Top Conservation Priorities</h2>
            <p className="text-sm text-slate-500 mb-6">
              Sites carrying the most high-priority flags. See{' '}
              <a href="/conservation" className="text-amber-700 underline">Conservation Insights</a> for full rationale.
            </p>
            {topPriorities.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topPriorities.map((p) => (
                  <div key={p.site_id} className="p-4 rounded-xl bg-rose-50 border border-rose-100">
                    <p className="font-semibold text-slate-800">{p.location_name}</p>
                    <p className="text-sm text-rose-700 mt-1">{p.high_priority_flags} high-priority flag(s)</p>
                    <p className="text-xs text-slate-500 mt-1">{p.total_recommendations} total recommendation(s)</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No sites currently carry a high-priority flag.</p>
            )}
          </div>

          {/* Population trend highlights */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Population Trend Highlights</h2>
            <p className="text-sm text-slate-500 mb-6">
              Species with a statistically significant trend across the whole platform. See{' '}
              <a href="/population" className="text-sky-700 underline">Population Intelligence</a> for per-site detail.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-sm font-semibold text-emerald-700 mb-3">Increasing</h3>
                {increasing.length > 0 ? (
                  <ul className="space-y-2">
                    {increasing.map((t) => (
                      <li key={t.species_id} className="text-sm text-slate-700">
                        {t.common_name || t.scientific_name}
                        <span className="text-emerald-600 font-medium"> ↑ {t.trend.percent_change_per_period ?? ''}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-slate-500">None with significant evidence yet.</p>}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-rose-700 mb-3">Decreasing</h3>
                {decreasing.length > 0 ? (
                  <ul className="space-y-2">
                    {decreasing.map((t) => (
                      <li key={t.species_id} className="text-sm text-slate-700">
                        {t.common_name || t.scientific_name}
                        <span className="text-rose-600 font-medium"> ↓ {t.trend.percent_change_per_period ?? ''}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-slate-500">None with significant evidence yet.</p>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function StatCard({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
      <p className="text-2xl font-bold text-slate-800">{value ?? 'n/a'}</p>
      <p className="text-sm text-slate-500 mt-1">{label}</p>
    </div>
  );
}
