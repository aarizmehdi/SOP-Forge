import { Download, FilePlus2, FileUp, Paperclip, Search } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { RequestDetail, RequestItem } from "../types/api";
import {
  Badge,
  Dialog,
  Empty,
  ErrorState,
  KeyValue,
  Loading,
  PageHeader,
  formatDate,
  statusTone,
  titleCase,
  useToast,
} from "../components/ui";

export function RequestsPage() {
  const notify = useToast();
  const cache = useQueryClient();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<RequestDetail | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const query = useQuery({
    queryKey: ["my-requests"],
    queryFn: () => api.requests(100),
  });
  const evidenceUpload = useMutation({
    mutationFn: async ({
      requestId,
      file,
    }: {
      requestId: string;
      file: File;
    }) => {
      const result = await api.uploadRequestEvidence(requestId, file);
      const detail = await api.request(requestId);
      return { detail, result };
    },
    onSuccess: async ({ detail, result }) => {
      setSelected(detail);
      await cache.invalidateQueries({ queryKey: ["my-requests"] });
      notify(result.message);
    },
  });
  const list = useMemo(
    () =>
      query.data?.filter((x) =>
        (x.request_type + " " + x.decision + " " + x.status).includes(
          search.toLowerCase(),
        ),
      ) ?? [],
    [query.data, search],
  );
  async function open(item: RequestItem) {
    setDetailBusy(true);
    try {
      setSelected(await api.request(item.id));
    } catch (e) {
      notify(
        e instanceof Error ? e.message : "Unable to load request.",
        "error",
      );
    } finally {
      setDetailBusy(false);
    }
  }
  async function evidence(id: string) {
    try {
      await api.openEvidence(id);
    } catch (e) {
      notify(
        e instanceof Error ? e.message : "Unable to open evidence.",
        "error",
      );
    }
  }
  async function uploadEvidence(file: File) {
    if (!selected) return;
    await evidenceUpload.mutateAsync({ requestId: selected.id, file });
  }
  return (
    <>
      <PageHeader
        eyebrow="Employee workspace"
        title="My requests"
        description="Track every request from submission through its final decision."
        actions={
          <Link className="button button-primary" to="/request/new">
            <FilePlus2 size={17} />
            New request
          </Link>
        }
      />
      <div className="toolbar">
        <label className="search">
          <Search size={17} />
          <span className="sr-only">Search requests</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by type or status"
          />
        </label>
      </div>
      {query.isLoading ? (
        <Loading label="Loading requests" />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !list.length ? (
        <Empty
          title="No requests found"
          message={
            search
              ? "Try a different search."
              : "Your submitted requests will appear here."
          }
          action={
            !search && (
              <Link className="button button-primary" to="/request/new">
                Submit a request
              </Link>
            )
          }
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Submitted</th>
                <th>Status</th>
                <th>Decision</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {list.map((item) => (
                <tr
                  key={item.id}
                  tabIndex={0}
                  onClick={() => void open(item)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void open(item);
                  }}
                >
                  <td>
                    <strong>{titleCase(item.request_type)}</strong>
                    <small className="mono">{item.id.slice(0, 8)}</small>
                  </td>
                  <td>{formatDate(item.created_at)}</td>
                  <td>
                    <Badge tone={statusTone(item.status)}>
                      {titleCase(item.status)}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={statusTone(item.decision)}>
                      {titleCase(item.decision)}
                    </Badge>
                  </td>
                  <td>
                    {item.has_evidence ? (
                      <span className="with-icon">
                        <Paperclip size={15} />
                        {item.evidence_list.length}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Dialog
        open={!!selected || detailBusy}
        title={
          detailBusy
            ? "Loading request…"
            : `Request · ${selected?.id.slice(0, 8) ?? ""}`
        }
        onClose={() => {
          setSelected(null);
          evidenceUpload.reset();
        }}
        size="lg"
      >
        {detailBusy ? (
          <Loading />
        ) : (
          selected && (
            <RequestDetails
              item={selected}
              openEvidence={evidence}
              uploadEvidence={uploadEvidence}
              uploading={evidenceUpload.isPending}
            />
          )
        )}
      </Dialog>
    </>
  );
}
export function RequestDetails({
  item,
  openEvidence,
  uploadEvidence,
  uploading,
}: {
  item: RequestDetail;
  openEvidence: (id: string) => void;
  uploadEvidence: (file: File) => Promise<void>;
  uploading: boolean;
}) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const canUpload =
    !item.has_evidence &&
    (item.status === "in_progress" || item.status === "escalated");
  async function selectEvidence(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const selectedFile = input.files?.[0];
    input.value = "";
    if (!selectedFile) return;
    const validationError = validateEvidence(selectedFile);
    if (validationError) {
      setUploadError(validationError);
      return;
    }
    setUploadError(null);
    try {
      await uploadEvidence(selectedFile);
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Evidence upload failed.",
      );
    }
  }
  return (
    <div className="detail-stack">
      <div className="detail-summary">
        <div>
          <p className="eyebrow">{titleCase(item.request_type)}</p>
          <h3>{titleCase(item.decision)}</h3>
          <p>Submitted {formatDate(item.created_at)}</p>
        </div>
        <Badge tone={statusTone(item.status)}>{titleCase(item.status)}</Badge>
      </div>
      <dl className="key-grid">
        {Object.entries(item.submitted_data).map(([k, v]) => (
          <KeyValue
            key={k}
            label={titleCase(k)}
            value={
              typeof v === "boolean" ? (v ? "Yes" : "No") : String(v ?? "—")
            }
          />
        ))}
      </dl>
      {canUpload && (
        <section className="request-evidence-upload">
          <h3>Supporting evidence</h3>
          <label className="file-picker" aria-disabled={uploading}>
            <FileUp />
            <span>
              <strong>
                {uploading ? "Uploading evidence…" : "Attach evidence"}
              </strong>
              <small>PDF, JPEG or PNG · maximum 5 MB</small>
            </span>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/jpeg,image/png"
              disabled={uploading}
              onChange={(event) => void selectEvidence(event)}
            />
          </label>
          {uploadError && (
            <p className="inline-error" role="alert">
              {uploadError}
            </p>
          )}
        </section>
      )}
      {item.evidence_list.length > 0 && (
        <section>
          <h3>Supporting evidence</h3>
          <div className="attachment-list">
            {item.evidence_list.map((file) => (
              <button key={file.id} onClick={() => openEvidence(file.id)}>
                <Paperclip />
                <span>
                  <strong>{file.original_filename}</strong>
                  <small>
                    {Math.ceil(file.size_bytes / 1024)} KB · {file.content_type}
                  </small>
                </span>
                <Download />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const MAX_EVIDENCE_SIZE = 5 * 1024 * 1024;
const EVIDENCE_MIME_TYPES = new Set([
  "application/pdf",
  "image/jpeg",
  "image/jpg",
  "image/png",
]);

function validateEvidence(file: File) {
  if (!file.size) return "Choose a nonempty PDF, JPEG, or PNG file to upload.";
  if (file.size > MAX_EVIDENCE_SIZE)
    return "Evidence must be no larger than 5 MB.";
  if (
    !EVIDENCE_MIME_TYPES.has(file.type) ||
    !/\.(pdf|jpe?g|png)$/i.test(file.name)
  )
    return "Evidence must be a PDF, JPEG, or PNG file.";
  return null;
}
