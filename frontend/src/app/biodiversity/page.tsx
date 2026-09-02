"use client";

import { useCallback, useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type {
  AcousticActivity,
  CompositionRow,
  DiversityIndices,
  SiteIndices,
} from '@/lib/types';

const CHART_COLOURS = [
  '#059669', '#0891b2', '#7c3aed', '#d97706', '#dc2626',
  '#2563eb', '#65a30d', '#c026d3', '#0d9488', '#ea580c',
];

export default function BiodiversityPage() {
  const { logout } = useAuth();

  const [scope, setScope] = useState<string>('');
  const [sites, setSites] = useState<SiteIndices[]>([]);
  const [indices, setIndices] = useState<DiversityIndices | null>(null);
  const [composition, setComposition] = useState<CompositionRow[]>([]);
  const [acoustic, setAcoustic] = useState<AcousticActivity | null>(null);
  const [error, setError] = useState('');

  const fetchScoped = useCallback(async (siteId: string) => {
    const params = siteId ? { site_id: Number(siteId) } : {};
    try {
      const [indicesRes, compositionRes, acousticRes] = await Promise.all([
        api.get('/biodiversity/indices', { params }),
        api.get('/biodiversity/composition', { params }),
        api.get('/biodiversity/acoustic', { params }),
      ]);
      setIndices(indicesRes.data);
      setComposition(compositionRes.data.composition);
      setAcoustic(acousticRes.data);
    } catch {
      setError('Could not load biodiversity analytics.');
    }
  }, []);

  useEffect(() => {
    api
      .get('/biodiversity/sites')
      .then((res) => setSites(res.data.sites))
      .catch(() => setError('Could not load monitoring sites.'));
  }, []);

  useEffect(() => {
    fetchScoped(scope);
  }, [scope, fetchScoped]);

  const excluded = indices?.excluded_from_indices;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
                Biodiversity Analytics
              </h1>
              <p className="text-slate-500 mt-1">
                Diversity indices computed from species-level image detections
              </p>
            </div>
            <div className="flex gap-3">
              <a
                href="/"
                className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors"
              >
                Dashboard
              </a>
              <button
                onClick={logout}
                className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">
              {error}
            </div>
          )}

          {/* Scope selector */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Scope
            </label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              className="w-full sm:w-1/2 px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
            >
              <option value="">All monitoring sites</option>
              {sites.map((site) => (
                <option key={site.site_id} value={site.site_id}>
                  {site.location_name}
                </option>
              ))}
            </select>
          </div>

          {/* Index cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <IndexCard
              label="Species richness"
              value={indices?.species_richness ?? '—'}
              hint="distinct species (S)"
            />
            <IndexCard
              label="Shannon H'"
              value={fmt(indices?.shannon_index)}
              hint="−Σ p ln p"
            />
            <IndexCard
              label="Simpson D"
              value={fmt(indices?.simpson_index)}
              hint="Σ p² (dominance)"
            />
            <IndexCard
              label="Gini-Simpson"
              value={fmt(indices?.gini_simpson_index)}
              hint="1 − D (diversity)"
            />
            <IndexCard
              label="Pielou J'"
              value={fmt(indices?.pielou_evenness)}
              hint="H' / ln S (evenness)"
            />
          </div>

          {indices?.note && (
            <div className="p-4 bg-amber-50 text-amber-800 rounded-xl border border-amber-100">
              {indices.note}
            </div>
          )}

          {/* Species composition */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">
              Species Composition
            </h2>
            {composition.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(240, composition.length * 34)}>
                <BarChart
                  data={composition}
                  layout="vertical"
                  margin={{ left: 12, right: 24, top: 4, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <YAxis
                    type="category"
                    dataKey="species"
                    width={180}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <Tooltip
                    formatter={(value: number, _name, entry) => [
                      `${value} detections (${(
                        (entry.payload as CompositionRow).relative_abundance * 100
                      ).toFixed(1)}%)`,
                      'Detections',
                    ]}
                    contentStyle={{
                      borderRadius: '0.75rem',
                      border: '1px solid #e2e8f0',
                      fontSize: 13,
                    }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {composition.map((_, index) => (
                      <Cell key={index} fill={CHART_COLOURS[index % CHART_COLOURS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-8 text-center text-slate-500">
                No species-level detections in this scope yet. Run analysis on
                observations to populate this chart.
              </p>
            )}
          </div>

          {/* What was excluded — shown, not hidden */}
          {excluded && (
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-2">
                Excluded from these indices
              </h2>
              <p className="text-sm text-slate-500 mb-6">{excluded.reason}</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <IndexCard
                  label="Coarse-rank detections"
                  value={excluded.coarse_rank_detections}
                  hint="named a group, not a species"
                />
                <IndexCard
                  label="Unidentified animals"
                  value={excluded.unidentified_detections}
                  hint="found but not named"
                />
                <IndexCard
                  label="Acoustic detections"
                  value={excluded.acoustic_detections}
                  hint="sound type only"
                />
              </div>
            </div>
          )}

          {/* Acoustic activity */}
          {acoustic && acoustic.by_label.length > 0 && (
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-2">
                Acoustic Activity
              </h2>
              <p className="text-sm text-slate-500 mb-6">{acoustic.note}</p>
              <ResponsiveContainer
                width="100%"
                height={Math.max(220, acoustic.by_label.length * 30)}
              >
                <BarChart
                  data={acoustic.by_label}
                  layout="vertical"
                  margin={{ left: 12, right: 24, top: 4, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} stroke="#94a3b8" fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={200}
                    stroke="#94a3b8"
                    fontSize={12}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '0.75rem',
                      border: '1px solid #e2e8f0',
                      fontSize: 13,
                    }}
                  />
                  <Bar dataKey="count" fill="#0891b2" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-sm text-slate-500 mt-4">
                {acoustic.filtered_noise_events} further label(s) were filtered as
                environmental noise.
              </p>
            </div>
          )}

          {/* Per-site comparison */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">
              Site Comparison
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                    <th className="py-3 px-4 font-medium">Site</th>
                    <th className="py-3 px-4 font-medium">Observations</th>
                    <th className="py-3 px-4 font-medium">Richness</th>
                    <th className="py-3 px-4 font-medium">Shannon H&apos;</th>
                    <th className="py-3 px-4 font-medium">Evenness</th>
                    <th className="py-3 px-4 font-medium">Coordinates</th>
                  </tr>
                </thead>
                <tbody>
                  {sites.map((site) => (
                    <tr
                      key={site.site_id}
                      className="border-b border-slate-100 hover:bg-slate-50/50"
                    >
                      <td className="py-3 px-4 text-slate-800">{site.location_name}</td>
                      <td className="py-3 px-4 text-slate-600">{site.observations}</td>
                      <td className="py-3 px-4 text-slate-600">{site.species_richness}</td>
                      <td className="py-3 px-4 text-slate-600">{fmt(site.shannon_index)}</td>
                      <td className="py-3 px-4 text-slate-600">{fmt(site.pielou_evenness)}</td>
                      <td className="py-3 px-4 text-slate-500 text-sm font-mono">
                        {site.latitude != null && site.longitude != null
                          ? `${site.latitude.toFixed(3)}, ${site.longitude.toFixed(3)}`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                  {sites.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-500">
                        No monitoring sites with surveys yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {indices?.method && (
            <p className="text-sm text-slate-500 px-2">{indices.method}</p>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

/** Null indices are shown as "n/a", never as 0 — they mean "undefined here". */
function fmt(value: number | null | undefined): string {
  return value == null ? 'n/a' : value.toFixed(3);
}

function IndexCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint: string;
}) {
  return (
    <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
      <p className="text-3xl font-bold text-slate-800">{value}</p>
      <p className="text-sm font-medium text-slate-700 mt-1">{label}</p>
      <p className="text-xs text-slate-400 mt-0.5">{hint}</p>
    </div>
  );
}
