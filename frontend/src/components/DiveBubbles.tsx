/* DiveBubbles — the column of bubbles that rises past you while you sink.

   Rendered once inside the shell; invisible until the shell gets the
   .diving class (CSS turns .dive-bubbles opacity on). Positions/sizes/
   delays are spread across the width so it reads as a real curtain of
   bubbles rising, not a neat row. Purely decorative, aria-hidden. */

const BUBBLES = Array.from({ length: 18 }, (_, i) => {
  const left = (i * 5.5 + (i % 3) * 4) % 100;      // spread across width
  const size = 5 + ((i * 7) % 13);                  // 5-18px
  const delay = (i % 6) * 45;                        // staggered start (ms)
  const dx = ((i % 5) - 2) * 14;                      // horizontal wobble
  return { left, size, delay, dx, id: i };
});

export default function DiveBubbles() {
  return (
    <div className="dive-bubbles" aria-hidden="true">
      {BUBBLES.map((b) => (
        <span
          key={b.id}
          className="db"
          style={{
            left: `${b.left}vw`,
            width: `${b.size}px`,
            height: `${b.size}px`,
            animationDelay: `${b.delay}ms`,
            ["--dx" as string]: `${b.dx}px`,
          }}
        />
      ))}
    </div>
  );
}