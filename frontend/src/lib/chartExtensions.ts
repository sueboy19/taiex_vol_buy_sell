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

  registerIndicator({
    name: "PUT_CALL_RATIO",
    shortName: "買賣權P/C比",
    precision: 2,
    calc: (dataList: Record<string, unknown>[]) => {
      // 大盤對照線基準：第一個有 P/C 資料那根的收盤價（起點=1，與 1.0 基準線同尺）
      let baseClose: number | null = null;
      return dataList.map((d, i) => {
        const pcrVol = (d.pcr_vol as number) ?? null;
        const close = (d.close as number) ?? null;
        if (baseClose === null && pcrVol !== null && close !== null) {
          baseClose = close;
        }
        // 5 日均線：最近 5 根（含當根）皆有 P/C 值才計算
        let ma5: number | null = null;
        if (pcrVol !== null && i >= 4) {
          const vals = dataList
            .slice(i - 4, i + 1)
            .map((w) => (w.pcr_vol as number) ?? null);
          if (vals.every((v) => v !== null)) {
            ma5 = vals.reduce((s: number, v) => s + (v as number), 0) / 5;
          }
        }
        return {
          pcrVol,
          pcrVolMa5: ma5,
          pcrOi: (d.pcr_oi as number) ?? null,
          baseline: 1,
          indexRel:
            baseClose !== null && close !== null ? close / baseClose : null,
        };
      });
    },
    figures: [
      { key: "pcrVol", title: "成交量P/C: ", type: "line" },
      { key: "pcrVolMa5", title: "P/C均5: ", type: "line" },
      { key: "pcrOi", title: "未平倉P/C: ", type: "line" },
      { key: "baseline", title: "基準: ", type: "line" },
      { key: "indexRel", title: "大盤(=1): ", type: "line" },
    ],
    styles: {
      // klinecharts 的 lines 樣式若提供「不完整」物件會整組取代預設值，
      // 缺 size/dashedValue 等欄位會在繪製時拋 TypeError 導致整條線不畫，欄位必須補齊。
      lines: [
        { color: "#ff9800", size: 1, style: "solid", dashedValue: [2, 2], smooth: false },
        { color: "#e65100", size: 1, style: "solid", dashedValue: [2, 2], smooth: false },
        { color: "#42a5f5", size: 1, style: "solid", dashedValue: [2, 2], smooth: false },
        { color: "#787b86", size: 1, style: "dashed", dashedValue: [4, 2], smooth: false },
        { color: "#37474f", size: 1, style: "solid", dashedValue: [2, 2], smooth: false },
      ],
    } as never,
  } as never);

  registerIndicator({
    name: "OPTION_OI",
    shortName: "選擇權未平倉(口)",
    precision: 0,
    calc: (dataList: Record<string, unknown>[]) =>
      dataList.map((d) => ({
        callOi: (d.call_oi as number) ?? null,
        // 鏡像柱狀：賣權取負值向下畫，與買權以 0 軸對稱，兩邊堆積強弱一眼可比
        putOi: d.put_oi != null ? -(d.put_oi as number) : null,
      })),
    figures: [
      { key: "callOi", title: "買權OI: ", type: "bar", baseValue: 0 },
      { key: "putOi", title: "賣權OI: ", type: "bar", baseValue: 0 },
    ],
    styles: {
      // 樣式欄位補齊（同 lines 教訓，避免渲染例外）：買權紅向上、賣權綠向下，
      // 與融資(紅)/融券(綠)慣例一致；up/down/noChange 同色（靜態色）
      bars: [
        { style: "fill", borderSize: 1, borderStyle: "solid", borderDashedValue: [2, 2], upColor: "#ef5350", downColor: "#ef5350", noChangeColor: "#ef5350" },
        { style: "fill", borderSize: 1, borderStyle: "solid", borderDashedValue: [2, 2], upColor: "#26a69a", downColor: "#26a69a", noChangeColor: "#26a69a" },
      ],
    } as never,
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
