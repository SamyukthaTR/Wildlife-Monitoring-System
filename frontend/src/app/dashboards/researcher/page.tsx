"use client";

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import AnalysisPanel from '@/components/AnalysisPanel';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';

// Types
type Site = { id: number, location_name: string, latitude: number, longitude: number };
type Survey = { id: number, site_id: number, survey_date: string, status: string };
type Observation = { id: number, survey_id: number, file_type: string, uploaded_at: string, processing_status: string };

const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-sky-100 text-sky-700',
  pending: 'bg-amber-100 text-amber-700',
  failed: 'bg-rose-100 text-rose-700',
};

export default function ResearcherDashboard() {
  const { user, logout } = useAuth();

  // Data State
  const [sites, setSites] = useState<Site[]>([]);
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [viewingAnalysis, setViewingAnalysis] = useState<number | null>(null);

  // Form States
  const [siteForm, setSiteForm] = useState({ location_name: '', latitude: '', longitude: '', habitat_type: '', protected_area: '', monitoring_device_type: '' });
  const [surveyForm, setSurveyForm] = useState({ site_id: '', survey_date: '', notes: '' });
  const [deviceForm, setDeviceForm] = useState({ site_id: '', device_type: 'camera_trap', serial: '' });
  const [uploadForm, setUploadForm] = useState({ survey_id: '', file: null as File | null });

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Fetch Initial Data
  const fetchData = async () => {
    try {
      const [sitesRes, surveysRes, obsRes] = await Promise.all([
        api.get('/monitoring/sites'),
        api.get('/monitoring/surveys'),
        api.get('/observations')
      ]);
      setSites(sitesRes.data);
      setSurveys(surveysRes.data);
      setObservations(obsRes.data);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Handlers
  const handleCreateSite = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/monitoring/sites', {
        ...siteForm,
        latitude: parseFloat(siteForm.latitude),
        longitude: parseFloat(siteForm.longitude)
      });
      setMessage('Site created successfully!');
      fetchData();
      setSiteForm({ location_name: '', latitude: '', longitude: '', habitat_type: '', protected_area: '', monitoring_device_type: '' });
    } catch (err) {
      setMessage('Error creating site');
    }
    setLoading(false);
  };

  const handleCreateSurvey = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/monitoring/surveys', {
        ...surveyForm,
        site_id: parseInt(surveyForm.site_id)
      });
      setMessage('Survey registered successfully!');
      fetchData();
      setSurveyForm({ site_id: '', survey_date: '', notes: '' });
    } catch (err) {
      setMessage('Error creating survey');
    }
    setLoading(false);
  };

  const handleRegisterDevice = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/monitoring/devices', {
        ...deviceForm,
        site_id: parseInt(deviceForm.site_id)
      });
      setMessage('Device registered successfully!');
      setDeviceForm({ site_id: '', device_type: 'camera_trap', serial: '' });
    } catch (err) {
      setMessage('Error registering device (Serial might be duplicate)');
    }
    setLoading(false);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadForm.file || !uploadForm.survey_id) {
      setMessage('Please select a survey and a file');
      return;
    }
    setLoading(true);
    const formData = new FormData();
    formData.append('survey_id', uploadForm.survey_id);
    formData.append('file', uploadForm.file);

    try {
      await api.post('/observations/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setMessage('File uploaded. Analysis has been queued and runs in the background.');
      fetchData();
      setUploadForm({ survey_id: '', file: null });
    } catch (err) {
      setMessage('Error uploading file (check format/size)');
    }
    setLoading(false);
  };

  const handleAnalyze = async (obsId: number) => {
    try {
      await api.post(`/analysis/observations/${obsId}/analyze`);
      setMessage(`Analysis queued for observation #${obsId}.`);
      fetchData();
    } catch {
      setMessage(`Could not queue analysis for observation #${obsId}.`);
    }
  };

  return (
    <ProtectedRoute allowedRoles={['Wildlife Researcher']}>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        {viewingAnalysis !== null && (
          <AnalysisPanel
            observationId={viewingAnalysis}
            onClose={() => { setViewingAnalysis(null); fetchData(); }}
          />
        )}
        <div className="max-w-7xl mx-auto space-y-8">
          
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Researcher Dashboard</h1>
              <p className="text-slate-500 mt-1">Welcome back, {user?.name}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a href="/biodiversity" className="px-5 py-2.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-xl font-medium transition-colors">
                Biodiversity Analytics
              </a>
              <a href="/population" className="px-5 py-2.5 bg-sky-50 text-sky-700 hover:bg-sky-100 rounded-xl font-medium transition-colors">
                Population Intelligence
              </a>
              <button onClick={logout} className="px-5 py-2.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl font-medium transition-colors">
                Sign Out
              </button>
            </div>
          </div>

          {message && (
            <div className="p-4 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100 font-medium">
              {message}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Create Site Form */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Create Monitoring Site</h2>
              <form onSubmit={handleCreateSite} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Location Name</label>
                  <input required type="text" value={siteForm.location_name} onChange={e => setSiteForm({...siteForm, location_name: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Latitude</label>
                    <input required type="number" step="any" value={siteForm.latitude} onChange={e => setSiteForm({...siteForm, latitude: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Longitude</label>
                    <input required type="number" step="any" value={siteForm.longitude} onChange={e => setSiteForm({...siteForm, longitude: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none" />
                  </div>
                </div>
                <button disabled={loading} type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition-colors">Create Site</button>
              </form>
            </div>

            {/* Create Survey Form */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Register Survey</h2>
              <form onSubmit={handleCreateSurvey} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Select Site</label>
                  <select required value={surveyForm.site_id} onChange={e => setSurveyForm({...surveyForm, site_id: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none">
                    <option value="">-- Select a Site --</option>
                    {sites.map(s => <option key={s.id} value={s.id}>{s.location_name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Date</label>
                  <input required type="date" value={surveyForm.survey_date} onChange={e => setSurveyForm({...surveyForm, survey_date: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                  <textarea value={surveyForm.notes} onChange={e => setSurveyForm({...surveyForm, notes: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none" />
                </div>
                <button disabled={loading} type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition-colors">Register Survey</button>
              </form>
            </div>

            {/* Register Device Form */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Register Device</h2>
              <form onSubmit={handleRegisterDevice} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Select Site</label>
                  <select required value={deviceForm.site_id} onChange={e => setDeviceForm({...deviceForm, site_id: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none">
                    <option value="">-- Select a Site --</option>
                    {sites.map(s => <option key={s.id} value={s.id}>{s.location_name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Device Type</label>
                  <select required value={deviceForm.device_type} onChange={e => setDeviceForm({...deviceForm, device_type: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none">
                    <option value="camera_trap">Camera Trap</option>
                    <option value="audio_sensor">Audio Sensor</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Serial Number</label>
                  <input required type="text" value={deviceForm.serial} onChange={e => setDeviceForm({...deviceForm, serial: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none" />
                </div>
                <button disabled={loading} type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition-colors">Register Device</button>
              </form>
            </div>

            {/* Upload File Form */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
              <h2 className="text-xl font-bold text-slate-800 mb-6">Upload Observation File</h2>
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Select Survey</label>
                  <select required value={uploadForm.survey_id} onChange={e => setUploadForm({...uploadForm, survey_id: e.target.value})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none">
                    <option value="">-- Select a Survey --</option>
                    {surveys.map(s => <option key={s.id} value={s.id}>Survey ID: {s.id} ({s.survey_date})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">File (Image/Audio, max 50MB)</label>
                  <input required type="file" accept="image/*,audio/*" onChange={e => setUploadForm({...uploadForm, file: e.target.files ? e.target.files[0] : null})} className="w-full px-4 py-2 text-slate-900 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100" />
                </div>
                <button disabled={loading} type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 rounded-lg transition-colors">Upload File</button>
              </form>
            </div>
          </div>

          {/* Observations Table */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
            <h2 className="text-xl font-bold text-slate-800 mb-6">My Observations</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                    <th className="py-3 px-4 font-medium">ID</th>
                    <th className="py-3 px-4 font-medium">Survey ID</th>
                    <th className="py-3 px-4 font-medium">Type</th>
                    <th className="py-3 px-4 font-medium">Date</th>
                    <th className="py-3 px-4 font-medium">Status</th>
                    <th className="py-3 px-4 font-medium">Analysis</th>
                  </tr>
                </thead>
                <tbody>
                  {observations.map(obs => (
                    <tr key={obs.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="py-3 px-4 text-slate-800">#{obs.id}</td>
                      <td className="py-3 px-4 text-slate-600">{obs.survey_id}</td>
                      <td className="py-3 px-4 text-slate-600 capitalize">{obs.file_type}</td>
                      <td className="py-3 px-4 text-slate-600">{new Date(obs.uploaded_at).toLocaleDateString()}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${STATUS_STYLES[obs.processing_status] ?? 'bg-slate-100 text-slate-600'}`}>
                          {obs.processing_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <button onClick={() => setViewingAnalysis(obs.id)} className="text-indigo-600 hover:text-indigo-800 font-medium text-sm px-3 py-1 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors">
                          View Results
                        </button>
                        <button onClick={() => handleAnalyze(obs.id)} className="ml-2 text-slate-600 hover:text-slate-800 font-medium text-sm px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors">
                          {obs.processing_status === 'completed' ? 'Re-analyze' : 'Analyze'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {observations.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-500">No observations logged yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </ProtectedRoute>
  );
}
