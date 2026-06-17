import { TOOLS } from "../lib/tools";
import type { Period } from "../types";

interface ToolbarProps {
  period: Period;
  onPeriodChange: (p: Period) => void;
  activeTool: string | null;
  onToolSelect: (toolId: string) => void;
  onClear: () => void;
  wsConnected: boolean;
  redUp: boolean;
  onToggleColor: () => void;
}

export function Toolbar({
  period,
  onPeriodChange,
  activeTool,
  onToolSelect,
  onClear,
  wsConnected,
  redUp,
  onToggleColor,
}: ToolbarProps): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        padding: "6px 12px",
        background: "#1e1e1e",
        borderBottom: "1px solid #333",
        flexWrap: "wrap",
      }}
    >
      <span style={{ color: "#fff", fontWeight: 700, marginRight: 12, fontSize: 15 }}>
        台股大盤
      </span>

      <div style={{ display: "flex", gap: 2, marginRight: 12 }}>
        <PeriodBtn label="日線" active={period === "day"} onClick={() => onPeriodChange("day")} />
        <PeriodBtn label="分鐘" active={period === "minute"} onClick={() => onPeriodChange("minute")} />
      </div>

      <div
        style={{
          width: 1,
          height: 22,
          background: "#444",
          marginRight: 8,
        }}
      />

      {TOOLS.map((t) => (
        <button
          key={t.id}
          title={t.label}
          onClick={() => onToolSelect(t.id)}
          style={{
            padding: "3px 8px",
            background: activeTool === t.id ? "#2563eb" : "#2a2a2a",
            color: "#fff",
            border: "1px solid #3a3a3a",
            borderRadius: 3,
            cursor: "pointer",
            fontSize: 14,
            lineHeight: "20px",
          }}
        >
          {t.icon}
        </button>
      ))}

      <button
        title="切換漲跌顏色"
        onClick={onToggleColor}
        style={{
          padding: "3px 10px",
          background: "#2a2a2a",
          color: "#fff",
          border: "1px solid #3a3a3a",
          borderRadius: 3,
          cursor: "pointer",
          fontSize: 13,
        }}
      >
        {redUp ? "紅漲綠跌" : "綠漲紅跌"}
      </button>

      <button
        title="清除所有畫線"
        onClick={onClear}
        style={{
          marginLeft: 8,
          padding: "3px 10px",
          background: "#7f1d1d",
          color: "#fff",
          border: "1px solid #991b1b",
          borderRadius: 3,
          cursor: "pointer",
          fontSize: 13,
        }}
      >
        清除
      </button>

      <div style={{ flex: 1 }} />

      <span
        style={{
          fontSize: 12,
          color: wsConnected ? "#4ade80" : "#f87171",
        }}
      >
        {wsConnected ? "● 盤中連線" : "● 離線"}
      </span>
    </div>
  );
}

function PeriodBtn({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "3px 12px",
        background: active ? "#2563eb" : "#2a2a2a",
        color: "#fff",
        border: "1px solid #3a3a3a",
        borderRadius: 3,
        cursor: "pointer",
        fontSize: 13,
      }}
    >
      {label}
    </button>
  );
}
