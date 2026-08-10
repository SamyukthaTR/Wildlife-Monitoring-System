"use client";

import { useState } from 'react';
import type { ImageDetection } from '@/lib/types';

type Props = {
  imageUrl: string;
  detections: ImageDetection[];
  imageWidth?: number;
  imageHeight?: number;
};

/**
 * Draws detection boxes over an image.
 *
 * Boxes arrive in original-image pixel coordinates while the <img> is scaled to
 * fit its container, so each box is positioned as a percentage of the image's
 * natural size. Percentages scale with the rendered element for free — no
 * canvas, no resize listener, and correct at any container width.
 */
export default function DetectionOverlay({
  imageUrl,
  detections,
  imageWidth,
  imageHeight,
}: Props) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(
    imageWidth && imageHeight ? { w: imageWidth, h: imageHeight } : null
  );
  const [active, setActive] = useState<number | null>(null);

  const boxed = detections.filter((d) => d.bbox !== null);

  return (
    <div className="relative inline-block max-w-full">
      <img
        src={imageUrl}
        alt="Observation"
        className="max-w-full h-auto rounded-xl block"
        onLoad={(e) =>
          setNatural({
            w: e.currentTarget.naturalWidth,
            h: e.currentTarget.naturalHeight,
          })
        }
      />

      {natural &&
        boxed.map((detection) => {
          const box = detection.bbox!;
          const style = {
            left: `${(box.x / natural.w) * 100}%`,
            top: `${(box.y / natural.h) * 100}%`,
            width: `${(box.w / natural.w) * 100}%`,
            height: `${(box.h / natural.h) * 100}%`,
          };
          // Named identifications are emerald; unnamed animals are amber, so a
          // guess is never visually indistinguishable from a confirmed ID.
          const colour = detection.is_unknown
            ? 'border-amber-400'
            : 'border-emerald-400';
          const badge = detection.is_unknown
            ? 'bg-amber-400 text-amber-950'
            : 'bg-emerald-400 text-emerald-950';
          const isActive = active === detection.id;

          return (
            <div
              key={detection.id}
              className={`absolute border-2 ${colour} rounded transition-all ${
                isActive ? 'ring-2 ring-white/70' : ''
              }`}
              style={style}
              onMouseEnter={() => setActive(detection.id)}
              onMouseLeave={() => setActive(null)}
            >
              <span
                className={`absolute -top-6 left-0 whitespace-nowrap px-2 py-0.5 rounded text-xs font-semibold ${badge}`}
              >
                {detection.is_unknown
                  ? `#${detection.detection_index + 1} unidentified`
                  : `#${detection.detection_index + 1} ${detection.label_raw}`}
                {' '}
                {(detection.confidence * 100).toFixed(0)}%
              </span>
            </div>
          );
        })}

      {boxed.length === 0 && (
        <div className="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none">
          <span className="px-3 py-1.5 rounded-lg bg-slate-900/75 text-white text-sm font-medium">
            No animals localised in this frame
          </span>
        </div>
      )}
    </div>
  );
}
