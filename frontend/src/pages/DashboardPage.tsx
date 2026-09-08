import {
  Activity,
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
  return user?.role === "executive" || user?.role === "admin" ? (
    <ExecutiveCommandCenter />
  ) : (
    <TeamActionCenter name={user?.name} />
  );
}

function ExecutiveCommandCenter() {
  const summary = useQuery({
    queryKey: ["audit-summary"],
    queryFn: api.auditSummary,
  });
  const logs = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => api.audits({ limit: 6 }),
  });
  if (summary.isLoading || logs.isLoading)
    return <Loading label="Preparing the command center" />;
  const error = summary.error || logs.error;
  if (error)
    return (
      <ErrorState
        error={error}
        retry={() => {
          void summary.refetch();
          void logs.refetch();
        }}
      />
    );

  const total = summary.data?.total_entries ?? 0;
  const rateBase = total || 1;
  const aiResolutionRate =
    Math.round(((summary.data?.auto_approved ?? 0) / rateBase) * 100) +
    Math.round(((summary.data?.auto_rejected ?? 0) / rateBase) * 100);
  const escalationRate = Math.round(
    ((summary.data?.escalated ?? 0) / rateBase) * 100,
  );

  return (
    <>
      <PageHeader
        eyebrow="Decision operations"
        title="Executive Command Center"
        description="A source-backed view of automated decisions, escalations, service levels, and system activity."
      />
      <section className="metric-grid">
        <Metric
          icon={<ShieldCheck />}
          value={`${aiResolutionRate}%`}
          label="AI Resolution Rate"
          detail="Requests handled without human input"
        />
        <Metric
          icon={<Activity />}
          value={total}
          label="Total Volume"
          detail="Total organizational requests processed"
        />
        <Metric
          icon={<AlertTriangle />}
          value={`${escalationRate}%`}
          label="Escalation Rate"
          detail="Requests routed to manual review"
          tone={escalationRate > 0 ? "warning" : undefined}
        />
        <Metric
          icon={<Clock3 />}
          value={summary.data?.sla_breaches ?? 0}
          label="SLA Breaches"
          detail="Manager reviews exceeding time limits"
          tone={(summary.data?.sla_breaches ?? 0) > 0 ? "danger" : undefined}
        />
      </section>
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Activity</p>
            <h2>Recent System Activity</h2>
          </div>
          <Link to="/audit">
            Audit trail <ArrowUpRight size={15} />
          </Link>
        </div>
        {logs.data?.slice(0, 6).map((log) => (
          <div className="activity-row" key={log.id}>
            <span className="timeline-dot" />
            <span>
              <strong>{titleCase(log.event_type)}</strong>
              <small>
                {log.actor_name ?? "AI Engine"} · {log.actor_role ?? "System"}
              </small>
              <small>{log.evaluation_reasoning ?? "No details provided"}</small>
            </span>
            <small className="row-end">{formatDate(log.created_at)}</small>
          </div>
        ))}
        {!logs.data?.length && (
          <div className="compact-empty">
            <Activity />
            <p>No system activity has been recorded.</p>
          </div>
        )}
      </section>
    </>
  );
}

function TeamActionCenter({ name }: { name?: string }) {
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
    incidents.data?.filter((item) => item.status === "open").length ?? 0;
  return (
    <>
      <PageHeader
        eyebrow="Decision operations"
        title="Team Action Center"
        description={`Welcome back${name ? `, ${name.split(" ")[0]}` : ""}. Review governed requests, service levels, and exceptions.`}
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
  value: React.ReactNode;
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
