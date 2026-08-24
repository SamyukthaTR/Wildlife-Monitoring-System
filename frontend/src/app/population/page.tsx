"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type {
  DistributionRecord, PopulationDensityRow, PopulationEstimateRow, PopulationTrendRow,
} from '@/lib/types';

type Site = { id: number; location_name: string };

const DIRECTION_STYLES: Record<string, string> = {
  increasing: 'bg-emerald-100 text-emerald-700',
  decreasing: 'bg-rose-100 text-rose-700',
  stable: 'bg-sky-100 text-sky-700',
  'insufficient evidence': 'bg-slate-100 text-slate-600',
};

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export default function PopulationPage() {
  const { logout } = useAuth();

  const [scope, setScope] = useState('');
  const [sites, setSites] = useState<Site[]>([]);
  const [estimates, setEstimates] = useState<PopulationEstimateRow[]>([]);
  const [trends, setTrends] = useState<PopulationTrendRow[]>([]);
  const [density, setDensity] = useState<PopulationDensityRow[]>([]);
  const [distribution, setDistribution] = useState<DistributionRecord[]>([]);
  const [effort, setEffort] = useState<number | null>(null);
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/monitoring/sites')
      .then((res) => setSites(res.data))
      .catch(() => setError('Could not load monitoring sites.'));
  }, []);

  const fetchScoped = useCallback(async (siteId: string) => {
    const params = siteId ? { site_id: Number(siteId) } : {};
    try {
      const [estimatesRes, trendsRes, densityRes, distributionRes] = await Promise.all([
        api.get('/population/estimates', { params }),
        api.get('/population/trends', { params }),
        api.get('/population/density', { params }),
        api.get('/population/distribution', { params }),
      ]);
      setEstimates(estimatesRes.data.species);
      setTrends(trendsRes.data.species);
      setDensity(densityRes.data.species);
      setEffort(densityRes.data.observation_effort);
      setDistribution(distributionRes.data.records);
      setSelectedSpeciesId(trendsRes.data.species[0]?.species_id ?? null);
    } catch {
      setError('Could not load population analytics.');
    }
  }, []);

  useEffect(() => {
    fetchScoped(scope);
  }, [scope, fetchScoped]);

  const selectedTrend = useMemo(
    () => trends.find((t) => t.species_id === selectedSpeciesId) ?? null,
    [trends, selectedSpeciesId],
  );

  const distributionBySpecies = useMemo(() => {
    const grouped = new Map<string, DistributionRecord[]>();
    for (const record of distribution) {
      const key = record.common_name || record.scientific_name;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(record);
    }
    return Array.from(grouped.entries());
  }, [distribution]);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
                Population Intelligence
              </h1>
              <p className="text-slate-500 mt-1">
                Peak counts, trends, encounter rates and presence patterns from real detections
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
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">
              {error}
            </div>
          )}

          <div className="p-4 bg-amber-50 text-amber-800 rounded-xl border border-amber-100 text-sm">
            No individual animal is tracked across frames or locations. Figures below are
            peak counts (a lower bound), effort-normalised encounter rates, and presence
            patterns — never population estimates in the mark-recapture sense, and never
            confirmed migration.
          </div>

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

          {/* Peak simultaneous counts */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Peak Simultaneous Counts</h2>
            <p className="text-sm text-slate-500 mb-6">
              Largest number of individuals seen together in one frame, per species — a lower
              bound on population size, not an estimate of it.
            </p>
            {estimates.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Species</th>
                      <th className="py-3 px-4 font-medium">Peak count</th>
                      <th className="py-3 px-4 font-medium">Frames examined</th>
                      <th className="py-3 px-4 font-medium">Variability (median, 95% band)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {estimates.map((row) => (
                      <tr key={row.species_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                        <td className="py-3 px-4">
                          <span className="text-slate-900 font-medium">
                            {row.common_name || row.scientific_name}
                          </span>
                          <span className="block text-xs text-slate-400 italic">{row.scientific_name}</span>
                        </td>
                        <td className="py-3 px-4 text-slate-800 font-semibold">
                          {row.peak_simultaneous_count ?? 'n/a'}
                        </td>
                        <td className="py-3 px-4 text-slate-600">{row.frames_examined}</td>
                        <td className="py-3 px-4 text-slate-600 text-sm">
                          {row.variability.low != null && row.variability.high != null
                            ? `${row.variability.median} (${row.variability.low}–${row.variability.high})`
                            : `${row.variability.median ?? 'n/a'} — ${row.variability.note}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No species-level detections in this scope yet.</p>
            )}
          </div>

          {/* Trends */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Detection Trends</h2>
            <p className="text-sm text-slate-500 mb-6">
              Direction is only asserted when there are enough surveys and the fit is
              statistically significant (p &lt; 0.05); otherwise it reads &quot;insufficient
              evidence&quot;, even though a raw slope exists.
            </p>
            {trends.length > 0 ? (
              <>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                        <th className="py-3 px-4 font-medium">Species</th>
                        <th className="py-3 px-4 font-medium">Direction</th>
                        <th className="py-3 px-4 font-medium">% change / period</th>
                        <th className="py-3 px-4 font-medium">Survey points</th>
                        <th className="py-3 px-4 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {trends.map((row) => (
                        <tr key={row.species_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                          <td className="py-3 px-4 text-slate-900 font-medium">
                            {row.common_name || row.scientific_name}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${DIRECTION_STYLES[row.trend.direction] ?? 'bg-slate-100 text-slate-600'}`}>
                              {row.trend.direction}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-600">
                            {row.trend.percent_change_per_period != null
                              ? `${row.trend.percent_change_per_period > 0 ? '+' : ''}${row.trend.percent_change_per_period}%`
                              : 'n/a'}
                          </td>
                          <td className="py-3 px-4 text-slate-600">{row.trend.n_points}</td>
                          <td className="py-3 px-4">
                            <button
                              onClick={() => setSelectedSpeciesId(row.species_id)}
                              className="text-indigo-600 hover:text-indigo-800 font-medium text-sm px-3 py-1 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                            >
                              View chart
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {selectedTrend && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700 mb-3">
                      {selectedTrend.common_name || selectedTrend.scientific_name} — detections per survey
                    </h3>
                    {selectedTrend.data_points.length > 1 ? (
                      <ResponsiveContainer width="100%" height={240}>
                        <LineChart data={selectedTrend.data_points} margin={{ left: 8, right: 24, top: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="survey_date" stroke="#94a3b8" fontSize={12} />
                          <YAxis allowDecimals={false} stroke="#94a3b8" fontSize={12} />
                          <Tooltip contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e2e8f0', fontSize: 13 }} />
                          <Line type="monotone" dataKey="count" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="text-sm text-slate-500">Only one survey date recorded — nothing to chart yet.</p>
                    )}
                    {selectedTrend.trend.note && (
                      <p className="text-xs text-slate-400 mt-2">{selectedTrend.trend.note}</p>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="py-8 text-center text-slate-500">No trend data in this scope yet.</p>
            )}
          </div>

          {/* Density / encounter rate */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Encounter Rate</h2>
            <p className="text-sm text-slate-500 mb-6">
              Detections per 100 observations — effort-normalised, not a true area-based
              density. No monitoring site records its surveyed area.
              {effort != null && <> Total observation effort in scope: <strong>{effort}</strong>.</>}
            </p>
            {density.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Species</th>
                      <th className="py-3 px-4 font-medium">Detections</th>
                      <th className="py-3 px-4 font-medium">Encounter rate / 100 obs.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {density.map((row) => (
                      <tr key={row.species_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                        <td className="py-3 px-4 text-slate-900 font-medium">
                          {row.common_name || row.scientific_name}
                        </td>
                        <td className="py-3 px-4 text-slate-600">{row.detections}</td>
                        <td className="py-3 px-4 text-slate-600">
                          {row.encounter_rate_per_100_observations ?? 'n/a'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No detections in this scope yet.</p>
            )}
          </div>

          {/* Distribution / presence pattern */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Presence Pattern by Month</h2>
            <p className="text-sm text-slate-500 mb-6">
              Not confirmed migration tracking: no individual animal is identified across
              frames or locations, so an apparent seasonal shift may reflect survey timing or
              effort rather than animal movement.
            </p>
            {distributionBySpecies.length > 0 ? (
              <div className="space-y-4">
                {distributionBySpecies.map(([name, records]) => (
                  <div key={name} className="border border-slate-100 rounded-xl p-4">
                    <p className="font-medium text-slate-800 mb-2">{name}</p>
                    <div className="flex flex-wrap gap-2">
                      {records
                        .sort((a, b) => a.year - b.year || a.month - b.month)
                        .map((record, index) => (
                          <span
                            key={index}
                            className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700"
                            title={`${record.location_name}: ${record.detections} detection(s)`}
                          >
                            {MONTH_NAMES[record.month - 1]} {record.year}
                            {!scope && ` · ${record.location_name}`}
                          </span>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No presence records in this scope yet.</p>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
