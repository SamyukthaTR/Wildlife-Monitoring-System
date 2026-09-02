"use client";

import { useCallback, useEffect, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api, { downloadReport } from '@/lib/api';
import type { HabitatDetail, HabitatEnvironment, HabitatSuitability } from '@/lib/types';

type Site = { id: number; location_name: string; habitat_type: string | null };

const ASSESS_ROLES = ['Wildlife Researcher', 'Conservation Officer', 'Administrator'];
const SPECIES_GROUPS = ['mammal', 'bird', 'reptile', 'amphibian', 'insect', 'marine', 'other'];

const DIRECTION_STYLES: Record<string, string> = {
  increasing: 'bg-emerald-100 text-emerald-700',
  decreasing: 'bg-rose-100 text-rose-700',
  stable: 'bg-sky-100 text-sky-700',
  'insufficient evidence': 'bg-slate-100 text-slate-600',
};

export default function HabitatPage() {
  const { user, logout } = useAuth();

  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string>('');
  const [detail, setDetail] = useState<HabitatDetail | null>(null);
  const [environment, setEnvironment] = useState<HabitatEnvironment | null>(null);
  const [speciesGroup, setSpeciesGroup] = useState('mammal');
  const [suitability, setSuitability] = useState<HabitatSuitability | null>(null);
  const [assessing, setAssessing] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const canAssess = !!user && ASSESS_ROLES.includes(user.role);

  useEffect(() => {
    api.get('/monitoring/sites')
      .then((res) => {
        setSites(res.data);
        if (res.data.length > 0) setSiteId(String(res.data[0].id));
      })
      .catch(() => setError('Could not load monitoring sites.'));
  }, []);

  const fetchSiteData = useCallback(async (id: string, group: string) => {
    if (!id) return;
    try {
      const [detailRes, envRes, suitabilityRes] = await Promise.all([
        api.get(`/habitat/${id}`),
        api.get('/habitat/environment', { params: { site_id: Number(id) } }),
        api.get('/habitat/suitability', { params: { site_id: Number(id), species_group: group } }),
      ]);
      setDetail(detailRes.data);
      setEnvironment(envRes.data);
      setSuitability(suitabilityRes.data);
    } catch {
      setError('Could not load habitat data for this site.');
    }
  }, []);

  useEffect(() => {
    fetchSiteData(siteId, speciesGroup);
  }, [siteId, speciesGroup, fetchSiteData]);

  const runAssessment = async () => {
    if (!siteId) return;
    setAssessing(true);
    setMessage('');
    setError('');
    try {
      await api.post(`/habitat/assess-site/${siteId}`);
      setMessage('Assessment complete — vegetation metrics computed from this site\'s images.');
      fetchSiteData(siteId, speciesGroup);
    } catch (err: unknown) {
      const detailMsg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detailMsg || 'Assessment failed.');
    } finally {
      setAssessing(false);
    }
  };

  const handleDownloadReport = async (format: 'pdf' | 'xlsx') => {
    if (!siteId) return;
    const site = sites.find((s) => String(s.id) === siteId);
    try {
      await downloadReport(
        '/reports/habitat',
        { site_id: Number(siteId), format },
        `habitat-report-${(site?.location_name ?? siteId).replace(/\s+/g, '-')}.${format}`
      );
    } catch {
      setError('Could not generate habitat report.');
    }
  };

  const chartData = detail?.assessments.map((a) => ({
    date: new Date(a.assessed_at).toLocaleDateString(),
    vegetation_index: a.vegetation_index,
  })) ?? [];

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
                Habitat Intelligence
              </h1>
              <p className="text-slate-500 mt-1">
                Vegetation read from real camera-trap pixels, plus modelled historical weather
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
          {message && (
            <div className="p-4 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100 font-medium">{message}</div>
          )}

          {/* Site selector + assess action */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[240px]">
              <label className="block text-sm font-medium text-slate-700 mb-2">Monitoring site</label>
              <select
                value={siteId}
                onChange={(e) => setSiteId(e.target.value)}
                className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
              >
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>{site.location_name}</option>
                ))}
                {sites.length === 0 && <option value="">No sites yet</option>}
              </select>
            </div>
            {canAssess && (
              <button
                onClick={runAssessment}
                disabled={assessing || !siteId}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl font-medium transition-colors"
              >
                {assessing ? 'Assessing…' : 'Run Vegetation Assessment'}
              </button>
            )}
            <button
              onClick={() => handleDownloadReport('pdf')}
              disabled={!siteId}
              className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded-xl font-medium transition-colors"
            >
              Download PDF Report
            </button>
            <button
              onClick={() => handleDownloadReport('xlsx')}
              disabled={!siteId}
              className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded-xl font-medium transition-colors"
            >
              Download Excel Report
            </button>
          </div>

          {/* Habitat classification + degradation */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Habitat Classification</h2>
            {detail && detail.assessments.length > 0 ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                  <InfoCard label="Officer-declared type" value={detail.declared_habitat_type || 'not recorded'} />
                  <InfoCard
                    label="Latest inferred signal"
                    value={detail.assessments[detail.assessments.length - 1].inferred_habitat_signal}
                  />
                  <InfoCard
                    label="Degradation"
                    value={detail.degradation_flag ? 'Significant decline' : 'No significant decline'}
                    tone={detail.degradation_flag ? 'warning' : 'good'}
                  />
                </div>
                <p className="text-sm text-slate-500 mb-4">{detail.note}</p>
                {detail.vegetation_trend && (
                  <div className="mb-6">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${DIRECTION_STYLES[detail.vegetation_trend.direction] ?? 'bg-slate-100 text-slate-600'}`}>
                      vegetation index: {detail.vegetation_trend.direction}
                    </span>
                    {detail.vegetation_trend.note && (
                      <span className="text-xs text-slate-400 ml-2">{detail.vegetation_trend.note}</span>
                    )}
                  </div>
                )}
                {chartData.length > 1 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={chartData} margin={{ left: 8, right: 24, top: 8, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                      <YAxis domain={[0, 1]} stroke="#94a3b8" fontSize={12} />
                      <Tooltip contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e2e8f0', fontSize: 13 }} />
                      <Line type="monotone" dataKey="vegetation_index" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-slate-500">
                    Only one assessment recorded — run another assessment later to see a trend.
                  </p>
                )}
              </>
            ) : (
              <p className="py-8 text-center text-slate-500">
                {detail?.note ||
                  (canAssess
                    ? 'No habitat assessment yet — click "Run Vegetation Assessment" above.'
                    : 'No habitat assessment yet for this site.')}
              </p>
            )}
          </div>

          {/* Environmental conditions */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Environmental Conditions</h2>
            <p className="text-sm text-slate-500 mb-6">{environment?.note}</p>
            {environment && environment.readings.length > 0 ? (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                  <InfoCard label="Mean temperature" value={fmt(environment.mean_temperature_c, '°C')} />
                  <InfoCard label="Mean humidity" value={fmt(environment.mean_humidity_pct, '%')} />
                  <InfoCard label="Mean precipitation" value={fmt(environment.mean_precipitation_mm, 'mm')} />
                  <InfoCard label="Mean wind speed" value={fmt(environment.mean_wind_speed_kmh, 'km/h')} />
                </div>
                <p className="text-xs text-slate-400">{environment.readings.length} daily reading(s) on file.</p>
              </>
            ) : (
              <p className="py-8 text-center text-slate-500">
                No environmental readings for this site yet.
              </p>
            )}
          </div>

          {/* Habitat suitability */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Habitat Suitability</h2>
            <p className="text-sm text-slate-500 mb-4">
              A transparent heuristic score, not a trained suitability model — see the note
              below for how it was computed.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-2">Species group</label>
              <select
                value={speciesGroup}
                onChange={(e) => setSpeciesGroup(e.target.value)}
                className="w-full sm:w-1/3 px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none capitalize"
              >
                {SPECIES_GROUPS.map((group) => (
                  <option key={group} value={group} className="capitalize">{group}</option>
                ))}
              </select>
            </div>
            {suitability && (
              <div className="flex items-center gap-6">
                <div className="text-4xl font-bold text-slate-800">
                  {suitability.score != null ? `${suitability.score}` : 'n/a'}
                  <span className="text-lg text-slate-400 font-normal"> / 100</span>
                </div>
                <p className="text-sm text-slate-500 max-w-xl">{suitability.note}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function fmt(value: number | null, unit: string): string {
  return value == null ? 'n/a' : `${value}${unit}`;
}

function InfoCard({
  label, value, tone = 'neutral',
}: { label: string; value: string; tone?: 'neutral' | 'good' | 'warning' }) {
  const toneStyle = tone === 'good'
    ? 'text-emerald-700'
    : tone === 'warning'
      ? 'text-amber-700'
      : 'text-slate-800';
  return (
    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
      <p className="text-xs font-medium text-slate-500 mb-1">{label}</p>
      <p className={`text-base font-semibold ${toneStyle} capitalize`}>{value}</p>
    </div>
  );
}
