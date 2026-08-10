"use client";

import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import DetectionOverlay from '@/components/DetectionOverlay';
import type { ObservationAnalysis } from '@/lib/types';

type Props = {
  observationId: number;
  onClose: () => void;
};

const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-sky-100 text-sky-700',
  pending: 'bg-amber-100 text-amber-700',
  failed: 'bg-rose-100 text-rose-700',
};

export default function AnalysisPanel({ observationId, onClose }: Props) {
  const [analysis, setAnalysis] = useState<ObservationAnalysis | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/analysis/observations/${observationId}`);
      const data: ObservationAnalysis = res.data;
      setAnalysis(data);

      if (data.file_type === 'image' && !imageUrl) {
        const fileRes = await api.get(`/observations/${observationId}/file`, {
          responseType: 'blob',
        });
        setImageUrl(window.URL.createObjectURL(new Blob([fileRes.data])));
      }
    } catch {
      setError('Could not load analysis for this observation.');
    } finally {
      setLoading(false);
    }
  }, [observationId, imageUrl]);

  useEffect(() => {
    load();
  }, [load]);

  // Analysis runs in the background after upload, so poll while it is in flight.
  useEffect(() => {
    if (!analysis) return;
    const status = analysis.processing_status;
    if (status !== 'pending' && status !== 'processing') return;
    const timer = setTimeout(load, 3000);
    return () => clearTimeout(timer);
  }, [analysis, load]);

  // Revoke the blob URL when the panel closes.
  useEffect(() => {
    return () => {
      if (imageUrl) window.URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  const run = analysis?.run;
  const biological = analysis?.audio_classifications.filter((c) => !c.is_noise) ?? [];
  const noise = analysis?.audio_classifications.filter((c) => c.is_noise) ?? [];

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl my-4">
        <div className="flex justify-between items-center p-6 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-bold text-slate-800">
              Analysis — Observation #{observationId}
            </h2>
            {analysis && (
              <div className="flex items-center gap-3 mt-2 text-sm">
                <span
                  className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                    STATUS_STYLES[analysis.processing_status] ?? 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {analysis.processing_status}
                </span>
                <span className="text-slate-500 capitalize">{analysis.file_type}</span>
                {run?.models_used && (
                  <span className="text-slate-400 font-mono text-xs">{run.models_used}</span>
                )}
                {run?.latency_ms != null && (
                  <span className="text-slate-400">{(run.latency_ms / 1000).toFixed(1)}s</span>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>

        <div className="p-6 space-y-6">
          {loading && <p className="text-slate-500">Loading analysis…</p>}
          {error && (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100">
              {error}
            </div>
          )}

          {run?.status === 'failed' && (
            <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100">
              <p className="font-semibold">Analysis failed</p>
              <p className="text-sm mt-1 font-mono break-all">{run.error}</p>
            </div>
          )}

          {analysis &&
            (analysis.processing_status === 'pending' ||
              analysis.processing_status === 'processing') && (
              <div className="p-4 bg-sky-50 text-sky-700 rounded-xl border border-sky-100">
                Inference is running on CPU — this takes a few seconds. Refreshing
                automatically.
              </div>
            )}

          {/* ---------------- Image results ---------------- */}
          {analysis?.file_type === 'image' && (
            <>
              {run && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <Stat label="Animals localised" value={run.animal_count ?? '—'} />
                  <Stat
                    label="Image quality"
                    value={run.quality_score != null ? run.quality_score.toFixed(2) : '—'}
                  />
                  <Stat label="Identified" value={
                    analysis.image_detections.filter((d) => !d.is_unknown).length
                  } />
                </div>
              )}

              {run?.quality_notes && (
                <p className="text-sm text-slate-500">
                  Quality assessment: {run.quality_notes}
                </p>
              )}

              {imageUrl && (
                <DetectionOverlay
                  imageUrl={imageUrl}
                  detections={analysis.image_detections}
                />
              )}

              {analysis.image_detections.length === 0 &&
                analysis.processing_status === 'completed' && (
                  <div className="p-4 bg-slate-50 text-slate-600 rounded-xl border border-slate-200">
                    <p className="font-medium text-slate-700">No animals detected</p>
                    <p className="text-sm mt-1">
                      An empty frame is a normal and useful camera-trap result — most
                      camera-trap captures contain no animal.
                    </p>
                  </div>
                )}

              {analysis.image_detections.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-y border-slate-200 text-slate-600 text-sm">
                        <th className="py-3 px-4 font-medium">#</th>
                        <th className="py-3 px-4 font-medium">Identification</th>
                        <th className="py-3 px-4 font-medium">Confidence</th>
                        <th className="py-3 px-4 font-medium">Taxonomy</th>
                        <th className="py-3 px-4 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.image_detections.map((detection) => (
                        <tr
                          key={detection.id}
                          className="border-b border-slate-100 hover:bg-slate-50/50 align-top"
                        >
                          <td className="py-3 px-4 text-slate-800">
                            {detection.detection_index + 1}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={
                                detection.is_unknown
                                  ? 'text-amber-700 font-medium'
                                  : 'text-slate-800 font-medium'
                              }
                            >
                              {detection.label_raw}
                            </span>
                            {detection.is_unknown && detection.candidate_label && (
                              <p className="text-xs text-slate-500 mt-1">
                                closest match: {detection.candidate_label} (
                                {((detection.candidate_confidence ?? 0) * 100).toFixed(0)}%),
                                below the threshold to assert
                              </p>
                            )}
                            {detection.is_unknown && detection.detector_label && (
                              <p className="text-xs text-slate-400 mt-0.5">
                                localised as COCO &ldquo;{detection.detector_label}&rdquo; — a
                                shape match, not an identification
                              </p>
                            )}
                            {detection.posture_hint && (
                              <p className="text-xs text-slate-400 mt-0.5">
                                posture (geometric heuristic): {detection.posture_hint}
                              </p>
                            )}
                          </td>
                          <td className="py-3 px-4 text-slate-600">
                            {(detection.confidence * 100).toFixed(1)}%
                          </td>
                          <td className="py-3 px-4 text-slate-600 text-sm">
                            {detection.species ? (
                              <>
                                <span className="italic">
                                  {detection.species.scientific_name}
                                </span>
                                <span className="block text-xs text-slate-400">
                                  {detection.species.rank} · {detection.species.species_group}
                                </span>
                              </>
                            ) : (
                              <span className="text-slate-400">no catalog match</span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {detection.species?.iucn_status ? (
                              <span
                                className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                                  detection.species.is_endangered
                                    ? 'bg-rose-100 text-rose-700'
                                    : 'bg-slate-100 text-slate-600'
                                }`}
                              >
                                IUCN {detection.species.iucn_status}
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400">not published</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* ---------------- Audio results ---------------- */}
          {analysis?.file_type === 'audio' && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <Stat label="Biological labels" value={biological.length} />
                <Stat label="Filtered as noise" value={noise.length} />
                <Stat
                  label="Windows analysed"
                  value={
                    new Set(
                      analysis.audio_classifications.map(
                        (c) => `${c.start_time_s}-${c.end_time_s}`
                      )
                    ).size
                  }
                />
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-sm text-slate-600">
                These labels come from the AudioSet ontology, which names a{' '}
                <strong>sound type</strong> — bird, frog, insect — never a species.
                They are recorded at coarse rank and excluded from species diversity
                indices.
              </div>

              {biological.length > 0 ? (
                <div className="space-y-2">
                  {biological.map((classification) => (
                    <div
                      key={classification.id}
                      className="flex items-center gap-4 p-3 rounded-xl border border-slate-100 hover:bg-slate-50/50"
                    >
                      <span className="font-mono text-xs text-slate-500 w-24 shrink-0">
                        {classification.start_time_s.toFixed(1)}–
                        {classification.end_time_s.toFixed(1)}s
                      </span>
                      <span className="font-medium text-slate-800 flex-1">
                        {classification.label_raw}
                      </span>
                      <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden shrink-0">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${classification.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-sm text-slate-600 w-12 text-right shrink-0">
                        {(classification.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                analysis.processing_status === 'completed' && (
                  <div className="p-4 bg-slate-50 text-slate-600 rounded-xl border border-slate-200">
                    <p className="font-medium text-slate-700">
                      No biological sounds identified
                    </p>
                    <p className="text-sm mt-1">
                      Acoustic events were found but nothing scored above the
                      confidence threshold, or the audio contained only background
                      noise.
                    </p>
                  </div>
                )
              )}

              {noise.length > 0 && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-slate-500 hover:text-slate-700 font-medium">
                    {noise.length} label(s) filtered as environmental noise
                  </summary>
                  <div className="mt-3 space-y-1.5">
                    {noise.map((classification) => (
                      <div
                        key={classification.id}
                        className="flex items-center gap-4 px-3 py-2 text-slate-400"
                      >
                        <span className="font-mono text-xs w-24 shrink-0">
                          {classification.start_time_s.toFixed(1)}–
                          {classification.end_time_s.toFixed(1)}s
                        </span>
                        <span className="flex-1">{classification.label_raw}</span>
                        <span className="w-12 text-right">
                          {(classification.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}

          {analysis && (
            <details className="text-sm">
              <summary className="cursor-pointer text-slate-500 hover:text-slate-700 font-medium">
                How to read these results
              </summary>
              <ul className="mt-3 space-y-2 text-slate-600 list-disc list-inside">
                {Object.entries(analysis.interpretation).map(([key, text]) => (
                  <li key={key}>{text}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      <p className="text-sm text-slate-500 mt-0.5">{label}</p>
    </div>
  );
}
