import { useEffect, useState } from "react";
import Inkling from "./Inkling";

/* DeepLoader — the underwater loading moment.

   Fills the "checking" boot state (the /auth/success callback page, while
   the app verifies the token and fetches the profile) with a branded scene
   instead of a bare spinner: Inkling swimming in the deep, bubbles rising
   past him, and a line of playful ocean text that cycles every couple of
   seconds so the wait reads as motion, not a stall.

   Purely presentational — it shows for however long boot takes. The lines
   are flavor, not real status, so they loop gracefully however long that is. */

const LINES = [
  "Diving deep\u2026",
  "Following the current\u2026",
  "Down where the history lives\u2026",
  "Almost to the surface\u2026",
];

// a few bubbles rising past him, spread out
const BUBBLES = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  left: 20 + ((i * 13) % 60),      // % within the scene, clustered around center
  size: 4 + ((i * 5) % 9),
  delay: (i % 5) * 0.4,            // s
  dur: 2.6 + (i % 4) * 0.5,        // s
}));

export default function DeepLoader() {
  const [line, setLine] = useState(0);

  useEffect(() => {
    const t = window.setInterval(() => {
      setLine((i) => (i + 1) % LINES.length);
    }, 2100);
    return () => window.clearInterval(t);
  }, []);

  return (
    <div className="deep" aria-live="polite" aria-busy="true">
      <div className="deep-scene">
        <div className="deep-bubbles" aria-hidden="true">
          {BUBBLES.map((b) => (
            <span
              key={b.id}
              className="deep-bubble"
              style={{
                left: `${b.left}%`,
                width: `${b.size}px`,
                height: `${b.size}px`,
                animationDelay: `${b.delay}s`,
                animationDuration: `${b.dur}s`,
              }}
            />
          ))}
        </div>

        <div className="deep-inkling">
          <Inkling mood="working" size={96} />
        </div>
      </div>

      <div className="deep-line" key={line}>{LINES[line]}</div>
    </div>
  );
}