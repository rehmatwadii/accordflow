import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCheck,
  CircleAlert,
  Clock3,
  FileCheck2,
  Fingerprint,
  FlaskConical,
  MessageSquare,
  Pencil,
  Play,
  ShieldCheck,
  Upload,
  Users,
} from "lucide-react";
import { api, download, saveJson } from "./api";
import {
  Badge,
  dateTime,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  money,
  PageTitle,
  pretty,
} from "./components";
import type { Context } from "./App";
import type { Finding, LC, Result, Terms } from "./types";

const iso = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};
const defaultTerms = (): Terms => ({
  applicant: "",
  beneficiary: "",
  applicant_country: "Pakistan",
  beneficiary_country: "Singapore",
  issuing_bank: "Meridian Demo Bank",
  advising_bank: "Straits Synthetic Bank",
  confirming_bank: "",
  lc_type: "IMPORT",
  currency: "USD",
  amount: "125000",
  tolerance_pct: "5",
  tolerance_amount: "0",
  issue_date: iso(-12),
  expiry_date: iso(30),
  latest_shipment: iso(-2),
  presentation_date: iso(0),
  presentation_period: 21,
  loading_port: "Singapore",
  discharge_port: "Port Qasim",
  place_of_expiry: "Karachi",
  incoterm: "FOB",
  goods: "Synthetic cotton fabric",
  quantity: "100",
  quantity_unit: "MT",
  unit_price: "1250",
  payment_terms: "At sight",
  partial_shipment: false,
  transshipment: false,
  required_documents: [
    "COMMERCIAL_INVOICE",
    "BILL_OF_LADING",
    "PACKING_LIST",
    "CERTIFICATE_OF_ORIGIN",
  ],
  special_conditions: "Synthetic demonstration only",
  rule_profile: "STANDARD_IMPORT_LC",
});
const DOC_TYPES = [
  "COMMERCIAL_INVOICE",
  "BILL_OF_LADING",
  "PACKING_LIST",
  "CERTIFICATE_OF_ORIGIN",
  "INSURANCE_CERTIFICATE",
  "INSPECTION_CERTIFICATE",
  "BENEFICIARY_CERTIFICATE",
  "DRAFT",
  "OTHER",
];
const options: Partial<Record<keyof Terms, string[]>> = {
  currency: ["USD", "EUR", "GBP", "PKR", "AED", "CNY", "JPY"],
  incoterm: ["FOB", "CIF", "CFR", "EXW", "FCA", "CPT", "CIP", "DAP", "DDP"],
  lc_type: ["IMPORT", "EXPORT", "STANDBY"],
  rule_profile: [
    "STANDARD_IMPORT_LC",
    "EXPORT_LC",
    "HIGH_VALUE_LC",
    "INSURANCE_REQUIRED",
  ],
};
const sections: { name: string; keys: (keyof Terms)[] }[] = [
  {
    name: "Parties & credit",
    keys: [
      "applicant",
      "beneficiary",
      "applicant_country",
      "beneficiary_country",
      "issuing_bank",
      "advising_bank",
      "confirming_bank",
      "lc_type",
    ],
  },
  {
    name: "Value & merchandise",
    keys: [
      "currency",
      "amount",
      "tolerance_pct",
      "tolerance_amount",
      "goods",
      "quantity",
      "quantity_unit",
      "unit_price",
      "payment_terms",
    ],
  },
  {
    name: "Dates & shipment",
    keys: [
      "issue_date",
      "expiry_date",
      "latest_shipment",
      "presentation_date",
      "presentation_period",
      "loading_port",
      "discharge_port",
      "place_of_expiry",
      "incoterm",
    ],
  },
  { name: "Policy & conditions", keys: ["rule_profile", "special_conditions"] },
];

