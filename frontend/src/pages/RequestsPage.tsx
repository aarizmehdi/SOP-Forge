import { Download, FilePlus2, Paperclip, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { RequestDetail, RequestItem } from "../types/api";
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
  useToast,
} from "../components/ui";

export function RequestsPage() {
  const notify = useToast();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<RequestDetail | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const query = useQuery({
    queryKey: ["my-requests"],
    queryFn: () => api.requests(100),
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
        onClose={() => setSelected(null)}
        size="lg"
      >
        {detailBusy ? (
          <Loading />
        ) : (
          selected && <RequestDetails item={selected} openEvidence={evidence} />
        )}
      </Dialog>
    </>
  );
}
export function RequestDetails({
  item,
  openEvidence,
}: {
  item: RequestDetail;
  openEvidence: (id: string) => void;
}) {
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
