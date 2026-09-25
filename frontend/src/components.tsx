import { cloneElement, useEffect, useId, useRef } from "react";
import type { ReactElement, ReactNode } from "react";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  X,
} from "lucide-react";
import type { LC } from "./types";

export const pretty = (s: string) =>
  s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export const dateTime = (s: string) =>
  new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
export const money = (amount: string, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount));
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge b-${value.toLowerCase()}`}>
      <i />
      {pretty(value)}
    </span>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} /> Loading workspace…
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">◇</div>
      <h3>{title}</h3>
      <p>
        {children ||
          "Items will appear here as your cases move through the workflow."}
      </p>
    </div>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{actions}</div>
    </div>
  );
}
export function Pagination({
  page,
  total,
  size = 12,
  onChange,
}: {
  page: number;
  total: number;
  size?: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${(page - 1) * size + 1}–${Math.min(page * size, total)} of ${total}`
          : "0"}{" "}
        records
      </span>
      <div>
        <button
          aria-label="Previous page"
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={15} />
        </button>
        <span>Page {page}</span>
        <button
          aria-label="Next page"
          disabled={page * size >= total}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}
export function CaseTable({
  cases,
  onOpen,
}: {
  cases: LC[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>LC reference / applicant</th>
            <th>Value</th>
            <th>Status</th>
            <th>Risk score</th>
            <th>SLA</th>
            <th aria-label="Open case" />
          </tr>
        </thead>
        <tbody>
          {cases.map((lc) => (
            <tr key={lc.id}>
              <td>
                <button className="text-link" onClick={() => onOpen(lc.id)}>
                  {lc.reference}
                </button>
                <small>{lc.terms.applicant}</small>
              </td>
              <td>
                <strong>{money(lc.terms.amount, lc.terms.currency)}</strong>
                <small>
                  {lc.terms.currency} · {lc.terms.lc_type.toLowerCase()} credit
                </small>
              </td>
              <td>
                <Badge value={lc.status} />
              </td>
              <td>
                <div className="risk-cell">
                  <span className={"risk-value " + lc.risk_band.toLowerCase()}>
                    {lc.risk_score}
                  </span>
                  <span className="mini-track">
                    <i
                      style={{ width: `${lc.risk_score}%` }}
                      className={lc.risk_band.toLowerCase()}
                    />
                  </span>
                </div>
              </td>
              <td>
                <Badge value={lc.sla} />
              </td>
              <td>
                <button
                  className="icon-button"
                  aria-label={`Open ${lc.reference}`}
                  onClick={() => onOpen(lc.id)}
                >
                  <ArrowUpRight size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!cases.length && (
        <Empty title="No matching cases">
          Try a different search or create a new letter of credit.
        </Empty>
      )}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? "modal wide" : "modal"}
      onCancel={onClose}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {cloneElement(
        children as ReactElement<{ id: string; "aria-describedby"?: string }>,
        { id, "aria-describedby": hint ? id + "-hint" : undefined },
      )}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="error-box" role="alert">
      {message}
    </div>
  ) : null;
}
