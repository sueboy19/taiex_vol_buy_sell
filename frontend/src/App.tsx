import { useCallback, useState } from "react";

import { Chart } from "./components/Chart";
import { Toolbar } from "./components/Toolbar";
import { useKlineData } from "./hooks/useKlineData";
import { useRealtime } from "./hooks/useRealtime";
import type { Period } from "./types";

export default function App(): JSX.Element {
  const [period, setPeriod] = useState<Period>("day");
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [clearSignal, setClearSignal] = useState(0);

  const { bars, loading, error } = useKlineData(period);
  const { lastMessage, connected } = useRealtime(period === "minute");

  const handleToolSelect = useCallback((toolId: string) => {
    setActiveTool((prev) => (prev === toolId ? null : toolId));
  }, []);

  const handleToolConsumed = useCallback(() => {
    setActiveTool(null);
  }, []);

  const handleClear = useCallback(() => {
    setActiveTool(null);
    setClearSignal((s) => s + 1);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#131722" }}>
      <Toolbar
        period={period}
        onPeriodChange={setPeriod}
        activeTool={activeTool}
        onToolSelect={handleToolSelect}
        onClear={handleClear}
        wsConnected={connected}
      />
      {error && (
        <div style={{ padding: "8px 16px", background: "#7f1d1d", color: "#fca5a5", fontSize: 13 }}>
          資料載入失敗：{error}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <Chart
          period={period}
          bars={bars}
          loading={loading}
          realtimeMessage={lastMessage}
          activeTool={activeTool}
          onToolConsumed={handleToolConsumed}
          clearSignal={clearSignal}
        />
      </div>
    </div>
  );
}
