// 台股盤中時段判斷（Asia/Taipei，09:00-13:30，週一至週五）
// 不含國定假日（簡易判斷，與 backend/app/market_time.py 一致）

const MARKET_TZ = "Asia/Taipei";
const MARKET_OPEN_MIN = 9 * 60; // 09:00
const MARKET_CLOSE_MIN = 13 * 60 + 30; // 13:30

function getTwParts(now: Date = new Date()): { weekday: string; hour: number; minute: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: MARKET_TZ,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  // en-GB + hour12:false 在某些環境可能回傳 "24"，正規化為 0
  const hour = Number(get("hour")) % 24;
  return { weekday: get("weekday"), hour, minute: Number(get("minute")) };
}

export function isMarketOpen(now: Date = new Date()): boolean {
  const { weekday, hour, minute } = getTwParts(now);
  const isWeekday = weekday !== "Sat" && weekday !== "Sun";
  if (!isWeekday) return false;
  const mins = hour * 60 + minute;
  return mins >= MARKET_OPEN_MIN && mins < MARKET_CLOSE_MIN;
}
