import { useMemo } from "react";

/* Ocean — the living underwater backdrop.

   Renders behind everything (fixed, z-index 0, pointer-events none). Four
   layers, all pure SVG/CSS so it's cheap and GPU-friendly:

     1. depth gradient  — lighter near the top (surface light), deeper below
     2. god-rays        — faint light shafts drifting from the surface
     3. bubbles         — slow columns of bubbles rising and wobbling
     4. motes           — tiny suspended particles drifting sideways (current)

   Everything is slow and low-opacity on purpose: ocean movement is gentle,
   not busy. Fully paused for prefers-reduced-motion via the CSS. Bubble and
   mote positions are randomized once on mount (useMemo) so each load feels
   a little different without re-randomizing every render. */

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export default function Ocean() {
  // Generate bubble + mote fields once. Small counts — restraint is the whole
  // point; a busy ocean reads as a screensaver, not a product.
  const bubbles = useMemo(
    () =>
      Array.from({ length: 14 }, (_, i) => ({
        id: i,
        left: rand(2, 98),          // vw
        size: rand(4, 12),          // px
        dur: rand(11, 22),          // s to rise
        delay: rand(0, 16),         // s
        drift: rand(-24, 24),       // px horizontal wobble
        opacity: rand(0.06, 0.18),
      })),
    []
  );

  const motes = useMemo(
    () =>
      Array.from({ length: 22 }, (_, i) => ({
        id: i,
        top: rand(0, 100),
        left: rand(0, 100),
        size: rand(1.5, 3.5),
        dur: rand(26, 48),
        delay: rand(0, 20),
        opacity: rand(0.05, 0.14),
      })),
    []
  );

  return (
    <div className="ocean" aria-hidden="true">
      {/* 1. depth gradient handled in CSS on .ocean::before */}

      {/* 2. god-rays: a few wide, faint light shafts from the surface */}
      <div className="ocean-rays">
        <span className="ray r1" />
        <span className="ray r2" />
        <span className="ray r3" />
      </div>

      {/* 3. rising bubbles */}
      <div className="ocean-bubbles">
        {bubbles.map((b) => (
          <span
            key={b.id}
            className="bubble"
            style={{
              left: `${b.left}vw`,
              width: `${b.size}px`,
              height: `${b.size}px`,
              opacity: b.opacity,
              animationDuration: `${b.dur}s`,
              animationDelay: `${b.delay}s`,
              // custom prop the keyframe reads for horizontal wobble
              ["--drift" as string]: `${b.drift}px`,
            }}
          />
        ))}
      </div>

      {/* 4. suspended motes drifting on the current */}
      <div className="ocean-motes">
        {motes.map((m) => (
          <span
            key={m.id}
            className="mote"
            style={{
              top: `${m.top}%`,
              left: `${m.left}%`,
              width: `${m.size}px`,
              height: `${m.size}px`,
              opacity: m.opacity,
              animationDuration: `${m.dur}s`,
              animationDelay: `${m.delay}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}