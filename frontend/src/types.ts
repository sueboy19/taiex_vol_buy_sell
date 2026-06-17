export interface DailyBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  value: number | null;
  transactions: number | null;
  margin_balance: number | null;
  margin_buy: number | null;
  margin_sell: number | null;
  short_balance: number | null;
  short_buy: number | null;
  short_sell: number | null;
}

export interface MinuteBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KlineResponse {
  period: "day" | "minute";
  bars: DailyBar[] | MinuteBar[];
}

export interface RealtimeMessage {
  type: "minute" | "volume";
  timestamp: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
}

export type Period = "day" | "minute";
