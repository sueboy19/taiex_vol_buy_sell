import type { KlineResponse, Period } from "../types";

export async function fetchKline(period: Period, date?: string): Promise<KlineResponse> {
  const params = new URLSearchParams({ period });
  if (date) params.set("date", date);
  const resp = await fetch(`/api/kline?${params}`);
  if (!resp.ok) throw new Error(`fetchKline failed: ${resp.status}`);
  return resp.json();
}

export function getWsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/realtime`;
}
