import { ArrowLeft, CheckCircle2, Info } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { RequestType } from "../types/api";
import {
  Button,
  Field,
  PageHeader,
  SubmitForm,
  titleCase,
  useToast,
} from "../components/ui";

type FormDataState = Record<string, string | boolean>;
const defaults: Record<RequestType, FormDataState> = {
  leave: {
    leave_type: "annual",
    start_date: "",
    end_date: "",
    reason: "",
    half_day: false,
    contact_during_leave: "",
  },
  reimbursement: {
    category: "travel",
    amount: "",
    description: "",
    receipt_ref: "",
  },
  it_access: {
    system_name: "",
    access_level: "read",
    duration_days: "",
    justification: "",
  },
  other: {},
};
export function RequestFormPage() {
  const [type, setType] = useState<RequestType>("leave");
  const [data, setData] = useState<FormDataState>(defaults.leave);
  const notify = useToast();
  const nav = useNavigate();
  const cache = useQueryClient();
  const balances = useQuery({
    queryKey: ["leave-balances"],
    queryFn: api.leaveBalances,
    enabled: type === "leave",
  });
  const duration = useMemo(() => {
    if (
      typeof data.start_date !== "string" ||
      typeof data.end_date !== "string" ||
      !data.start_date ||
      !data.end_date
    )
      return 0;
    const start = new Date(data.start_date + "T00:00:00");
    const end = new Date(data.end_date + "T00:00:00");
    if (end < start) return 0;
    let workingDays = 0;
    for (
      const day = new Date(start);
      day <= end;
      day.setDate(day.getDate() + 1)
    ) {
      if (day.getDay() !== 0 && day.getDay() !== 6) workingDays += 1;
    }
    return data.half_day ? 0.5 : workingDays;
  }, [data]);
  const mutation = useMutation({
    mutationFn: async () => {
      const submitted: Record<string, unknown> = { ...data };
      if (type === "reimbursement") submitted.amount = Number(data.amount);
      if (type === "it_access")
        submitted.duration_days = data.duration_days
          ? Number(data.duration_days)
          : null;
      for (const key of Object.keys(submitted))
        if (submitted[key] === "" || submitted[key] === null)
          delete submitted[key];
      return api.submitRequest({
        request_type: type,
        submitted_data: submitted,
      });
    },
    onSuccess: (result) => {
      void cache.invalidateQueries({ queryKey: ["my-requests"] });
      notify("Request submitted for governed evaluation.");
      nav(`/requests`, { state: { requestId: result.id } });
    },
    onError: (e) =>
      notify(e instanceof Error ? e.message : "Submission failed.", "error"),
  });
  function set(key: string, value: string | boolean) {
    setData((v) => ({ ...v, [key]: value }));
  }
  return (
    <>
      <PageHeader
        eyebrow="Structured submission"
        title="New request"
        description="Provide the facts needed for a policy grounded decision."
        actions={
          <Link className="button button-secondary" to="/requests">
            <ArrowLeft size={17} />
            My requests
          </Link>
        }
      />
      <SubmitForm
        className="form-layout"
        onSubmit={() => mutation.mutateAsync()}
      >
        <section className="panel form-main">
          <Field label="Request type">
            <select
              value={type}
              onChange={(e) => {
                const next = e.target.value as RequestType;
                setType(next);
                setData(defaults[next]);
              }}
            >
              <option value="leave">Leave application</option>
              <option value="reimbursement">Expense reimbursement</option>
              <option value="it_access">IT access</option>
            </select>
          </Field>
          {type === "leave" && (
            <>
              <div className="form-grid">
                <Field label="Leave type">
                  <select
                    value={String(data.leave_type)}
                    onChange={(e) => set("leave_type", e.target.value)}
                  >
                    <option value="annual">Annual</option>
                    <option value="sick">Sick</option>
                    <option value="casual">Casual</option>
                    <option value="unpaid">Unpaid</option>
                  </select>
                </Field>
                <Field label="Day arrangement">
                  <select
                    value={data.half_day ? "half" : "full"}
                    onChange={(e) => set("half_day", e.target.value === "half")}
                  >
                    <option value="full">Full day</option>
                    <option value="half">Half day</option>
                  </select>
                </Field>
                <Field label="Start date">
                  <input
                    required
                    type="date"
                    value={String(data.start_date)}
                    onChange={(e) => set("start_date", e.target.value)}
                  />
                </Field>
                <Field label="End date">
                  <input
                    required
                    type="date"
                    min={String(data.start_date)}
                    value={String(data.end_date)}
                    onChange={(e) => set("end_date", e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Reason">
                <textarea
                  required
                  minLength={2}
                  maxLength={1000}
                  value={String(data.reason)}
                  onChange={(e) => set("reason", e.target.value)}
                  placeholder="Briefly explain why you need this leave."
                />
              </Field>
              <Field label="Contact during leave" help="Optional">
                <input
                  value={String(data.contact_during_leave)}
                  onChange={(e) => set("contact_during_leave", e.target.value)}
                />
              </Field>
            </>
          )}
          {type === "reimbursement" && (
            <>
              <div className="form-grid">
                <Field label="Category">
                  <select
                    value={String(data.category)}
                    onChange={(e) => set("category", e.target.value)}
                  >
                    <option value="travel">Travel</option>
                    <option value="medical">Medical</option>
                    <option value="equipment">Equipment</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
                <Field label="Amount (USD)">
                  <input
                    required
                    min="0.01"
                    step="0.01"
                    type="number"
                    value={String(data.amount)}
                    onChange={(e) => set("amount", e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Description">
                <textarea
                  required
                  minLength={5}
                  maxLength={1000}
                  value={String(data.description)}
                  onChange={(e) => set("description", e.target.value)}
                />
              </Field>
              <Field label="Receipt reference" help="Optional">
                <input
                  value={String(data.receipt_ref)}
                  onChange={(e) => set("receipt_ref", e.target.value)}
                />
              </Field>
            </>
          )}
          {type === "it_access" && (
            <>
              <div className="form-grid">
                <Field label="System">
                  <input
                    required
                    minLength={2}
                    value={String(data.system_name)}
                    onChange={(e) => set("system_name", e.target.value)}
                  />
                </Field>
                <Field label="Access level">
                  <select
                    value={String(data.access_level)}
                    onChange={(e) => set("access_level", e.target.value)}
                  >
                    <option value="read">Read</option>
                    <option value="write">Write</option>
                    <option value="admin">Administrator</option>
                  </select>
                </Field>
                <Field
                  label="Duration in days"
                  help="Optional for permanent access"
                >
                  <input
                    min="1"
                    type="number"
                    value={String(data.duration_days)}
                    onChange={(e) => set("duration_days", e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Business justification">
                <textarea
                  required
                  minLength={10}
                  maxLength={1000}
                  value={String(data.justification)}
                  onChange={(e) => set("justification", e.target.value)}
                />
              </Field>
            </>
          )}
          <div className="form-footer">
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Submitting…" : "Submit request"}
            </Button>
          </div>
        </section>
        <aside className="form-aside">
          <div className="soft-card">
            <Info />
            <h2>What happens next</h2>
            <p>
              Your request is checked against current policy. Clear cases can
              resolve automatically; exceptions go to a manager with the
              decision context intact.
            </p>
          </div>
          {type === "leave" && (
            <div className="soft-card">
              <CheckCircle2 />
              <h2>Current balance</h2>
              {balances.isLoading ? (
                <p>Loading balance…</p>
              ) : balances.error ? (
                <p>Balance unavailable.</p>
              ) : (
                <dl>
                  {Object.entries(balances.data ?? {}).map(([k, v]) => (
                    <div key={k}>
                      <dt>{titleCase(k)}</dt>
                      <dd>
                        {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {duration > 0 && (
                <p className="duration-callout">
                  This request covers{" "}
                  <strong>
                    {duration} day{duration === 1 ? "" : "s"}
                  </strong>
                  .
                </p>
              )}
            </div>
          )}
        </aside>
      </SubmitForm>
    </>
  );
}
