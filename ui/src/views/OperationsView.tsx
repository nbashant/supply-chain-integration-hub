import { Activity, Check, CircleAlert } from "lucide-react";
import type { Overview } from "../types";

export function OperationsView({
  overview,
  embedded = false
}: {
  overview: Overview;
  embedded?: boolean;
}) {
  const unavailable = overview.components.filter((item) => item.status === "unavailable");
  return (
    <section className="health-page">
      {!embedded && (
        <header className="section-heading">
          <span className="location-label">System health</span>
          <h1>See whether the local pieces are reachable.</h1>
        </header>
      )}
      <div className="section-title-row">
        <div>
          <h2>System health</h2>
          <p>This page checks the pieces needed by the learning hub and explains what each check actually proves.</p>
        </div>
        <a className="quiet-button" href="/metrics" target="_blank" rel="noreferrer">
          <Activity size={15} /> Technical measurements
        </a>
      </div>
      <div className={`overall-health ${unavailable.length ? "has-problem" : ""}`}>
        {unavailable.length ? <CircleAlert size={21} /> : <Check size={21} />}
        <div>
          <strong>{unavailable.length ? `${unavailable.length} piece needs attention` : "The checked pieces are reachable"}</strong>
          <span>{unavailable.length ? "The details below show which check failed." : "The live checks completed from this running application."}</span>
        </div>
      </div>
      <div className="health-list">
        {overview.components.map((component) => (
          <article key={component.id}>
            <span className={`health-icon health-icon--${component.status}`}>
              {component.status === "unavailable" ? <CircleAlert size={16} /> : <Check size={16} />}
            </span>
            <div>
              <h3>{component.name}</h3>
              <p>{component.role}</p>
              <details>
                <summary>What this status is based on</summary>
                <span>{component.evidence}</span>
              </details>
            </div>
            <em>{humanComponentStatus(component.status)}</em>
          </article>
        ))}
      </div>
      <details className="technical-details">
        <summary>Recent system events</summary>
        <ol className="technical-event-list">
          {overview.recent_events.slice(0, 10).map((event) => (
            <li key={event.id}>
              <time>{new Date(event.occurred_at).toLocaleString()}</time>
              <span>{event.title}</span>
              <code>{event.component}</code>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

function humanComponentStatus(status: string) {
  if (status === "available") return "Checked now";
  if (status === "configured") return "Ready when used";
  return "Not reachable";
}
