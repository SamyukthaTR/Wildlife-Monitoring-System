"use client";

import { useState, useEffect } from 'react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import ProtectedRoute from '@/components/ProtectedRoute';
import AnalysisPanel from '@/components/AnalysisPanel';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import type { SpeciesDetectionSummary } from '@/lib/types';

// Types
type Site = { id: number, location_name: string, latitude: number, longitude: number, habitat_type: string, protected_area: string };
type Survey = { id: number, site_id: number, survey_date: string, status: string };
type Device = { id: number, site_id: number, device_type: string, serial: string };
type Observation = { id: number, survey_id: number, file_type: string, uploaded_at: string, processing_status: string };

const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-sky-100 text-sky-700',
  pending: 'bg-amber-100 text-amber-700',
  failed: 'bg-rose-100 text-rose-700',
};

// IUCN Red List categories, most severe first. EX/EW sit outside the formal
// "threatened" bracket (CR/EN/VU) but obviously belong on a conservation view.
const IUCN_SEVERITY: Record<string, { label: string, style: string }> = {
  EX: { label: 'Extinct', style: 'bg-slate-800 text-white' },
  EW: { label: 'Extinct in the Wild', style: 'bg-slate-600 text-white' },
  CR: { label: 'Critically Endangered', style: 'bg-rose-600 text-white' },
  EN: { label: 'Endangered', style: 'bg-rose-100 text-rose-700' },
  VU: { label: 'Vulnerable', style: 'bg-amber-100 text-amber-800' },
  NT: { label: 'Near Threatened', style: 'bg-yellow-100 text-yellow-800' },
  LC: { label: 'Least Concern', style: 'bg-emerald-100 text-emerald-700' },
};
const SEVERITY_ORDER = ['EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC'];

