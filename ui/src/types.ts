export type ImportStatus =
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type ComponentStatus = {
  id: string;
  name: string;
  role: string;
  status: "available" | "unavailable" | "configured";
  evidence: string;
};

export type OperationEvent = {
  id: string;
  import_job_id: string;
  correlation_id: string | null;
  component: string;
  stage: string;
  status: string;
  title: string;
  explanation: string;
  evidence_reference: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
};

export type ImportSummary = {
  id: string;
  supplier_code: string;
  source_type: string;
  status: ImportStatus;
  accepted_records: number;
  rejected_records: number;
  attempt_count: number;
  correlation_id: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ImportJob = {
  id: string;
  supplier_id: string;
  source_type: string;
  adapter_version: string;
  original_filename: string | null;
  content_sha256: string;
  payload_object_key: string | null;
  payload_size_bytes: number | null;
  idempotency_key: string | null;
  correlation_id: string | null;
  status: ImportStatus;
  total_records: number;
  accepted_records: number;
  rejected_records: number;
  attempt_count: number;
  max_attempts: number;
  dispatched_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  next_retry_at: string | null;
  lease_expires_at: string | null;
  worker_id: string | null;
  failure_code: string | null;
  failure_message: string | null;
  last_error_retryable: boolean | null;
  replay_of_job_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Snapshot = {
  id: string;
  source_reference: string;
  source_row: number;
  external_sku: string;
  canonical_sku: string;
  external_location: string;
  warehouse_code: string;
  source_unit: string;
  units_per_source_unit: string;
  source_on_hand: string;
  canonical_on_hand: string;
  source_reserved: string;
  canonical_reserved: string;
  product_mapping_version: number;
  warehouse_mapping_version: number;
  observed_at: string;
};

export type ImportAttempt = {
  id: string;
  attempt_number: number;
  status: string;
  celery_task_id: string | null;
  worker_id: string;
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
};

export type ImportError = {
  id: string;
  source_row: number | null;
  error_code: string;
  field_name: string | null;
  message: string;
};

export type ImportDetail = {
  job: ImportJob;
  supplier_code: string;
  events: OperationEvent[];
  attempts: ImportAttempt[];
  errors: ImportError[];
  snapshots: Snapshot[];
};

export type Overview = {
  components: ComponentStatus[];
  import_status_counts: Record<string, number>;
  entity_counts: Record<string, number>;
  recent_imports: ImportSummary[];
  recent_events: OperationEvent[];
};

export type DemoResponse = {
  job: ImportJob;
  created: boolean;
  demo_input: Record<string, unknown>;
};

export type PipelineRun = {
  manifest_key: string;
  status: string;
  partition_date: string | null;
  run_id: string | null;
  created_at: string | null;
  input_rows: number | null;
  curated_object_count: number;
  summary_object_count: number;
  spark_version: string | null;
  manifest: Record<string, unknown>;
};

export type AnalyticsRun = {
  id: string;
  run_type: string;
  engine: string;
  dataset_seed: number;
  input_rows: number;
  duration_ms: string;
  summary: Record<string, unknown>;
  created_at: string;
  completed_at: string;
};

export type AnalyticsEngineComparison = {
  durations_ms: number[];
  minimum_ms: number;
  median_ms: number;
  maximum_ms: number;
  p95_ms: number;
  dataframe_bytes: number;
};

export type AnalyticsComparison = {
  workload: {
    row_count: number;
    seed: number;
    repeats: number;
    measurement: string;
  };
  correctness: {
    outputs_equal: boolean;
    mismatch_count: number;
    match_count: number;
  };
  engines: {
    pandas: AnalyticsEngineComparison;
    polars: AnalyticsEngineComparison;
  };
  environment: Record<string, string>;
};
