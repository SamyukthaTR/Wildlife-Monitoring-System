"use client";

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type { MapSite } from '@/components/SiteMap';
import type { EcosystemHealthSiteRow, HabitatSiteSummary, SitePriorityRow } from '@/lib/types';

const SiteMap = dynamic(() => import('@/components/SiteMap'), { ssr: false });

type Site = {
  id: number;
  location_name: string;
  habitat_type: string | null;
  latitude: number | null;
  longitude: number | null;
};

const BAND_COLORS: Record<string, string> = {
  Good: 'text-emerald-700', Fair: 'text-amber-700', Poor: 'text-orange-700', Critical: 'text-rose-700',
};

export default function MapPage() {
  const { logout } = useAuth();
  const [sites, setSites] = useState<MapSite[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/monitoring/sites'),
      api.get('/ecosystem/health/sites'),
      api.get('/habitat/sites'),
      api.get('/conservation/priorities'),
    ])
      .then(([sitesRes, healthRes, habitatRes, prioritiesRes]) => {
        const healthBySite = new Map<number, EcosystemHealthSiteRow>(
          healthRes.data.sites.map((h: EcosystemHealthSiteRow) => [h.site_id as number, h])
        );
        const habitatBySite = new Map<number, HabitatSiteSummary>(
          habitatRes.data.sites.map((h: HabitatSiteSummary) => [h.site_id, h])
        );
        const priorityBySite = new Map<number, SitePriorityRow>(
          prioritiesRes.data.sites.map((p: SitePriorityRow) => [p.site_id, p])
        );

        setSites(
          (sitesRes.data as Site[]).map((s) => {
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
      .catch(() => setError('Could not load map data.'))
      .finally(() => setLoading(false));
  }, []);

  const located = sites.filter((s) => s.latitude != null && s.longitude != null);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Map View</h1>
              <p className="text-slate-500 mt-1">
                Monitoring sites plotted by coordinates, colored by ecosystem health band
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

          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-slate-800">Monitoring Sites</h2>
              <div className="flex gap-4 text-xs text-slate-500">
                {Object.entries(BAND_COLORS).map(([band, cls]) => (
                  <span key={band} className={`font-semibold ${cls}`}>&#9679; {band}</span>
                ))}
                <span className="font-semibold text-slate-500">&#9679; Unscored</span>
              </div>
            </div>
            {loading ? (
              <p className="text-slate-500">Loading…</p>
            ) : located.length > 0 ? (
              <SiteMap sites={sites} height={520} />
            ) : (
              <p className="py-8 text-center text-slate-500">
                No monitoring sites with coordinates yet.
              </p>
            )}
            {!loading && sites.length > located.length && (
              <p className="text-xs text-slate-400 mt-3">
                {sites.length - located.length} site(s) omitted — no coordinates recorded.
              </p>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
