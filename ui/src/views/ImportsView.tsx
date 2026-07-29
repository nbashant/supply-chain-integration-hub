import { ArrowRight, Check, CircleAlert, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { LoadingBlock, formatDate } from "../components/Shared";
import type { ImportDetail, ImportSummary, Snapshot } from "../types";

export function ImportsView({ embedded = false }: { embedded?: boolean }) {
  const [imports, setImports] = useState<ImportSummary[]>([]);
  const [selected, setSelected] = useState<ImportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const jobs = await api.imports();
      setImports(jobs);
      if (jobs.length) {
        setSelected(await api.importDetail(selected?.job.id ?? jobs[0].id));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load past updates.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const choose = async (id: string) => {
    try {
      setSelected(await api.importDetail(id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load that update.");
    }
  };

  return (
    <section className="history-page">
      {!embedded && (
        <header className="section-heading">
          <span className="location-label">Past supplier updates</span>
          <h1>See what arrived and what changed.</h1>
        </header>
      )}
      <div className="section-title-row">
        <div>
          <h2>Past supplier updates</h2>
          <p>Each entry answers four useful questions. Technical records stay available, but out of the way.</p>
        </div>
        <button className="quiet-button" onClick={() => void load()}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {loading ? <LoadingBlock /> : (
        <div className="history-layout">
          <aside className="history-list" aria-label="Past supplier updates">
            {imports.length ? imports.map((job) => (
              <button
                type="button"
                key={job.id}
                className={selected?.job.id === job.id ? "is-selected" : ""}
                onClick={() => void choose(job.id)}
              >
                <span className={`history-status history-status--${job.status}`}>
                  {job.status === "failed" ? <CircleAlert size={15} /> : <Check size={15} />}
                </span>
                <span>
                  <strong>{supplierName(job.supplier_code)} updated inventory</strong>
                  <small>
                    {formatDate(job.created_at)} · {job.accepted_records} {job.accepted_records === 1 ? "item" : "items"} changed
                  </small>
                </span>
                <em>{humanStatus(job.status)}</em>
              </button>
            )) : (
              <div className="plain-empty">No updates yet. Run the guided example first.</div>
            )}
          </aside>
          <main className="history-detail">
            {selected ? <UpdateStory detail={selected} /> : (
              <div className="plain-empty">Choose an update to read its story.</div>
            )}
          </main>
        </div>
      )}
    </section>
  );
}

function UpdateStory({ detail }: { detail: ImportDetail }) {
  const snapshot = detail.snapshots[0];
  const available = snapshot
    ? Math.max(Number(snapshot.canonical_on_hand) - Number(snapshot.canonical_reserved), 0)
    : 0;
  return (
    <article className="update-story">
      <header>
        <div>
          <small>{supplierName(detail.supplier_code)} · {formatDate(detail.job.created_at)}</small>
          <h2>{detail.job.accepted_records} {detail.job.accepted_records === 1 ? "inventory item" : "inventory items"} updated</h2>
        </div>
        <span className={`story-outcome story-outcome--${detail.job.status}`}>
          {humanStatus(detail.job.status)}
        </span>
      </header>

      <StoryQuestion number="1" title="What did the supplier send?">
        {snapshot ? (
          <div className="sent-values">
            <Value label="Their product name" value={snapshot.external_sku} />
            <Value label="Their location name" value={snapshot.external_location} />
            <Value label="Physically present" value={`${snapshot.source_on_hand} ${snapshot.source_unit}`} />
            <Value label="Already promised" value={`${snapshot.source_reserved} ${snapshot.source_unit}`} />
          </div>
        ) : <p>No accepted product rows were found in this message.</p>}
      </StoryQuestion>

      <StoryQuestion number="2" title="How did the hub translate it?">
        {snapshot ? <CompactTranslation snapshot={snapshot} /> : (
          <p>The message stopped before any product could be translated.</p>
        )}
      </StoryQuestion>

      <StoryQuestion number="3" title="What changed inside the hub?">
        {snapshot ? (
          <div className="change-receipt">
            <strong>{snapshot.canonical_sku} at {snapshot.warehouse_code}</strong>
            <div>
              <span>{snapshot.canonical_on_hand}<small>on hand</small></span>
              <b>−</b>
              <span>{snapshot.canonical_reserved}<small>promised</small></span>
              <b>=</b>
              <span className="change-total">{available.toFixed(3)}<small>available</small></span>
            </div>
          </div>
        ) : <p>No inventory changed.</p>}
      </StoryQuestion>

      <StoryQuestion number="4" title="Did anything go wrong?">
        {detail.errors.length ? (
          <div className="problem-list">
            {detail.errors.map((problem) => (
              <p key={problem.id}><CircleAlert size={16} /> {problem.message}</p>
            ))}
          </div>
        ) : (
          <p className="all-clear"><Check size={16} /> No. Every included item was understood and saved.</p>
        )}
      </StoryQuestion>

      <details className="technical-details">
        <summary>Technical record</summary>
        <dl>
          <div><dt>Work ticket</dt><dd><code>{detail.job.id}</code></dd></div>
          <div><dt>Saved source</dt><dd><code>{detail.job.payload_object_key ?? "not available"}</code></dd></div>
          <div><dt>File fingerprint</dt><dd><code>{detail.job.content_sha256}</code></dd></div>
          <div><dt>Worker attempts</dt><dd>{detail.attempts.length}</dd></div>
        </dl>
        <ol className="technical-event-list">
          {detail.events.map((event) => (
            <li key={event.id}><time>{formatDate(event.occurred_at)}</time><span>{event.title}</span><code>{event.stage}</code></li>
          ))}
        </ol>
      </details>
    </article>
  );
}

function StoryQuestion({
  number,
  title,
  children
}: {
  number: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="story-question">
      <div className="question-number">{number}</div>
      <div><h3>{title}</h3>{children}</div>
    </section>
  );
}

function Value({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>;
}

function CompactTranslation({ snapshot }: { snapshot: Snapshot }) {
  return (
    <div className="compact-translation">
      <div><small>Supplier said</small><strong>{snapshot.external_sku}</strong></div>
      <span><ArrowRight size={15} /> Product rule v{snapshot.product_mapping_version}</span>
      <div><small>Hub understands</small><strong>{snapshot.canonical_sku}</strong></div>
      <div><small>Supplier said</small><strong>{snapshot.external_location}</strong></div>
      <span><ArrowRight size={15} /> Location rule v{snapshot.warehouse_mapping_version}</span>
      <div><small>Hub understands</small><strong>{snapshot.warehouse_code}</strong></div>
    </div>
  );
}

function supplierName(code: string) {
  return code === "SUPPLIER_A" ? "Supplier A" : code.replaceAll("_", " ");
}

function humanStatus(status: string) {
  if (status === "completed") return "Completed successfully";
  if (status === "completed_with_errors") return "Finished with a problem";
  if (status === "processing") return "Still working";
  if (status === "queued") return "Waiting for a worker";
  return "Stopped";
}