export function CaseForm(
  ctx: Context & { existing?: LC; onSaved?: () => void; onCancel?: () => void },
) {
  const [terms, setTerms] = useState<Terms>(
      ctx.existing?.terms || defaultTerms(),
    ),
    [title, setTitle] = useState(ctx.existing?.title || ""),
    [priority, setPriority] = useState(ctx.existing?.priority || "STANDARD"),
    [reason, setReason] = useState(""),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  return (
    <>
      <PageTitle
        eyebrow="LETTER OF CREDIT"
        title={ctx.existing ? "Amend LC terms" : "Create a new LC case"}
        description="Start with precise terms. Every amendment preserves the previous version."
        actions={
          <button
            className="button"
            onClick={() =>
              ctx.onCancel ? ctx.onCancel() : ctx.go("workbench")
            }
          >
            <ArrowLeft size={16} /> Back
          </button>
        }
      />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setSaving(true);
          setError("");
          try {
            const result = await api<LC>(
              ctx.existing ? "/lcs/" + ctx.existing.id : "/lcs",
              {
                method: ctx.existing ? "PUT" : "POST",
                body: JSON.stringify({
                  title,
                  priority,
                  terms,
                  ...(ctx.existing
                    ? { version: ctx.existing.version, reason }
                    : {}),
                }),
              },
            );
            ctx.toast(
              ctx.existing
                ? "LC amendment saved with version history"
                : "New LC case created",
            );
            if (ctx.onSaved) ctx.onSaved();
            else ctx.go("case/" + result.id);
          } catch (e) {
            setError(String(e));
          } finally {
            setSaving(false);
          }
        }}
      >
        <ErrorBox message={error} />
        <section className="panel form-panel">
          <h2>Case identification</h2>
          <div className="form-grid">
            <Field label="Case title">
              <input
                required
                minLength={3}
                maxLength={150}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Synthetic cotton import — September"
              />
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                {["STANDARD", "HIGH", "CRITICAL"].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </Field>
          </div>
        </section>
        {sections.map((section) => (
          <section className="panel form-panel" key={section.name}>
            <h2>{section.name}</h2>
            <div className="form-grid">
              {section.keys.map((key) => (
                <Field label={pretty(key)} key={key}>
                  {options[key] ? (
                    <select
                      value={String(terms[key])}
                      onChange={(e) =>
                        setTerms({ ...terms, [key]: e.target.value })
                      }
                    >
                      {options[key]!.map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={
                        key.includes("date") || key === "latest_shipment"
                          ? "date"
                          : [
                                "amount",
                                "tolerance_pct",
                                "tolerance_amount",
                                "quantity",
                                "unit_price",
                                "presentation_period",
                              ].includes(key)
                            ? "number"
                            : "text"
                      }
                      step={key === "presentation_period" ? "1" : "any"}
                      required={
                        !["confirming_bank", "special_conditions"].includes(key)
                      }
                      value={String(terms[key])}
                      onChange={(e) =>
                        setTerms({
                          ...terms,
                          [key]:
                            key === "presentation_period"
                              ? Number(e.target.value)
                              : e.target.value,
                        })
                      }
                    />
                  )}
                </Field>
              ))}
            </div>
          </section>
        ))}
        <section className="panel form-panel">
          <h2>Required documents & shipment permissions</h2>
          <div className="check-grid">
            {DOC_TYPES.map((d) => (
              <label className="checkbox" key={d}>
                <input
                  type="checkbox"
                  checked={terms.required_documents.includes(d)}
                  onChange={(e) =>
                    setTerms({
                      ...terms,
                      required_documents: e.target.checked
                        ? [...terms.required_documents, d]
                        : terms.required_documents.filter((t) => t !== d),
                    })
                  }
                />
                {pretty(d)}
              </label>
            ))}
          </div>
          <div className="check-grid">
            {(["partial_shipment", "transshipment"] as const).map((k) => (
              <label className="checkbox" key={k}>
                <input
                  type="checkbox"
                  checked={terms[k]}
                  onChange={(e) =>
                    setTerms({ ...terms, [k]: e.target.checked })
                  }
                />
                Allow {pretty(k).toLowerCase()}
              </label>
            ))}
          </div>
          {ctx.existing && (
            <Field label="Amendment reason">
              <textarea
                required
                minLength={10}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
          )}
        </section>
        <div className="form-actions">
          <span>
            <ShieldCheck size={16} /> Synthetic data only. Changes are recorded
            in the audit trail.
          </span>
          <button className="button primary" disabled={saving}>
            {saving
              ? "Saving…"
              : ctx.existing
                ? "Save amendment"
                : "Create LC case"}
            <ArrowRight size={17} />
          </button>
        </div>
      </form>
    </>
  );
}

