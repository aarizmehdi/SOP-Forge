import { CheckCircle2, MessageSquareWarning, ShieldAlert } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import type { Incident } from "../types/api";
import {
  Badge,
  Button,
  ConfirmDialog,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  formatDate,
  statusTone,
  titleCase,
  useToast,
} from "../components/ui";
export function IncidentsPage() {
  const [selected, setSelected] = useState<Incident | null>(null);
  const query = useQuery({ queryKey: ["incidents"], queryFn: api.incidents });
  const cache = useQueryClient();
  const notify = useToast();
  const mutation = useMutation({
    mutationFn: (id: string) => api.dismissIncident(id),
    onSuccess: () => {
      notify("Incident marked as reviewed.");
      setSelected(null);
      void cache.invalidateQueries({ queryKey: ["incidents"] });
    },
    onError: (e) =>
      notify(e instanceof Error ? e.message : "Update failed.", "error"),
  });
  return (
    <>
      <PageHeader
        eyebrow="Protected review"
        title="Conversation incidents"
        description="Review conversations flagged for security, conduct, or policy bypass concerns."
      />
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.data?.length ? (
        <Empty
          title="No incidents"
          message="Flagged conversations will appear here."
        />
      ) : (
        <div className="incident-list">
          {query.data.map((item) => (
            <article
              className={item.status === "reviewed" ? "reviewed" : ""}
              key={item.id}
            >
              <header>
                <div className="incident-icon">
                  <ShieldAlert />
                </div>
                <div>
                  <p className="eyebrow">{titleCase(item.incident_type)}</p>
                  <h2>Employee {item.employee_id.slice(0, 8)}</h2>
                  <p>{formatDate(item.created_at)}</p>
                </div>
                <Badge tone={statusTone(item.status)}>
                  {titleCase(item.status)}
                </Badge>
              </header>
              <section>
                <span>Captured message</span>
                <blockquote>{item.message}</blockquote>
              </section>
              {item.ai_reasoning && (
                <section>
                  <span>Detection context</span>
                  <p>{item.ai_reasoning}</p>
                </section>
              )}
              <footer>
                <span>
                  {Math.round(item.confidence * 100)}% detection confidence
                </span>
                {item.status === "open" && (
                  <Button variant="secondary" onClick={() => setSelected(item)}>
                    <CheckCircle2 />
                    Mark reviewed
                  </Button>
                )}
              </footer>
            </article>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={!!selected}
        title="Mark incident as reviewed?"
        message="This records the incident as reviewed. It remains available in the incident history."
        confirmLabel="Mark reviewed"
        onClose={() => setSelected(null)}
        onConfirm={() => selected && mutation.mutate(selected.id)}
      />
    </>
  );
}
