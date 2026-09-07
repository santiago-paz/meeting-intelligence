import type { Exchange } from "@/components/answer-view";

const KEY = "ask.exchanges";
const KEPT = 20;
const EMPTY: Exchange[] = [];

let cache: Exchange[] | undefined;
const listeners = new Set<() => void>();

/**
 * The answers on the Ask page, kept in session storage so a trip to a
 * transcript and back does not lose them. Read through useSyncExternalStore:
 * the server snapshot is empty, the client one is whatever was saved, and
 * React reconciles the two without a hydration mismatch.
 */
export function readExchanges(): Exchange[] {
  if (cache === undefined) {
    try {
      const saved = window.sessionStorage.getItem(KEY);
      cache = saved ? (JSON.parse(saved) as Exchange[]) : EMPTY;
    } catch {
      cache = EMPTY; // nothing saved, or storage blocked: start empty
    }
  }
  return cache;
}

export function readServerExchanges(): Exchange[] {
  return EMPTY;
}

export function writeExchanges(next: Exchange[]): void {
  cache = next.slice(0, KEPT);
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(cache));
  } catch {
    // Storage full or blocked: the page still works, it just forgets on navigation.
  }
  for (const listener of listeners) listener();
}

export function subscribeExchanges(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Forget the in-memory copy so the next read goes back to storage. Tests use it between cases. */
export function resetExchangeStore(): void {
  cache = undefined;
}
