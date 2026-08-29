import { useEffect, useState } from "react";

export function useLoopPlayback(runId: string, eventCount: number) {
  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    setRevealed(0);
    setPlaying(true);
  }, [runId]);

  useEffect(() => {
    if (!playing || eventCount <= 0 || revealed >= eventCount) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setRevealed(eventCount);
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setRevealed((current) => Math.min(eventCount, current + 1));
    }, 550);
    return () => window.clearTimeout(timer);
  }, [playing, revealed, eventCount]);

  useEffect(() => {
    if (playing && eventCount > 0 && revealed >= eventCount) {
      setPlaying(false);
    }
  }, [playing, revealed, eventCount]);

  return {
    revealed,
    playing,
    jump: setRevealed,
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
