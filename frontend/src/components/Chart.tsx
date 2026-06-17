import { useCallback, useEffect, useRef, useState } from "react";
import { dispose, init } from "klinecharts";
import type { Chart, KLineData } from "klinecharts";

import { setupChartExtensions } from "../lib/chartExtensions";
import { loadOverlays, saveOverlays, StoredOverlay } from "../store/overlays";
import type { DailyBar, MinuteBar, Period, RealtimeMessage } from "../types";

export interface ChartHandle {
  clearAll: () => void;
}

interface ChartProps {
  period: Period;
  bars: (DailyBar | MinuteBar)[];
  loading: boolean;
  realtimeMessage: RealtimeMessage | null;
  activeTool: string | null;
  onToolConsumed: () => void;
  clearSignal: number;
  redUp: boolean;
}

const CHART_ID = "taiex-chart";
let uid = 0;

export function Chart({
  period,
  bars,
  loading,
  realtimeMessage,
  activeTool,
  onToolConsumed,
  clearSignal,
  redUp,
}: ChartProps): JSX.Element {
  const chartRef = useRef<Chart | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [containerH, setContainerH] = useState(0);
  const barsRef = useRef<(DailyBar | MinuteBar)[]>([]);
  const overlaysRef = useRef<StoredOverlay[]>([]);
  const periodRef = useRef(period);
  periodRef.current = period;
  const activeToolRef = useRef<string | null>(activeTool);
  activeToolRef.current = activeTool;
  const eraserActiveRef = useRef(false);
  eraserActiveRef.current = activeTool === "eraser";
  const progressIdRef = useRef<string | null>(null);

  const handleOverlayClick = useCallback((id: string) => () => {
    if (!eraserActiveRef.current) return;
    const chart = chartRef.current;
    if (!chart) return;
    chart.removeOverlay(id);
    overlaysRef.current = overlaysRef.current.filter((o) => o.id !== id);
    saveOverlays(overlaysRef.current);
  }, []);

  const restoreOverlays = useCallback((chart: Chart) => {
    overlaysRef.current = loadOverlays();
    for (const ov of overlaysRef.current) {
      chart.createOverlay({
        id: ov.id,
        name: ov.name,
        points: ov.points,
        mode: "normal",
        lock: false,
        extendData: ov.id,
        onClick: handleOverlayClick(ov.id),
      } as never);
    }
  }, [handleOverlayClick]);

  const startDrawing = useCallback(
    (tool: string) => {
      const chart = chartRef.current;
      if (!chart) return;
      const id = `ov_${Date.now()}_${uid++}`;
      const createdId = chart.createOverlay({
        id,
        name: tool,
        onDrawEnd: (event: { overlay?: { points?: unknown[] } }) => {
          const pts = event?.overlay?.points ?? [];
          if (pts.length > 0) {
            overlaysRef.current.push({ id, name: tool, points: pts });
            saveOverlays(overlaysRef.current);
          }
          progressIdRef.current = null;
          // 工具仍選取中 → 接著畫下一條（微任務延後，避開 klinecharts 當下事件）
          if (activeToolRef.current === tool) {
            queueMicrotask(() => startDrawing(tool));
          }
          return false;
        },
        onClick: handleOverlayClick(id),
      } as never);
      if (createdId !== null) {
        progressIdRef.current = id;
      } else {
        onToolConsumed();
      }
    },
    [onToolConsumed, handleOverlayClick],
  );

  useEffect(() => {
    setupChartExtensions();
    const chart = init(CHART_ID);
    if (!chart) return;
    chartRef.current = chart;

    chart.setStyles({
      candle: {
        type: "candle_solid",
        tooltip: { showRule: "follow_cross" },
      },
      indicator: {
        lastValueMark: { show: false },
      },
      grid: { show: false },
    } as never);

    chart.createIndicator("VOL", false, { id: "vol_pane", height: 120, dragEnabled: true } as never);
    chart.createIndicator("FOREIGN_FUTURE", false, { id: "ff_pane", height: 100, dragEnabled: true } as never);
    chart.createIndicator("MARGIN_PURCHASE", false, { id: "margin_buy_pane", height: 100, dragEnabled: true } as never);
    chart.createIndicator("MARGIN_SHORTSALE", false, { id: "margin_short_pane", height: 100, dragEnabled: true } as never);

    restoreOverlays(chart);

    return () => {
      dispose(CHART_ID);
      chartRef.current = null;
    };
  }, [restoreOverlays]);

  // 追蹤圖表容器高度
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const update = () => setContainerH(el.clientHeight);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 大盤 K 線佔約 1/3：4 個副圖平分其餘 2/3
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || containerH === 0) return;
    const subH = Math.max(70, Math.round(((containerH - 30) * 2) / 3 / 4));
    for (const id of ["vol_pane", "ff_pane", "margin_buy_pane", "margin_short_pane"]) {
      chart.setPaneOptions({ id, height: subH } as never);
    }
  }, [containerH]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const up = redUp ? "#ef5350" : "#26a69a";
    const down = redUp ? "#26a69a" : "#ef5350";
    chart.setStyles({
      candle: {
        bar: {
          upColor: up,
          downColor: down,
          noChangeColor: "#888888",
          upBorderColor: up,
          downBorderColor: down,
          noChangeBorderColor: "#888888",
          upWickColor: up,
          downWickColor: down,
          noChangeWickColor: "#888888",
        },
      },
      indicator: {
        bars: [{ upColor: up, downColor: down, noChangeColor: "#888888" }],
      },
    } as never);
  }, [redUp]);

  useEffect(() => {
    barsRef.current = bars;
    chartRef.current?.applyNewData(bars as KLineData[]);
  }, [bars]);

  useEffect(() => {
    if (!realtimeMessage || !chartRef.current) return;
    const current = barsRef.current;
    if (current.length === 0) return;

    if (realtimeMessage.type === "minute") {
      const last = current[current.length - 1];
      if (last.timestamp === realtimeMessage.timestamp) {
        last.open = realtimeMessage.open!;
        last.high = realtimeMessage.high!;
        last.low = realtimeMessage.low!;
        last.close = realtimeMessage.close!;
      } else if (realtimeMessage.timestamp > last.timestamp) {
        current.push({
          timestamp: realtimeMessage.timestamp,
          open: realtimeMessage.open!,
          high: realtimeMessage.high!,
          low: realtimeMessage.low!,
          close: realtimeMessage.close!,
          volume: last.volume ?? 0,
        } as MinuteBar);
      }
      chartRef.current.updateData(current[current.length - 1] as KLineData);
    } else if (realtimeMessage.type === "volume") {
      const last = current[current.length - 1];
      last.volume = realtimeMessage.volume!;
      chartRef.current.updateData(last as KLineData);
    }
  }, [realtimeMessage]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (!activeTool) {
      if (progressIdRef.current) {
        chart.removeOverlay(progressIdRef.current);
        progressIdRef.current = null;
      }
      return;
    }
    // 橡皮擦：不畫新線，僅啟用「點擊既有線刪除」
    if (activeTool === "eraser") return;
    startDrawing(activeTool);
  }, [activeTool, startDrawing]);

  useEffect(() => {
    if (clearSignal === 0) return;
    chartRef.current?.removeOverlay();
    progressIdRef.current = null;
    overlaysRef.current = [];
    saveOverlays([]);
  }, [clearSignal]);

  return (
    <div ref={wrapperRef} style={{ position: "relative", width: "100%", height: "100%" }}>
      <div id={CHART_ID} style={{ width: "100%", height: "100%" }} />
      {loading && (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            background: "rgba(0,0,0,0.6)",
            color: "#fff",
            padding: "4px 12px",
            borderRadius: 4,
            fontSize: 13,
          }}
        >
          載入中…
        </div>
      )}
    </div>
  );
}
