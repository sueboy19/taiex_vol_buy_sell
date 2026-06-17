export interface ToolDef {
  id: string;
  label: string;
  icon: string;
}

export const TOOLS: ToolDef[] = [
  { id: "segment", label: "線段", icon: "╱" },
  { id: "rayLine", label: "射線", icon: "↗" },
  { id: "straightLine", label: "直線", icon: "／" },
  { id: "horizontalStraightLine", label: "水平線", icon: "━" },
  { id: "verticalStraightLine", label: "垂直線", icon: "┃" },
  { id: "parallelStraightLine", label: "平行通道", icon: "║" },
  { id: "brush", label: "畫筆", icon: "✎" },
  { id: "arrowLine", label: "箭頭", icon: "→" },
];
