import { useEffect, useState } from "react";
import { api, auth, consumeTokenFromHash } from "./lib/api";
import type { Repo, User } from "./lib/types";
import { useTheme } from "./lib/useTheme";
import RepoSearch from "./components/RepoSearch";
import IngestProgress from "./components/IngestProgress";
import Chat from "./components/Chat";
import Sidebar from "./components/Sidebar";
import WaterFooter from "./components/WaterFooter";
import GuideInkling from "./components/GuideInkling";
import { GuideProvider, useGuide } from "./lib/guide";

type Boot = "checking" | "signed-out" | "signed-in";

function Glyph() {
  return (
    <svg className="hdr-glyph" viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <path d="M15 3 C 9 3, 6 9, 6 14.5 C 6 20, 10 23.5, 15 23.5 C 20 23.5, 24 20, 24 14.5 C 24 9, 21 3, 15 3 Z" fill="var(--sand)" stroke="var(--terra)" strokeWidth="1.4" />
      <circle cx="11.6" cy="13.5" r="2.1" fill="#fdf9ee" />
      <circle cx="18.4" cy="12.8" r="2.1" fill="#fdf9ee" />
      <circle cx="11.9" cy="13.7" r="1" fill="#33241a" />
      <circle cx="18.7" cy="13" r="1" fill="#33241a" />
      <path d="M9 23 C 6 26, 5.5 28, 7 29.5" stroke="var(--blue-deep)" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M15 24 C 15 26.5, 15 28, 15 29.5" stroke="var(--rust)" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M21 23 C 24 26, 24.5 28, 23 29.5" stroke="var(--rust)" strokeWidth="2" strokeLinecap="round" fill="none" />
    </svg>
  );
}

function SunMoon({ theme }: { theme: "light" | "dark" }) {
  return theme === "dark" ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" fill="currentColor" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="4.5" fill="currentColor" stroke="none" />
      <g strokeLinecap="round">
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2 2M17.1 17.1l2 2M19.1 4.9l-2 2M6.9 17.1l-2 2" />
      </g>
    </svg>
  );
}

function Header({
  user, repo, theme, onToggleTheme, onHome, onSignOut,
}: {
  user: User | null; repo: Repo | null; theme: "light" | "dark";
  onToggleTheme: () => void; onHome: () => void; onSignOut: () => void;
}) {
  return (
    <header className="hdr">
      <button className="hdr-mark" onClick={onHome} aria-label="Home">
        <Glyph />reflex<span>RAG</span>
      </button>
      {repo && (
        <>
          <span className="hdr-divider" />
          <div className="hdr-repo">
            <b>{repo.owner}/{repo.name}</b>
            {repo.chunk_count > 0 && <span className="hdr-repo-badge">{repo.chunk_count} passages</span>}
          </div>
        </>
      )}
      <span className="hdr-spacer" />
      <nav className="hdr-nav">
        <a href={repo ? repo.github_url : "https://github.com"} target="_blank" rel="noreferrer">
          {repo ? "View on GitHub" : "GitHub"}
        </a>
        {repo && <a onClick={onHome} style={{ cursor: "pointer" }}>Change repo</a>}
      </nav>
      <button className="theme-btn" onClick={onToggleTheme} aria-label="Toggle theme" title="Toggle light/dark">
        <SunMoon theme={theme} />
      </button>
      {user && (
        <div className="hdr-user">
          {user.avatar_url && <img src={user.avatar_url} alt="" />}
          <span className="hdr-user-name">{user.username}</span>
          <button className="ghost-btn" onClick={onSignOut}>Sign out</button>
        </div>
      )}
    </header>
  );
}

function AppInner() {
  const [boot, setBoot] = useState<Boot>("checking");
  const [user, setUser] = useState<User | null>(null);
  const [repo, setRepo] = useState<Repo | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [theme, toggleTheme] = useTheme();
  const { setBase } = useGuide();

  // Ambient guidance: whatever the app is doing, Inkling always has a
  // target and a line. Direct interaction (typing, hovering) temporarily
  // overrides this via focus()/blur() in the child components.
  useEffect(() => {
    if (boot === "signed-out") {
      setBase({ target: "signin", say: "Sign in and we'll dig into a repo.", mood: "curious" });
    } else if (!repo) {
      setBase({ target: "search", say: "Paste a repo here \u2014 I'll dig in.", mood: "curious" });
    } else if (repo.status !== "done") {
      setBase({ target: "progress", say: "Reading the history\u2026 hang tight.", mood: "working" });
    } else {
      setBase({ target: "composer", say: "Ask me why it's built this way.", mood: "curious" });
    }
  }, [boot, repo?.id, repo?.status, setBase]);

  useEffect(() => {
    consumeTokenFromHash();
    if (!auth.get()) { setBoot("signed-out"); return; }
    api.me().then((u) => { setUser(u); setBoot("signed-in"); })
      .catch(() => { auth.clear(); setBoot("signed-out"); });
  }, []);

  function goHome() { setRepo(null); setSessionId(null); }
  function signOut() { auth.clear(); setUser(null); setRepo(null); setSessionId(null); setBoot("signed-out"); }
  useEffect(() => { setSessionId(null); }, [repo?.id]);

  if (boot === "checking") {
    return <div className="app"><div className="stage"><span className="spin" /></div></div>;
  }

  if (boot === "signed-out") {
    return (
      <div className="shell">
        <Header user={null} repo={null} theme={theme} onToggleTheme={toggleTheme} onHome={goHome} onSignOut={signOut} />
        <div className="stage">
          <div className="hero-card" data-guide="signin" style={{ maxWidth: 520 }}>
            <span className="eyebrow">reflexRAG</span>
            <h1 className="headline">The code says what.<br />The history says <em>why</em>.</h1>
            <p className="sub">Chat with any public GitHub repository, including the issues, pull requests, and commits that shaped it.</p>
            <a className="primary-btn" href={auth.loginUrl()}>Continue with GitHub</a>
            <p className="hint">Read-only access to public repositories.</p>
          </div>
        </div>
        <WaterFooter />
        <GuideInkling />
      </div>
    );
  }

  const ready = repo && repo.status === "done";

  return (
    <div className="shell">
      <Header user={user} repo={repo} theme={theme} onToggleTheme={toggleTheme} onHome={goHome} onSignOut={signOut} />
      {!repo && (
        <div className="body no-aside"><div className="main"><RepoSearch onPick={setRepo} /></div></div>
      )}
      {repo && !ready && (
        <div className="body no-aside"><div className="main"><IngestProgress repo={repo} onReady={setRepo} onCancel={goHome} /></div></div>
      )}
      {repo && ready && (
        <div className="body">
          <Sidebar repoId={repo.id} activeSessionId={sessionId} onSelect={setSessionId} onNew={() => setSessionId(null)} refreshKey={sidebarKey} />
          <div className="main">
            <Chat key={sessionId ?? "new"} repo={repo} sessionId={sessionId}
              onSessionCreated={(id) => { setSessionId(id); setSidebarKey((k) => k + 1); }} />
          </div>
        </div>
      )}
      <WaterFooter />
      <GuideInkling />
    </div>
  );
}

export default function App() {
  return (
    <GuideProvider>
      <AppInner />
    </GuideProvider>
  );
}