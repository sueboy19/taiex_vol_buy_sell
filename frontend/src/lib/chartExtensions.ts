import { registerIndicator, registerOverlay } from "klinecharts";

let initialized = false;

export function setupChartExtensions(): void {
  if (initialized) return;
  initialized = true;

  registerIndicator({
    name: "MARGIN_PURCHASE",
    shortName: "融資餘額(億)",
    baseValue: 0,
    precision: 1,
    calc: (dataList: Record<string, unknown>[]) =>
      dataList.map((d) => ({
        marginValue: ((d.margin_value as number) ?? 0) / 1e8,
      })),
    figures: [{ key: "marginValue", title: "融資(億): ", type: "bar", baseValue: 0 }],
    styles: { bars: [{ noChangeColor: "#ef5350" }] } as never,
  } as never);

  registerIndicator({
    name: "MARGIN_SHORTSALE",
    shortName: "融券餘額(張)",
    baseValue: 0,
    precision: 0,
    calc: (dataList: Record<string, unknown>[]) =>
      dataList.map((d) => ({
        shortBalance: (d.short_balance as number) ?? 0,
      })),
    figures: [{ key: "shortBalance", title: "融券(張): ", type: "bar", baseValue: 0 }],
    styles: { bars: [{ noChangeColor: "#26a69a" }] } as never,
  } as never);

  registerIndicator({
    name: "FOREIGN_FUTURE",
    shortName: "外資台指期未平倉",
    baseValue: 0,
    precision: 0,
    minValue: -120000,
    maxValue: 120000,
    calc: (dataList: Record<string, unknown>[]) =>
      dataList.map((d) => ({
        netOi: (d.net_oi as number) ?? 0,
      })),
    figures: [{ key: "netOi", title: "外資未平倉(口): ", type: "bar", baseValue: 0 }],
    styles: { bars: [{ noChangeColor: "#ab47bc" }] } as never,
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
