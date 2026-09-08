import {
  Clock3,
  Eye,
  FileCheck2,
  Paperclip,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import type { Decision, ReviewItem } from "../types/api";
import {
  Badge,
  Button,
  Dialog,
  Empty,
  ErrorState,
  Field,
  KeyValue,
  Loading,
  PageHeader,
  SubmitForm,
  formatDate,
  statusTone,
  titleCase,
  useToast,
} from "../components/ui";

type ReviewFilter = "escalated" | "resolved" | "overridden" | "all";

export function ReviewPage() {
  const { user } = useAuth();
  const [filter, setFilter] = useState<ReviewFilter>("escalated");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [mode, setMode] = useState<"detail" | "decide" | "override">("detail");
  const backendFilter =
    filter === "resolved" || filter === "overridden" ? "resolved" : filter;
  const query = useQuery({
    queryKey: ["reviews", filter],
    queryFn: () => api.reviewQueue(backendFilter),
  });
  const list = useMemo(
    () =>
      query.data?.filter((item) => {
        const statusMatches = filter === "all" ? true : item.status === filter;
        const searchMatches =
          `${item.employee_name} ${item.employee_id_code} ${item.request_type}`
            .toLowerCase()
            .includes(search.toLowerCase());
        return statusMatches && searchMatches;
      }) ?? [],
    [filter, query.data, search],
  );
  return (
    <>
      <PageHeader
        eyebrow="Human review"
        title="Review queue"
        description="Inspect policy context, evidence, and exceptions before recording a decision."
      />
      <div className="toolbar">
        <label className="search">
          <Search />
          <input
            aria-label="Search review queue"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search employee or request"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as ReviewFilter)}
          >
            <option value="escalated">Awaiting review</option>
            <option value="resolved">Resolved</option>
            <option value="overridden">Overridden</option>
            <option value="all">All</option>
          </select>
        </label>
      </div>
      {query.isLoading ? (
        <Loading label="Loading review queue" />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !list.length ? (
        <Empty
          title="Queue clear"
          message="No requests match the current view."
        />
      ) : (
        <div className="review-list">
          {list.map((item) => (
            <article className="review-card" key={item.id}>
              <div className="review-person">
                <div className="avatar">
                  {item.employee_name
                    .split(" ")
                    .map((x) => x[0])
                    .join("")
                    .slice(0, 2)}
                </div>
                <div>
                  <strong>{item.employee_name}</strong>
                  <span>
                    {item.employee_id_code} ·{" "}
                    {item.department ?? "No department"}
                  </span>
                </div>
              </div>
              <div>
                <p className="eyebrow">{titleCase(item.request_type)}</p>
                <strong>{summary(item.submitted_data)}</strong>
                <span>Submitted {formatDate(item.created_at)}</span>
              </div>
              <div className="review-sla">
                <Clock3 />
                <strong>
                  {item.sla_remaining_minutes === null
                    ? "No SLA"
                    : `${item.sla_remaining_minutes} min`}
                </strong>
                <span>remaining</span>
              </div>
              <div>
                <Badge tone={statusTone(item.status)}>
                  {titleCase(item.status)}
                </Badge>
                {item.has_evidence && (
                  <span className="with-icon">
                    <Paperclip />
                    Evidence
                  </span>
                )}
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  setSelected(item);
                  setMode("detail");
                }}
              >
                <Eye />
                Review
              </Button>
            </article>
          ))}
        </div>
      )}
      <Dialog
        open={!!selected}
        title={
          mode === "detail"
            ? "Review request"
            : mode === "override"
              ? "Executive override"
              : "Record decision"
        }
        onClose={() => setSelected(null)}
        size="lg"
      >
        {selected && mode === "detail" && (
          <ReviewDetail
            item={selected}
            canDecide={selected.status === "escalated"}
            canOverride={
              (user?.role === "executive" || user?.role === "admin") &&
              selected.status !== "overridden"
            }
            onDecide={() => setMode("decide")}
            onOverride={() => setMode("override")}
          />
        )}{" "}
        {selected && mode === "decide" && (
          <DecisionForm
            item={selected}
            override={false}
            done={() => setSelected(null)}
          />
        )}{" "}
        {selected && mode === "override" && (
          <DecisionForm
            item={selected}
            override
            done={() => setSelected(null)}
          />
        )}
      </Dialog>
    </>
  );
}
function summary(data: Record<string, unknown>) {
  return String(
    data.reason ??
      data.description ??
      data.justification ??
      data.system_name ??
      "Policy request",
  );
}
function ReviewDetail({
  item,
  canDecide,
  canOverride,
  onDecide,
  onOverride,
}: {
  item: ReviewItem;
  canDecide: boolean;
  canOverride: boolean;
  onDecide: () => void;
  onOverride: () => void;
}) {
  const notify = useToast();
  return (
    <div className="detail-stack">
      <div className="review-hero">
        <div>
          <p className="eyebrow">{titleCase(item.request_type)}</p>
          <h3>{item.employee_name}</h3>
          <p>
            {item.employee_id_code} · {item.department ?? "No department"}
          </p>
        </div>
        <div>
          <Badge tone={statusTone(item.ai_decision)}>
            AI: {titleCase(item.ai_decision)}
          </Badge>
          {item.ai_confidence !== null && (
            <span>{Math.round(item.ai_confidence * 100)}% confidence</span>
          )}
        </div>
      </div>
      <dl className="key-grid">
        {Object.entries(item.submitted_data).map(([k, v]) => (
          <KeyValue key={k} label={titleCase(k)} value={String(v ?? "—")} />
        ))}
      </dl>
      {item.evaluation_reasoning && (
        <section className="reasoning">
          <ShieldAlert />
          <div>
            <h3>Evaluation context</h3>
            <p>{item.evaluation_reasoning}</p>
          </div>
        </section>
      )}
      {item.policy_refs?.length ? (
        <section>
          <h3>Policy references</h3>
          <div className="chips">
            {[
              ...new Set(
                item.policy_refs.map((x) => x.replace(/:\s*chunk\s*\d+/gi, "")),
              ),
            ].map((x) => (
              <Badge key={x}>{x}</Badge>
            ))}
          </div>
        </section>
      ) : null}
      {item.evidence_list?.length ? (
        <section>
          <h3>Evidence</h3>
          <div className="attachment-list">
            {item.evidence_list.map((e) => (
              <button
                key={e.id}
                onClick={() =>
                  void api
                    .openEvidence(e.id)
                    .catch((err) =>
                      notify(
                        err instanceof Error
                          ? err.message
                          : "Unable to open file.",
                        "error",
                      ),
                    )
                }
              >
                <FileCheck2 />
                <span>
                  <strong>{e.original_filename}</strong>
                  <small>{Math.ceil(e.size_bytes / 1024)} KB</small>
                </span>
                <Eye />
              </button>
            ))}
          </div>
        </section>
      ) : null}
      <div className="dialog-actions">
        {canDecide && (
          <Button variant="secondary" onClick={onDecide}>
            Manager decision
          </Button>
        )}
        {canOverride && (
          <Button onClick={onOverride}>Executive override</Button>
        )}
      </div>
    </div>
  );
}
function DecisionForm({
  item,
  override,
  done,
}: {
  item: ReviewItem;
  override: boolean;
  done: () => void;
}) {
  const [value, setValue] = useState<Decision>("approved");
  const [comment, setComment] = useState("");
  const notify = useToast();
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      override
        ? api.override(item.id, value, comment)
        : api.decide(item.id, value, comment),
    onSuccess: (r) => {
      notify(r.message);
      void cache.invalidateQueries({ queryKey: ["reviews"] });
      void cache.invalidateQueries({ queryKey: ["audit"] });
      done();
    },
    onError: (e) =>
      notify(e instanceof Error ? e.message : "Decision failed.", "error"),
  });
  return (
    <SubmitForm
      className="decision-form"
      onSubmit={() => mutation.mutateAsync()}
    >
      <p>
        {override
          ? "Overrides are recorded permanently with your justification."
          : "This action updates the request and its audit trail."}
      </p>
      <Field label="Decision">
        <select
          value={value}
          onChange={(e) => setValue(e.target.value as Decision)}
        >
          <option value="approved">Approve</option>
          <option value="rejected">Reject</option>
          {!override && (
            <option value="routed">Request more information</option>
          )}
        </select>
      </Field>
      <Field
        label={override ? "Mandatory justification" : "Review comment"}
        help={`Minimum ${override ? 10 : 5} characters`}
      >
        <textarea
          required
          minLength={override ? 10 : 5}
          maxLength={2000}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Field>
      <div className="dialog-actions">
        <Button disabled={mutation.isPending}>
          {mutation.isPending
            ? "Recording…"
            : override
              ? "Apply override"
              : "Record decision"}
        </Button>
      </div>
    </SubmitForm>
  );
}
