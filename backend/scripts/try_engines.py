"""Run the image and audio engines over the sample corpus without a database.

A quick way to see what the models actually produce on real files, and to check
the engines work before wiring them to the API. Prints the honest output,
including the empty frames and the low-confidence rejections.

    python -m scripts.try_engines            # everything in the manifest
    python -m scripts.try_engines --limit 5
    python -m scripts.try_engines --images-only
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(SCRIPT_DIR, "sample_data")
MANIFEST_PATH = os.path.join(SAMPLE_DIR, "manifest.json")


def main() -> int:
    from app.ml.audio import analyse_audio
    from app.ml.image import analyse_image

    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    images_only = "--images-only" in sys.argv
    audio_only = "--audio-only" in sys.argv

    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        records = json.load(fh).get("records", [])

    if images_only:
        records = [r for r in records if r.get("media_kind") == "image"]
    if audio_only:
        records = [r for r in records if r.get("media_kind") == "audio"]
    if limit:
        records = records[:limit]

    print(f"Running engines over {len(records)} file(s)\n" + "=" * 78)

    for record in records:
        path = os.path.join(SAMPLE_DIR, record["file"])
        if not os.path.exists(path):
            continue

        truth = (record.get("ground_truth") or {}).get("scientific_name") or "(unlabelled)"
        common = (record.get("ground_truth") or {}).get("common_name") or ""
        print(f"\n{record['file']}")
        print(f"  expected: {truth} {f'({common})' if common else ''}")

        try:
            if record.get("media_kind") == "image":
                _print_image(analyse_image(path))
            else:
                _print_audio(analyse_audio(path))
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {type(exc).__name__}: {exc}")

    return 0


def _print_image(result: dict) -> None:
    quality = result["quality"]
    print(f"  {result['width']}x{result['height']}  "
          f"quality={quality['score']:.2f} ({quality['notes']})")
    print(f"  animals detected: {result['animal_count']}   "
          f"latency: {result['latency_ms']} ms")
    if not result["detections"]:
        print("  -> no animal identified")
    for detection in result["detections"]:
        marker = "?" if detection["is_unknown"] else "+"
        bbox = detection.get("bbox")
        location = (f"box=({bbox['x']},{bbox['y']},{bbox['w']}x{bbox['h']})"
                    if bbox else "whole frame")
        print(f"  {marker} [{detection['detection_index']}] {detection['label_raw']}"
              f"  conf={detection['confidence']:.3f}"
              f"  via {detection['label_source']}  {location}")
        if detection.get("posture_hint"):
            print(f"      posture hint: {detection['posture_hint']}")
        if detection["is_unknown"]:
            if detection.get("detector_label"):
                print(f"      localised as COCO '{detection['detector_label']}' "
                      "(shape match, not an ID)")
            if detection.get("candidate_label"):
                print(f"      closest match: {detection['candidate_label']} "
                      f"({detection['candidate_confidence']:.3f}) - "
                      f"{detection.get('rejection_reason', 'not asserted')}")


def _print_audio(result: dict) -> None:
    profile = result["noise_profile"]
    print(f"  {result['duration_s']}s  events={result['acoustic_events']}  "
          f"latency={result['latency_ms']} ms")
    print(f"  noise floor {profile['noise_floor_db']} dB, "
          f"spectral flatness {profile['spectral_flatness']}")
    print(f"  biological labels: {result['biological_detections']}, "
          f"filtered as noise: {result['filtered_noise_labels']}")
    for classification in result["classifications"]:
        marker = "." if classification["is_noise"] else "+"
        print(f"  {marker} [{classification['start_time_s']:.1f}-"
              f"{classification['end_time_s']:.1f}s] {classification['label_raw']}"
              f"  conf={classification['confidence']:.3f}")


if __name__ == "__main__":
    sys.exit(main())
