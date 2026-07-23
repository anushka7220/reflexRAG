import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Repo } from "../lib/types";
import Inkling from "./Inkling";

const STAGES: { key: string; label: string }[] = [
  { key: "fetching", label: "Reading issues, pull requests, and commits" },
  { key: "chunking", label: "Splitting into passages" },
  { key: "embedding", label: "Building the search index" },
  { key: "extracting", label: "Mapping who owns what" },
  { key: "done", label: "Ready" },
];

const QUIPS = [
  "Eight arms, all busy.",
  "Reading the arguments in the PRs\u2026",
  "Someone had opinions in issue #12.",
  "Connecting code to the people who wrote it.",
];

export default function IngestProgress({
  repo, onReady, onCancel,
}: {
  repo: Repo; onReady: (r: Repo) => void; onCancel: () => void;
}) {
  const [stage, setStage] = useState(repo.status || "fetching");
  const [pct, setPct] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [quip, setQuip] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const q = window.setInterval(() => setQuip((n) => (n + 1) % QUIPS.length), 5200);
    return () => window.clearInterval(q);
  }, []);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const s = await api.repoStatus(repo.id);
        if (!alive) return;
        setStage(s.stage);
        setPct(s.progress_pct ?? 0);
        if (s.stage === "failed") { setError(s.error_msg || "Indexing failed. Try again."); return; }
        if (s.stage === "done") {
          const fresh = await api.getRepo(repo.id).catch(() => repo);
          if (alive) onReady(fresh);
          return;
        }
        timer.current = window.setTimeout(poll, 2000);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    }
    void poll();
    return () => { alive = false; if (timer.current) window.clearTimeout(timer.current); };
  }, [repo.id]);

  const currentIndex = STAGES.findIndex((s) => s.key === stage);

  return (
    <div className="stage">
      <div className="hero-split">
        <div className="prog-card">
          <span className="eyebrow">Indexing</span>
          <h1 className="headline">{repo.owner}/<em>{repo.name}</em></h1>
          <p className="sub">
            You can chat as soon as the index is built; the contributor map
            keeps building after that.
          </p>
          {error ? (
            <>
              <div className="err-note">{error}</div>
              <div style={{ marginTop: 16 }}>
                <button className="primary-btn" onClick={onCancel}>Back</button>
              </div>
            </>
          ) : (
            <>
              <div className="prog-stages">
                {STAGES.map((s, i) => {
                  const state =
                    currentIndex < 0 ? "" : i < currentIndex ? "past" : i === currentIndex ? "active" : "";
                  return (
                    <div key={s.key} className={`prog-stage ${state}`}>
                      <span className="prog-tick">
                        {state === "past" ? "\u2713" : state === "active" ? "\u203a" : "\u00b7"}
                      </span>
                      <span>{s.label}</span>
                      {state === "active" && <span style={{ marginLeft: "auto" }} className="spin" />}
                    </div>
                  );
                })}
              </div>
              <div className="prog-rail"><div className="prog-fill" style={{ width: `${pct}%` }} /></div>
              <p className="hint">This runs in the background. Leaving won&rsquo;t stop it.</p>
            </>
          )}
        </div>
        <div className="inkling-stage">
          <Inkling mood={error ? "idle" : "working"} size={165} />
          <span className="inkling-say">{error ? "Hm. That one fought back." : QUIPS[quip]}</span>
        </div>
      </div>
    </div>
  );
}
