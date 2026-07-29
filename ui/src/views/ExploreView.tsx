import { useState } from "react";
import type { Overview } from "../types";
import { AnalyticsView } from "./AnalyticsView";
import { ImportsView } from "./ImportsView";
import { OperationsView } from "./OperationsView";
import { PipelineView } from "./PipelineView";

type Section = "updates" | "daily" | "calculations" | "health";

export function ExploreView({
  overview,
  onDataChanged
}: {
  overview: Overview;
  onDataChanged: () => void;
}) {
  const [section, setSection] = useState<Section>("updates");
  return (
    <div>
      <header className="history-header">
        <span className="location-label">See past work</span>
        <h1>What has the hub done?</h1>
        <p>
          Choose the kind of work you want to understand. Each section tells
          the story first and keeps system details out of the way.
        </p>
      </header>
      <nav className="section-tabs" aria-label="Past work sections">
        <button
          className={section === "updates" ? "is-active" : ""}
          onClick={() => setSection("updates")}
        >
          Supplier updates
        </button>
        <button
          className={section === "daily" ? "is-active" : ""}
          onClick={() => setSection("daily")}
        >
          Daily processing
        </button>
        <button
          className={section === "calculations" ? "is-active" : ""}
          onClick={() => setSection("calculations")}
        >
          Calculations
        </button>
        <button
          className={section === "health" ? "is-active" : ""}
          onClick={() => setSection("health")}
        >
          System health
        </button>
      </nav>
      {section === "updates" && <ImportsView embedded />}
      {section === "daily" && <PipelineView embedded />}
      {section === "calculations" && (
        <AnalyticsView embedded onDataChanged={onDataChanged} />
      )}
      {section === "health" && <OperationsView overview={overview} embedded />}
    </div>
  );
}
