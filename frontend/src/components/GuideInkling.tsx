import { useEffect, useRef, useState } from "react";
import Inkling from "./Inkling";
import { useGuide } from "../lib/guide";

const W = 110;
const PAD = 24;
const BUBBLE_MS = 3500; // how long the caption stays before fading

type Bubble = { id: number; x: number; y: number; size: number };

export default function GuideInkling() {
  const { aim } = useGuide();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [anchor, setAnchor] = useState<"center" | "left" | "right">("center");
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [sayVisible, setSayVisible] = useState(true);

  const wrapRef = useRef<HTMLDivElement>(null);
  const prevPos = useRef<{ x: number; y: number } | null>(null);
  const bubbleId = useRef(0);

  const alert = Boolean((aim as { alert?: boolean }).alert);

  // Show the caption fresh whenever the text changes, then fade it out
  // after a few seconds so it never permanently covers anything behind him.
  useEffect(() => {
    if (!aim.say) return;
    setSayVisible(true);
    const t = window.setTimeout(() => setSayVisible(false), BUBBLE_MS);
    return () => window.clearTimeout(t);
  }, [aim.say]);

  useEffect(() => {
    function corner() {
      setPos({ x: window.innerWidth - W - PAD, y: window.innerHeight - 250 });
      setAnchor("right");
    }
    function place() {
      if (!aim.target) return corner();
      const el = document.querySelector<HTMLElement>(`[data-guide="${aim.target}"]`);
      if (!el) return corner();
      const r = el.getBoundingClientRect();
      const roomRight = window.innerWidth - r.right;
      let x: number;
      if (roomRight > W + PAD * 2) x = r.right + PAD;
      else if (r.left > W + PAD * 2) x = r.left - W - PAD;
      else x = window.innerWidth - W - PAD;
      x = Math.max(PAD, Math.min(x, window.innerWidth - W - PAD));
      const y = Math.max(96, Math.min(r.top + r.height / 2 - 55, window.innerHeight - 230));
      setPos({ x, y });
      const centre = x + W / 2;
      if (centre > window.innerWidth - 210) setAnchor("right");
      else if (centre < 210) setAnchor("left");
      else setAnchor("center");
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [aim.target]);

  useEffect(() => {
    if (!pos) return;
    const prev = prevPos.current;
    prevPos.current = pos;
    if (!prev) return;
    const dist = Math.hypot(pos.x - prev.x, pos.y - prev.y);
    if (dist < 40) return;
    let stopped = false;
    function drop() {
      const el = wrapRef.current;
      if (!el || stopped) return;
      const r = el.getBoundingClientRect();
      const id = bubbleId.current++;
      const b: Bubble = {
        id,
        x: r.left + W / 2 + (Math.random() * 18 - 9),
        y: r.top + 60 + (Math.random() * 10 - 5),
        size: 4 + Math.random() * 5,
      };
      setBubbles((cur) => [...cur.slice(-7), b]);
      window.setTimeout(() => {
        setBubbles((cur) => cur.filter((x) => x.id !== id));
      }, 1100);
    }
    const dropTimer = window.setInterval(drop, 150);
    const stopTimer = window.setTimeout(() => {
      stopped = true;
      window.clearInterval(dropTimer);
    }, 1500);
    return () => {
      stopped = true;
      window.clearInterval(dropTimer);
      window.clearTimeout(stopTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos?.x, pos?.y]);

  if (!pos || aim.hidden) return null;

  return (
    <>
      {bubbles.map((b) => (
        <span
          key={b.id}
          className="wake-bubble"
          style={{ left: b.x, top: b.y, width: b.size, height: b.size }}
        />
      ))}
      <div
        ref={wrapRef}
        className={`guide guide-float${alert ? " guide-alert" : ""}`}
        style={{ left: pos.x, top: pos.y }}
      >
        <span className="guide-ripple" />
        {aim.say && (
          <div className={`guide-bubble anchor-${anchor}${sayVisible ? "" : " faded"}`}>
            {aim.say}
          </div>
        )}
        <Inkling mood={aim.mood ?? "curious"} size={78} />
      </div>
    </>
  );
}