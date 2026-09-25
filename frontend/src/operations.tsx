import { useEffect, useState } from "react";
import { Play, ShieldEllipsis } from "lucide-react";
import { api } from "./api";
import { Badge, dateTime, Empty, ErrorBox, Field, Modal } from "./components";
import type { Context } from "./App";

type Incident = {
  id: string;
  title: string;
  status: string;
  severity: string;
  details: Record<string, unknown>;
  decision: string;
  created_at: string;
};
type Jobs = {
  counts: Record<string, number>;
  provider: string;
  items: {
    id: string;
    event_type: string;
    state: string;
    attempts: number;
    outcome: string;
    created_at: string;
  }[];
};
export function OperationsPanel(ctx: Context) {
  const [jobs, setJobs] = useState<Jobs | null>(null),
    [signals, setSignals] = useState<Incident[]>([]),
    [selected, setSelected] = useState<Incident | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    Promise.all([api<Jobs>("/jobs"), api<Incident[]>("/incidents")])
      .then(([j, s]) => {
        setJobs(j);
        setSignals(s);
      })
      .catch((e) => setError(String(e)));
  }, [revision]);
  return (
    <>
      <section className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h2>Background operations</h2>
            <p>
              SLA monitoring, security signals and transactional demo
              notifications.
            </p>
          </div>
          <button
            className="button primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const result = await api<Record<string, number>>("/jobs/run", {
                  method: "POST",
                });
                setRevision((r) => r + 1);
                ctx.toast(
                  `Worker complete: ${result.sla_events} SLA notices, ${result.delivered} demo messages processed`,
                );
              } catch (e) {
                setError(String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Play size={16} />
            {busy ? "Processing…" : "Run worker cycle"}
          </button>
        </div>
        <ErrorBox message={error} />
        <div className="settings-values">
          {["PENDING", "DELIVERED", "RETRY", "DEAD"].map((state) => (
            <span key={state}>
              {state}
              <strong>{jobs?.counts[state] || 0}</strong>
            </span>
          ))}
        </div>
        <p className="muted">
          {jobs?.provider}. Three attempts maximum; retries use exponential
          backoff. SLA escalation notifies managers without making business
          decisions.
        </p>
        <details>
          <summary>Recent worker records</summary>
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {jobs?.items.map((j) => (
                <tr key={j.id}>
                  <td>
                    {j.event_type}
                    <small>{dateTime(j.created_at)}</small>
                  </td>
                  <td>
                    <Badge value={j.state} />
                  </td>
                  <td>{j.attempts}</td>
                  <td>{j.outcome || "Queued"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>
      <section className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h2>Operational security signals</h2>
            <p>
              Synthetic incident investigation. These signals are not definitive
              fraud determinations.
            </p>
          </div>
          <ShieldEllipsis size={21} />
        </div>
        {signals.length ? (
          <table>
            <thead>
              <tr>
                <th>Signal</th>
                <th>Severity</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.title}</strong>
                    <small>{dateTime(s.created_at)}</small>
                  </td>
                  <td>
                    <Badge value={s.severity} />
                  </td>
                  <td>
                    <Badge value={s.status} />
                  </td>
                  <td>
                    <button
                      className="text-link"
                      onClick={() => setSelected(s)}
                    >
                      Investigate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="No operational security signals">
            A monitoring cycle will surface repeated authentication failures and
            refresh-token replay events.
          </Empty>
        )}
      </section>
      {selected && (
        <Modal title={selected.title} onClose={() => setSelected(null)}>
          <pre>{JSON.stringify(selected.details, null, 2)}</pre>
          {selected.decision && <p>Previous decision: {selected.decision}</p>}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              try {
                await api("/incidents/" + selected.id, {
                  method: "PATCH",
                  body: JSON.stringify({
                    status: form.get("status"),
                    reason: form.get("reason"),
                  }),
                });
                setSelected(null);
                setRevision((r) => r + 1);
                ctx.toast("Investigation decision recorded");
              } catch (e) {
                ctx.toast(String(e));
              }
            }}
          >
            <Field label="Investigation status">
              <select name="status">
                <option>INVESTIGATING</option>
                <option>RESOLVED</option>
                <option>ESCALATED</option>
              </select>
            </Field>
            <Field label="Investigation reason">
              <textarea
                name="reason"
                minLength={10}
                maxLength={1000}
                required
              />
            </Field>
            <button className="button primary">Record decision</button>
          </form>
        </Modal>
      )}
    </>
  );
}
