import { useCallback, useEffect, useRef, useState } from "react";

import { fetchKline } from "../api/client";
import type { DailyBar, MinuteBar, Period } from "../types";

interface State {
  bars: (DailyBar | MinuteBar)[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useKlineData(period: Period): State {
  const [bars, setBars] = useState<(DailyBar | MinuteBar)[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const barsRef = useRef(bars);
  barsRef.current = bars;

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchKline(period)
      .then((res) => {
        if (!cancelled) {
          setBars(res.bars as (DailyBar | MinuteBar)[]);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [period, tick]);

  return { bars, loading, error, reload };
}
