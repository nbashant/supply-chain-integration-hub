import {
  BookOpen,
  CircleHelp,
  History,
  House,
  Menu,
  PlayCircle,
  X
} from "lucide-react";
import { useCallback, useEffect, useState, type ComponentType } from "react";
import { api } from "./api";
import { LoadingBlock } from "./components/Shared";
import type { Overview } from "./types";
import { ClassroomView } from "./views/ClassroomView";
import { ExploreView } from "./views/ExploreView";
import { OverviewView } from "./views/OverviewView";
import { WalkthroughView } from "./views/WalkthroughView";

type NavItem = {
  id: string;
  label: string;
  detail: string;
  icon: ComponentType<{ size?: number }>;
};

const navigation: NavItem[] = [
  { id: "overview", label: "How it works", detail: "Start here", icon: House },
  {
    id: "walkthrough",
    label: "Follow an update",
    detail: "Watch one happen",
    icon: PlayCircle
  },
  {
    id: "history",
    label: "See past work",
    detail: "Updates, daily runs, calculations",
    icon: History
  },
  {
    id: "learn",
    label: "Learn the pieces",
    detail: "Words and concepts",
    icon: BookOpen
  }
];

export default function App() {
  const [active, setActive] = useState(() => window.location.hash.slice(1) || "overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setOverview(await api.overview());
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the hub API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const navigate = (id: string) => {
    setActive(id);
    window.location.hash = id;
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const content = () => {
    if (!overview && loading) return <LoadingBlock label="Connecting to the learning API…" />;
    if (!overview) return (
      <div className="fatal-state">
        <CircleHelp size={35} />
        <h1>The UI is ready, but the API is not reachable.</h1>
        <p>Start the local stack with <code>make compose-up</code>, then refresh this page.</p>
        <button className="button button--primary" onClick={() => void refresh()}>Try again</button>
      </div>
    );
    switch (active) {
      case "walkthrough":
        return <WalkthroughView components={overview.components} onDataChanged={() => void refresh()} />;
      case "history":
        return (
          <ExploreView
            overview={overview}
            onDataChanged={() => void refresh()}
          />
        );
      case "learn":
        return <ClassroomView />;
      default:
        return <OverviewView overview={overview} onNavigate={navigate} />;
    }
  };

  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open navigation">
        <Menu />
      </button>
      <aside className={`sidebar ${menuOpen ? "is-open" : ""}`}>
        <button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X /></button>
        <div className="brand">
          <span className="brand-mark">S</span>
          <div><strong>Supply Chain Hub</strong><small>A visual guide</small></div>
        </div>
        <nav>
          {navigation.map(({ id, label, detail, icon: Icon }) => (
            <button
              key={id}
              className={active === id ? "is-active" : ""}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span><strong>{label}</strong><small>{detail}</small></span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={`live-indicator ${error ? "has-error" : ""}`}><i />{error ? "API unavailable" : "Local system connected"}</span>
          <p>No account. No cloud. Your data stays on this machine.</p>
          <a href="/docs" target="_blank" rel="noreferrer">
            <CircleHelp size={14} /> Technical API reference
          </a>
        </div>
      </aside>
      {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <main className="content">
        {error && overview && <div className="error-banner slim">Live refresh failed; the last known view is still shown.</div>}
        {content()}
      </main>
    </div>
  );
}