export function CaseDetail(ctx: Context & { id: string }) {
  const [lc, setLC] = useState<LC | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Overview"),
    [revision, setRevision] = useState(0),
    [edit, setEdit] = useState(false),
    [upload, setUpload] = useState(false),
    [action, setAction] = useState(""),
    [reason, setReason] = useState(""),
    [checks, setChecks] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState(""),
    [evidence, setEvidence] = useState<Result | null>(null),
    [finding, setFinding] = useState<Finding | null>(null),
    [decision, setDecision] = useState("ACKNOWLEDGED"),
    [note, setNote] = useState(""),
    [simAmount, setSimAmount] = useState(""),
    [sim, setSim] = useState<{
      risk: { score: number; band: string };
      results: Result[];
    } | null>(null),
    [assign, setAssign] = useState(false),
    [assignees, setAssignees] = useState<
      { id: string; name: string; role: string }[]
    >([]);
  const reload = () => setRevision((r) => r + 1);
  useEffect(() => {
    api<LC>("/lcs/" + ctx.id)
      .then((d) => {
        setLC(d);
        setSimAmount(d.terms.amount);
        setError("");
      })
      .catch((e) => setError(String(e)));
  }, [ctx.id, revision]);
  if (error) return <ErrorBox message={error} />;
  if (!lc) return <Loading />;
  if (edit)
    return (
      <CaseForm
        {...ctx}
        existing={lc}
        onCancel={() => setEdit(false)}
        onSaved={() => {
          setEdit(false);
          reload();
        }}
      />
    );
  const currentDocs = Object.values(
    (lc.documents || []).reduce<
      Record<string, NonNullable<LC["documents"]>[number]>
    >((a, d) => {
      if (!a[d.type] || a[d.type].version < d.version) a[d.type] = d;
      return a;
    }, {}),
  );
  const currentFindings =
    lc.discrepancies?.filter((d) => d.run_id === lc.validation?.id) || [];
  const mutate = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      reload();
      ctx.toast(message);
    } catch (e) {
      ctx.toast(String(e));
    } finally {
      setBusy(false);
    }
  };
  const tabs = [
    "Overview",
    "LC terms",
    "Documents",
    "Validation",
    "Discrepancies",
    "Risk",
    "Workflow",
    "Audit",
    "Comments",
  ];
  return (
    <>
      <button className="back-link" onClick={() => ctx.go("workbench")}>
        <ArrowLeft size={14} /> Back to workbench
      </button>
      <PageTitle
        eyebrow={lc.reference + " · TERMS VERSION " + lc.terms_version}
        title={lc.title}
        description={lc.terms.applicant + " → " + lc.terms.beneficiary}
        actions={
          <>
            {ctx.can("EXPORT_DATA") && (
              <button
                className="button"
                onClick={() =>
                  download(
                    `/reports/lcs/${lc.id}?format=pdf`,
                    lc.reference + "-report.pdf",
                  ).catch((e) => ctx.toast(String(e)))
                }
              >
                <ArrowDownToLine size={16} /> Compliance report
              </button>
            )}
            {ctx.can("VALIDATION_RUN") &&
              [
                "SUBMITTED",
                "DOCUMENTS_PENDING",
                "VALIDATION_COMPLETED",
                "DISCREPANCIES_FOUND",
              ].includes(lc.status) && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() =>
                    mutate(
                      () =>
                        api("/lcs/" + lc.id + "/validation", {
                          method: "POST",
                        }),
                      "Validation completed; evidence and risk updated",
                    )
                  }
                >
                  <Play size={16} />
                  {busy ? "Validating…" : "Run validation"}
                </button>
              )}
          </>
        }
      />
      <div className="case-meta">
        <Badge value={lc.status} />
        <span>{money(lc.terms.amount, lc.terms.currency)}</span>
        <span>
          {lc.terms.incoterm} · {lc.terms.loading_port} →{" "}
          {lc.terms.discharge_port}
        </span>
        <span>
          <Clock3 size={14} /> Due {dateTime(lc.due_at)}
        </span>
      </div>
      <div className="case-layout">
        <div className="case-content">
          <div className="detail-tabs">
            {tabs.map((t) => (
              <button
                key={t}
                className={tab === t ? "selected" : ""}
                onClick={() => setTab(t)}
              >
                {t}
                {t === "Discrepancies" && currentFindings.length > 0 && (
                  <span>{currentFindings.length}</span>
                )}
              </button>
            ))}
          </div>
          {tab === "Overview" && (
            <>
              <section className="panel detail-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Credit at a glance</h2>
                    <p>Structured terms are the source of truth.</p>
                  </div>
                  <FileCheck2 size={21} />
                </div>
                <div className="term-grid">
                  {[
                    ["Applicant", lc.terms.applicant],
                    ["Beneficiary", lc.terms.beneficiary],
                    ["Credit value", money(lc.terms.amount, lc.terms.currency)],
                    ["Goods", lc.terms.goods],
                    ["Latest shipment", lc.terms.latest_shipment],
                    ["Expiry date", lc.terms.expiry_date],
                    [
                      "Quantity",
                      lc.terms.quantity + " " + lc.terms.quantity_unit,
                    ],
                    ["Payment terms", lc.terms.payment_terms],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel detail-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Document readiness</h2>
                    <p>{currentDocs.length} document types received</p>
                  </div>
                  <button
                    className="text-link"
                    onClick={() => setTab("Documents")}
                  >
                    Document center <ArrowRight size={15} />
                  </button>
                </div>
                <div className="check-grid readiness">
                  {[
                    ...new Set([
                      ...lc.terms.required_documents,
                      ...(["CIF", "CIP"].includes(lc.terms.incoterm) ||
                      lc.terms.rule_profile === "INSURANCE_REQUIRED"
                        ? ["INSURANCE_CERTIFICATE"]
                        : []),
                    ]),
                  ].map((type) => (
                    <div
                      key={type}
                      className={
                        currentDocs.some((d) => d.type === type)
                          ? "ready"
                          : "missing"
                      }
                    >
                      {currentDocs.some((d) => d.type === type) ? (
                        <CheckCheck size={19} />
                      ) : (
                        <CircleAlert size={19} />
                      )}
                      <span>
                        {pretty(type)}
                        <small>
                          {currentDocs.find((d) => d.type === type)?.number ||
                            "Awaiting submission"}
                        </small>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel detail-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Validation summary</h2>
                    <p>
                      {lc.validation
                        ? "Last run " + dateTime(lc.validation.created_at)
                        : "Submit your case, then run the consistency checks."}
                    </p>
                  </div>
                </div>
                {lc.validation ? (
                  <div className="validation-summary">
                    {["PASS", "FAIL", "WARNING", "NOT_APPLICABLE"].map(
                      (status) => (
                        <button
                          key={status}
                          onClick={() => setTab("Validation")}
                        >
                          <strong>
                            {
                              lc.validation!.results.filter(
                                (r) => r.status === status,
                              ).length
                            }
                          </strong>
                          <Badge value={status} />
                        </button>
                      ),
                    )}
                  </div>
                ) : (
                  <Empty title="Ready when your documents are">
                    Upload the required evidence and submit this case for
                    validation.
                  </Empty>
                )}
              </section>
            </>
          )}
          {tab === "LC terms" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <h2>LC terms · version {lc.terms_version}</h2>
                {ctx.can("LC_UPDATE") &&
                  ["DRAFT", "ADDITIONAL_INFORMATION_REQUIRED"].includes(
                    lc.status,
                  ) && (
                    <button className="button" onClick={() => setEdit(true)}>
                      <Pencil size={15} /> Amend terms
                    </button>
                  )}
              </div>
              <div className="term-grid">
                {Object.entries(lc.terms).map(([key, value]) => (
                  <div key={key}>
                    <span>{pretty(key)}</span>
                    <strong>
                      {Array.isArray(value)
                        ? value.map(pretty).join(", ")
                        : typeof value === "boolean"
                          ? value
                            ? "Permitted"
                            : "Not permitted"
                          : String(value) || "—"}
                    </strong>
                  </div>
                ))}
              </div>
              <div className="panel-heading">
                <h2>Amendment history</h2>
              </div>
              {lc.versions?.map((v) => (
                <details className="version-entry" key={v.id}>
                  <summary>
                    Version {v.version} · {dateTime(v.created_at)} · {v.reason}
                  </summary>
                  <pre>{JSON.stringify(v.terms, null, 2)}</pre>
                </details>
              ))}
            </section>
          )}
          {tab === "Documents" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <div>
                  <h2>Document evidence</h2>
                  <p>Every version preserved. Every file SHA-256 verified.</p>
                </div>
                {ctx.can("DOCUMENT_CREATE") &&
                  [
                    "DRAFT",
                    "SUBMITTED",
                    "DOCUMENTS_PENDING",
                    "ADDITIONAL_INFORMATION_REQUIRED",
                  ].includes(lc.status) && (
                    <button
                      className="button primary"
                      onClick={() => setUpload(true)}
                    >
                      <Upload size={16} /> Upload document
                    </button>
                  )}
              </div>
              <div className="info-banner">
                <FlaskConical size={17} /> Synthetic JSON is extracted locally.
                PDF and image evidence supports OCR extraction with field
                review.
              </div>
              {lc.documents?.length ? (
                lc.documents.map((d) => (
                  <article className="document-card" key={d.id}>
                    <div className="document-icon">
                      <FilesIcon />
                    </div>
                    <div>
                      <strong>
                        {pretty(d.type)}{" "}
                        <span className="count-pill">v{d.version}</span>
                      </strong>
                      <p>
                        {d.number} · {d.filename} · {(d.size / 1024).toFixed(1)}{" "}
                        KB
                      </p>
                      <code>SHA-256 {d.sha256}</code>
                      <small>
                        Uploaded {dateTime(d.uploaded_at)} · {d.reason}
                      </small>
                      <details>
                        <summary>View structured evidence</summary>
                        <pre>{JSON.stringify(d.fields, null, 2)}</pre>
                      </details>
                    </div>
                    <button
                      className="icon-button"
                      aria-label={
                        "Download " + d.number + " version " + d.version
                      }
                      onClick={() =>
                        download(
                          "/documents/" + d.id + "/download",
                          d.filename,
                        ).catch((e) => ctx.toast(String(e)))
                      }
                    >
                      <ArrowDownToLine size={18} />
                    </button>
                  </article>
                ))
              ) : (
                <Empty title="No documents received">
                  Upload your synthetic document package to begin.
                </Empty>
              )}
            </section>
          )}
          {tab === "Validation" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Rule execution results</h2>
                  <p>
                    {lc.validation
                      ? `Run ${lc.validation.id.slice(0, 8)} · ${dateTime(lc.validation.created_at)}`
                      : "No validation run yet"}
                  </p>
                </div>
              </div>
              {lc.validation ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Rule</th>
                        <th>Status</th>
                        <th>Severity</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lc.validation.results.map((r) => (
                        <tr key={r.rule_id}>
                          <td>
                            <strong>{r.rule_name}</strong>
                            <small>
                              {r.category} · v{r.rule_version}.0
                            </small>
                          </td>
                          <td>
                            <Badge value={r.status} />
                          </td>
                          <td>
                            <Badge value={r.severity} />
                          </td>
                          <td>
                            <button
                              className="text-link"
                              onClick={() => setEvidence(r)}
                            >
                              Compare <ArrowRight size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty title="No validation results" />
              )}
            </section>
          )}
          {tab === "Discrepancies" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <div>
                  <h2>Discrepancy review</h2>
                  <p>
                    System results remain visible alongside every human
                    decision.
                  </p>
                </div>
              </div>
              {lc.discrepancies?.length ? (
                lc.discrepancies.map((d) => (
                  <article className="finding-card" key={d.id}>
                    <div className="finding-head">
                      <strong>{d.result.rule_name}</strong>
                      <div>
                        <Badge value={d.severity} />
                        <Badge value={d.status} />
                      </div>
                    </div>
                    <p>{d.result.explanation}</p>
                    <div className="compare-mini">
                      <span>
                        Expected<strong>{d.result.expected_value}</strong>
                      </span>
                      <span>
                        Actual<strong>{d.result.actual_value}</strong>
                      </span>
                    </div>
                    {d.decision && (
                      <p className="decision-note">
                        <strong>Human decision:</strong> {d.decision}
                      </p>
                    )}
                    <div className="finding-actions">
                      <button
                        className="text-link"
                        onClick={() => setEvidence(d.result)}
                      >
                        Inspect evidence <ArrowRight size={14} />
                      </button>
                      {ctx.can("CASE_REVIEW") &&
                        lc.status === "UNDER_REVIEW" &&
                        d.run_id === lc.validation?.id && (
                          <button
                            className="button"
                            onClick={() => {
                              setFinding(d);
                              setDecision("ACKNOWLEDGED");
                              setReason("");
                              setFormError("");
                            }}
                          >
                            Record decision
                          </button>
                        )}
                    </div>
                  </article>
                ))
              ) : (
                <Empty title="No discrepancies found">
                  Your latest validation has no findings to review.
                </Empty>
              )}
            </section>
          )}
          {tab === "Risk" && (
            <>
              <section className="panel detail-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Risk assessment</h2>
                    <p>A transparent score, derived from rule findings.</p>
                  </div>
                  <Badge value={lc.risk_band} />
                </div>
                <div className="risk-large">
                  {lc.risk_score}
                  <span>/ 100</span>
                </div>
                {lc.risk_factors.length ? (
                  lc.risk_factors.map((f, i) => (
                    <div className="factor" key={i}>
                      <span>{f.label}</span>
                      <strong>+{f.points}</strong>
                    </div>
                  ))
                ) : (
                  <p className="muted">
                    No scored risk factors in the latest validation.
                  </p>
                )}
                <p className="muted">
                  Critical +25 · High +15 · Medium +8 · Low +3 · Info +1.
                  Additional factors may apply; total capped at 100. Waivers do
                  not erase system risk.
                </p>
              </section>
              {ctx.can("RULE_VIEW") && (
                <section className="panel detail-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        <FlaskConical size={19} /> What-if simulator
                      </h2>
                      <p>
                        Explore an invoice change without altering the case.
                      </p>
                    </div>
                  </div>
                  <form
                    className="inline-form"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      try {
                        setSim(
                          await api("/lcs/" + lc.id + "/simulate", {
                            method: "POST",
                            body: JSON.stringify({ invoice_amount: simAmount }),
                          }),
                        );
                      } catch (e) {
                        ctx.toast(String(e));
                      }
                    }}
                  >
                    <Field label="Hypothetical invoice amount">
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={simAmount}
                        onChange={(e) => setSimAmount(e.target.value)}
                      />
                    </Field>
                    <button className="button primary">Run simulation</button>
                  </form>
                  {sim && (
                    <>
                      <div className="info-banner">
                        Current risk {lc.risk_score} → simulated risk{" "}
                        {sim.risk.score} · {sim.risk.band}. No case data
                        changed.
                      </div>
                      {sim.results
                        .filter((r) => r.status === "FAIL")
                        .map((r) => (
                          <p key={r.rule_id}>
                            <Badge value="FAIL" /> {r.rule_name} —{" "}
                            {r.actual_value}
                          </p>
                        ))}
                    </>
                  )}
                </section>
              )}
            </>
          )}
          {tab === "Workflow" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <div>
                  <h2>Decision history</h2>
                  <p>Independent review and checker accountability.</p>
                </div>
              </div>
              <div className="timeline">
                {lc.decisions?.map((d) => (
                  <article key={d.id}>
                    <span className="timeline-dot">
                      <Check size={12} />
                    </span>
                    <strong>{pretty(d.action)}</strong>
                    <small>
                      {dateTime(d.created_at)} · Actor {d.actor_id.slice(0, 8)}
                    </small>
                    <p>{d.reason}</p>
                  </article>
                ))}
              </div>
              {!lc.decisions?.length && (
                <Empty title="Draft case">
                  Submit the case to start its controlled workflow.
                </Empty>
              )}
              <h3>Review checklist</h3>
              <div className="check-grid">
                {lc.review_checklist?.map((c) => (
                  <div className="check-status" key={c}>
                    {lc.checklist.includes(c) ? (
                      <CheckCheck size={17} />
                    ) : (
                      <span className="unchecked" />
                    )}
                    {pretty(c)}
                  </div>
                ))}
              </div>
            </section>
          )}
          {tab === "Audit" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <h2>Case audit trail</h2>
                <Fingerprint size={20} />
              </div>
              <div className="timeline">
                {lc.audit?.map((e) => (
                  <article key={e.id}>
                    <span className="timeline-dot">
                      <Fingerprint size={12} />
                    </span>
                    <strong>{pretty(e.action)}</strong>
                    <small>
                      {e.actor} · {dateTime(e.timestamp)}
                    </small>
                    <details>
                      <summary>
                        Event #{e.id} · {e.event_hash.slice(0, 16)}…
                      </summary>
                      <pre>{JSON.stringify(e.details, null, 2)}</pre>
                      <code>{e.correlation_id}</code>
                    </details>
                  </article>
                ))}
              </div>
              {!lc.audit?.length && (
                <Empty title="No accessible audit events" />
              )}
            </section>
          )}
          {tab === "Comments" && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <h2>Investigation notes</h2>
                <MessageSquare size={20} />
              </div>
              {ctx.can("CASE_COMMENT") && (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    await mutate(
                      () =>
                        api("/lcs/" + lc.id + "/comments", {
                          method: "POST",
                          body: JSON.stringify({ body: note }),
                        }),
                      "Investigation note recorded",
                    );
                    setNote("");
                  }}
                >
                  <Field label="Add an internal note">
                    <textarea
                      minLength={3}
                      maxLength={4000}
                      required
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Record the evidence examined and the next action…"
                    />
                  </Field>
                  <button className="button primary" disabled={busy}>
                    Save note
                  </button>
                </form>
              )}
              {lc.comments?.map((c) => (
                <article className="comment" key={c.id}>
                  <div>
                    <strong>{c.actor_name}</strong>
                    <small>{dateTime(c.created_at)}</small>
                  </div>
                  <p>{c.body}</p>
                </article>
              ))}
            </section>
          )}
        </div>
        <aside className="case-aside">
          <section className="panel">
            <div className="panel-heading">
              <h2>Case assurance</h2>
              <ShieldCheck size={18} />
            </div>
            <div className="aside-risk">
              <strong>
                {lc.risk_score}
                <small>/100</small>
              </strong>
              <Badge value={lc.risk_band} />
            </div>
            <div className="aside-row">
              <span>SLA status</span>
              <Badge value={lc.sla} />
            </div>
            <div className="aside-row">
              <span>Priority</span>
              <strong>{pretty(lc.priority)}</strong>
            </div>
            <div className="aside-assignee">
              <Users size={17} />
              <div>
                <span>Assigned reviewer</span>
                <strong>{lc.assignee_name}</strong>
              </div>
              {ctx.can("CASE_ASSIGN") && (
                <button
                  className="icon-button"
                  aria-label="Assign case"
                  onClick={async () => {
                    try {
                      setAssignees(await api("/cases/assignees"));
                      setAssign(true);
                    } catch (e) {
                      ctx.toast(String(e));
                    }
                  }}
                >
                  <Pencil size={14} />
                </button>
              )}
            </div>
            <div className="aside-foot">
              <Fingerprint size={15} /> Version {lc.version} · Changes are
              audited
            </div>
          </section>
          <section className="panel next-actions">
            <h2>Next step</h2>
            <p>
              Available actions reflect your role and the current case state.
            </p>
            {lc.allowed_actions?.length ? (
              lc.allowed_actions.map((a) => (
                <button
                  className={
                    "button " +
                    (a === "APPROVE" || a === "SUBMIT" ? "primary" : "")
                  }
                  key={a}
                  onClick={() => {
                    setAction(a);
                    setReason("");
                    setChecks(lc.checklist || []);
                    setFormError("");
                  }}
                >
                  {pretty(a)}
                  <ArrowRight size={15} />
                </button>
              ))
            ) : (
              <p className="muted">
                No workflow action is available to your role at this stage.
              </p>
            )}
          </section>
          <div className="human-note">
            <ShieldCheck size={22} />
            <strong>Human judgment, by design.</strong>
            <p>
              System checks inform decisions. They never independently approve a
              credit.
            </p>
          </div>
        </aside>
      </div>
      {upload && (
        <UploadModal
          lc={lc}
          onClose={() => setUpload(false)}
          onSaved={() => {
            setUpload(false);
            reload();
            ctx.toast("Document securely stored with version and SHA-256 hash");
          }}
        />
      )}
      {action && (
        <Modal title={pretty(action)} onClose={() => setAction("")}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setFormError("");
              try {
                await api("/lcs/" + lc.id + "/workflow", {
                  method: "POST",
                  body: JSON.stringify({
                    action,
                    version: lc.version,
                    reason,
                    checklist: checks,
                  }),
                });
                setAction("");
                reload();
                ctx.toast("Workflow decision recorded");
              } catch (e) {
                setFormError(String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <ErrorBox message={formError} />
            <p>
              Case <strong>{lc.reference}</strong> · current state{" "}
              <strong>{pretty(lc.status)}</strong>
            </p>
            {action === "COMPLETE_REVIEW" && (
              <div className="check-grid">
                {lc.review_checklist?.map((c) => (
                  <label className="checkbox" key={c}>
                    <input
                      type="checkbox"
                      checked={checks.includes(c)}
                      onChange={(e) =>
                        setChecks(
                          e.target.checked
                            ? [...checks, c]
                            : checks.filter((x) => x !== c),
                        )
                      }
                    />
                    {pretty(c)} verified
                  </label>
                ))}
              </div>
            )}
            <Field label="Decision reason (required)">
              <textarea
                minLength={10}
                maxLength={2000}
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain your decision and the evidence reviewed…"
              />
            </Field>
            <div className="modal-actions">
              <button
                type="button"
                className="button"
                onClick={() => setAction("")}
              >
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                Confirm {pretty(action).toLowerCase()}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {evidence && (
        <Modal
          title={evidence.rule_name}
          onClose={() => setEvidence(null)}
          wide
        >
          <div className="evidence-status">
            <Badge value={evidence.status} />
            <Badge value={evidence.severity} />
            <span>
              Rule {evidence.rule_id} · v{evidence.rule_version}.0
            </span>
          </div>
          <div className="compare-grid">
            <div>
              <span>LC TERM / EXPECTED</span>
              <strong>{evidence.expected_value}</strong>
            </div>
            <div>
              <span>DOCUMENT / ACTUAL</span>
              <strong>{evidence.actual_value}</strong>
            </div>
          </div>
          <h3>Why this result?</h3>
          <p>{evidence.explanation}</p>
          <h3>Source evidence</h3>
          {evidence.evidence.map((e, i) => (
            <p key={i}>
              {pretty(e.type)} · {e.number} · version {e.version}
            </p>
          ))}
          <h3>Recommended review</h3>
          <p>{evidence.recommendation}</p>
        </Modal>
      )}
      {finding && (
        <Modal
          title="Record discrepancy decision"
          onClose={() => setFinding(null)}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setFormError("");
              try {
                await api("/discrepancies/" + finding.id, {
                  method: "PATCH",
                  body: JSON.stringify({
                    status: decision,
                    reason,
                    version: lc.version,
                  }),
                });
                setFinding(null);
                reload();
                ctx.toast(
                  "Human decision recorded alongside the system result",
                );
              } catch (e) {
                setFormError(String(e));
              }
            }}
          >
            <ErrorBox message={formError} />
            <p>
              <strong>{finding.result.rule_name}</strong> · System result
              remains FAIL
            </p>
            <Field label="Decision">
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
              >
                {[
                  "ACKNOWLEDGED",
                  "UNDER_REVIEW",
                  "ESCALATED",
                  "REJECTED",
                  ...(ctx.can("CASE_OVERRIDE") ? ["WAIVED"] : []),
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <Field label="Justification and supporting comment">
              <textarea
                required
                minLength={10}
                maxLength={2000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <p className="muted">
              Corrected evidence must be revalidated. Critical findings and
              missing documents cannot be waived.
            </p>
            <button className="button primary">Save decision</button>
          </form>
        </Modal>
      )}
      {assign && (
        <Modal title="Assign case reviewer" onClose={() => setAssign(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              await mutate(
                () =>
                  api("/lcs/" + lc.id + "/assign", {
                    method: "POST",
                    body: JSON.stringify({
                      user_id: f.get("user"),
                      reason: f.get("reason"),
                      version: lc.version,
                    }),
                  }),
                "Assignment updated",
              );
              setAssign(false);
            }}
          >
            <Field label="Reviewer">
              <select name="user" required>
                {assignees.map((u) => (
                  <option value={u.id} key={u.id}>
                    {u.name} · {pretty(u.role)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Assignment reason">
              <textarea name="reason" minLength={10} required />
            </Field>
            <button className="button primary">Assign case</button>
          </form>
        </Modal>
      )}
    </>
  );
}
function FilesIcon() {
  return <FileCheck2 size={23} />;
}

function sampleFields(lc: LC, type: string) {
  const t = lc.terms;
  const base = {
    number: "SYN-" + type.slice(0, 3) + "-" + Date.now().toString().slice(-6),
    issue_date: t.latest_shipment,
  };
  if (type === "COMMERCIAL_INVOICE")
    return {
      ...base,
      amount: t.amount,
      currency: t.currency,
      quantity: t.quantity,
      unit_price: t.unit_price,
      quantity_unit: t.quantity_unit,
      applicant: t.applicant,
      beneficiary: t.beneficiary,
      incoterm: t.incoterm,
      line_totals: [t.amount],
    };
  if (type === "BILL_OF_LADING")
    return {
      ...base,
      quantity: t.quantity,
      quantity_unit: t.quantity_unit,
      shipment_date: t.latest_shipment,
      loading_port: t.loading_port,
      discharge_port: t.discharge_port,
      consignee: t.applicant,
      notify_party: t.applicant,
      vessel: "MV Synthetic Horizon",
      partial_shipment: false,
      transshipment: false,
    };
  if (type === "PACKING_LIST")
    return { ...base, quantity: t.quantity, quantity_unit: t.quantity_unit };
  if (type === "CERTIFICATE_OF_ORIGIN")
    return { ...base, country: t.beneficiary_country };
  if (type === "INSURANCE_CERTIFICATE")
    return {
      ...base,
      amount: (Number(t.amount) * 1.1).toFixed(2),
      currency: t.currency,
    };
  return base;
}
function UploadModal({
  lc,
  onClose,
  onSaved,
}: {
  lc: LC;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [type, setType] = useState("COMMERCIAL_INVOICE"),
    [file, setFile] = useState<File | null>(null),
    [fields, setFields] = useState(""),
    [reason, setReason] = useState("Initial document submission"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [extracting, setExtracting] = useState(false),
    [ocrText, setOcrText] = useState(""),
    [extractionWarnings, setExtractionWarnings] = useState<string[]>([]),
    [extractionProvider, setExtractionProvider] = useState(""),
    [fieldEvidence, setFieldEvidence] = useState<
      Record<string, { source: string; method: string }>
    >({}),
    [confirmed, setConfirmed] = useState(false);
  const extract = async (selected: File, advanced = false) => {
    setConfirmed(false);
    setExtracting(true);
    setError("");
    if (!advanced) {
      setFields("");
      setOcrText("");
      setExtractionWarnings([]);
      setExtractionProvider("");
      setFieldEvidence({});
    }
    const body = new FormData();
    body.set("file", selected);
    body.set("advanced", String(advanced));
    try {
      const result = await api<{
        text: string;
        fields: Record<string, unknown>;
        document_type?: string;
        warnings?: string[];
        provider?: string;
        evidence?: Record<string, { source: string; method: string }>;
      }>("/lcs/" + lc.id + "/documents/extract", { method: "POST", body });
      setFields(JSON.stringify(result.fields, null, 2));
      setOcrText(result.text);
      setExtractionWarnings(result.warnings || []);
      setExtractionProvider(result.provider || "");
      setFieldEvidence(result.evidence || {});
      if (result.document_type && DOC_TYPES.includes(result.document_type))
        setType(result.document_type);
    } catch (e) {
      setError(String(e));
    } finally {
      setExtracting(false);
    }
  };
  let reviewed: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(fields || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
      reviewed = parsed as Record<string, unknown>;
  } catch {
    /* Advanced JSON is validated on submission. */
  }
  return (
    <Modal title="Add document evidence" onClose={onClose} wide>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!file) {
            setError("Choose a document file");
            return;
          }
          setBusy(true);
          setError("");
          const body = new FormData();
          body.set("type", type);
          body.set("version", String(lc.version));
          body.set("file", file);
          body.set("fields", fields);
          body.set("reason", reason);
          try {
            await api("/lcs/" + lc.id + "/documents", { method: "POST", body });
            onSaved();
          } catch (e) {
            setError(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorBox message={error} />
        <Field label="Document type">
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {DOC_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
        <div className="sample-row">
          <span>Need synthetic evidence for this case?</span>
          <button
            type="button"
            className="text-link"
            onClick={() =>
              saveJson(sampleFields(lc, type), type.toLowerCase() + ".json")
            }
          >
            <ArrowDownToLine size={15} /> Download matching sample
          </button>
        </div>
        <Field
          label="Document file"
          hint="PDF, PNG, JPEG or JSON, up to 5 MB. Text PDFs are read locally (up to 50 pages). Scans and images are sent to OCR.space: maximum 1 MB and 3 PDF pages."
        >
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.json"
            required
            disabled={extracting || busy}
            onChange={(e) => {
              const selected = e.target.files?.[0] || null;
              setFile(selected);
              setFields("");
              setOcrText("");
              if (selected) void extract(selected);
            }}
          />
        </Field>
        {extracting && (
          <p role="status">Reading your document and extracting fields…</p>
        )}
        {file && !extracting && (
          <>
            {extractionProvider && (
              <p role="status">
                {Object.keys(reviewed).length} fields extracted with{" "}
                {extractionProvider}. Review the values below before saving.
              </p>
            )}
            {extractionWarnings.map((warning) => (
              <p role="status" key={warning}>
                {warning}
              </p>
            ))}
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => void extract(file)}
            >
              Retry extraction
            </button>
            {!file.name.toLowerCase().endsWith(".json") && (
              <button
                type="button"
                className="button"
                disabled={busy || file.size > 1024 * 1024}
                onClick={() => void extract(file, true)}
              >
                Try advanced OCR
              </button>
            )}
            {!file.name.toLowerCase().endsWith(".json") && (
              <p className="field-hint">
                Advanced OCR sends the document to OCR.space Engine 3 and
                replaces the extracted values. Use it for difficult scans or
                layouts (up to 1 MB / 3 pages).
              </p>
            )}
            <p>
              Review extracted values against your document. Missing or
              ambiguous values are left blank. OCR reads text; field recognition
              depends on document labels and layout.
            </p>
            <div className="form-grid">
              {[
                "number",
                "issue_date",
                "amount",
                "currency",
                "quantity",
                "quantity_unit",
                "unit_price",
                "applicant",
                "beneficiary",
                "consignee",
                "notify_party",
                "shipment_date",
                "loading_port",
                "discharge_port",
                "incoterm",
                "country",
                "vessel",
              ].map((name) => (
                <Field
                  key={name}
                  label={pretty(name)}
                  hint={
                    (name === "number" || name === "issue_date") &&
                    !reviewed[name]
                      ? "Required to save. This value was not found; enter the actual document detail."
                      : fieldEvidence[name]
                        ? `Document source: ${fieldEvidence[name].source}`
                        : undefined
                  }
                >
                  <input
                    type={name.endsWith("date") ? "date" : "text"}
                    required={name === "number" || name === "issue_date"}
                    value={String(reviewed[name] ?? "")}
                    onChange={(e) => {
                      setConfirmed(false);
                      const next = { ...reviewed };
                      if (e.target.value) next[name] = e.target.value;
                      else delete next[name];
                      setFields(JSON.stringify(next, null, 2));
                    }}
                  />
                </Field>
              ))}
            </div>
            {ocrText && (
              <details open>
                <summary>Recognized document text</summary>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    maxHeight: 240,
                    overflow: "auto",
                  }}
                >
                  {ocrText}
                </pre>
              </details>
            )}
          </>
        )}
        <details>
          <summary>Advanced structured fields / sample data</summary>
          <Field
            label="Reviewed structured fields (JSON)"
            hint="Automatically populated by OCR. You can also edit the structured fields directly."
          >
            <textarea
              className="code-input"
              rows={5}
              value={fields}
              onChange={(e) => setFields(e.target.value)}
              placeholder={JSON.stringify(sampleFields(lc, type), null, 2)}
            />
          </Field>
          <button
            type="button"
            className="text-link"
            onClick={() =>
              setFields(JSON.stringify(sampleFields(lc, type), null, 2))
            }
          >
            Fill sample fields for manual review
          </button>
        </details>
        {file && (
          <Field label="Review confirmation">
            <label>
              <input
                type="checkbox"
                required
                disabled={extracting}
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />{" "}
              I reviewed the extracted fields against the document.
            </label>
          </Field>
        )}
        <Field label="Submission / replacement reason">
          <textarea
            minLength={10}
            maxLength={1000}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <div className="modal-actions">
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button primary" disabled={busy || extracting}>
            <Upload size={16} />
            {busy ? "Securing document…" : "Upload document"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
