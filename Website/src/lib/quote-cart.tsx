// src/lib/quote-cart.tsx
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { CATALOG, type CatalogItem } from "./catalog";

export interface QuoteLine {
  id: string;
  qty: number;
  note?: string;
}

interface QuoteCartValue {
  lines: QuoteLine[];
  count: number;
  hydrated: boolean;
  has: (id: string) => boolean;
  add: (id: string, qty?: number) => void;
  toggle: (id: string) => void;
  setQty: (id: string, qty: number) => void;
  setNote: (id: string, note: string) => void;
  remove: (id: string) => void;
  clear: () => void;
  items: Array<{ item: CatalogItem; line: QuoteLine }>;
}

const STORAGE_KEY = "uits-quote-cart";
const QuoteCartContext = createContext<QuoteCartValue | undefined>(undefined);

export function QuoteCartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<QuoteLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as QuoteLine[];
        // Validate that items exist in catalog
        const validLines = parsed.filter(line => 
          CATALOG.some(item => item.id === line.id)
        );
        setLines(validLines);
      }
    } catch {
      /* ignore malformed storage */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      /* ignore storage errors */
    }
  }, [lines, hydrated]);

  const value = useMemo<QuoteCartValue>(() => {
    const has = (id: string) => lines.some((l) => l.id === id);
    return {
      lines,
      hydrated,
      count: lines.length,
      has,
      add: (id, qty = 1) =>
        setLines((prev) => (prev.some((l) => l.id === id) ? prev : [...prev, { id, qty: Math.max(1, qty) }])),
      toggle: (id) =>
        setLines((prev) =>
          prev.some((l) => l.id === id)
            ? prev.filter((l) => l.id !== id)
            : [...prev, { id, qty: 1 }],
        ),
      setQty: (id, qty) =>
        setLines((prev) =>
          prev.map((l) => (l.id === id ? { ...l, qty: Math.max(1, Math.min(999, qty)) } : l)),
        ),
      setNote: (id, note) =>
        setLines((prev) => prev.map((l) => (l.id === id ? { ...l, note } : l))),
      remove: (id) => setLines((prev) => prev.filter((l) => l.id !== id)),
      clear: () => setLines([]),
      items: lines
        .map((line) => {
          const item = CATALOG.find((c) => c.id === line.id);
          return item ? { item, line } : null;
        })
        .filter((x): x is { item: CatalogItem; line: QuoteLine } => x !== null),
    };
  }, [lines, hydrated]);

  return <QuoteCartContext.Provider value={value}>{children}</QuoteCartContext.Provider>;
}

export function useQuoteCart() {
  const ctx = useContext(QuoteCartContext);
  if (!ctx) throw new Error("useQuoteCart must be used inside QuoteCartProvider");
  return ctx;
}