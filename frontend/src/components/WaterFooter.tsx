/* Footer with flowing-water animation: three SVG wave bands drifting at
   different speeds and directions, so the motion reads as water rather than
   a single sliding shape. Colors come from --water-* tokens (blue in both
   themes). The waves are wider than the footer and translate horizontally
   on a loop, so the edges never show a seam. */

export default function WaterFooter() {
  return (
    <footer className="ftr">
      <svg
        className="ftr-water"
        viewBox="0 0 1200 46"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <rect x="0" y="0" width="1200" height="46" fill="var(--water-1)" />
        <g className="ftr-wave w3">
          <path
            d="M0 30 Q 70 20 140 30 T 280 30 T 420 30 T 560 30 T 700 30 T 840 30 T 980 30 T 1120 30 T 1260 30 V46 H0 Z"
            fill="var(--water-2)"
          />
        </g>
        <g className="ftr-wave w2">
          <path
            d="M0 34 Q 60 26 120 34 T 240 34 T 360 34 T 480 34 T 600 34 T 720 34 T 840 34 T 960 34 T 1080 34 T 1200 34 T 1320 34 V46 H0 Z"
            fill="var(--water-3)"
          />
        </g>
        <g className="ftr-wave">
          <path
            d="M0 38 Q 50 32 100 38 T 200 38 T 300 38 T 400 38 T 500 38 T 600 38 T 700 38 T 800 38 T 900 38 T 1000 38 T 1100 38 T 1200 38 T 1300 38 V46 H0 Z"
            fill="var(--water-1)"
            opacity="0.7"
          />
        </g>
      </svg>

      <span className="ftr-mono">reflexRAG</span>
      <span className="ftr-dot" />
      <span>The code says what. The history says why.</span>
      <span className="ftr-spacer" />
      <a href="https://github.com/anushka7220/reflexRAG" target="_blank" rel="noreferrer">
        Source
      </a>
      <span className="ftr-dot" />
      <a href="https://github.com/anushka7220/reflexRAG#readme" target="_blank" rel="noreferrer">
        Docs
      </a>
      <span className="ftr-dot" />
      <span className="ftr-mono">Built for engineers · v0.1</span>
    </footer>
  );
}