export default function ConservationOfficerDashboard() {
  const { user, logout } = useAuth();

  // Data State
  const [sites, setSites] = useState<Site[]>([]);
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [speciesSummary, setSpeciesSummary] = useState<SpeciesDetectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewingFileUrl, setViewingFileUrl] = useState<string | null>(null);
  const [viewingAnalysis, setViewingAnalysis] = useState<number | null>(null);

  const fetchData = async () => {
    try {
      const [sitesRes, surveysRes, devicesRes, obsRes, speciesRes] = await Promise.all([
        api.get('/monitoring/sites'),
        api.get('/monitoring/surveys'),
        api.get('/monitoring/devices'),
        api.get('/observations'),
        api.get('/species/detections/summary')
      ]);
      setSites(sitesRes.data);
      setSurveys(surveysRes.data);
      setDevices(devicesRes.data);
      setObservations(obsRes.data);
      setSpeciesSummary(speciesRes.data);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleViewFile = async (obsId: number, fileType: string) => {
    try {
      const response = await api.get(`/observations/${obsId}/file`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      
      // If it's an image, we can show it in a simple modal overlay
      if (fileType === 'image') {
        setViewingFileUrl(url);
      } else {
        // For audio, just trigger a download for simplicity
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `observation_${obsId}.mp3`);
        document.body.appendChild(link);
        link.click();
        link.parentNode?.removeChild(link);
      }
    } catch (err) {
      console.error("Failed to download file", err);
      alert("Failed to access file. You may not have permission.");
    }
  };

  // Helper to find device info for an observation
  const getDeviceInfo = (surveyId: number) => {
    const survey = surveys.find(s => s.id === surveyId);
    if (!survey) return { type: 'N/A', serial: 'N/A' };
    const device = devices.find(d => d.site_id === survey.site_id);
    if (!device) return { type: 'N/A', serial: 'N/A' };
    return { type: device.device_type, serial: device.serial };
  };

  // Detected species carrying a published IUCN category, most severe first.
  const conservationConcern = speciesSummary
    .filter(row => row.species.iucn_status && SEVERITY_ORDER.includes(row.species.iucn_status))
    .sort((a, b) =>
      SEVERITY_ORDER.indexOf(a.species.iucn_status!) -
      SEVERITY_ORDER.indexOf(b.species.iucn_status!)
    );

  const topSpecies = speciesSummary.slice(0, 12).map(row => ({
    name: row.species.common_name || row.species.scientific_name,
    detections: row.total_detections,
  }));

  return (
    <ProtectedRoute allowedRoles={['Conservation Officer']}>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">

        {viewingAnalysis !== null && (
          <AnalysisPanel
            observationId={viewingAnalysis}
            onClose={() => { setViewingAnalysis(null); fetchData(); }}
          />
        )}

        {/* Simple Modal for Images */}
        {viewingFileUrl && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="relative bg-white p-4 rounded-xl max-w-4xl max-h-screen">
              <button onClick={() => setViewingFileUrl(null)} className="absolute -top-4 -right-4 bg-rose-500 text-white rounded-full p-2 hover:bg-rose-600 font-bold">
                Close
              </button>
              <img src={viewingFileUrl} alt="Observation" className="max-w-full max-h-[80vh] rounded-lg" />
            </div>
          </div>
        )}

        <div className="max-w-7xl mx-auto space-y-8">
          
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Global Park Overview</h1>
              <p className="text-slate-500 mt-1">Conservation Officer: {user?.name}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a href="/biodiversity" className="px-5 py-2.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-xl font-medium transition-colors">
                Biodiversity Analytics
              </a>
              <a href="/population" className="px-5 py-2.5 bg-sky-50 text-sky-700 hover:bg-sky-100 rounded-xl font-medium transition-colors">
                Population Intelligence
              </a>
              <a href="/habitat" className="px-5 py-2.5 bg-teal-50 text-teal-700 hover:bg-teal-100 rounded-xl font-medium transition-colors">
                Habitat Intelligence
              </a>
              <a href="/conservation" className="px-5 py-2.5 bg-amber-50 text-amber-700 hover:bg-amber-100 rounded-xl font-medium transition-colors">
                Conservation Insights
              </a>
              <button onClick={logout} className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors">
                Sign Out
              </button>
            </div>
          </div>

          {/* Species of conservation concern */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Species of Conservation Concern</h2>
            <p className="text-sm text-slate-500 mb-6">
              Detected species whose source database publishes an IUCN Red List category.
              Species without a published status are not listed — a missing status is not
              evidence of low risk.
            </p>
            {conservationConcern.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                      <th className="py-3 px-4 font-medium">Species</th>
                      <th className="py-3 px-4 font-medium">Group</th>
                      <th className="py-3 px-4 font-medium">IUCN Status</th>
                      <th className="py-3 px-4 font-medium">Detections</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conservationConcern.map(row => {
                      const status = IUCN_SEVERITY[row.species.iucn_status!];
                      return (
                        <tr key={row.species.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                          <td className="py-3 px-4">
                            <span className="text-slate-900 font-medium">{row.species.common_name || row.species.scientific_name}</span>
                            <span className="block text-xs text-slate-400 italic">{row.species.scientific_name}</span>
                          </td>
                          <td className="py-3 px-4 text-slate-600 text-sm capitalize">{row.species.species_group}</td>
                          <td className="py-3 px-4">
                            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${status.style}`}>
                              {row.species.iucn_status} · {status.label}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-600">{row.total_detections}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-slate-500">
                No detected species carries a published IUCN status yet. Run analysis on
                observations to populate this table.
              </p>
            )}
          </div>

          {/* Most-detected species */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Most-Detected Species</h2>
            <p className="text-sm text-slate-500 mb-6">
              Detection counts index relative activity, not population size. The same animal
              photographed twice counts twice.
            </p>
            {topSpecies.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(220, topSpecies.length * 32)}>
                <BarChart data={topSpecies} layout="vertical" margin={{ left: 12, right: 24, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} stroke="#94a3b8" fontSize={12} />
                  <YAxis type="category" dataKey="name" width={180} stroke="#94a3b8" fontSize={12} />
                  <Tooltip contentStyle={{ borderRadius: '0.75rem', border: '1px solid #e2e8f0', fontSize: 13 }} />
                  <Bar dataKey="detections" fill="#059669" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-8 text-center text-slate-500">No species detected yet.</p>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Sites Overview */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Active Monitoring Sites</h2>
              {loading ? (
                <div className="text-slate-500">Loading sites...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                        <th className="py-3 px-4 font-medium">Location</th>
                        <th className="py-3 px-4 font-medium">Coordinates</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sites.map(site => (
                        <tr key={site.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                          <td className="py-3 px-4 text-slate-900 font-medium">{site.location_name}</td>
                          <td className="py-3 px-4 text-slate-600 text-sm">{site.latitude.toString()}, {site.longitude.toString()}</td>
                        </tr>
                      ))}
                      {sites.length === 0 && (
                        <tr>
                          <td colSpan={2} className="py-8 text-center text-slate-500">No monitoring sites created yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Observations Summary */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Recent Observations Pipeline</h2>
              {loading ? (
                <div className="text-slate-500">Loading observations...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                        <th className="py-3 px-4 font-medium">Survey</th>
                        <th className="py-3 px-4 font-medium">File Type</th>
                        <th className="py-3 px-4 font-medium">Device (Serial)</th>
                        <th className="py-3 px-4 font-medium">Status</th>
                        <th className="py-3 px-4 font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {observations.map(obs => {
                        const deviceInfo = getDeviceInfo(obs.survey_id);
                        return (
                          <tr key={obs.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                            <td className="py-3 px-4 text-slate-600 text-sm">Survey #{obs.survey_id}</td>
                            <td className="py-3 px-4 text-slate-600 text-sm capitalize">{obs.file_type}</td>
                            <td className="py-3 px-4 text-slate-600 text-sm">
                              <span className="capitalize block">{deviceInfo.type.replace('_', ' ')}</span>
                              <span className="text-xs text-slate-400 font-mono">{deviceInfo.serial}</span>
                            </td>
                            <td className="py-3 px-4">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${STATUS_STYLES[obs.processing_status] ?? 'bg-slate-100 text-slate-600'}`}>
                                {obs.processing_status}
                              </span>
                            </td>
                            <td className="py-3 px-4 whitespace-nowrap">
                              <button onClick={() => setViewingAnalysis(obs.id)} className="text-indigo-600 hover:text-indigo-800 font-medium text-sm px-3 py-1 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors">
                                Analysis
                              </button>
                              <button onClick={() => handleViewFile(obs.id, obs.file_type)} className="ml-2 text-slate-600 hover:text-slate-800 font-medium text-sm px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors">
                                File
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                      {observations.length === 0 && (
                        <tr>
                          <td colSpan={5} className="py-8 text-center text-slate-500">No observations uploaded yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

          </div>

        </div>
      </div>
    </ProtectedRoute>
  );
}
