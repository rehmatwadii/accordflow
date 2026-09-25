import { useEffect, useState } from "react";
import { OperationsPanel } from "./operations";
import { CreateUserButton, ResetPasswordControl } from "./identity";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  Files,
  Fingerprint,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { api, download } from "./api";
import {
  Badge,
  CaseTable,
  dateTime,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  Pagination,
  pretty,
} from "./components";
import type { Context } from "./App";
import type { Audit, Dashboard, Finding, LC, Page, Rule, User } from "./types";

function useData<T>(url: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let live = true;
    setError("");
    api<T>(url)
      .then((d) => {
        if (live) setData(d);
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [url, revision]);
  return { data, error, reload: () => setRevision((r) => r + 1) };
}

export function DashboardPage(ctx: Context) {
  const { data: d, error } = useData<Dashboard>("/reports/dashboard");
  if (error) return <ErrorBox message={error} />;
  if (!d) return <Loading />;
  const max = Math.max(
    4,
    Math.ceil(Math.max(...d.trend.map((t) => t.cases)) / 4) * 4,
  );
  const riskTotal =
    Object.values(d.risk_distribution).reduce((a, b) => a + b, 0) || 1;
  const riskStops = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    .map((band, index, arr) => {
      const before =
        (arr
          .slice(0, index)
          .reduce((sum, b) => sum + (d.risk_distribution[b] || 0), 0) /
          riskTotal) *
        100;
      return `${["#21877b", "#e4bf62", "#e29160", "#c36266"][index]} ${before}% ${before + ((d.risk_distribution[band] || 0) / riskTotal) * 100}%`;
    })
    .join(",");
  return (
    <>
      <PageTitle
        eyebrow="YOUR OPERATIONS, AT A GLANCE"
        title={`Good ${new Date().getHours() < 12 ? "morning" : "afternoon"}, ${ctx.user.name.split(" ")[0]}.`}
        description="A clear view of your trade portfolio. Every exception, every next step."
        actions={
          <>
            {ctx.can("EXPORT_DATA") && (
              <button
                className="button"
                onClick={() =>
                  download("/reports/export", "lc-portfolio.csv").catch((e) =>
                    ctx.toast(String(e)),
                  )
                }
              >
                <ArrowDownToLine size={16} /> Export report
              </button>
            )}
            {ctx.can("LC_CREATE") && (
              <button
                className="button primary"
                onClick={() => ctx.go("create")}
              >
                <Plus size={17} /> New LC case
              </button>
            )}
          </>
        }
      />
      <div className="overview-note">
        <span>
          <i className="live-dot" /> Live portfolio overview
        </span>
        <span>
          {new Date().toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
          })}{" "}
          <span className="divider">|</span> Updated {dateTime(d.generated_at)}
        </span>
      </div>
      <div className="kpi-grid">
        {[
          {
            label: "Total letters of credit",
            value: d.total,
            sub: `${d.open} active in your workspace`,
            Icon: Files,
            color: "teal",
          },
          {
            label: "Pending review",
            value: d.pending_review,
            sub: "Awaiting an accountable decision",
            Icon: FileCheck2,
            color: "blue",
          },
          {
            label: "High-risk cases",
            value: d.high_risk,
            sub: "Prioritize a closer review",
            Icon: ShieldCheck,
            color: "amber",
          },
          {
            label: "SLA breaches",
            value: d.sla_breaches,
            sub: "Cases requiring timely attention",
            Icon: Clock3,
            color: "red",
          },
        ].map((k) => (
          <article className="kpi-card" key={k.label}>
            <div>
              <span>{k.label}</span>
              <span className={"kpi-icon " + k.color}>
                <k.Icon size={19} />
              </span>
            </div>
            <strong>{k.value.toString().padStart(2, "0")}</strong>
            <small>
              <span className={"tiny-dot " + k.color} />
              {k.sub}
            </small>
          </article>
        ))}
      </div>
      <div className="dashboard-charts">
        <section className="panel volume-panel">
          <div className="panel-heading">
            <div>
              <h2>Case activity</h2>
              <p>Credits opened across the last 7 days</p>
            </div>
            <span className="period-chip">
              Last 7 days <ChevronIcon />
            </span>
          </div>
          <div className="chart-legend">
            <span>
              <i className="teal-fill" /> Total cases
            </span>
            <span>
              <i className="amber-fill" /> High-risk cases
            </span>
          </div>
          <div
            className="bar-chart"
            role="img"
            aria-label={d.trend
              .map(
                (t) => `${t.label}: ${t.cases} cases, ${t.flagged} high risk`,
              )
              .join("; ")}
          >
            <div className="chart-grid-lines">
              {[
                max,
                Math.round(max * 0.75),
                Math.round(max * 0.5),
                Math.round(max * 0.25),
                0,
              ].map((n, i) => (
                <div key={i}>
                  <span>{n}</span>
                </div>
              ))}
            </div>
            <div className="chart-bars">
              {d.trend.map((t) => (
                <div className="chart-column" key={t.date}>
                  <div className="bar-pair">
                    <div
                      className="bar teal-fill"
                      title={`${t.cases} cases`}
                      style={{ height: `${(t.cases / max) * 100}%` }}
                    />
                    <div
                      className="bar amber-fill"
                      title={`${t.flagged} high risk`}
                      style={{ height: `${(t.flagged / max) * 100}%` }}
                    />
                  </div>
                  <span>{t.label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="chart-footer">
            <Activity size={15} /> Computed from case creation timestamps in
            your database.
          </div>
        </section>
        <section className="panel risk-panel">
          <div className="panel-heading">
            <div>
              <h2>Portfolio risk</h2>
              <p>Explainable, rule-based assessment</p>
            </div>
            <ShieldCheck size={19} />
          </div>
          <div className="donut-wrap">
            <div
              className="donut"
              style={{ background: `conic-gradient(${riskStops})` }}
            >
              <div>
                <strong>{d.total}</strong>
                <span>Total cases</span>
              </div>
            </div>
          </div>
          <div className="risk-legend">
            {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((band, i) => (
              <div key={band}>
                <span>
                  <i
                    style={{
                      background: ["#21877b", "#e4bf62", "#e29160", "#c36266"][
                        i
                      ],
                    }}
                  />
                  {pretty(band)} risk
                </span>
                <strong>{d.risk_distribution[band] || 0}</strong>
                <small>
                  {Math.round(
                    ((d.risk_distribution[band] || 0) / riskTotal) * 100,
                  )}
                  %
                </small>
              </div>
            ))}
          </div>
        </section>
      </div>
      <div className="dashboard-lower">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>
                Recent letters of credit{" "}
                <span className="count-pill">{d.total}</span>
              </h2>
              <p>Your latest portfolio activity</p>
            </div>
            <button className="text-link" onClick={() => ctx.go("workbench")}>
              View workbench <ArrowRight size={15} />
            </button>
          </div>
          <CaseTable cases={d.recent} onOpen={(id) => ctx.go("case/" + id)} />
        </section>
        <section className="panel attention-panel">
          <div className="panel-heading">
            <div>
              <h2>Needs attention</h2>
              <p>Start where your review matters most</p>
            </div>
            <span className="attention-icon">
              <CircleAlert size={18} />
            </span>
          </div>
          {d.attention.length ? (
            d.attention.slice(0, 4).map((lc) => (
              <button
                className="attention-item"
                key={lc.id}
                onClick={() => ctx.go("case/" + lc.id)}
              >
                <div>
                  <strong>{lc.reference}</strong>
                  <ArrowUpRight size={16} />
                </div>
                <p>{lc.terms.applicant}</p>
                <div>
                  <Badge value={lc.risk_band} />
                  <small>{pretty(lc.sla)}</small>
                </div>
              </button>
            ))
          ) : (
            <Empty title="All caught up" />
          )}
          <div className="attention-footer">
            <ShieldCheck size={15} /> Human review makes the difference.
          </div>
        </section>
      </div>
    </>
  );
}
function ChevronIcon() {
  return <span style={{ fontSize: 10 }}>⌄</span>;
}

export function WorkbenchPage(
  ctx: Context & { mode: string; initialSearch: string },
) {
  const [search, setSearch] = useState(ctx.initialSearch),
    [status, setStatus] = useState(ctx.mode === "review" ? "UNDER_REVIEW" : ""),
    [page, setPage] = useState(1),
    [sort, setSort] = useState(ctx.mode === "review" ? "risk" : "updated");
  const { data, error, reload } = useData<Page<LC>>(
    `/lcs?q=${encodeURIComponent(search)}&status=${status}&page=${page}&sort=${sort}`,
  );
  const title =
    ctx.mode === "review"
      ? "Review queue"
      : ctx.mode === "documents"
        ? "Document center"
        : "LC workbench";
  return (
    <>
      <PageTitle
        eyebrow="TRADE OPERATIONS"
        title={title}
        description={
          ctx.mode === "documents"
            ? "Open a case to upload, version, and compare its document evidence."
            : "Every credit, from first submission to final decision."
        }
        actions={
          ctx.can("LC_CREATE") && (
            <button className="button primary" onClick={() => ctx.go("create")}>
              <Plus size={17} /> New LC case
            </button>
          )
        }
      />
      <div className="workbench-tabs">
        {[
          ["", "All cases"],
          ["DRAFT", "Drafts"],
          ["DISCREPANCIES_FOUND", "With discrepancies"],
          ["UNDER_REVIEW", "Under review"],
          ["PENDING_CHECKER", "Awaiting checker"],
          ["APPROVED", "Approved"],
        ].map(([s, label]) => (
          <button
            key={s}
            className={status === s ? "selected" : ""}
            onClick={() => {
              setStatus(s);
              setPage(1);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <section className="panel">
        <div className="filters">
          <div className="search-input">
            <Search size={17} />
            <input
              aria-label="Search workbench"
              placeholder="Search reference, applicant or beneficiary"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <select
            aria-label="Sort cases"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="updated">Recently updated</option>
            <option value="risk">Highest risk first</option>
            <option value="due">SLA due first</option>
            <option value="reference">LC reference</option>
          </select>
          <button
            className="button"
            onClick={() => {
              localStorage.setItem(
                "lcv-filter",
                JSON.stringify({ search, status, sort }),
              );
              ctx.toast("Workbench filter saved on this device");
            }}
          >
            <SlidersHorizontal size={15} /> Save view
          </button>
          <button
            className="button"
            onClick={() => {
              const v = localStorage.getItem("lcv-filter");
              if (v) {
                const f = JSON.parse(v);
                setSearch(f.search);
                setStatus(f.status);
                setSort(f.sort);
                setPage(1);
              } else ctx.toast("Save a view first");
            }}
          >
            Saved view
          </button>
          <button
            className="icon-button"
            aria-label="Refresh cases"
            onClick={reload}
          >
            <RefreshCw size={17} />
          </button>
        </div>
        <ErrorBox message={error} />
        {data ? (
          <>
            <CaseTable
              cases={data.items}
              onOpen={(id) => ctx.go("case/" + id)}
            />
            <Pagination page={page} total={data.total} onChange={setPage} />
          </>
        ) : (
          <Loading />
        )}
      </section>
    </>
  );
}

export function FindingsPage(ctx: Context) {
  const [page, setPage] = useState(1);
  const { data, error } = useData<Page<Finding>>("/discrepancies?page=" + page);
  return (
    <>
      <PageTitle
        eyebrow="EXCEPTION MANAGEMENT"
        title="Discrepancy center"
        description="Trace every finding back to its rule, evidence, and human decision."
      />
      <ErrorBox message={error} />
      <section className="panel">
        {data ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Rule / finding</th>
                    <th>Category</th>
                    <th>Severity</th>
                    <th>Decision</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.result.rule_name}</strong>
                        <small>
                          {d.id.slice(0, 8).toUpperCase()} ·{" "}
                          {d.result.explanation}
                        </small>
                      </td>
                      <td>{d.result.category}</td>
                      <td>
                        <Badge value={d.severity} />
                      </td>
                      <td>
                        <Badge value={d.status} />
                      </td>
                      <td>
                        <button
                          className="text-link"
                          onClick={() => ctx.go("case/" + d.lc_id)}
                        >
                          Review evidence <ArrowUpRight size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              total={data.total}
              size={25}
              onChange={setPage}
            />
            {!data.total && <Empty title="No discrepancies" />}
          </>
        ) : (
          <Loading />
        )}
      </section>
    </>
  );
}

export function AuditPage(ctx: Context) {
  const [q, setQ] = useState(""),
    [entity, setEntity] = useState(""),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState<Audit | null>(null),
    [integrity, setIntegrity] = useState("");
  const { data, error } = useData<Page<Audit>>(
    `/audit?q=${encodeURIComponent(q)}&entity_id=${encodeURIComponent(entity)}&page=${page}`,
  );
  return (
    <>
      <PageTitle
        eyebrow="GOVERNANCE & TRACEABILITY"
        title="Audit explorer"
        description="An append-only record of actions, evidence, and accountable decisions."
        actions={
          ctx.can("AUDIT_VERIFY") && (
            <button
              className="button primary"
              onClick={async () => {
                try {
                  const r = await api<{ status: string; checked: number }>(
                    "/audit/verify",
                    { method: "POST" },
                  );
                  setIntegrity(
                    `${r.status}: ${r.checked} audit events checked`,
                  );
                } catch (e) {
                  ctx.toast(String(e));
                }
              }}
            >
              <Fingerprint size={17} /> Verify audit integrity
            </button>
          )
        }
      />
      {integrity && (
        <div className="info-banner">
          <ShieldCheck size={18} />
          {integrity}. Application-level integrity verification.
        </div>
      )}
      <section className="panel">
        <div className="filters">
          <div className="search-input">
            <Search size={17} />
            <input
              aria-label="Filter audit actions"
              placeholder="Search actions, e.g. APPROVE"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <input
            aria-label="Filter audit case ID"
            placeholder="Exact case ID"
            value={entity}
            onChange={(e) => {
              setEntity(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <ErrorBox message={error} />
        {data ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>Timestamp (local)</th>
                    <th>Integrity</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <span className="audit-action">
                          <Fingerprint size={16} />
                          {pretty(e.action)}
                        </span>
                        <small>
                          #{e.id} · {e.entity_id.slice(0, 14)}
                        </small>
                      </td>
                      <td>
                        {e.actor}
                        <small>{pretty(e.role)}</small>
                      </td>
                      <td>{dateTime(e.timestamp)}</td>
                      <td>
                        <code className="hash">
                          {e.event_hash.slice(0, 12)}…
                        </code>
                      </td>
                      <td>
                        <button
                          className="text-link"
                          onClick={() => setSelected(e)}
                        >
                          Inspect <ArrowUpRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              total={data.total}
              size={30}
              onChange={setPage}
            />
          </>
        ) : (
          <Loading />
        )}
      </section>
      {selected && (
        <Modal
          title={`Audit event #${selected.id}`}
          onClose={() => setSelected(null)}
          wide
        >
          <p>
            <strong>{pretty(selected.action)}</strong> by {selected.actor}
          </p>
          <pre>{JSON.stringify(selected, null, 2)}</pre>
        </Modal>
      )}
    </>
  );
}

export function RulesPage(ctx: Context) {
  const { data, error, reload } = useData<Rule[]>("/rules");
  const [selected, setSelected] = useState<Rule | null>(null),
    [reason, setReason] = useState(""),
    [saving, setSaving] = useState(false),
    [formError, setFormError] = useState("");
  return (
    <>
      <PageTitle
        eyebrow="EXPLAINABLE BY DESIGN"
        title="Business rules catalog"
        description="Deterministic checks. Versioned policy. Evidence behind every result."
      />
      <div className="info-banner">
        <ShieldCheck size={18} /> Simplified synthetic consistency checks
        inspired by trade-finance workflows. Human review is always required.
      </div>
      <ErrorBox message={error} />
      <section className="panel">
        {data ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Rule / logic</th>
                  <th>Category</th>
                  <th>Severity</th>
                  <th>Version</th>
                  <th>Status</th>
                  {ctx.can("RULE_CONFIGURE") && <th />}
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.name}</strong>
                      <small>{r.description}</small>
                      <code className="rule-id">{r.id}</code>
                    </td>
                    <td>{r.category}</td>
                    <td>
                      <Badge value={r.severity} />
                    </td>
                    <td>v{r.version}.0</td>
                    <td>
                      <Badge value={r.enabled ? "ACTIVE" : "DISABLED"} />
                    </td>
                    {ctx.can("RULE_CONFIGURE") && (
                      <td>
                        <button
                          className="text-link"
                          onClick={() => {
                            setSelected({ ...r });
                            setReason("");
                            setFormError("");
                          }}
                        >
                          Configure
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Loading />
        )}
      </section>
      {selected && (
        <Modal title={selected.name} onClose={() => setSelected(null)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setSaving(true);
              try {
                await api("/rules/" + selected.id, {
                  method: "PATCH",
                  body: JSON.stringify({
                    severity: selected.severity,
                    enabled: selected.enabled,
                    version: selected.version,
                    reason,
                  }),
                });
                setSelected(null);
                reload();
                ctx.toast("Rule configuration version saved and audited");
              } catch (e) {
                setFormError(String(e));
              } finally {
                setSaving(false);
              }
            }}
          >
            <ErrorBox message={formError} />
            <Field label="Severity">
              <select
                value={selected.severity}
                onChange={(e) =>
                  setSelected({ ...selected, severity: e.target.value })
                }
              >
                {["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={selected.enabled}
                onChange={(e) =>
                  setSelected({ ...selected, enabled: e.target.checked })
                }
              />{" "}
              Enable rule
            </label>
            <Field label="Change justification">
              <textarea
                required
                minLength={10}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <p className="muted">
              Existing results retain their original rule version. Final
              approval requires validation against current policy.
            </p>
            <button className="button primary" disabled={saving}>
              Save new version
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function ReportsPage(ctx: Context) {
  const { data: d, error } = useData<Dashboard>("/reports/dashboard");
  return (
    <>
      <PageTitle
        eyebrow="OPERATIONAL INTELLIGENCE"
        title="Reports & analytics"
        description="Measured from your synthetic portfolio. Ready for an informed review."
        actions={
          ctx.can("EXPORT_DATA") && (
            <>
              <button
                className="button"
                onClick={() =>
                  download(
                    "/reports/export?format=json",
                    "lc-portfolio.json",
                  ).catch((e) => ctx.toast(String(e)))
                }
              >
                <ArrowDownToLine size={16} /> JSON
              </button>
              <button
                className="button primary"
                onClick={() =>
                  download("/reports/export", "lc-portfolio.csv").catch((e) =>
                    ctx.toast(String(e)),
                  )
                }
              >
                <ArrowDownToLine size={16} /> Export CSV
              </button>
            </>
          )
        }
      />
      <ErrorBox message={error} />
      {d ? (
        <>
          <div className="kpi-grid">
            {[
              ["Approval rate", d.approval_rate + "%"],
              ["Average completed time", d.average_hours + "h"],
              ["Recorded findings", d.discrepancies],
              ["Authorized overrides", d.overrides],
            ].map(([label, value]) => (
              <article className="kpi-card" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
                <small>Calculated from accessible cases</small>
              </article>
            ))}
          </div>
          <div className="analytics-grid">
            {[
              ["Discrepancy categories", d.discrepancy_categories],
              ["SLA performance", d.sla_distribution],
              ["Workflow distribution", d.status_distribution],
              ["Rule failure frequency", d.rule_failures],
            ].map(([title, values]) => (
              <section className="panel analytics-panel" key={String(title)}>
                <h2>{String(title)}</h2>
                {Object.entries(values as Record<string, number>).map(
                  ([label, value]) => (
                    <div className="horizontal-metric" key={label}>
                      <div>
                        <span>{pretty(label)}</span>
                        <strong>{value}</strong>
                      </div>
                      <span>
                        <i
                          style={{
                            width: `${(value / Math.max(1, ...Object.values(values as Record<string, number>))) * 100}%`,
                          }}
                        />
                      </span>
                    </div>
                  ),
                )}
              </section>
            ))}
          </div>
          <div className="info-banner">
            <FileCheck2 size={18} /> Open any LC case to export its full
            compliance report, including evidence, decisions, risk factors, and
            audit summary.
          </div>
        </>
      ) : (
        <Loading />
      )}
    </>
  );
}

type AdminUser = User & { active: boolean; last_login: string | null };
export function AdminPage(ctx: Context) {
  const { data: users, error, reload } = useData<AdminUser[]>("/users"),
    { data: metrics } = useData<Record<string, string | number>>("/metrics"),
    { data: settings, reload: reloadSettings } = useData<
      {
        key: string;
        value: Record<string, number | string>;
        version: number;
      }[]
    >("/settings");
  const [selected, setSelected] = useState<AdminUser | null>(null),
    [reason, setReason] = useState(""),
    [formError, setFormError] = useState("");
  const sla = settings?.find((s) => s.key === "sla_hours");
  const [slaEdit, setSlaEdit] = useState(false);
  return (
    <>
      <PageTitle
        eyebrow="PLATFORM GOVERNANCE"
        title="Administration"
        description="Manage access and configuration with separation of operational duties."
        actions={<CreateUserButton onCreated={reload} toast={ctx.toast} />}
      />
      <ErrorBox message={error} />
      <div className="kpi-grid">
        {["requests", "errors", "rate_limited", "average_latency_ms"].map(
          (k) => (
            <article className="kpi-card" key={k}>
              <span>{pretty(k)}</span>
              <strong>{metrics?.[k] ?? "—"}</strong>
              <small>Current server process</small>
            </article>
          ),
        )}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>People & access</h2>
            <p>Role changes revoke existing sessions immediately.</p>
          </div>
          <ShieldCheck size={20} />
        </div>
        {users ? (
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last login</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.name}</strong>
                    <small>{u.email}</small>
                  </td>
                  <td>{pretty(u.role)}</td>
                  <td>
                    <Badge value={u.active ? "ACTIVE" : "DISABLED"} />
                  </td>
                  <td>{u.last_login ? dateTime(u.last_login) : "Never"}</td>
                  <td>
                    <button
                      className="text-link"
                      disabled={u.id === ctx.user.id}
                      onClick={() => {
                        setSelected({ ...u });
                        setReason("");
                        setFormError("");
                      }}
                    >
                      Manage
                    </button>
                    <div className="user-reset">
                      <ResetPasswordControl userId={u.id} toast={ctx.toast} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Loading />
        )}
      </section>
      <section className="panel settings-panel">
        <h2>Service-level policy</h2>
        <p>
          New cases use these configured deadlines. Existing case deadlines are
          preserved.
        </p>
        <div className="settings-values">
          {sla &&
            Object.entries(sla.value).map(([k, v]) => (
              <span key={k}>
                {pretty(k)}
                <strong>{v} hours</strong>
              </span>
            ))}
          <button className="button" onClick={() => setSlaEdit(true)}>
            Configure SLA
          </button>
        </div>
        <p className="muted">
          Retention: audit records remain indefinitely in the demo. No automatic
          deletion. Email provider: mock, external delivery suppressed.
        </p>
      </section>
      <OperationsPanel {...ctx} />
      {selected && (
        <Modal title="Manage user access" onClose={() => setSelected(null)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api("/users/" + selected.id, {
                  method: "PATCH",
                  body: JSON.stringify({
                    role: selected.role,
                    active: selected.active,
                    reason,
                  }),
                });
                reload();
                setSelected(null);
                ctx.toast("Access updated; sessions revoked");
              } catch (e) {
                setFormError(String(e));
              }
            }}
          >
            <ErrorBox message={formError} />
            <p>{selected.email}</p>
            <Field label="Role">
              <select
                value={selected.role}
                onChange={(e) =>
                  setSelected({ ...selected, role: e.target.value })
                }
              >
                {[
                  "TRADE_ANALYST",
                  "COMPLIANCE_REVIEWER",
                  "SENIOR_CHECKER",
                  "COMPLIANCE_MANAGER",
                  "INTERNAL_AUDITOR",
                  "EXECUTIVE_VIEWER",
                  "SYSTEM_ADMIN",
                ].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </Field>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={selected.active}
                onChange={(e) =>
                  setSelected({ ...selected, active: e.target.checked })
                }
              />{" "}
              Account active
            </label>
            <Field label="Reason">
              <textarea
                required
                minLength={10}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <button className="button primary">Update access</button>
          </form>
        </Modal>
      )}
      {slaEdit && sla && (
        <Modal title="Configure SLA policy" onClose={() => setSlaEdit(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              try {
                await api("/settings/sla", {
                  method: "PUT",
                  body: JSON.stringify({
                    standard_hours: Number(f.get("STANDARD")),
                    high_hours: Number(f.get("HIGH")),
                    critical_hours: Number(f.get("CRITICAL")),
                    reason: f.get("reason"),
                    version: sla.version,
                  }),
                });
                setSlaEdit(false);
                reloadSettings();
                ctx.toast("SLA policy updated");
              } catch (e) {
                ctx.toast(String(e));
              }
            }}
          >
            {["STANDARD", "HIGH", "CRITICAL"].map((k) => (
              <Field key={k} label={pretty(k) + " hours"}>
                <input
                  type="number"
                  name={k}
                  min={1}
                  max={720}
                  defaultValue={sla.value[k]}
                  required
                />
              </Field>
            ))}
            <Field label="Change reason">
              <textarea name="reason" minLength={10} required />
            </Field>
            <button className="button primary">Save policy</button>
          </form>
        </Modal>
      )}
    </>
  );
}
