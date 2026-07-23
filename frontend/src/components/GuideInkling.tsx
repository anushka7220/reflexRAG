import { useEffect, useState } from "react";
import Inkling from "./Inkling";
import { useGuide } from "../lib/guide";

/* The drifting guide.

   Reads its aim from the guide context, so typing in a field or hovering a
   card can redirect it mid-flight. Looks the target element up by
   data-guide="<key>", reads its rect, and glides beside it; CSS transitions
   on left/top do the travel, the drift keyframes do the idle float.

   Because targets can change while he is still moving, the position effect
   re-runs on every aim change and simply retargets, which reads as him
   changing course rather than teleporting. */

const W = 110;   // roughly his rendered width
const PAD = 24;  // breathing room from the target and the viewport edge

export default function GuideInkling() {
  const { aim } = useGuide();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [anchor, setAnchor] = useState<"center" | "left" | "right">("center");

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
      if (roomRight > W + PAD * 2) {
        x = r.right + PAD;               // prefer just right of the target
      } else if (r.left > W + PAD * 2) {
        x = r.left - W - PAD;            // no room: swim to its left instead
      } else {
        x = window.innerWidth - W - PAD; // target spans the width: hug the edge
      }
      x = Math.max(PAD, Math.min(x, window.innerWidth - W - PAD));

      const y = Math.max(
        96,
        Math.min(r.top + r.height / 2 - 55, window.innerHeight - 230)
      );

      setPos({ x, y });

      // Anchor the speech bubble away from whichever edge is close, so it
      // never gets clipped off screen.
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

  if (!pos) return null;

  return (
    <div className="guide guide-float" style={{ left: pos.x, top: pos.y }}>
      {aim.say && <div className={`guide-bubble anchor-${anchor}`}>{aim.say}</div>}
      <Inkling mood={aim.mood ?? "curious"} size={104} />
    </div>
  );
}