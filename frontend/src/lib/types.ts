// Shared shapes for the Milestone 2 analysis, species and biodiversity APIs.

export type SpeciesBrief = {
  id: number;
  scientific_name: string;
  common_name: string | null;
  rank: 'species' | 'genus' | 'family' | 'coarse';
  species_group: string;
  taxon_class: string | null;
  iucn_status: string | null;
  is_endangered: boolean;
};

export type BoundingBox = { x: number; y: number; w: number; h: number };

export type ImageDetection = {
  id: number;
  detection_index: number;
  /** "unidentified animal" when the platform declines to name what it found. */
  label_raw: string;
  label_source: string;
  confidence: number;
  /** COCO class that located the box — a shape match, not an identification. */
  detector_label: string | null;
  /** Classifier's best guess, kept even when too weak to assert. */
  candidate_label: string | null;
  candidate_confidence: number | null;
  /** Pixel coordinates in the ORIGINAL image, not the rendered one. */
  bbox: BoundingBox | null;
  posture_hint: string | null;
  is_unknown: boolean;
  species: SpeciesBrief | null;
};

export type AudioClassification = {
  id: number;
  label_raw: string;
  label_source: string;
  confidence: number;
  start_time_s: number;
  end_time_s: number;
  is_noise: boolean;
  species: SpeciesBrief | null;
};

export type AnalysisRun = {
  id: number;
  observation_id: number;
  status: 'running' | 'completed' | 'failed';
  models_used: string | null;
  latency_ms: number | null;
  animal_count: number | null;
  quality_score: number | null;
  quality_notes: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type ObservationAnalysis = {
  observation_id: number;
  file_type: 'image' | 'audio';
  processing_status: string;
  run: AnalysisRun | null;
  image_detections: ImageDetection[];
  audio_classifications: AudioClassification[];
  interpretation: Record<string, string>;
};

export type DiversityIndices = {
  species_richness: number;
  total_detections: number;
  shannon_index: number | null;
  simpson_index: number | null;
  gini_simpson_index: number | null;
  inverse_simpson_index: number | null;
  pielou_evenness: number | null;
  note: string | null;
  scope?: { type: string; id: number | null; name?: string };
  excluded_from_indices?: {
    coarse_rank_detections: number;
    unidentified_detections: number;
    acoustic_detections: number;
    reason: string;
  };
  observations?: { total: number; by_processing_status: Record<string, number> };
  method?: string;
};

export type CompositionRow = {
  species: string;
  count: number;
  relative_abundance: number;
};

export type SiteIndices = DiversityIndices & {
  site_id: number;
  location_name: string;
  habitat_type: string | null;
  latitude: number | null;
  longitude: number | null;
  observations: number;
};

export type AcousticActivity = {
  biological_events: number;
  filtered_noise_events: number;
  by_label: { label: string; count: number }[];
  note: string;
};

export type Species = SpeciesBrief & {
  taxon_order: string | null;
  taxon_family: string | null;
  gbif_taxon_key: number | null;
  gbif_match_type: string | null;
  inat_taxon_id: number | null;
  iucn_source: string | null;
  label_source: string | null;
};

export type SpeciesDetectionSummary = {
  species: Species;
  image_detections: number;
  acoustic_detections: number;
  total_detections: number;
};
