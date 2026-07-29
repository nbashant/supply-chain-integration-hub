import {
  AlertTriangle,
  Check,
  Clock3,
  LoaderCircle,
  XCircle
} from "lucide-react";
import type { ImportStatus, OperationEvent } from "../types";

export function StatusPill({ status }: { status: string }) {
  const safe = status.replaceAll("_", "-");
  return (
    <span className={`pill pill--${safe}`}>
      <span />
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function EventTimeline({
  events,
  empty = "Events will appear here as the real workflow moves."
}: {
  events: OperationEvent[];
  empty?: string;
}) {
  if (!events.length) {
    return <div className="empty-state">{empty}</div>;
  }
  return (
    <ol className="event-timeline">
      {events.map((event) => {
        const Icon =
          event.status === "failed"
            ? XCircle
            : event.status === "warning"
              ? AlertTriangle
              : event.status === "running"
                ? LoaderCircle
                : Check;
        return (
          <li key={event.id} className={`event event--${event.status}`}>
            <span className="event-marker">
              <Icon size={16} />
            </span>
            <div className="event-copy">
              <div className="event-heading">
                <strong>{event.title}</strong>
                <span>{event.component}</span>
              </div>
              <p>{event.explanation}</p>
              <div className="event-evidence">
                <Clock3 size={13} />
                {formatTime(event.occurred_at)}
                {event.evidence_reference && (
                  <code>{event.evidence_reference}</code>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function LoadingBlock({ label = "Loading real hub data…" }: { label?: string }) {
  return (
    <div className="loading-block">
      <LoaderCircle className="spin" size={20} />
      {label}
    </div>
  );
}

export function formatTime(value: string | null) {
  if (!value) return "Not yet";
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

export function formatDate(value: string | null) {
  if (!value) return "Not yet";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function statusStep(status: ImportStatus) {
  if (status === "queued") return 1;
  if (status === "processing") return 2;
  return 3;
}
