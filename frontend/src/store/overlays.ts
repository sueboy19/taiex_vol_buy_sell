const STORAGE_KEY = "taiex_overlays";

export interface StoredOverlay {
  id: string;
  name: string;
  points: unknown[];
}

export function loadOverlays(): StoredOverlay[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredOverlay[]) : [];
  } catch {
    return [];
  }
}

export function saveOverlays(overlays: StoredOverlay[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overlays));
  } catch {
    /* quota or private mode */
  }
}

export function clearOverlays(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
