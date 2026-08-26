import { useEffect, useRef, useState } from "react";

/* HeroDemo — the auto-swiping proof carousel.

   Three panels, each a mock of a real reflexRAG interaction, cycling on a
   timer. Each panel "types" its question character by character, then reveals
   its answer, holds, and advances. Together they show the three pillars:

     1. WHY     — the code-to-discussion join (code + the PR that explains it)
     2. CAUTION — the self-healing layer catching a duplicate before it's filed
     3. WHO     — the contributor map answering "who do I ask?"

   Entirely static/mock. It's a poster that moves, not a live feature, so it
   never touches the API. Respects prefers-reduced-motion by skipping the
   typing and just showing each panel's final state. */

type Panel = {
  kind: "why" | "caution" | "who";
  tag: string;
  question: string;
  render: () => JSX.Element;
};

const PANELS: Panel[] = [
  {
    kind: "why",
    tag: "the join",
    question: "Why does this fetch use a retry loop?",
    render: () => (
      <>
        <div className="demo-a">
          It retries because the GitHub API rate-limits under load &mdash; a
          contributor added backoff after failures in production.
        </div>
        <div className="demo-split">
          <span className="demo-split-rail" />
          <span className="demo-split-label">what &middot; shaped by &middot; why</span>
        </div>
        <div className="demo-cite code">
          <div className="demo-cite-top">
            <span className="demo-cite-id">fetcher.py</span>
            <span className="demo-cite-lines">42&ndash;51</span>
            <span className="demo-cite-tag">code</span>
          </div>
          <div className="demo-cite-body">
            for attempt in range(MAX_RETRIES):
          </div>
        </div>
        <div className="demo-cite why">
          <div className="demo-cite-top">
            <span className="demo-cite-id">PR #128</span>
            <span className="demo-cite-tag why">why</span>
          </div>
          <div className="demo-cite-body">
            &ldquo;flaky under load in prod &mdash; added exponential backoff.&rdquo;
          </div>
        </div>
      </>
    ),
  },
  {
    kind: "caution",
    tag: "self-healing",
    question: "Bug: pages render blank when merging two PDFs\u2026",
    render: () => (
      <>
        <div className="demo-flag">
          <span className="demo-flag-mark">!</span>
          <span>
            This looks like <b>Issue #2841</b> &mdash; already reported 4 months
            ago and closed as fixed in <b>v4.1.0</b>.
          </span>
        </div>
        <div className="demo-a demo-a-muted">
          Before you file: the blank-page bug on merge was a stream-reset issue,
          patched in #2856. Try upgrading first.
        </div>
        <div className="demo-cite why">
          <div className="demo-cite-top">
            <span className="demo-cite-id">Issue #2841</span>
            <span className="demo-cite-tag why">closed</span>
          </div>
          <div className="demo-cite-body">
            &ldquo;blank pages after merge &mdash; fixed by resetting the buffer.&rdquo;
          </div>
        </div>
      </>
    ),
  },
  {
    kind: "who",
    tag: "contributor map",
    question: "Who should I ask about the encryption code?",
    render: () => (
      <>
        <div className="demo-a">
          Two people own most of it. Start with the first &mdash; they wrote the
          current implementation and review nearly every change to it.
        </div>
        <div className="demo-who">
          <div className="demo-who-row">
            <span className="demo-who-dot" />
            <span className="demo-who-name">@exiledkingcc</span>
            <span className="demo-who-meta">38 commits &middot; 24 reviews on crypt.py</span>
          </div>
          <div className="demo-who-row">
            <span className="demo-who-dot dim" />
            <span className="demo-who-name">@MartinThoma</span>
            <span className="demo-who-meta">wrote the original AES support</span>
          </div>
        </div>
        <div className="demo-cite why">
          <div className="demo-cite-top">
            <span className="demo-cite-id">PR #1932</span>
            <span className="demo-cite-tag why">why</span>
          </div>
          <div className="demo-cite-body">
            &ldquo;rewrote RC4 handling &mdash; see thread for the security context.&rdquo;
          </div>
        </div>
      </>
    ),
  },
];

const TYPE_MS = 42;      // per character
const REVEAL_MS = 520;   // pause after typing, before the answer appears
const HOLD_MS = 3600;    // how long the finished panel stays up

export default function HeroDemo() {
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [revealed, setRevealed] = useState(false);
  const timers = useRef<number[]>([]);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    const panel = PANELS[idx];
    const q = panel.question;

    // clear any scheduled work from the previous panel
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setTyped("");
    setRevealed(false);

    if (reduced) {
      setTyped(q);
      setRevealed(true);
      const t = window.setTimeout(() => setIdx((i) => (i + 1) % PANELS.length), HOLD_MS + 1200);
      timers.current.push(t);
      return () => timers.current.forEach(clearTimeout);
    }

    // 1. type the question
    let ci = 0;
    const typer = window.setInterval(() => {
      ci += 1;
      setTyped(q.slice(0, ci));
      if (ci >= q.length) {
        window.clearInterval(typer);
        // 2. reveal the answer
        const r = window.setTimeout(() => setRevealed(true), REVEAL_MS);
        // 3. hold, then advance
        const a = window.setTimeout(
          () => setIdx((i) => (i + 1) % PANELS.length),
          REVEAL_MS + HOLD_MS
        );
        timers.current.push(r, a);
      }
    }, TYPE_MS);
    timers.current.push(typer as unknown as number);

    return () => {
      window.clearInterval(typer);
      timers.current.forEach(clearTimeout);
    };
  }, [idx, reduced]);

  const panel = PANELS[idx];

  return (
    <div className="demo" aria-hidden="true">
      <div className="demo-head">
        <span className="demo-head-dots"><i /><i /><i /></span>
        <span className="demo-head-tag">{panel.tag}</span>
      </div>

      <div className="demo-q">
        {typed}
        {!revealed && <span className="demo-caret" />}
      </div>

      <div className={`demo-body ${revealed ? "in" : ""}`}>
        {revealed && panel.render()}
      </div>

      <div className="demo-dots">
        {PANELS.map((p, i) => (
          <span key={p.kind} className={`demo-dot ${i === idx ? "on" : ""}`} />
        ))}
      </div>
    </div>
  );
}