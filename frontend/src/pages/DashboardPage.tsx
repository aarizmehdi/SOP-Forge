import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Gauge,
  ShieldCheck,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import {
  Badge,
  ErrorState,
  Loading,
  PageHeader,
  formatDate,
  titleCase,
} from "../components/ui";

export function DashboardPage() {
  const { user } = useAuth();
  const reviews = useQuery({
    queryKey: ["reviews", "escalated"],
    queryFn: () => api.reviewQueue("escalated"),
  });
  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: api.incidents,
  });
  const summary = useQuery({
    queryKey: ["audit-summary"],
    queryFn: api.auditSummary,
  });
  const logs = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => api.audits({ limit: 6 }),
  });
  if (reviews.isLoading || incidents.isLoading || summary.isLoading)
    return <Loading label="Preparing your overview" />;
  const error = reviews.error || incidents.error || summary.error;
  if (error)
    return (
      <ErrorState
        error={error}
        retry={() => {
          void reviews.refetch();
          void incidents.refetch();
          void summary.refetch();
        }}
      />
    );
  const openIncidents =
    incidents.data?.filter((x) => x.status === "open").length ?? 0;
  return (
    <>
      <PageHeader
        eyebrow="Decision operations"
        title={`Good day, ${user?.name.split(" ")[0]}`}
        description="A current view of governed requests, service levels, and exceptions."
      />
      <section className="metric-grid">
        <Metric
          icon={<Clock3 />}
          value={reviews.data?.length ?? 0}
          label="Awaiting review"
          detail="Manager action required"
        />
        <Metric
          icon={<AlertTriangle />}
          value={openIncidents}
          label="Open incidents"
          detail="Flagged conversations"
          tone={openIncidents ? "warning" : undefined}
        />
        <Metric
          icon={<CheckCircle2 />}
          value={summary.data?.auto_approved ?? 0}
          label="Auto approved"
          detail="Policy rules satisfied"
        />
        <Metric
          icon={<Gauge />}
          value={summary.data?.sla_breaches ?? 0}
          label="SLA breaches"
          detail="Recorded in audit"
          tone={(summary.data?.sla_breaches ?? 0) > 0 ? "danger" : undefined}
        />
      </section>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Priority queue</p>
              <h2>Requests that need attention</h2>
            </div>
            <Link to="/review">
              Open queue <ArrowUpRight size={15} />
            </Link>
          </div>
          {reviews.data?.slice(0, 5).map((item) => (
            <Link className="activity-row" to="/review" key={item.id}>
              <span className="activity-icon">
                <ShieldCheck />
              </span>
              <span>
                <strong>{item.employee_name}</strong>
                <small>
                  {titleCase(item.request_type)} ·{" "}
                  {item.department ?? "Unassigned"}
                </small>
              </span>
              <span className="row-end">
                <Badge tone="warning">
                  {item.sla_remaining_minutes === null
                    ? "No SLA"
                    : `${item.sla_remaining_minutes} min`}
                </Badge>
                <small>{formatDate(item.created_at)}</small>
              </span>
            </Link>
          ))}
          {!reviews.data?.length && (
            <div className="compact-empty">
              <CheckCircle2 />
              <p>The review queue is clear.</p>
            </div>
          )}
        </section>
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Activity</p>
              <h2>Recent governed events</h2>
            </div>
            <Link to="/audit">
              Audit trail <ArrowUpRight size={15} />
            </Link>
          </div>
          {logs.isLoading ? (
            <Loading />
          ) : (
            logs.data?.slice(0, 6).map((log) => (
              <div className="activity-row" key={log.id}>
                <span className="timeline-dot" />
                <span>
                  <strong>{titleCase(log.event_type)}</strong>
                  <small>
                    {log.actor_name ?? "System"} ·{" "}
                    {log.decision ? titleCase(log.decision) : "Recorded"}
                  </small>
                </span>
                <small className="row-end">{formatDate(log.created_at)}</small>
              </div>
            ))
          )}
        </section>
      </div>
    </>
  );
}
function Metric({
  icon,
  value,
  label,
  detail,
  tone,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={`metric ${tone ?? ""}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
        <small>{detail}</small>
      </div>
    </article>
  );
}
