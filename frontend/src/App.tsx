import { useEffect, useState } from "react";
import {
  ArrowRight,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  ChevronDown,
  CircleHelp,
  FileCheck2,
  Files,
  Fingerprint,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Moon,
  Search,
  Settings2,
  ShieldCheck,
  ShieldEllipsis,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api, refreshSession, setToken } from "./api";
import { ErrorBox, Field, Loading, pretty } from "./components";
import type { Notice, User } from "./types";
import {
  DashboardPage,
  WorkbenchPage,
  FindingsPage,
  AuditPage,
  RulesPage,
  ReportsPage,
  AdminPage,
} from "./pages";
import { CaseDetail, CaseForm } from "./case";
import { SessionsModal } from "./identity";

export type Context = {
  user: User;
  go: (path: string) => void;
  toast: (message: string) => void;
  can: (permission: string) => boolean;
};
const navigation = [
  {
    label: "Overview",
    items: [
      ["dashboard", "Overview", LayoutDashboard, "REPORT_VIEW"],
      ["workbench", "LC workbench", BriefcaseBusiness, "LC_VIEW"],
      ["review", "Review queue", FileCheck2, "CASE_REVIEW"],
    ],
  },
  {
    label: "Assurance",
    items: [
      ["documents", "Document center", Files, "DOCUMENT_VIEW"],
      ["discrepancies", "Discrepancies", ShieldEllipsis, "LC_VIEW"],
      ["rules", "Rules catalog", BookOpen, "RULE_VIEW"],
      ["audit", "Audit explorer", Fingerprint, "AUDIT_VIEW"],
    ],
  },
  {
    label: "Intelligence",
    items: [
      ["reports", "Reports & analytics", ChartNoAxesCombined, "REPORT_VIEW"],
      ["admin", "Administration", Settings2, "SYSTEM_CONFIGURE"],
    ],
  },
] as const;

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [route, setRoute] = useState(location.hash.slice(1) || "dashboard"),
    [message, setMessage] = useState(""),
    [dark, setDark] = useState(localStorage.getItem("lcv-theme") === "dark"),
    [notices, setNotices] = useState<Notice[]>([]),
    [showNotices, setShowNotices] = useState(false),
    [search, setSearch] = useState(""),
    [sidebar, setSidebar] = useState(false),
    [showSessions, setShowSessions] = useState(false);
  const go = (path: string) => {
    location.hash = path;
    setSidebar(false);
  };
  useEffect(() => {
    refreshSession().then((u) => {
      setUser(u);
      setReady(true);
    });
    const routeChange = () => setRoute(location.hash.slice(1) || "dashboard");
    const expired = () => setUser(null);
    window.addEventListener("hashchange", routeChange);
    window.addEventListener("session-expired", expired);
    return () => {
      window.removeEventListener("hashchange", routeChange);
      window.removeEventListener("session-expired", expired);
    };
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("lcv-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 6000);
      return () => clearTimeout(timer);
    }
  }, [message]);
  useEffect(() => {
    if (user)
      api<Notice[]>("/notifications")
        .then(setNotices)
        .catch(() => {});
  }, [user, route]);
  if (!ready) return <Loading />;
  if (!user)
    return (
      <Login
        onLogin={(u) => {
          setUser(u);
          go(u.role === "SYSTEM_ADMIN" ? "admin" : "dashboard");
        }}
      />
    );
  const context: Context = {
    user,
    go,
    toast: setMessage,
    can: (p) => user.permissions.includes(p),
  };
  const active = route.split("/")[0].split("?")[0];
  const logout = async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (e) {
      setMessage(String(e));
    } finally {
      setToken("");
      setUser(null);
    }
  };
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (sidebar ? "mobile-open" : "")}>
        <a className="brand" href="#dashboard">
          <span className="brand-icon">
            <ShieldCheck size={27} />
          </span>
          <span>
            LC-VERIFY<small>ENTERPRISE</small>
          </span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-icon">M</span>
          <div>
            Meridian Trade Operations<small>Synthetic workspace</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav>
          {navigation.map((group) => (
            <div className="nav-group" key={group.label}>
              <span className="nav-label">{group.label}</span>
              {group.items
                .filter((item) => context.can(item[3]))
                .map(([key, label, Icon]) => (
                  <a
                    key={key}
                    href={"#" + key}
                    className={
                      active === key ||
                      (active === "case" && key === "workbench")
                        ? "nav-link active"
                        : "nav-link"
                    }
                    onClick={() => setSidebar(false)}
                  >
                    <Icon size={18} />
                    {label}
                    {key === "workbench" && <span className="nav-dot" />}
                  </a>
                ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="assurance-card">
            <ShieldCheck size={21} />
            <strong>Confidence in every credit.</strong>
            <p>
              Explainable checks.
              <br />
              Accountable decisions.
            </p>
            <a href="/api/docs" target="_blank" rel="noreferrer">
              Explore the API <ArrowRight size={14} />
            </a>
          </div>
          <div className="system-status">
            <i /> Synthetic local workspace <span>v1.0</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Open menu"
              onClick={() => setSidebar(!sidebar)}
            >
              <BriefcaseBusiness size={20} />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>
              {active === "case" ? "LC workbench" : pretty(active)}
            </strong>
          </div>
          <div className="topbar-right">
            <form
              className="global-search"
              onSubmit={(e) => {
                e.preventDefault();
                go("workbench?q=" + encodeURIComponent(search));
              }}
            >
              <Search size={16} />
              <input
                aria-label="Search all cases"
                placeholder="Search cases, applicants…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>↵</kbd>
            </form>
            <button
              className="icon-button"
              aria-label="Toggle color theme"
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <div className="notification-anchor">
              <button
                className="icon-button"
                aria-label="Notifications"
                onClick={() => setShowNotices(!showNotices)}
              >
                <Bell size={19} />
                {notices.some((n) => !n.read) && (
                  <i className="notification-dot" />
                )}
              </button>
              {showNotices && (
                <div className="notification-panel">
                  <h3>Notifications</h3>
                  {notices.length ? (
                    notices.map((n) => (
                      <button
                        key={n.id}
                        className={n.read ? "notice read" : "notice"}
                        onClick={async () => {
                          try {
                            await api("/notifications/" + n.id + "/read", {
                              method: "PATCH",
                            });
                            setNotices(
                              notices.map((x) =>
                                x.id === n.id ? { ...x, read: true } : x,
                              ),
                            );
                            if (n.lc_id) go("case/" + n.lc_id);
                            setShowNotices(false);
                          } catch (e) {
                            setMessage(String(e));
                          }
                        }}
                      >
                        {n.message}
                      </button>
                    ))
                  ) : (
                    <p>You’re all caught up.</p>
                  )}
                </div>
              )}
            </div>
            <button
              className="user-profile profile-button"
              aria-label="Manage my sessions"
              onClick={() => setShowSessions(true)}
            >
              <span className="avatar">
                {user.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </span>
              <span>
                <strong>{user.name}</strong>
                <small>{pretty(user.role)}</small>
              </span>
            </button>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <div className="demo-strip">
          <FlaskConical size={14} />
          <span>SYNTHETIC DEMONSTRATION DATA — NOT FOR REAL BANKING USE</span>
          <span className="demo-tag">DEMO ENVIRONMENT</span>
        </div>
        <main key={route}>
          {active === "dashboard" ? (
            <DashboardPage {...context} />
          ) : active === "case" ? (
            <CaseDetail {...context} id={route.split("/")[1]} />
          ) : active === "create" ? (
            <CaseForm {...context} />
          ) : ["workbench", "review", "documents"].includes(active) ? (
            <WorkbenchPage
              {...context}
              mode={active}
              initialSearch={
                new URLSearchParams(route.split("?")[1]).get("q") || ""
              }
            />
          ) : active === "discrepancies" ? (
            <FindingsPage {...context} />
          ) : active === "rules" ? (
            <RulesPage {...context} />
          ) : active === "audit" ? (
            <AuditPage {...context} />
          ) : active === "reports" ? (
            <ReportsPage {...context} />
          ) : active === "admin" ? (
            <AdminPage {...context} />
          ) : (
            <DashboardPage {...context} />
          )}
        </main>
        <footer className="app-footer">
          <span>
            LC-Verify Enterprise <span>·</span> Intelligent trade assurance
          </span>
          <span>
            <ShieldCheck size={12} /> Synthetic data. Human decisions. Complete
            traceability.
          </span>
        </footer>
      </div>
      {showSessions && (
        <SessionsModal
          onClose={() => setShowSessions(false)}
          toast={setMessage}
        />
      )}
      {message && (
        <div className="toast" role="status">
          <ShieldCheck size={18} />
          <span>{message}</span>
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setMessage("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("analyst@lcverify.demo"),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="login-page">
      <section className="login-story">
        <a className="brand" href="#">
          <span className="brand-icon">
            <ShieldCheck size={29} />
          </span>
          <span>
            LC-VERIFY<small>ENTERPRISE</small>
          </span>
        </a>
        <div>
          <span className="eyebrow">INTELLIGENT TRADE ASSURANCE</span>
          <h1>
            Every document.
            <br />
            Every decision.
            <br />
            <em>Complete confidence.</em>
          </h1>
          <p>
            A connected workspace for documentary-credit operations, explainable
            validation, and accountable human review.
          </p>
          <div className="login-features">
            <span>
              <FileCheck2 /> Evidence-led validation
            </span>
            <span>
              <Users /> Independent maker-checker controls
            </span>
            <span>
              <Fingerprint /> Verifiable audit history
            </span>
          </div>
        </div>
        <small>
          Built for a better understanding of trade-finance operations.
        </small>
        <div className="orbit orbit-one" />
        <div className="orbit orbit-two" />
      </section>
      <section className="login-form-wrap">
        <form
          className="login-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const result = await api<{ access_token: string; user: User }>(
                "/auth/login",
                { method: "POST", body: JSON.stringify({ email, password }) },
              );
              setToken(result.access_token);
              onLogin(result.user);
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <span className="small-label">
            <FlaskConical size={15} /> SYNTHETIC DEMO WORKSPACE
          </span>
          <h2>Welcome to your workbench</h2>
          <p>Sign in to manage the next step in every credit.</p>
          <ErrorBox message={error} />
          <Field label="Demo persona">
            <select
              aria-label="Demo persona"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            >
              {[
                "analyst",
                "reviewer",
                "checker",
                "manager",
                "auditor",
                "executive",
                "admin",
              ].map((role) => (
                <option key={role} value={role + "@lcverify.demo"}>
                  {pretty(role)} · {role}@lcverify.demo
                </option>
              ))}
            </select>
          </Field>
          <Field label="Email address">
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your local demo password"
            />
          </Field>
          <button className="button primary full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in to workspace"}
            <ArrowRight size={17} />
          </button>
          <div className="login-help">
            <CircleHelp size={19} />
            <p>
              Your generated demo password is in{" "}
              <code>.demo-credentials.json</code> in the project folder. All
              seven personas use this local demo password.
            </p>
          </div>
          <div className="login-privacy">
            <ShieldCheck size={16} /> Synthetic demonstration data only.
            <br />
            Not for real banking use.
          </div>
        </form>
      </section>
    </div>
  );
}
