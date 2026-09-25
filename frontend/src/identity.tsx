import { useEffect, useState } from "react";
import { KeyRound, Plus, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { dateTime, ErrorBox, Field, Modal, pretty } from "./components";

const roles = [
  "TRADE_ANALYST",
  "COMPLIANCE_REVIEWER",
  "SENIOR_CHECKER",
  "COMPLIANCE_MANAGER",
  "INTERNAL_AUDITOR",
  "EXECUTIVE_VIEWER",
  "SYSTEM_ADMIN",
];
export function CreateUserButton({
  onCreated,
  toast,
}: {
  onCreated: () => void;
  toast: (s: string) => void;
}) {
  const [open, setOpen] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <button
        className="button primary"
        onClick={() => {
          setOpen(true);
          setError("");
        }}
      >
        <Plus size={16} />
        Create demo user
      </button>
      {open && (
        <Modal
          title="Create synthetic demo account"
          onClose={() => setOpen(false)}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              const f = new FormData(e.currentTarget);
              try {
                await api("/users", {
                  method: "POST",
                  body: JSON.stringify(Object.fromEntries(f)),
                });
                setOpen(false);
                onCreated();
                toast("Demo account created and audited");
              } catch (e) {
                setError(String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <ErrorBox message={error} />
            <Field label="Synthetic display name">
              <input name="name" required minLength={3} maxLength={100} />
            </Field>
            <Field
              label="Demo email"
              hint="Only addresses ending @lcverify.demo are permitted."
            >
              <input
                name="email"
                type="email"
                required
                pattern="[a-zA-Z0-9._+\-]+@lcverify\.demo"
              />
            </Field>
            <Field label="Role">
              <select name="role">
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {pretty(r)}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Initial demo password"
              hint="At least 12 characters with uppercase, lowercase and a number. Share only within this local demo."
            >
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
              />
            </Field>
            <Field label="Provisioning reason">
              <textarea
                name="reason"
                minLength={10}
                maxLength={1000}
                required
              />
            </Field>
            <button className="button primary" disabled={busy}>
              Create account
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function ResetPasswordControl({
  userId,
  toast,
}: {
  userId: string;
  toast: (s: string) => void;
}) {
  const [show, setShow] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <button type="button" className="button" onClick={() => setShow(true)}>
        <KeyRound size={15} />
        Reset demo password
      </button>
      {show && (
        <Modal title="Reset local demo password" onClose={() => setShow(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              try {
                await api("/users/" + userId + "/password", {
                  method: "PUT",
                  body: JSON.stringify(Object.fromEntries(f)),
                });
                setShow(false);
                toast("Password reset; all account sessions revoked");
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            <ErrorBox message={error} />
            <Field
              label="New demo password"
              hint="12+ characters; uppercase, lowercase and a number."
            >
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
              />
            </Field>
            <Field label="Reset justification">
              <textarea
                name="reason"
                minLength={10}
                maxLength={1000}
                required
              />
            </Field>
            <div className="info-banner">
              <ShieldCheck size={17} />
              This revokes all account sessions and clears temporary lockout.
              Production recovery uses an approved identity provider.
            </div>
            <button className="button primary">
              Reset and revoke sessions
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

type Session = {
  id: string;
  device: string;
  created_at: string;
  expires_at: string;
};
export function SessionsModal({
  onClose,
  toast,
}: {
  onClose: () => void;
  toast: (s: string) => void;
}) {
  const [sessions, setSessions] = useState<Session[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api<Session[]>("/auth/sessions")
      .then(setSessions)
      .catch((e) => setError(String(e)));
  }, []);
  return (
    <Modal title="Your active sessions" onClose={onClose} wide>
      <ErrorBox message={error} />
      <p>
        Sessions expire after eight hours. Revoking the current session signs
        you out on the next request.
      </p>
      {sessions.map((s) => (
        <article className="document-card" key={s.id}>
          <ShieldCheck size={20} />
          <div>
            <strong>
              {s.device.includes("Mozilla")
                ? "Web browser"
                : s.device || "API client"}
            </strong>
            <small>
              Created {dateTime(s.created_at)} · Expires{" "}
              {dateTime(s.expires_at)}
            </small>
            <code>{s.id}</code>
          </div>
          <button
            className="button"
            onClick={async () => {
              try {
                await api("/auth/sessions/" + s.id, { method: "DELETE" });
                setSessions(sessions.filter((x) => x.id !== s.id));
                toast("Session revoked");
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            Revoke
          </button>
        </article>
      ))}
    </Modal>
  );
}
