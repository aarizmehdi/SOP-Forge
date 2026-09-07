import {
  BookOpen,
  Boxes,
  Edit3,
  Eye,
  FilePlus2,
  Search,
  ShieldOff,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../lib/api";
import type { SopDocument, SopDocumentListItem } from "../types/api";
import {
  Badge,
  Button,
  ConfirmDialog,
  Dialog,
  Empty,
  ErrorState,
  Field,
  Loading,
  PageHeader,
  SubmitForm,
  formatDate,
  statusTone,
  titleCase,
  useToast,
} from "../components/ui";
export function AdminPage() {
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(true);
  const [dialog, setDialog] = useState<
    "create" | "view" | "edit" | "chunks" | null
  >(null);
  const [selected, setSelected] = useState<SopDocumentListItem | null>(null);
  const [deactivate, setDeactivate] = useState<SopDocumentListItem | null>(
    null,
  );
  const query = useQuery({
    queryKey: ["policies", showInactive],
    queryFn: () => api.policies(!showInactive),
  });
  const list = useMemo(
    () =>
      query.data?.filter((x) =>
        `${x.title} ${x.category}`.toLowerCase().includes(search.toLowerCase()),
      ) ?? [],
    [query.data, search],
  );
  function open(item: SopDocumentListItem, view: typeof dialog) {
    setSelected(item);
    setDialog(view);
  }
  return (
    <>
      <PageHeader
        eyebrow="Policy operations"
        title="Policy library"
        description="Manage the source documents used by governed retrieval and decision workflows."
        actions={
          <Button
            onClick={() => {
              setSelected(null);
              setDialog("create");
            }}
          >
            <FilePlus2 />
            New policy
          </Button>
        }
      />
      <div className="toolbar">
        <label className="search">
          <Search />
          <input
            aria-label="Search policies"
            placeholder="Search policies"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Show inactive
        </label>
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !list.length ? (
        <Empty message="No policies match this view." />
      ) : (
        <div className="policy-grid">
          {list.map((item) => (
            <article key={item.id}>
              <header>
                <div className="policy-icon">
                  <BookOpen />
                </div>
                <Badge tone={item.is_active ? "success" : "neutral"}>
                  {item.is_active ? "Active" : "Inactive"}
                </Badge>
              </header>
              <p className="eyebrow">
                {titleCase(item.category)} · v{item.version}
              </p>
              <h2>{item.title}</h2>
              <p>Updated {formatDate(item.updated_at)}</p>
              <footer>
                <Button variant="ghost" onClick={() => open(item, "view")}>
                  <Eye />
                  Read
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => open(item, "edit")}
                  disabled={!item.is_active}
                >
                  <Edit3 />
                  Edit
                </Button>
                <Button variant="ghost" onClick={() => open(item, "chunks")}>
                  <Boxes />
                  Chunks
                </Button>
                {item.is_active && (
                  <Button variant="ghost" onClick={() => setDeactivate(item)}>
                    <ShieldOff />
                    Deactivate
                  </Button>
                )}
              </footer>
            </article>
          ))}
        </div>
      )}
      <PolicyDialog
        mode={dialog}
        item={selected}
        close={() => setDialog(null)}
      />
      <DeactivateDialog item={deactivate} close={() => setDeactivate(null)} />
    </>
  );
}
function PolicyDialog({
  mode,
  item,
  close,
}: {
  mode: "create" | "view" | "edit" | "chunks" | null;
  item: SopDocumentListItem | null;
  close: () => void;
}) {
  const detail = useQuery({
    queryKey: ["policy", item?.id],
    queryFn: () => api.policy(item!.id),
    enabled: !!item && (mode === "view" || mode === "edit"),
  });
  const chunks = useQuery({
    queryKey: ["policy-chunks", item?.id],
    queryFn: () => api.policyChunks(item!.id),
    enabled: !!item && mode === "chunks",
  });
  if (!mode) return null;
  return (
    <Dialog
      open
      title={
        mode === "create"
          ? "Create policy"
          : mode === "edit"
            ? "Edit policy"
            : mode === "chunks"
              ? "Embedded chunks"
              : "Policy document"
      }
      onClose={close}
      size="lg"
    >
      {mode === "create" ? (
        <PolicyForm close={close} />
      ) : mode === "chunks" ? (
        chunks.isLoading ? (
          <Loading />
        ) : chunks.error ? (
          <ErrorState error={chunks.error} />
        ) : (
          <div className="chunk-list">
            {chunks.data?.map((c) => (
              <article key={c.id}>
                <header>
                  <strong>Chunk {c.chunk_index + 1}</strong>
                  <Badge tone={c.has_embedding ? "success" : "warning"}>
                    {c.has_embedding ? "Embedded" : "No embedding"}
                  </Badge>
                </header>
                <p>{c.chunk_text}</p>
              </article>
            ))}
          </div>
        )
      ) : detail.isLoading ? (
        <Loading />
      ) : detail.error ? (
        <ErrorState error={detail.error} />
      ) : mode === "edit" ? (
        <PolicyForm policy={detail.data} close={close} />
      ) : (
        detail.data && (
          <div className="document-view">
            <div>
              <Badge tone={detail.data.is_active ? "success" : "neutral"}>
                {detail.data.is_active ? "Active" : "Inactive"}
              </Badge>
              <span>
                {titleCase(detail.data.category)} · Version{" "}
                {detail.data.version} · {detail.data.chunk_count ?? 0} chunks
              </span>
            </div>
            <h2>{detail.data.title}</h2>
            <pre>{detail.data.content_text}</pre>
          </div>
        )
      )}
    </Dialog>
  );
}
function PolicyForm({
  policy,
  close,
}: {
  policy?: SopDocument;
  close: () => void;
}) {
  const [title, setTitle] = useState(policy?.title ?? "");
  const [category, setCategory] = useState(policy?.category ?? "");
  const [content, setContent] = useState(policy?.content_text ?? "");
  const notify = useToast();
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      policy
        ? api.updatePolicy(policy.id, {
            title,
            category,
            content_text: content,
          })
        : api.createPolicy({ title, category, content_text: content }),
    onSuccess: (r) => {
      notify(`${r.title} saved and indexed.`);
      void cache.invalidateQueries({ queryKey: ["policies"] });
      close();
    },
    onError: (e) =>
      notify(
        e instanceof Error ? e.message : "Unable to save policy.",
        "error",
      ),
  });
  return (
    <SubmitForm className="policy-form" onSubmit={() => mutation.mutateAsync()}>
      <Field label="Title">
        <input
          required
          minLength={3}
          maxLength={500}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </Field>
      <Field label="Category" help="Examples: leave, reimbursement, it_access">
        <input
          required
          minLength={2}
          maxLength={100}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />
      </Field>
      <Field
        label="Full policy text"
        help={`${content.length} characters · minimum 50`}
      >
        <textarea
          className="policy-editor"
          required
          minLength={50}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </Field>
      <div className="dialog-actions">
        <Button variant="secondary" type="button" onClick={close}>
          Cancel
        </Button>
        <Button disabled={mutation.isPending}>
          {mutation.isPending ? "Saving and indexing…" : "Save policy"}
        </Button>
      </div>
    </SubmitForm>
  );
}
function DeactivateDialog({
  item,
  close,
}: {
  item: SopDocumentListItem | null;
  close: () => void;
}) {
  const cache = useQueryClient();
  const notify = useToast();
  const mutation = useMutation({
    mutationFn: () => api.deactivatePolicy(item!.id),
    onSuccess: (r) => {
      notify(r.message);
      void cache.invalidateQueries({ queryKey: ["policies"] });
      close();
    },
    onError: (e) =>
      notify(
        e instanceof Error ? e.message : "Unable to deactivate policy.",
        "error",
      ),
  });
  return (
    <ConfirmDialog
      open={!!item}
      title="Deactivate policy?"
      message={`“${item?.title ?? ""}” will stop participating in active policy retrieval. Its history remains available.`}
      confirmLabel="Deactivate"
      danger
      onClose={close}
      onConfirm={() => mutation.mutate()}
    />
  );
}
