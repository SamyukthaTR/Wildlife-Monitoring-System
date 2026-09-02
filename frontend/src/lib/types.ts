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

// Shared shapes for the Milestone 3 population, habitat, conservation and
// ecosystem-health APIs. Every derived numeric field is `number | null` —
// null means "undefined here", never a fabricated 0.

export type TrendResult = {
  n_points: number;
  slope: number | null;
  r_value: number | null;
  p_value: number | null;
  significant: boolean;
  direction: 'increasing' | 'decreasing' | 'stable' | 'insufficient evidence';
  percent_change_per_period: number | null;
  note: string | null;
};

export type PopulationVariability = {
  n_surveys: number;
  median: number | null;
  low: number | null;
  high: number | null;
  note: string;
};

export type PopulationEstimateRow = {
  species_id: number;
  scientific_name: string;
  common_name: string | null;
  species_group: string;
  /** A lower bound on population size, not an estimate of it. */
  peak_simultaneous_count: number | null;
  frames_examined: number;
  note: string;
  variability: PopulationVariability;
};

export type PopulationEstimates = {
  site_id: number | null;
  species: PopulationEstimateRow[];
  method: string;
};

export type PopulationTrendRow = {
  species_id: number;
  scientific_name: string;
  common_name: string | null;
  species_group: string;
  data_points: { survey_date: string; count: number }[];
  trend: TrendResult;
};

export type PopulationTrends = {
  site_id: number | null;
  species: PopulationTrendRow[];
  method: string;
};

export type PopulationDensityRow = {
  species_id: number;
  scientific_name: string;
  common_name: string | null;
  species_group: string;
  detections: number;
  encounter_rate_per_100_observations: number | null;
};

export type PopulationDensity = {
  site_id: number | null;
  observation_effort: number;
  species: PopulationDensityRow[];
  is_true_density: false;
  note: string;
};

export type DistributionRecord = {
  species_id: number;
  scientific_name: string;
  common_name: string | null;
  site_id: number;
  location_name: string;
  year: number;
  month: number;
  detections: number;
};

export type PopulationDistribution = {
  site_id: number | null;
  records: DistributionRecord[];
  note: string;
};

export type HabitatAssessmentRecord = {
  id: number;
  site_id: number;
  assessed_at: string;
  images_sampled: number;
  vegetation_index: number;
  green_pixel_fraction: number;
  canopy_texture_index: number;
  declared_habitat_type: string | null;
  inferred_habitat_signal: string;
};

export type HabitatSiteSummary = HabitatAssessmentRecord & {
  location_name: string;
  assessments: number;
  vegetation_trend: TrendResult;
  degradation_flag: boolean;
};

export type HabitatDetail = {
  site_id: number;
  location_name: string;
  declared_habitat_type: string | null;
  assessments: HabitatAssessmentRecord[];
  vegetation_trend?: TrendResult;
  degradation_flag?: boolean;
  note: string;
};

export type EnvironmentalReadingRow = {
  recorded_date: string;
  temperature_c: number | null;
  humidity_pct: number | null;
  precipitation_mm: number | null;
  wind_speed_kmh: number | null;
};

export type HabitatEnvironment = {
  site_id: number;
  location_name: string;
  readings: EnvironmentalReadingRow[];
  readings_count?: number;
  mean_temperature_c: number | null;
  mean_humidity_pct: number | null;
  mean_precipitation_mm: number | null;
  mean_wind_speed_kmh: number | null;
  note: string;
};

export type HabitatSuitability = {
  site_id: number;
  location_name: string;
  species_group: string;
  score: number | null;
  computed_from: string[];
  note: string;
};

export type ConservationRecommendation = {
  category: 'conservation_priority' | 'habitat_restoration' | 'wildlife_protection' | 'monitoring_allocation';
  priority: 'high' | 'medium' | 'low';
  title: string;
  rationale: string;
};

export type SiteRecommendations = {
  site_id: number;
  location_name: string;
  recommendations: ConservationRecommendation[];
};

export type ConservationRecommendationsResponse = {
  sites: SiteRecommendations[];
  note: string;
};

export type EcosystemHealth = {
  site_id: number | null;
  biodiversity_score: number | null;
  habitat_quality_score: number | null;
  population_stability_score: number | null;
  overall_ecosystem_health_score: number | null;
  band: string | null;
  computed_from: string[];
  note: string;
  inputs: {
    species_richness: number;
    shannon_index: number | null;
    pielou_evenness: number | null;
    species_with_trend_data: number;
  };
};

export type EcosystemHealthSiteRow = EcosystemHealth & { location_name: string };

export type SitePriorityRow = {
  site_id: number;
  location_name: string;
  overall_health: number | null;
  high_priority_flags: number;
  total_recommendations: number;
};

// Shared shapes for the Administrator endpoints (user management + platform overview).

export type AppRole = 'Wildlife Researcher' | 'Conservation Officer' | 'Forest Department Officer' | 'Administrator';

export type AdminUser = {
  id: number;
  name: string;
  email: string;
  role: AppRole;
  organization: string | null;
  created_at: string;
};

export type PlatformOverview = {
  users: { total: number; by_role: Record<string, number> };
  monitoring: {
    sites: number;
    surveys: number;
    devices: number;
    devices_by_status: Record<string, number>;
  };
  observations: { total: number; by_status: Record<string, number> };
  analysis: {
    runs_completed: number;
    runs_failed: number;
    runs_running: number;
    ml_enabled: boolean;
  };
  species: {
    distinct_species_detected: number;
    endangered_species_detected: number;
  };
};
