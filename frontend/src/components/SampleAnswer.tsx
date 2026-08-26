/* SampleAnswer — the hero's proof panel.

   The landing screen's job is to sell the one thing reflexRAG does that
   other tools don't: it joins the code to the human reasoning behind it.
   Describing that in a sentence is weak; showing it is strong. So this is a
   static, non-interactive mock of a real answer — a question, a one-line
   reply, then the signature split: what the CODE says (cool/blue) vs WHY it
   says it, pulled from a PR (rust). Same colour logic the live citations
   use, so the palette is legible from the very first screen.

   Deliberately not wired to anything. It's a poster, not a feature. */

export default function SampleAnswer() {
  return (
    <div className="proof" aria-hidden="true">
      <div className="proof-q">Why does this fetch use a retry loop?</div>

      <div className="proof-a">
        It retries because the GitHub API rate-limits under load — a
        contributor added backoff after seeing failures in production.
      </div>

      <div className="proof-split">
        <span className="proof-split-rail" />
        <span className="proof-split-label">what · shaped by · why</span>
      </div>

      <div className="proof-cite code">
        <div className="proof-cite-top">
          <span className="proof-cite-id">fetcher.py</span>
          <span className="proof-cite-lines">42&ndash;51</span>
          <span className="proof-cite-tag">code</span>
        </div>
        <div className="proof-cite-body">
          for attempt in range(MAX_RETRIES):
          <br />
          &nbsp;&nbsp;&nbsp;&nbsp;try: return _get(url)
        </div>
      </div>

      <div className="proof-cite why">
        <div className="proof-cite-top">
          <span className="proof-cite-id">PR #128</span>
          <span className="proof-cite-tag why">why</span>
        </div>
        <div className="proof-cite-body">
          &ldquo;flaky under load in prod &mdash; added exponential backoff so
          ingestion stops dying on secondary limits.&rdquo;
        </div>
      </div>
    </div>
  );
}