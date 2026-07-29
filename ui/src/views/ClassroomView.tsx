import { ArrowRight, BookOpen, Search } from "lucide-react";
import { useMemo, useState } from "react";

const pieces = [
  {
    term: "FastAPI",
    plain: "The front door",
    does: "Receives a supplier message, checks its shape, and starts the safe import process.",
    fits: "It is the first piece a supplier reaches. It responds quickly because slower work is handed to a background worker."
  },
  {
    term: "PostgreSQL",
    plain: "The official notebook",
    does: "Keeps work tickets, inventory, attempts, errors, and the history of what happened.",
    fits: "Other pieces may move work around, but this database is where the hub checks the official state."
  },
  {
    term: "SeaweedFS object storage",
    plain: "The file archive",
    does: "Keeps the exact supplier message and larger daily processing files.",
    fits: "The database stores a small pointer to each file. This avoids stuffing large files into work tickets or waiting lines."
  },
  {
    term: "Redis",
    plain: "The waiting line",
    does: "Carries a tiny work-ticket number to the next available worker.",
    fits: "Only the number travels here. The worker uses it to find the official ticket and saved file."
  },
  {
    term: "Celery",
    plain: "The background worker system",
    does: "Picks up work tickets and runs translations without making the supplier wait.",
    fits: "It records each attempt, so unfinished work can be tried again instead of silently disappearing."
  },
  {
    term: "Supplier adapter and mappings",
    plain: "The translation guide",
    does: "Turns supplier product names, location names, and units into the hub’s shared language.",
    fits: "It never guesses. A versioned rule shows exactly why one outside value became one inside value."
  },
  {
    term: "Pandas and Polars",
    plain: "Two inventory-list checkers",
    does: "Compare a supplier list with the hub list and identify quantity disagreements.",
    fits: "They answer the same question in different ways. The fair comparison page verifies their answers before comparing speed."
  },
  {
    term: "NumPy",
    plain: "The many-number calculator",
    does: "Applies the stock-risk formula across many inventory rows efficiently.",
    fits: "It answers a planning question, so it is taught separately from the list-comparison tools."
  },
  {
    term: "Airflow and Spark",
    plain: "The daily processing team",
    does: "Schedules a day of historical files, checks them, calculates risk, and publishes compact results.",
    fits: "Airflow keeps the checklist and schedule. Spark performs the larger batch of data work."
  },
  {
    term: "Prometheus",
    plain: "The health counter",
    does: "Counts requests and records timing and health measurements.",
    fits: "It helps explain whether the running system is responding normally; it does not change inventory."
  }
];

const vocabulary = [
  ["Canonical model", "The hub’s one shared way to name and describe inventory."],
  ["Idempotency", "A duplicate message is recognized, so the same work is not accidentally created twice."],
  ["Data lineage", "The evidence trail from a final number back to its supplier message and translation rule."],
  ["Worker lease", "A time limit on a worker’s claim, making abandoned work visible and recoverable."],
  ["Manifest", "A processing receipt listing what was read, what was written, and what completed the work."],
  ["Parquet", "A compact analysis file that groups values by column so calculations can read only what they need."],
  ["Observability", "The events, counts, and timings that help people understand what the running system is doing."]
];

export function ClassroomView() {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const search = query.trim().toLowerCase();
    if (!search) return pieces;
    return pieces.filter((piece) =>
      `${piece.term} ${piece.plain} ${piece.does} ${piece.fits}`.toLowerCase().includes(search)
    );
  }, [query]);

  return (
    <div className="learn-page">
      <header className="learn-header">
        <span className="location-label">Learn the pieces</span>
        <h1>Understand the system one plain idea at a time.</h1>
        <p>Technical names are included because you will see them in real projects. Their everyday meaning always comes first.</p>
      </header>

      <section className="mental-story">
        <div><small>Outside</small><strong>Supplier language</strong></div>
        <ArrowRight />
        <div><small>In the hub</small><strong>Check, save, translate</strong></div>
        <ArrowRight />
        <div><small>Useful result</small><strong>Shared inventory</strong></div>
      </section>

      <label className="piece-search">
        <Search size={17} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search a name or idea"
        />
      </label>

      <section className="piece-list">
        {shown.map((piece) => (
          <details key={piece.term}>
            <summary>
              <span><strong>{piece.plain}</strong><small>{piece.term}</small></span>
              <BookOpen size={18} />
            </summary>
            <div>
              <p><small>What it does</small>{piece.does}</p>
              <p><small>How it fits</small>{piece.fits}</p>
            </div>
          </details>
        ))}
        {!shown.length && <div className="plain-empty">No piece matches that search.</div>}
      </section>

      <section className="vocabulary-list">
        <header><small>Words worth knowing</small><h2>Plain-English vocabulary</h2></header>
        <dl>
          {vocabulary.map(([term, meaning]) => (
            <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>
          ))}
        </dl>
      </section>
    </div>
  );
}
