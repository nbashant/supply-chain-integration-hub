import { ArrowRight, Check, FileText, Package, Send } from "lucide-react";
import type { Overview } from "../types";

const steps = [
  {
    number: "01",
    title: "A supplier sends an update",
    detail: "A JSON message or spreadsheet says what inventory they have.",
    tech: "Partner API"
  },
  {
    number: "02",
    title: "The hub checks it",
    detail: "Missing or impossible information is stopped before it can cause harm.",
    tech: "FastAPI + Pydantic"
  },
  {
    number: "03",
    title: "The original is kept",
    detail: "An untouched copy is saved so we can always prove what arrived.",
    tech: "SeaweedFS"
  },
  {
    number: "04",
    title: "The work happens in the background",
    detail: "The supplier does not have to wait while a worker handles the update.",
    tech: "Redis + Celery"
  },
  {
    number: "05",
    title: "Names and quantities are translated",
    detail: "The supplier’s product and location names become the hub’s shared names.",
    tech: "Partner adapter"
  },
  {
    number: "06",
    title: "Inventory is updated",
    detail: "The translated result becomes the current, searchable inventory record.",
    tech: "PostgreSQL"
  }
];

export function OverviewView({
  overview,
  onNavigate
}: {
  overview: Overview;
  onNavigate: (view: string) => void;
}) {
  const live = overview.components.filter(
    (component) => component.status === "available"
  ).length;
  return (
    <div className="home-page">
      <header className="home-intro">
        <span className="location-label">How the hub works</span>
        <h1>One supplier message.<br />One clear journey.</h1>
        <p>
          The hub takes information written in a supplier’s language, checks
          it, translates it, and safely updates the company’s inventory.
        </p>
        <button
          className="button button--primary button--large"
          onClick={() => onNavigate("walkthrough")}
        >
          Follow a real update <ArrowRight size={18} />
        </button>
      </header>

      <section className="plain-flow" aria-label="How a supplier update moves">
        <div className="flow-source">
          <span><Send size={20} /></span>
          <small>Information arrives</small>
          <strong>Supplier inventory message</strong>
        </div>
        <div className="flow-line"><span /></div>
        <div className="flow-destination">
          <span><Package size={20} /></span>
          <small>Information leaves</small>
          <strong>Inventory the company understands</strong>
        </div>
      </section>

      <section className="home-steps">
        <div className="simple-heading">
          <span className="location-label">The important part</span>
          <h2>What happens in between</h2>
          <p>Technology names are shown quietly underneath—not used as explanations.</p>
        </div>
        <ol>
          {steps.map((step) => (
            <li key={step.number}>
              <span className="step-number">{step.number}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.detail}</p>
                <small>{step.tech}</small>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <footer className="home-status">
        <Check size={16} />
        <span>
          The local hub is connected. {live} core pieces answered the latest
          health check.
        </span>
        <button onClick={() => onNavigate("history")}>
          See what it has done <ArrowRight size={15} />
        </button>
      </footer>
    </div>
  );
}
