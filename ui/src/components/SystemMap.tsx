import {
  Activity,
  Boxes,
  BrainCircuit,
  Database,
  Gauge,
  HardDrive,
  Network,
  ServerCog
} from "lucide-react";
import { useMemo, useState, type ComponentType } from "react";
import type { ComponentStatus } from "../types";

type MapNode = {
  id: string;
  name: string;
  eyebrow: string;
  icon: ComponentType<{ size?: number }>;
  input: string;
  output: string;
  why: string;
};

const nodes: MapNode[] = [
  {
    id: "fastapi",
    name: "FastAPI",
    eyebrow: "Front door",
    icon: Network,
    input: "Partner JSON or CSV",
    output: "A validated request",
    why: "Rejects malformed or unauthorized input before it reaches the system."
  },
  {
    id: "seaweedfs",
    name: "SeaweedFS",
    eyebrow: "Raw memory",
    icon: HardDrive,
    input: "Original payload bytes",
    output: "A durable object key",
    why: "Lets the hub replay the exact source without making a partner resend it."
  },
  {
    id: "postgresql",
    name: "PostgreSQL",
    eyebrow: "Source of truth",
    icon: Database,
    input: "Job facts and references",
    output: "A durable queued job",
    why: "Owns status, retries, evidence, inventory, and analytical results."
  },
  {
    id: "redis",
    name: "Redis",
    eyebrow: "Fast handoff",
    icon: Boxes,
    input: "A small job ID",
    output: "Work waiting for a worker",
    why: "Decouples the API response from slower background processing."
  },
  {
    id: "celery",
    name: "Celery",
    eyebrow: "Background worker",
    icon: ServerCog,
    input: "A durable job ID",
    output: "A claimed processing attempt",
    why: "Provides retry, scheduling, and worker isolation around imports."
  },
  {
    id: "adapter",
    name: "Adapter",
    eyebrow: "Translator",
    icon: BrainCircuit,
    input: "Supplier-specific fields",
    output: "Canonical inventory records",
    why: "Gives every partner freedom to speak differently while the hub stays stable."
  },
  {
    id: "analytics",
    name: "Analytics",
    eyebrow: "Decision layer",
    icon: Activity,
    input: "Clean shared data",
    output: "Reconciliation and risk",
    why: "Turns operational records into measurable supply-chain decisions."
  },
  {
    id: "prometheus",
    name: "Observability",
    eyebrow: "System senses",
    icon: Gauge,
    input: "Requests and durations",
    output: "Health and performance signals",
    why: "Makes invisible behavior measurable when something slows or fails."
  }
];

type Props = {
  components: ComponentStatus[];
  activeComponent?: string | null;
  compact?: boolean;
};

export function SystemMap({
  components,
  activeComponent,
  compact = false
}: Props) {
  const [selectedId, setSelectedId] = useState("fastapi");
  const statusById = useMemo(
    () => Object.fromEntries(components.map((item) => [item.id, item])),
    [components]
  );
  const selected = nodes.find((node) => node.id === selectedId) ?? nodes[0];
  const live = statusById[selected.id];

  return (
    <section className={`system-map ${compact ? "system-map--compact" : ""}`}>
      <div className="map-track" aria-label="Supply chain import flow">
        {nodes.map((node, index) => {
          const Icon = node.icon;
          const status = statusById[node.id]?.status ?? "configured";
          const active =
            node.id === selectedId ||
            node.name.toLowerCase() === activeComponent?.toLowerCase();
          return (
            <div className="map-stop" key={node.id}>
              <button
                type="button"
                className={`map-node ${active ? "is-active" : ""}`}
                onClick={() => setSelectedId(node.id)}
              >
                <span className={`status-dot status-dot--${status}`} />
                <span className="map-icon">
                  <Icon size={20} />
                </span>
                <span>
                  <small>{node.eyebrow}</small>
                  <strong>{node.name}</strong>
                </span>
              </button>
              {index < nodes.length - 1 && (
                <span className="map-connector" aria-hidden="true">
                  <span />
                </span>
              )}
            </div>
          );
        })}
      </div>
      {!compact && (
        <div className="map-explainer">
          <div>
            <span className="eyebrow">You selected</span>
            <h3>{selected.name}</h3>
            <p>{selected.why}</p>
          </div>
          <dl>
            <div>
              <dt>Receives</dt>
              <dd>{selected.input}</dd>
            </div>
            <div>
              <dt>Produces</dt>
              <dd>{selected.output}</dd>
            </div>
            <div>
              <dt>Live evidence</dt>
              <dd>{live?.evidence ?? "Evidence appears as this component runs."}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}
