import { Check, FileArchive, Files, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { LoadingBlock, formatDate } from "../components/Shared";
import type { PipelineRun } from "../types";

const stages = [
  ["1", "Gather the day’s files", "Find every historical inventory file for the selected date."],
  ["2", "Check and combine them", "Reject broken rows and bring valid supplier records together."],
  ["3", "Calculate stock risk", "Estimate which product and warehouse pairs may run short."],
  ["4", "Pack the useful result", "Store the result column by column so analysis can read only what it needs."],
  ["5", "Write a receipt", "Record what went in, what came out, and which version did the work."]
];

export function PipelineView({ embedded = false }: { embedded?: boolean }) {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selected, setSelected] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const result = await api.pipelines();
      setRuns(result);
      setSelected((current) =>
        result.find((run) => run.manifest_key === current?.manifest_key) ??
        result[0] ??
        null
      );
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  return (
    <section className="processing-page">
      {!embedded && (
        <header className="section-heading">
          <span className="location-label">Daily data processing</span>
          <h1>Turn a day of files into data that is easier to study.</h1>
        </header>
      )}
      <div className="section-title-row">
        <div>
          <h2>Daily data processing</h2>
          <p>This is the larger, scheduled path used when many historical files need the same careful treatment.</p>
        </div>
        <button className="quiet-button" onClick={() => void load()}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      <div className="daily-flow">
        {stages.map(([number, title, description]) => (
          <article key={number}>
            <span>{number}</span>
            <div><strong>{title}</strong><p>{description}</p></div>
          </article>
        ))}
      </div>

      <section className="parquet-lesson">
        <header>
          <span><FileArchive size={20} /></span>
          <div>
            <small>One unfamiliar word, made simple</small>
            <h3>What is Parquet?</h3>
          </div>
        </header>
        <p>
          It is a compact file format made for analysis. A normal row-based file
          stores one complete inventory item after another. Parquet groups all
          product values together, all warehouse values together, and all
          quantity values together.
        </p>
        <div className="file-comparison">
          <div>
            <small>Normal row file</small>
            <span>Product A · West · 120</span>
            <span>Product B · East · 45</span>
            <span>Product C · West · 88</span>
          </div>
          <div>
            <small>Parquet groups columns</small>
            <span><b>Products</b> A, B, C</span>
            <span><b>Warehouses</b> West, East, West</span>
            <span><b>Quantities</b> 120, 45, 88</span>
          </div>
        </div>
        <p className="plain-benefit">
          If a calculation only needs quantities, it can skip the other groups.
          That usually means less data read and faster analysis.
        </p>
      </section>

      {loading ? <LoadingBlock /> : runs.length ? (
        <div className="processing-history">
          <aside>
            <h3>Completed days</h3>
            {runs.map((run) => (
              <button
                key={run.manifest_key}
                className={selected?.manifest_key === run.manifest_key ? "is-selected" : ""}
                onClick={() => setSelected(run)}
              >
                <span className="history-status"><Check size={14} /></span>
                <span><strong>{run.partition_date ?? "Unlabeled date"}</strong><small>{formatDate(run.created_at)}</small></span>
              </button>
            ))}
          </aside>
          {selected && <ProcessingReceipt run={selected} />}
        </div>
      ) : (
        <div className="plain-empty processing-empty">
          <Files size={24} />
          <strong>No completed daily runs yet</strong>
          <p>The scheduled pipeline has not published a receipt. The explanation above still shows what it will do.</p>
          <details className="technical-details">
            <summary>Commands for running it locally</summary>
            <code>make pipeline-up &amp;&amp; make pipeline-seed &amp;&amp; make pipeline-backfill</code>
          </details>
        </div>
      )}
    </section>
  );
}

function ProcessingReceipt({ run }: { run: PipelineRun }) {
  return (
    <article className="processing-receipt">
      <header>
        <span><ShieldCheck size={22} /></span>
        <div><small>Processing receipt</small><h3>{run.partition_date ?? "Daily run"}</h3></div>
        <em>{run.status === "succeeded" ? "Completed" : run.status}</em>
      </header>
      <div className="receipt-facts">
        <div><strong>{run.input_rows ?? "—"}</strong><span>inventory rows read</span></div>
        <div><strong>{run.curated_object_count}</strong><span>analysis-ready files written</span></div>
        <div><strong>{run.summary_object_count}</strong><span>risk summaries written</span></div>
      </div>
      <p>
        The run gathered the selected day, checked it, calculated stock risk,
        packed the results for analysis, and left this receipt.
      </p>
      <details className="technical-details">
        <summary>Technical receipt</summary>
        <dl>
          <div><dt>Run ID</dt><dd><code>{run.run_id ?? "not recorded"}</code></dd></div>
          <div><dt>Processing engine</dt><dd>Spark {run.spark_version ?? "version not recorded"}</dd></div>
          <div><dt>Receipt location</dt><dd><code>{run.manifest_key}</code></dd></div>
        </dl>
        <pre>{JSON.stringify(run.manifest, null, 2)}</pre>
      </details>
    </article>
  );
}
