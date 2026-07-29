import {
  ArrowRight,
  Check,
  ClipboardList,
  FileJson,
  FolderArchive,
  PackageCheck,
  Play,
  RotateCcw,
  Truck,
  UserRoundCheck
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";
import { api } from "../api";
import type {
  ComponentStatus,
  DemoResponse,
  ImportDetail,
  OperationEvent,
  Snapshot
} from "../types";

const flowSteps = [
  { number: 1, title: "Supplier sends an update", stage: "" },
  { number: 2, title: "The message is checked", stage: "request.validated" },
  { number: 3, title: "An untouched copy is saved", stage: "payload.stored" },
  { number: 4, title: "A work ticket is created", stage: "job.queued" },
  { number: 5, title: "A worker picks it up", stage: "worker.claimed" },
  { number: 6, title: "Names and quantities are translated", stage: "payload.transformed" },
  { number: 7, title: "Inventory is updated", stage: "inventory.committed" }
];

export function WalkthroughView({
  components: _components,
  onDataChanged
}: {
  components: ComponentStatus[];
  onDataChanged: () => void;
}) {
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [events, setEvents] = useState<OperationEvent[]>([]);
  const [detail, setDetail] = useState<ImportDetail | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [followLive, setFollowLive] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const sourceRef = useRef<EventSource | null>(null);
  const followLiveRef = useRef(true);

  const setFollowing = (value: boolean) => {
    followLiveRef.current = value;
    setFollowLive(value);
  };

  const run = async () => {
    sourceRef.current?.close();
    setRunning(true);
    setError("");
    setEvents([]);
    setDetail(null);
    setActiveStep(1);
    setFollowing(true);
    try {
      const result = await api.runDemo();
      setDemo(result);
      const source = new EventSource(
        `/api/v1/learning/imports/${result.job.id}/events`
      );
      sourceRef.current = source;
      source.addEventListener("operation", (message) => {
        const event = JSON.parse((message as MessageEvent).data) as OperationEvent;
        setEvents((current) =>
          current.some((item) => item.id === event.id)
            ? current
            : [...current, event]
        );
        const nextStep = stepForStage(event.stage);
        if (nextStep) {
          setActiveStep((current) =>
            followLiveRef.current ? Math.max(current, nextStep) : current
          );
        }
      });
      source.addEventListener("complete", async () => {
        source.close();
        const finalDetail = await api.importDetail(result.job.id);
        setDetail(finalDetail);
        setEvents(finalDetail.events);
        setActiveStep((current) => (followLiveRef.current ? 7 : current));
        setRunning(false);
        onDataChanged();
      });
      source.onerror = () => {
        source.close();
        window.setTimeout(async () => {
          try {
            const finalDetail = await api.importDetail(result.job.id);
            setDetail(finalDetail);
            setEvents(finalDetail.events);
            const finished =
              finalDetail.job.status === "completed" ||
              finalDetail.job.status === "completed_with_errors" ||
              finalDetail.job.status === "failed";
            setRunning(!finished);
            if (finished && followLiveRef.current) setActiveStep(7);
          } catch {
            setError(
              "The live view paused. The update itself is still safely recorded."
            );
            setRunning(false);
          }
        }, 700);
      };
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start the example.");
      setRunning(false);
    }
  };

  useEffect(() => () => sourceRef.current?.close(), []);

  const item = useMemo(() => {
    const items = demo?.demo_input.items;
    return Array.isArray(items) ? (items[0] as Record<string, unknown>) : null;
  }, [demo]);
  const snapshot = detail?.snapshots[0] ?? null;
  const eventFor = (...stages: string[]) =>
    events.find((event) => stages.includes(event.stage));
  const hasStage = (stage: string) => events.some((event) => event.stage === stage);

  const chooseStep = (step: number) => {
    setFollowing(false);
    setActiveStep(step);
  };

  return (
    <div className="guided-page">
      <header className="guided-header">
        <div>
          <span className="location-label">Follow a supplier update</span>
          <h1>See exactly what changes at every step.</h1>
          <p>
            This is a real trip through the local hub. The example data is made
            for learning, but every check, file, ticket, worker, translation,
            and inventory update is real.
          </p>
        </div>
        <button
          className="button button--primary button--large"
          onClick={run}
          disabled={running}
        >
          {demo ? <RotateCcw size={17} /> : <Play size={17} />}
          {running ? "Update in progress…" : demo ? "Run a new example" : "Start the example"}
        </button>
      </header>

      <div className="guided-safety">
        This creates one clearly labeled practice product and warehouse. It
        cannot change or delete existing business data.
      </div>
      {error && <div className="error-banner">{error}</div>}

      <nav className="step-rail" aria-label="Supplier update steps">
        {flowSteps.map((step) => {
          const complete =
            step.number === 1 ? Boolean(demo) : hasStage(step.stage);
          return (
            <button
              key={step.number}
              className={activeStep === step.number ? "is-active" : ""}
              onClick={() => chooseStep(step.number)}
              disabled={!demo}
            >
              <span>{complete ? <Check size={14} /> : step.number}</span>
              <strong>{step.title}</strong>
            </button>
          );
        })}
      </nav>

      {!demo ? (
        <section className="guided-empty">
          <FileJson size={30} />
          <h2>Ready when you are</h2>
          <p>
            Start the example and this space will follow one message from the
            supplier all the way to updated inventory.
          </p>
        </section>
      ) : (
        <section className="scene-shell">
          <div className="scene-topline">
            <span>Step {activeStep} of 7</span>
            {running && followLive && <small>Following the live update</small>}
            {!followLive && running && (
              <button onClick={() => setFollowing(true)}>Return to live step</button>
            )}
          </div>
          {activeStep === 1 && <SupplierScene input={demo.demo_input} item={item} />}
          {activeStep === 2 && (
            <ValidationScene
              input={demo.demo_input}
              item={item}
              event={eventFor("request.validated")}
            />
          )}
          {activeStep === 3 && (
            <ArchiveScene
              job={detail?.job ?? demo.job}
              event={eventFor("payload.stored")}
            />
          )}
          {activeStep === 4 && (
            <TicketScene
              job={detail?.job ?? demo.job}
              queued={eventFor("job.queued")}
              dispatched={eventFor("job.dispatched")}
            />
          )}
          {activeStep === 5 && (
            <WorkerScene
              claimed={eventFor("worker.claimed")}
              verified={eventFor("payload.verified")}
            />
          )}
          {activeStep === 6 && (
            <TranslationScene
              item={item}
              snapshot={snapshot}
              event={eventFor("payload.transformed")}
            />
          )}
          {activeStep === 7 && (
            <InventoryScene
              snapshot={snapshot}
              event={eventFor("inventory.committed")}
              outcome={detail?.job.status ?? demo.job.status}
            />
          )}
          <div className="scene-actions">
            <button
              onClick={() => chooseStep(Math.max(1, activeStep - 1))}
              disabled={activeStep === 1}
            >
              Previous
            </button>
            <button
              onClick={() => chooseStep(Math.min(7, activeStep + 1))}
              disabled={activeStep === 7}
            >
              Next step <ArrowRight size={15} />
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function SupplierScene({
  input,
  item
}: {
  input: Record<string, unknown>;
  item: Record<string, unknown> | null;
}) {
  return (
    <Scene
      title="The supplier describes its inventory"
      intro="Supplier A sends the product name, location, and quantities using its own vocabulary."
      why="The hub must understand this outside language without forcing every supplier to change its systems."
      visual={
        <div className="supplier-scene">
          <div className="person-label"><span>A</span><strong>Supplier A</strong></div>
          <ArrowRight />
          <JsonDocument value={input} />
        </div>
      }
      output={
        <>
          The message says <strong>{String(item?.on_hand)} items</strong> are
          physically present and <strong>{String(item?.allocated)} are already
          promised</strong> to orders.
        </>
      }
    />
  );
}

function ValidationScene({
  input,
  item,
  event
}: {
  input: Record<string, unknown>;
  item: Record<string, unknown> | null;
  event?: OperationEvent;
}) {
  const checks = [
    ["Message has a reference number", String(input.snapshot_id ?? "missing")],
    ["Time includes a time zone", String(input.captured_at ?? "missing")],
    ["At least one product was included", "1 product"],
    ["Quantities are zero or greater", `${String(item?.on_hand)} and ${String(item?.allocated)}`],
    ["The unit is one the hub understands", String(item?.unit ?? "missing")]
  ];
  return (
    <Scene
      title="The hub checks the message before trusting it"
      intro="Each important field is checked. A bad message stops here instead of quietly damaging inventory."
      why="Catching a problem at the front door is safer than discovering it after inventory has already changed."
      visual={
        <div className="validation-board">
          <div className="mini-document">
            <FileJson size={22} />
            <span>{String(input.snapshot_id)}</span>
          </div>
          <ul>
            {checks.map(([label, value]) => (
              <li key={label}>
                <span className={event ? "check-ok" : "check-wait"}>
                  {event ? <Check size={13} /> : "·"}
                </span>
                <div><strong>{label}</strong><small>{value}</small></div>
              </li>
            ))}
          </ul>
          <div className={`validation-result ${event ? "is-ready" : ""}`}>
            {event ? "The message passed every check" : "Checks are running"}
          </div>
        </div>
      }
      output={
        event
          ? "A clean, understood message can continue."
          : "The hub is still checking the message."
      }
      event={event}
    />
  );
}

function ArchiveScene({
  job,
  event
}: {
  job: DemoResponse["job"];
  event?: OperationEvent;
}) {
  const key = event?.evidence_reference ?? job.payload_object_key;
  return (
    <Scene
      title="The original message is saved untouched"
      intro="The hub makes a permanent copy before translating anything."
      why="If a mapping changes or someone questions a number later, we can return to the exact message that arrived."
      visual={
        <div className="archive-visual">
          <div className="archive-file">
            <FileJson size={27} />
            <strong>Supplier message</strong>
            <small>{job.payload_size_bytes ?? "—"} bytes</small>
          </div>
          <div className="moving-arrow"><ArrowRight /></div>
          <div className={`archive-box ${event ? "is-filled" : ""}`}>
            <FolderArchive size={30} />
            <strong>Original copies</strong>
            <small>{event ? "Copy saved" : "Waiting for copy"}</small>
          </div>
        </div>
      }
      output={
        event ? (
          <>The untouched file now lives at <code>{key}</code>.</>
        ) : "The copy is being saved."
      }
      event={event}
    />
  );
}

function TicketScene({
  job,
  queued,
  dispatched
}: {
  job: DemoResponse["job"];
  queued?: OperationEvent;
  dispatched?: OperationEvent;
}) {
  return (
    <Scene
      title="The hub writes a work ticket"
      intro="Instead of doing everything while the supplier waits, the hub records a small ticket describing the work."
      why="The ticket survives a restart. If a worker is busy or temporarily unavailable, the update is not forgotten."
      visual={
        <div className="ticket-journey">
          <div className="work-ticket">
            <ClipboardList size={24} />
            <span>Work ticket</span>
            <strong>#{job.id.slice(0, 8)}</strong>
            <dl>
              <div><dt>Supplier</dt><dd>Supplier A</dd></div>
              <div><dt>State</dt><dd>{queued ? "Waiting" : "Being written"}</dd></div>
              <div><dt>Tries allowed</dt><dd>{job.max_attempts}</dd></div>
            </dl>
          </div>
          <ArrowRight />
          <div className={`queue-note ${dispatched ? "is-sent" : ""}`}>
            <Truck size={25} />
            <strong>{dispatched ? "Ticket number sent" : "Waiting to send"}</strong>
            <p>Only <code>{job.id.slice(0, 8)}…</code> travels through the fast queue—not the supplier file.</p>
          </div>
        </div>
      }
      output={
        dispatched
          ? "A worker can now find the full ticket in the database."
          : "The ticket is safely waiting in the database."
      }
      event={dispatched ?? queued}
    />
  );
}

function WorkerScene({
  claimed,
  verified
}: {
  claimed?: OperationEvent;
  verified?: OperationEvent;
}) {
  return (
    <Scene
      title="A background worker takes responsibility"
      intro="A worker picks up the ticket, loads the saved message, and makes sure the copy has not changed."
      why="Slow work stays away from the supplier-facing request, while the ticket records who handled it and whether another try is needed."
      visual={
        <div className="worker-visual">
          <div className="worker-person">
            <UserRoundCheck size={34} />
            <strong>Background worker</strong>
            <small>{claimed ? "Ticket claimed" : "Waiting for ticket"}</small>
          </div>
          <div className="worker-checks">
            <div className={claimed ? "is-done" : ""}>
              <span>{claimed ? <Check size={13} /> : "1"}</span>
              Open attempt {String(claimed?.details.attempt_number ?? "—")}
            </div>
            <div className={verified ? "is-done" : ""}>
              <span>{verified ? <Check size={13} /> : "2"}</span>
              Compare the file fingerprint
            </div>
            <div className={verified ? "is-done" : ""}>
              <span>{verified ? <Check size={13} /> : "3"}</span>
              Begin translation
            </div>
          </div>
        </div>
      }
      output={
        verified
          ? "The saved file matches the original fingerprint and is safe to translate."
          : claimed
            ? "The worker owns this attempt and is checking the file."
            : "The ticket is waiting for a worker."
      }
      event={verified ?? claimed}
    />
  );
}

function TranslationScene({
  item,
  snapshot,
  event
}: {
  item: Record<string, unknown> | null;
  snapshot: Snapshot | null;
  event?: OperationEvent;
}) {
  const externalSku = String(item?.item_number ?? "—");
  const externalLocation = String(item?.location ?? "—");
  return (
    <Scene
      title="The supplier’s language becomes the hub’s language"
      intro="The worker looks up the agreed product, location, and unit rules. It never guesses."
      why="Every supplier can keep its own names while the rest of the company works with one consistent set of names."
      visual={
        <div className="translation-table">
          <div className="translation-head">
            <span>Supplier said</span>
            <span>Rule used</span>
            <span>Hub understands</span>
          </div>
          <TranslationRow
            label="Product"
            source={externalSku}
            rule={snapshot ? `Product map v${snapshot.product_mapping_version}` : "Looking up product…"}
            result={snapshot?.canonical_sku ?? "Waiting…"}
          />
          <TranslationRow
            label="Location"
            source={externalLocation}
            rule={snapshot ? `Location map v${snapshot.warehouse_mapping_version}` : "Looking up location…"}
            result={snapshot?.warehouse_code ?? "Waiting…"}
          />
          <TranslationRow
            label="On hand"
            source={`${String(item?.on_hand ?? "—")} ${String(item?.unit ?? "")}`}
            rule={snapshot ? `Multiply by ${snapshot.units_per_source_unit}` : "Checking units…"}
            result={snapshot ? `${snapshot.canonical_on_hand} units` : "Waiting…"}
          />
          <TranslationRow
            label="Already promised"
            source={`${String(item?.allocated ?? "—")} ${String(item?.unit ?? "")}`}
            rule={snapshot ? `Multiply by ${snapshot.units_per_source_unit}` : "Checking units…"}
            result={snapshot ? `${snapshot.canonical_reserved} units` : "Waiting…"}
          />
        </div>
      }
      output={
        snapshot
          ? `${snapshot.external_sku} at ${snapshot.external_location} now has a precise meaning inside the hub.`
          : event
            ? "The translation rules ran. The final inventory record is being saved."
            : "The worker is preparing the translation."
      }
      event={event}
    />
  );
}

function TranslationRow({
  label,
  source,
  rule,
  result
}: {
  label: string;
  source: string;
  rule: string;
  result: string;
}) {
  return (
    <div className="translation-row">
      <small>{label}</small>
      <strong>{source}</strong>
      <span><ArrowRight size={15} />{rule}</span>
      <strong>{result}</strong>
    </div>
  );
}

function InventoryScene({
  snapshot,
  event,
  outcome
}: {
  snapshot: Snapshot | null;
  event?: OperationEvent;
  outcome: string;
}) {
  const onHand = Number(snapshot?.canonical_on_hand ?? 0);
  const reserved = Number(snapshot?.canonical_reserved ?? 0);
  const available = Math.max(onHand - reserved, 0);
  return (
    <Scene
      title="The translated inventory is saved"
      intro="The company can now search and use the supplier’s update without knowing the supplier’s field names."
      why="Planning, purchasing, reporting, and later calculations can all use the same product and warehouse identities."
      visual={
        snapshot ? (
          <div className="inventory-receipt">
            <div className="receipt-title">
              <PackageCheck size={27} />
              <div><small>Inventory updated</small><strong>{snapshot.canonical_sku}</strong></div>
              <span>Saved</span>
            </div>
            <div className="receipt-location">Warehouse: <strong>{snapshot.warehouse_code}</strong></div>
            <div className="quantity-equation">
              <div><strong>{snapshot.canonical_on_hand}</strong><span>physically present</span></div>
              <b>−</b>
              <div><strong>{snapshot.canonical_reserved}</strong><span>already promised</span></div>
              <b>=</b>
              <div className="available-total"><strong>{available.toFixed(3)}</strong><span>available to use</span></div>
            </div>
          </div>
        ) : (
          <div className="inventory-waiting">The final inventory row is being saved…</div>
        )
      }
      output={
        snapshot
          ? `The update finished as “${humanStatus(outcome)}” with one product changed.`
          : "The worker has not finished writing the final result yet."
      }
      event={event}
    />
  );
}

function Scene({
  title,
  intro,
  why,
  visual,
  output,
  event
}: {
  title: string;
  intro: string;
  why: string;
  visual: ReactNode;
  output: ReactNode;
  event?: OperationEvent;
}) {
  return (
    <article className="guided-scene">
      <header><h2>{title}</h2><p>{intro}</p></header>
      <div className="scene-visual">{visual}</div>
      <div className="scene-explanation">
        <div><small>What came out</small><p>{output}</p></div>
        <div><small>Why this matters</small><p>{why}</p></div>
      </div>
      {event && (
        <details className="technical-details">
          <summary>Technical evidence</summary>
          <dl>
            <div><dt>System piece</dt><dd>{event.component}</dd></div>
            <div><dt>Recorded at</dt><dd>{new Date(event.occurred_at).toLocaleTimeString()}</dd></div>
            {event.evidence_reference && (
              <div><dt>Saved reference</dt><dd><code>{event.evidence_reference}</code></dd></div>
            )}
          </dl>
          <pre>{JSON.stringify(event.details, null, 2)}</pre>
        </details>
      )}
    </article>
  );
}

function JsonDocument({ value }: { value: Record<string, unknown> }) {
  return (
    <div className="json-document">
      <div><FileJson size={17} /><span>supplier-a-update.json</span></div>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function stepForStage(stage: string): number | null {
  if (stage === "request.validated") return 2;
  if (stage === "payload.stored") return 3;
  if (stage === "job.queued" || stage === "job.dispatched") return 4;
  if (stage === "worker.claimed" || stage === "payload.verified") return 5;
  if (stage === "payload.transformed") return 6;
  if (stage === "inventory.committed" || stage === "job.completed") return 7;
  return null;
}

function humanStatus(status: string) {
  if (status === "completed") return "completed successfully";
  if (status === "completed_with_errors") return "completed with some rejected rows";
  if (status === "failed") return "stopped because something was wrong";
  return status.replaceAll("_", " ");
}
