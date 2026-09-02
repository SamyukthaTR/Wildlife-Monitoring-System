"use client";

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import api, { downloadReport } from '@/lib/api';
import type { AdminUser, AppRole, PlatformOverview } from '@/lib/types';

type Site = { id: number; location_name: string };
type Device = { id: number; site_id: number; device_type: string; serial: string; status: string; last_active: string | null };

const ROLES: AppRole[] = ['Wildlife Researcher', 'Conservation Officer', 'Forest Department Officer', 'Administrator'];

const STAT_CARDS: { label: string; get: (o: PlatformOverview) => number | string }[] = [
  { label: 'Users', get: (o) => o.users.total },
  { label: 'Monitoring sites', get: (o) => o.monitoring.sites },
  { label: 'Surveys', get: (o) => o.monitoring.surveys },
  { label: 'Devices', get: (o) => o.monitoring.devices },
  { label: 'Observations', get: (o) => o.observations.total },
  { label: 'Analysis runs completed', get: (o) => o.analysis.runs_completed },
  { label: 'Species detected', get: (o) => o.species.distinct_species_detected },
  { label: 'Endangered species detected', get: (o) => o.species.endangered_species_detected },
];

export default function AdminDashboard() {
  const { user, logout } = useAuth();

  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const fetchAll = () => {
    setLoading(true);
    Promise.all([
      api.get('/admin/overview'),
      api.get('/users'),
      api.get('/monitoring/sites'),
      api.get('/monitoring/devices'),
    ])
      .then(([overviewRes, usersRes, sitesRes, devicesRes]) => {
        setOverview(overviewRes.data);
        setUsers(usersRes.data);
        setSites(sitesRes.data);
        setDevices(devicesRes.data);
      })
      .catch(() => setError('Could not load platform data.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const siteName = (siteId: number) => sites.find((s) => s.id === siteId)?.location_name ?? `Site #${siteId}`;

  const handleRoleChange = async (userId: number, role: AppRole) => {
    try {
      await api.patch(`/users/${userId}/role`, { role });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
      setMessage('Role updated.');
    } catch {
      setMessage('Could not update role.');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('Remove this user? This cannot be undone.')) return;
    try {
      await api.delete(`/users/${userId}`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setMessage('User removed.');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMessage(detail || 'Could not remove user.');
    }
  };

  const handleDownloadReport = async (format: 'csv' | 'pdf' | 'xlsx') => {
    try {
      await downloadReport('/reports/monitoring', { format }, `wildlife-report-all-sites.${format}`);
    } catch {
      setMessage('Could not generate report.');
    }
  };

  return (
    <ProtectedRoute allowedRoles={['Administrator']}>
      <div className="min-h-screen bg-slate-50 p-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div>
              <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Administrator Dashboard</h1>
              <p className="text-slate-500 mt-1">Welcome back, {user?.name}</p>
            </div>
            <div className="flex flex-wrap gap-3">
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

          {error && <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 font-medium">{error}</div>}
          {message && <div className="p-4 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100 font-medium">{message}</div>}

          {/* Platform analytics */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Platform Analytics</h2>
            {loading ? (
              <p className="text-slate-500">Loading…</p>
            ) : overview ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {STAT_CARDS.map((card) => (
                  <div key={card.label} className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <p className="text-2xl font-bold text-slate-800">{card.get(overview)}</p>
                    <p className="text-sm text-slate-500 mt-1">{card.label}</p>
                  </div>
                ))}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                  <p className={`text-2xl font-bold ${overview.analysis.ml_enabled ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {overview.analysis.ml_enabled ? 'Enabled' : 'Disabled'}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">ML analysis</p>
                </div>
              </div>
            ) : null}
          </div>

          {/* User management */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">User Management</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                    <th className="py-3 px-4 font-medium">Name</th>
                    <th className="py-3 px-4 font-medium">Email</th>
                    <th className="py-3 px-4 font-medium">Organization</th>
                    <th className="py-3 px-4 font-medium">Role</th>
                    <th className="py-3 px-4 font-medium">Joined</th>
                    <th className="py-3 px-4 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="py-3 px-4 text-slate-900 font-medium">{u.name}</td>
                      <td className="py-3 px-4 text-slate-600">{u.email}</td>
                      <td className="py-3 px-4 text-slate-600">{u.organization ?? '—'}</td>
                      <td className="py-3 px-4">
                        <select
                          value={u.role}
                          onChange={(e) => handleRoleChange(u.id, e.target.value as AppRole)}
                          disabled={u.id === user?.id}
                          className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm text-slate-800 disabled:opacity-50"
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </td>
                      <td className="py-3 px-4 text-slate-600">{new Date(u.created_at).toLocaleDateString()}</td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => handleDeleteUser(u.id)}
                          disabled={u.id === user?.id}
                          className="text-rose-600 hover:text-rose-800 font-medium text-sm px-3 py-1 bg-rose-50 hover:bg-rose-100 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!loading && users.length === 0 && (
                    <tr><td colSpan={6} className="py-8 text-center text-slate-500">No users found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Monitoring system management */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Monitoring System Management</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                    <th className="py-3 px-4 font-medium">Serial</th>
                    <th className="py-3 px-4 font-medium">Type</th>
                    <th className="py-3 px-4 font-medium">Site</th>
                    <th className="py-3 px-4 font-medium">Status</th>
                    <th className="py-3 px-4 font-medium">Last active</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((d) => (
                    <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="py-3 px-4 text-slate-900 font-medium">{d.serial}</td>
                      <td className="py-3 px-4 text-slate-600 capitalize">{d.device_type.replace('_', ' ')}</td>
                      <td className="py-3 px-4 text-slate-600">{siteName(d.site_id)}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${d.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                          {d.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-600">{d.last_active ? new Date(d.last_active).toLocaleString() : 'Never'}</td>
                    </tr>
                  ))}
                  {!loading && devices.length === 0 && (
                    <tr><td colSpan={5} className="py-8 text-center text-slate-500">No devices registered yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Report generation */}
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
            <h2 className="text-xl font-bold text-slate-800 mb-2">Report Generation</h2>
            <p className="text-sm text-slate-500 mb-6">
              Platform-wide wildlife monitoring report: species detected, biodiversity indices and analysis coverage across every site.
            </p>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => handleDownloadReport('csv')}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors"
              >
                Download CSV
              </button>
              <button
                onClick={() => handleDownloadReport('pdf')}
                className="px-5 py-2.5 bg-rose-600 hover:bg-rose-700 text-white font-medium rounded-xl transition-colors"
              >
                Download PDF
              </button>
              <button
                onClick={() => handleDownloadReport('xlsx')}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-xl transition-colors"
              >
                Download Excel
              </button>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
