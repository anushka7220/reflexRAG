import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Repo } from "../lib/types";
import { useGuide } from "../lib/guide";

function timeAgo(iso: string | null): string {
  if (!iso) return "not indexed";
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function dotClass(status: string): string {
  if (status === "done") return "dot done";
  if (status === "failed") return "dot failed";
  return "dot queued";
}

export default function RepoSearch({ onPick }: { onPick: (r: Repo) => void }) {
  const [value, setValue] = useState("");
  const [repos, setRepos] = useState<Repo[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { focus, blur } = useGuide();

  useEffect(() => {
    api.listRepos().then(setRepos).catch(() => {});
  }, []);

  async function submit() {
    const url = value.trim();
    if (!url || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const full = url.startsWith("http") ? url : `https://github.com/${url}`;
      const repo = await api.addRepo(full);
      onPick(repo);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="stage">
      <div className="panes">
        {/* Left pane: paste a repository */}
        <section className="pane">
          <span className="eyebrow">Repository history, indexed</span>
          <h1 className="headline">
            Paste a repository.<br />Ask why it&rsquo;s <em>built that way</em>.
          </h1>
          <p className="sub">
            Most tools read the code. reflexRAG also reads the issues, pull
            requests, and commits around it.
          </p>
          <div className="field" data-guide="search">
            <span className="field-prefix">github.com/</span>
            <input
              value={value}
              onFocus={() =>
                focus({ target: "search", say: "Go on \u2014 owner/repo.", mood: "curious" })
              }
              onBlur={blur}
              onChange={(e) => {
                setValue(e.target.value);
                focus({
                  target: "search",
                  say: e.target.value.includes("/")
                    ? "That looks right. Hit Index."
                    : "Keep going\u2026 owner/repo.",
                  mood: "curious",
                });
              }}
              onKeyDown={(e) => { if (e.key === "Enter") void submit(); }}
              placeholder="owner/repo"
              spellCheck={false}
              autoFocus
              aria-label="GitHub repository"
            />
            <button
              className="primary-btn"
              onClick={() => void submit()}
              disabled={!value.trim() || submitting}
            >
              {submitting ? "Starting\u2026" : "Index"}
            </button>
          </div>
          <p className="hint">
            Public repositories only. Small ones index in about a minute.
          </p>
          {error && <div className="err-note">{error}</div>}
        </section>

        {/* Right pane: everything already indexed */}
        <section className="pane pane-lib" data-guide="library">
          <span className="eyebrow">Already indexed</span>
          {repos.length === 0 ? (
            <p className="sub" style={{ marginTop: 14 }}>
              Nothing here yet. Index a repository and it will appear in this
              shelf, ready to chat with instantly.
            </p>
          ) : (
            <div className="recent-grid">
              {repos.map((r) => (
                <button
                  key={r.id}
                  className="repo-card"
                  data-guide={`repo-${r.id}`}
                  onMouseEnter={() =>
                    focus({
                      target: `repo-${r.id}`,
                      say:
                        r.status === "done"
                          ? `${r.chunk_count} passages ready. Click to chat.`
                          : `This one is ${r.status}.`,
                      mood: r.status === "done" ? "happy" : "idle",
                    })
                  }
                  onMouseLeave={blur}
                  onFocus={() =>
                    focus({ target: `repo-${r.id}`, say: "Click to chat.", mood: "happy" })
                  }
                  onBlur={blur}
                  onClick={() => onPick(r)}
                >
                  <div className="repo-card-name">
                    <span className={dotClass(r.status)} />
                    <span>{r.owner}/{r.name}</span>
                  </div>
                  <div className="repo-card-meta">
                    {r.status === "done"
                      ? `${r.chunk_count} passages \u00b7 ${timeAgo(r.last_ingested_at)}`
                      : r.status}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}