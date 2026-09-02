"use client";

import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

export type MapSite = {
  site_id: number;
  location_name: string;
  habitat_type: string | null;
  latitude: number | null;
  longitude: number | null;
  health_score: number | null;
  health_band: string | null;
  degradation_flag: boolean;
  high_priority_flags: number;
};

const BAND_COLORS: Record<string, string> = {
  Good: '#059669',
  Fair: '#d97706',
  Poor: '#ea580c',
  Critical: '#dc2626',
};
const UNSCORED_COLOR = '#64748b';

export default function SiteMap({ sites, height = 500 }: { sites: MapSite[]; height?: number }) {
  const located = sites.filter(
    (s): s is MapSite & { latitude: number; longitude: number } =>
      s.latitude != null && s.longitude != null
  );
  const center: [number, number] = located.length
    ? [
        located.reduce((sum, s) => sum + s.latitude, 0) / located.length,
        located.reduce((sum, s) => sum + s.longitude, 0) / located.length,
      ]
    : [20, 0];

  return (
    <MapContainer
      center={center}
      zoom={located.length ? 6 : 2}
      style={{ height, width: '100%', borderRadius: '1rem' }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {located.map((site) => {
        const color = site.health_band ? BAND_COLORS[site.health_band] ?? UNSCORED_COLOR : UNSCORED_COLOR;
        return (
          <CircleMarker
            key={site.site_id}
            center={[site.latitude, site.longitude]}
            radius={10}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.7, weight: 2 }}
          >
            <Popup>
              <div className="text-sm space-y-1">
                <p className="font-semibold text-slate-900">{site.location_name}</p>
                <p className="text-slate-600">{site.habitat_type ?? 'Habitat type not recorded'}</p>
                <p className="text-slate-600">
                  Health: {site.health_score ?? 'n/a'}{site.health_band ? ` (${site.health_band})` : ''}
                </p>
                {site.degradation_flag && <p className="text-amber-700">Vegetation significantly declining</p>}
                {site.high_priority_flags > 0 && (
                  <p className="text-rose-700">{site.high_priority_flags} high-priority conservation flag(s)</p>
                )}
                <div className="pt-1 flex gap-2 text-emerald-700 underline">
                  <a href="/habitat">Habitat</a>
                  <a href="/conservation">Conservation</a>
                  <a href="/population">Population</a>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
