import { Download, Eye, ScrollText, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../lib/api";
import type { AuditLog } from "../types/api";
import {
  Badge,
  Button,
  Dialog,
  Empty,
  ErrorState,
  KeyValue,
  Loading,
  PageHeader,
  formatDate,
  statusTone,
  titleCase,
} from "../components/ui";
export function AuditPage() {
  const [event, setEvent] = useState("");
  const [days, setDays] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditLog | null>(null);
  const summary = useQuery({
    queryKey: ["audit-summary"],
    queryFn: api.auditSummary,
  });
  const logs = useQuery({
    queryKey: ["audit", event, days],
    queryFn: () =>
      api.audits({
        limit: 200,
        ...(event ? { event_type: event } : {}),
        ...(days ? { days } : {}),
      }),
  });
  const list = useMemo(
    () =>
      logs.data?.filter((x) =>
        `${x.event_type} ${x.actor_name} ${x.decision} ${x.request_id}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ) ?? [],
    [logs.data, search],
  );
  function exportCsv() {
    const quote = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
    const rows = [
      [
        "Audit ID",
        "Request ID",
        "Event",
        "Decision",
        "Actor",
        "Role",
        "Timestamp",
      ],
      ...list.map((x) => [
        x.id,
        x.request_id,
        x.event_type,
        x.decision,
        x.actor_name,
        x.actor_role,
        x.created_at,
      ]),
    ];
    const url = URL.createObjectURL(
      new Blob([rows.map((r) => r.map(quote).join(",")).join("\n")], {
        type: "text/csv",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `sop-forge-audit-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageHeader
        eyebrow="Immutable ledger"
        title="Audit trail"
        description="Trace automated decisions, manager actions, overrides, and policy changes."
        actions={
          <Button
            variant="secondary"
            onClick={exportCsv}
            disabled={!list.length}
          >
            <Download />
            Export CSV
          </Button>
        }
      />
      {summary.data && (
        <section className="summary-strip">
          <div>
            <strong>{summary.data.total_entries}</strong>
            <span>Total records</span>
          </div>
          <div>
            <strong>{summary.data.auto_approved}</strong>
            <span>Auto approved</span>
          </div>
          <div>
            <strong>{summary.data.auto_rejected}</strong>
            <span>Auto rejected</span>
          </div>
          <div>
            <strong>{summary.data.escalated}</strong>
            <span>Escalated</span>
          </div>
          <div>
            <strong>{summary.data.overridden}</strong>
            <span>Overrides</span>
          </div>
          <div>
            <strong>{summary.data.sla_breaches}</strong>
            <span>SLA breaches</span>
          </div>
        </section>
      )}
      <div className="toolbar">
        <label className="search">
          <Search />
          <input
            aria-label="Search audit trail"
            placeholder="Search event, actor or request"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter event"
          value={event}
          onChange={(e) => setEvent(e.target.value)}
        >
          <option value="">All events</option>
          <option value="auto_approved">Auto approved</option>
          <option value="auto_rejected">Auto rejected</option>
          <option value="escalated">Escalated</option>
          <option value="executive_override">Executive override</option>
        </select>
        <select
          aria-label="Filter time"
          value={days}
          onChange={(e) => setDays(e.target.value)}
        >
          <option value="">All time</option>
          <option value="30">Past month</option>
          <option value="90">Past 3 months</option>
          <option value="365">Past year</option>
        </select>
      </div>
      {logs.isLoading ? (
        <Loading />
      ) : logs.error ? (
        <ErrorState error={logs.error} retry={() => void logs.refetch()} />
      ) : !list.length ? (
        <Empty message="No audit records match these filters." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Decision</th>
                <th>Actor</th>
                <th>Request</th>
                <th>Time</th>
                <th>
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((log) => (
                <tr key={log.id}>
                  <td>
                    <Badge
                      tone={statusTone(log.event_type.replace("auto_", ""))}
                    >
                      {titleCase(log.event_type)}
                    </Badge>
                  </td>
                  <td>{log.decision ? titleCase(log.decision) : "Recorded"}</td>
                  <td>
                    <strong>{log.actor_name ?? "AI Engine"}</strong>
                    <small>{titleCase(log.actor_role ?? "system")}</small>
                  </td>
                  <td className="mono">{log.request_id?.slice(0, 8) ?? "—"}</td>
                  <td>{formatDate(log.created_at)}</td>
                  <td>
                    <Button
                      variant="ghost"
                      aria-label="Inspect audit record"
                      onClick={() => setSelected(log)}
                    >
                      <Eye />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Dialog
        open={!!selected}
        title="Audit record"
        onClose={() => setSelected(null)}
        size="lg"
      >
        {selected && (
          <div className="detail-stack">
            <dl className="key-grid">
              <KeyValue label="Event" value={titleCase(selected.event_type)} />
              <KeyValue
                label="Decision"
                value={titleCase(selected.decision ?? "recorded")}
              />
              <KeyValue
                label="Actor"
                value={selected.actor_name ?? "AI Engine"}
              />
              <KeyValue
                label="Timestamp"
                value={formatDate(selected.created_at)}
              />
              <KeyValue
                label="Request ID"
                value={
                  <span className="mono">{selected.request_id ?? "—"}</span>
                }
              />
              <KeyValue
                label="Confidence"
                value={
                  selected.confidence === null
                    ? "—"
                    : `${Math.round(selected.confidence * 100)}%`
                }
              />
            </dl>
            {selected.override_justification && (
              <section className="reasoning">
                <ScrollText />
                <div>
                  <h3>Override justification</h3>
                  <p>{selected.override_justification}</p>
                </div>
              </section>
            )}
            {selected.evaluation_reasoning && (
              <section>
                <h3>Evaluation summary</h3>
                <p>{selected.evaluation_reasoning}</p>
              </section>
            )}
            <section>
              <h3>Ledger payload</h3>
              <pre>{JSON.stringify(selected.details ?? {}, null, 2)}</pre>
            </section>
          </div>
        )}
      </Dialog>
    </>
  );
}
