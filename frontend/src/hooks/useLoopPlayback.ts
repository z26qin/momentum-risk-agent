import { useEffect, useState } from "react";

export function useLoopPlayback(eventCount: number) {
  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (!playing || eventCount <= 0 || revealed >= eventCount) return;
    const timer = window.setTimeout(() => {
      setRevealed((current) => {
        const next = Math.min(eventCount, current + 1);
        if (next >= eventCount) setPlaying(false);
        return next;
      });
    }, 550);
    return () => window.clearTimeout(timer);
  }, [eventCount, playing, revealed]);

  return {
    revealed,
    playing,
    jump: (count: number) => {
      setPlaying(false);
      setRevealed(Math.max(0, Math.min(eventCount, count)));
    },
    play: () => {
      setRevealed((current) => (current >= eventCount ? 0 : current));
      setPlaying(true);
    },
    pause: () => setPlaying(false),
    step: () => {
      setPlaying(false);
      setRevealed((current) => Math.min(eventCount, current + 1));
    },
    reset: () => {
      setPlaying(false);
      setRevealed(0);
    },
  };
}
