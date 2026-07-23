import { useEffect, useRef, useState } from "react";

/* Inkling, the reflexRAG guide.

   An octopus because the octopus IS the architecture: many arms reaching
   into issues, PRs, commits, and code at once, one brain connecting them.
   Warm (rust) arms carry the "why", cool (blue) arms carry the "what",
   the same split the citation cards use.

   Alive in three ways:
   - Eyes track the cursor anywhere on the page (pupils clamp inside the eye).
   - He blinks on a natural random interval.
   - Moods: idle (sway), curious (wide eyes), working (eyes dart, arms
     hustle), happy (squint smile). */

export type InklingMood = "idle" | "curious" | "working" | "happy";

export default function Inkling({
  mood = "idle",
  size = 150,
}: {
  mood?: InklingMood;
  size?: number;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [pupil, setPupil] = useState({ x: 0, y: 0 });
  const [blink, setBlink] = useState(false);
  const dartRef = useRef<number | null>(null);

  // Eyes follow the cursor. Pupil offset is clamped to stay in the eye.
  useEffect(() => {
    if (mood === "working") return; // working mode darts instead
    function onMove(e: MouseEvent) {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height * 0.38;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, dist / 220);
      setPupil({ x: (dx / dist) * 3.2 * reach, y: (dy / dist) * 3.2 * reach });
    }
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mood]);

  // Working: eyes dart left-right like he's scanning pages.
  useEffect(() => {
    if (mood !== "working") return;
    let flip = 1;
    dartRef.current = window.setInterval(() => {
      flip = -flip;
      setPupil({ x: 3 * flip, y: 1.2 });
    }, 420);
    return () => {
      if (dartRef.current) window.clearInterval(dartRef.current);
    };
  }, [mood]);

  // Natural blinking.
  useEffect(() => {
    let alive = true;
    function schedule() {
      const wait = 2400 + Math.random() * 3200;
      window.setTimeout(() => {
        if (!alive) return;
        setBlink(true);
        window.setTimeout(() => {
          setBlink(false);
          schedule();
        }, 140);
      }, wait);
    }
    schedule();
    return () => {
      alive = false;
    };
  }, []);

  const happy = mood === "happy";
  const curious = mood === "curious";
  const eyeRy = blink ? 0.6 : happy ? 6.2 : curious ? 8.6 : 7.6;

  return (
    <svg
      ref={ref}
      className={`inkling ${mood}`}
      width={size}
      height={size * 1.25}
      viewBox="0 0 120 150"
      role="img"
      aria-label="Inkling, the reflexRAG octopus guide"
    >
      {/* arms behind the head: cool = what, warm = why */}
      <g className="arm a1">
        <path d="M30 96 C 12 112, 6 132, 16 146" fill="none" stroke="var(--blue-deep)" strokeWidth="6" strokeLinecap="round" />
        <circle cx="16" cy="146" r="2.6" fill="var(--blue-deep)" />
      </g>
      <g className="arm a2">
        <path d="M45 102 C 36 122, 34 138, 42 148" fill="none" stroke="var(--rust)" strokeWidth="6" strokeLinecap="round" />
        <circle cx="42" cy="148" r="2.6" fill="var(--rust)" />
      </g>
      <g className="arm a3">
        <path d="M75 102 C 84 122, 86 138, 78 148" fill="none" stroke="var(--rust)" strokeWidth="6" strokeLinecap="round" />
        <circle cx="78" cy="148" r="2.6" fill="var(--rust)" />
      </g>
      <g className="arm a4">
        <path d="M90 96 C 108 112, 114 132, 104 146" fill="none" stroke="var(--blue-deep)" strokeWidth="6" strokeLinecap="round" />
        <circle cx="104" cy="146" r="2.6" fill="var(--blue-deep)" />
      </g>
      {/* curl-up arms */}
      <path d="M24 86 C 4 82, 0 62, 12 52" fill="none" stroke="var(--rust)" strokeWidth="6" strokeLinecap="round" />
      <path d="M96 86 C 116 82, 120 62, 108 52" fill="none" stroke="var(--blue-deep)" strokeWidth="6" strokeLinecap="round" />

      {/* head */}
      <path
        d="M60 8 C 32 8, 18 36, 18 62 C 18 88, 36 104, 60 104 C 84 104, 102 88, 102 62 C 102 36, 88 8, 60 8 Z"
        fill="var(--sand)"
        stroke="var(--terra)"
        strokeWidth="2.5"
      />
      {/* freckles */}
      <circle cx="34" cy="44" r="2" fill="var(--terra)" opacity="0.45" />
      <circle cx="86" cy="40" r="2" fill="var(--terra)" opacity="0.45" />
      <circle cx="90" cy="50" r="1.5" fill="var(--terra)" opacity="0.35" />

      {/* eyes: whites + tracking pupils, ry animates for blink/moods */}
      <ellipse cx="46" cy="58" rx="9" ry={eyeRy} fill="#fdf9ee" stroke="var(--terra)" strokeWidth="1.2" />
      <ellipse cx="74" cy="55" rx="9" ry={eyeRy} fill="#fdf9ee" stroke="var(--terra)" strokeWidth="1.2" />
      {!blink && (
        <>
          <circle cx={46 + pupil.x} cy={58 + pupil.y} r="3.8" fill="#33241a" />
          <circle cx={74 + pupil.x} cy={55 + pupil.y} r="3.8" fill="#33241a" />
          <circle cx={47.4 + pupil.x} cy={56.6 + pupil.y} r="1.1" fill="#fdf9ee" />
          <circle cx={75.4 + pupil.x} cy={53.6 + pupil.y} r="1.1" fill="#fdf9ee" />
        </>
      )}
      {/* cheeky brow */}
      <path d="M66 40 Q 74 36, 83 41" fill="none" stroke="var(--rust)" strokeWidth="2" strokeLinecap="round" />
      {/* mouth: smile widens when happy */}
      {happy ? (
        <path d="M46 80 Q 60 92, 74 80" fill="none" stroke="var(--rust)" strokeWidth="2.4" strokeLinecap="round" />
      ) : (
        <path d="M51 82 Q 60 88, 69 82" fill="none" stroke="var(--rust)" strokeWidth="2" strokeLinecap="round" />
      )}
    </svg>
  );
}