import { Check, CircleAlert, Play, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { LoadingBlock, formatDate } from "../components/Shared";
import type {
  AnalyticsComparison,
  AnalyticsEngineComparison,
  AnalyticsRun
} from "../types";

export function AnalyticsView({
  onDataChanged,
  embedded = false
}: {
  onDataChanged: () => void;
  embedded?: boolean;
}) {
  const [runs, setRuns] = useState<AnalyticsRun[]>([]);
  const [comparison, setComparison] = useState<AnalyticsComparison | null>(null);
  const [running, setRunning] = useState<"compare" | "risk" | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setRuns(await api.analytics());
    setLoading(false);
  };
  useEffect(() => { void load(); }, []);

  const compare = async () => {
    setRunning("compare");
    setError("");
    try {
      setComparison(await api.compareAnalytics());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The comparison could not run.");
    } finally {
      setRunning("");
    }
  };

  const runRisk = async () => {
    setRunning("risk");
    setError("");
    try {
      await api.runRisk();
      await load();
      onDataChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The risk estimate could not run.");
    } finally {
      setRunning("");
    }
  };

  const latestRisk = runs.find((run) => run.run_type === "stockout_risk");

  return (
    <section className="calculations-page">
      {!embedded && (
        <header className="section-heading">
          <span className="location-label">Calculations</span>
          <h1>Use the hub’s data to answer practical questions.</h1>
        </header>
      )}
      <div className="section-title-row">
        <div>
          <h2>Calculations</h2>
          <p>These are two different questions, so they are taught and measured separately.</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <article className="calculation-lesson">
        <header>
          <span className="lesson-number">1</span>
          <div><small>Accuracy check</small><h3>Do two inventory lists agree?</h3></div>
        </header>
        <p>
          Give Pandas and Polars the exact same 5,000 supplier and hub records.
          Each tool joins the lists and finds quantity disagreements. We first
          verify their answers match, then time the same work five times.
        </p>
        <button className="button button--primary" disabled={!!running} onClick={() => void compare()}>
          <Scale size={16} /> {running === "compare" ? "Running five fair trials…" : "Run a fair comparison"}
        </button>
        {comparison && <ComparisonResult comparison={comparison} />}
      </article>

      <article className="calculation-lesson">
        <header>
          <span className="lesson-number">2</span>
          <div><small>Planning estimate</small><h3>Where might inventory run out?</h3></div>
        </header>
        <p>
          This calculation asks whether expected demand is larger than usable
          supply. NumPy performs the same formula across many inventory rows at once.
        </p>
        <div className="risk-formula">
          <div><strong>On hand</strong><small>what is physically present</small></div>
          <b>−</b>
          <div><strong>Reserved</strong><small>already promised</small></div>
          <b>+</b>
          <div><strong>Incoming</strong><small>expected to arrive</small></div>
          <b>vs.</b>
          <div><strong>Demand</strong><small>expected to be needed</small></div>
        </div>
        <button className="button button--primary" disabled={!!running} onClick={() => void runRisk()}>
          <Play size={16} /> {running === "risk" ? "Estimating risk…" : "Estimate stockout risk"}
        </button>
        {latestRisk && <RiskResult run={latestRisk} />}
      </article>

      {loading ? <LoadingBlock /> : runs.length > 0 && (
        <details className="technical-details calculation-history">
          <summary>Previous calculation records</summary>
          <div>
            {runs.map((run) => (
              <p key={run.id}>
                <span>{run.run_type.replaceAll("_", " ")}</span>
                <code>{run.engine}</code>
                <span>{run.input_rows.toLocaleString()} rows</span>
                <span>{run.duration_ms} ms</span>
                <time>{formatDate(run.created_at)}</time>
              </p>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

function ComparisonResult({ comparison }: { comparison: AnalyticsComparison }) {
  const max = Math.max(
    comparison.engines.pandas.maximum_ms,
    comparison.engines.polars.maximum_ms
  );
  return (
    <section className="comparison-result">
      <div className="correctness-result">
        {comparison.correctness.outputs_equal ? <Check size={18} /> : <CircleAlert size={18} />}
        <div>
          <strong>
            {comparison.correctness.outputs_equal
              ? "Both tools produced the same answer"
              : "The answers did not match"}
          </strong>
          <span>
            {comparison.correctness.match_count.toLocaleString()} matching rows ·{" "}
            {comparison.correctness.mismatch_count.toLocaleString()} disagreements
          </span>
        </div>
      </div>
      <p className="measurement-note">
        Every dot below is one real run on the same data. Both rows share the
        same scale, so their positions are directly comparable.
      </p>
      <TimingRow name="Pandas" stats={comparison.engines.pandas} max={max} />
      <TimingRow name="Polars" stats={comparison.engines.polars} max={max} />
      <p className="timing-caution">
        Small timing changes are normal because your computer is doing other
        work too. The median is the middle run—not a decorative bar.
      </p>
      <details className="technical-details">
        <summary>Exact setup and measurements</summary>
        <dl>
          <div><dt>Rows</dt><dd>{comparison.workload.row_count.toLocaleString()}</dd></div>
          <div><dt>Repeated</dt><dd>{comparison.workload.repeats} times after one warm-up</dd></div>
          <div><dt>Data seed</dt><dd>{comparison.workload.seed}</dd></div>
          <div><dt>Measured work</dt><dd>{comparison.workload.measurement}</dd></div>
        </dl>
      </details>
    </section>
  );
}

function TimingRow({
  name,
  stats,
  max
}: {
  name: string;
  stats: AnalyticsEngineComparison;
  max: number;
}) {
  return (
    <div className="timing-row">
      <div><strong>{name}</strong><span>median {stats.median_ms.toFixed(2)} ms</span></div>
      <div className="timing-track" aria-label={`${name} exact execution times`}>
        {stats.durations_ms.map((duration, index) => (
          <i
            key={`${duration}-${index}`}
            style={{ left: `${Math.max(2, (duration / max) * 96)}%` }}
            title={`Run ${index + 1}: ${duration.toFixed(3)} ms`}
          />
        ))}
      </div>
      <small>
        Exact runs: {stats.durations_ms.map((value) => `${value.toFixed(2)} ms`).join(" · ")}
      </small>
      <small>Range {stats.minimum_ms.toFixed(2)}–{stats.maximum_ms.toFixed(2)} ms</small>
    </div>
  );
}

function RiskResult({ run }: { run: AnalyticsRun }) {
  const counts = (run.summary.severity_counts ?? {}) as Record<string, number>;
  return (
    <section className="risk-result">
      <strong>Latest estimate across {run.input_rows.toLocaleString()} inventory rows</strong>
      <div>
        <span><b>{counts.low ?? 0}</b><small>lower risk</small></span>
        <span><b>{counts.medium ?? 0}</b><small>needs attention</small></span>
        <span><b>{counts.high ?? 0}</b><small>higher risk</small></span>
      </div>
      <p>This is a planning signal based on synthetic learning data, not a prediction of a real shortage.</p>
    </section>
  );
}
