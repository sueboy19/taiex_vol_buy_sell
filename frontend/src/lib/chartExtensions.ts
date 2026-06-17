import { registerIndicator, registerOverlay } from "klinecharts";

let initialized = false;

export function setupChartExtensions(): void {
  if (initialized) return;
  initialized = true;

  registerIndicator({
    name: "MARGIN",
    shortName: "融資融券",
    baseValue: 0,
    precision: 0,
    calc: (dataList: Record<string, unknown>[]) =>
      dataList.map((d) => ({
        marginBalance: (d.margin_balance as number) ?? 0,
        shortBalance: -((d.short_balance as number) ?? 0),
      })),
    figures: [
      { key: "marginBalance", title: "融資: ", type: "bar" },
      { key: "shortBalance", title: "融券: ", type: "bar" },
    ],
    styles: {
      marginBalance: { color: "#ef5350" },
      shortBalance: { color: "#26a69a" },
    },
  } as never);

  registerOverlay({
    name: "arrowLine",
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: true,
    needDefaultYAxisFigure: true,
    createPointFigures: ({ coordinates }: { coordinates: { x: number; y: number }[] }) => {
      if (coordinates.length < 2) return [];
      const [start, end] = coordinates;
      const angle = Math.atan2(end.y - start.y, end.x - start.x);
      const headLen = 12;
      const headAngle = Math.PI / 6;
      const p1 = {
        x: end.x - headLen * Math.cos(angle - headAngle),
        y: end.y - headLen * Math.sin(angle - headAngle),
      };
      const p2 = {
        x: end.x - headLen * Math.cos(angle + headAngle),
        y: end.y - headLen * Math.sin(angle + headAngle),
      };
      return [
        { type: "line", attrs: { coordinates: [start, end] } },
        { type: "polygon", attrs: { coordinates: [end, p1, p2] } },
      ];
    },
  } as never);
}
