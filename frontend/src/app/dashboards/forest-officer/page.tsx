"use client";

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type { HabitatSiteSummary } from '@/lib/types';

type PriorityRow = {
  site_id: number;
  location_name: string;
  overall_health: number | null;
  high_priority_flags: number;
  total_recommendations: number;
};

export default function ForestOfficerDashboard() {
  const { user, logout } = useAuth();

  const [habitatSites, setHabitatSites] = useState<HabitatSiteSummary[]>([]);
  const [priorities, setPriorities] = useState<PriorityRow[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/habitat/sites'),
      api.get('/conservation/priorities'),
    ])
      .then(([habitatRes, prioritiesRes]) => {
        setHabitatSites(habitatRes.data.sites);
        setPriorities(prioritiesRes.data.sites);
      })
      .catch(() => setError('Could not load habitat/conservation data.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ProtectedRoute allowedRoles={['Forest Department Officer']}>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
                Forest Department Officer Dashboard
              </h1>
              <p className="text-slate-500 mt-1">Welcome back, {user?.name}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a href="/habitat" className="px-5 py-2.5 bg-teal-50 text-teal-700 hover:bg-teal-100 rounded-xl font-medium transition-colors">
                Habitat Intelligence
              </a>
              <a href="/conservation" className="px-5 py-2.5 bg-amber-50 text-amber-700 hover:bg-amber-100 rounded-xl font-medium transition-colors">
                Conservation Insights
              </a>
              <a href="/map" className="px-5 py-2.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-xl font-medium transition-colors">
                Map View
              </a>
              <a href="/executive" className="px-5 py-2.5 bg-violet-50 text-violet-700 hover:bg-violet-100 rounded-xl font-medium transition-colors">
                Executive Overview
              </a>
              <button onClick={logout} className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors">
                Sign Out
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">{error}</div>
          )}

          {/* Conservation priorities */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Sites Needing Attention</h2>
            <p className="text-sm text-slate-500 mb-6">
              Ranked by how many high-priority conservation flags each site carries. See{' '}
              <a href="/conservation" className="text-amber-700 underline">Conservation Insights</a>{' '}
              for the full rationale behind each one.
            </p>
            {loading ? (
              <p className="text-slate-500">Loading…</p>
            ) : priorities.filter((p) => p.high_priority_flags > 0 || p.total_recommendations > 0).length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Site</th>
                      <th className="py-3 px-4 font-medium">Overall health</th>
                      <th className="py-3 px-4 font-medium">High-priority flags</th>
                      <th className="py-3 px-4 font-medium">Total recommendations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priorities
                      .filter((p) => p.high_priority_flags > 0 || p.total_recommendations > 0)
                      .map((row) => (
                        <tr key={row.site_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                          <td className="py-3 px-4 text-slate-900 font-medium">{row.location_name}</td>
                          <td className="py-3 px-4 text-slate-600">{row.overall_health ?? 'n/a'}</td>
                          <td className="py-3 px-4">
                            {row.high_priority_flags > 0 ? (
                              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-700">
                                {row.high_priority_flags}
                              </span>
                            ) : '0'}
                          </td>
                          <td className="py-3 px-4 text-slate-600">{row.total_recommendations}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">No sites currently flagged.</p>
            )}
          </div>

          {/* Habitat overview */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Habitat Overview</h2>
            <p className="text-sm text-slate-500 mb-6">
              Latest vegetation assessment per site. Run a new assessment from{' '}
              <a href="/habitat" className="text-teal-700 underline">Habitat Intelligence</a>.
            </p>
            {loading ? (
              <p className="text-slate-500">Loading…</p>
            ) : habitatSites.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Site</th>
                      <th className="py-3 px-4 font-medium">Vegetation index</th>
                      <th className="py-3 px-4 font-medium">Inferred signal</th>
                      <th className="py-3 px-4 font-medium">Degradation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {habitatSites.map((site) => (
                      <tr key={site.site_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                        <td className="py-3 px-4 text-slate-900 font-medium">{site.location_name}</td>
                        <td className="py-3 px-4 text-slate-600">{site.vegetation_index}</td>
                        <td className="py-3 px-4 text-slate-600 text-sm">{site.inferred_habitat_signal}</td>
                        <td className="py-3 px-4">
                          {site.degradation_flag ? (
                            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                              Significant decline
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                              Stable
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">
                No sites have been assessed yet. Visit Habitat Intelligence to run one.
              </p>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
