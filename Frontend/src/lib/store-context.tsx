// src/lib/store-context.tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { products, type Product } from "./store-data";

export type Line = { id: string; qty: number };
export type QuoteLine = { id: string; qty: number; kind: "product" | "service"; name: string };

type StoreCtx = {
  cart: Line[];
  quote: QuoteLine[];
  addToCart: (id: string, qty?: number) => void;
  setCartQty: (id: string, qty: number) => void;
  removeFromCart: (id: string) => void;
  clearCart: () => void;
  addToQuote: (item: { id: string; name: string; kind: "product" | "service"; qty?: number }) => void;
  setQuoteQty: (id: string, qty: number) => void;
  removeFromQuote: (id: string) => void;
  clearQuote: () => void;
  cartCount: number;
  quoteCount: number;
  cartTotal: number;
};

const Ctx = createContext<StoreCtx | null>(null);

const CART_KEY = "uits.cart";
const QUOTE_KEY = "uits.quote";

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Line[]>([]);
  const [quote, setQuote] = useState<QuoteLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setCart(read<Line[]>(CART_KEY, []));
    setQuote(read<QuoteLine[]>(QUOTE_KEY, []));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) window.localStorage.setItem(CART_KEY, JSON.stringify(cart));
  }, [cart, hydrated]);
  
  useEffect(() => {
    if (hydrated) window.localStorage.setItem(QUOTE_KEY, JSON.stringify(quote));
  }, [quote, hydrated]);

  const addToCart = useCallback((id: string, qty = 1) => {
    setCart((prev) => {
      const found = prev.find((l) => l.id === id);
      if (found) return prev.map((l) => (l.id === id ? { ...l, qty: l.qty + qty } : l));
      return [...prev, { id, qty }];
    });
  }, []);

  const setCartQty = useCallback((id: string, qty: number) => {
    setCart((prev) => (qty <= 0 ? prev.filter((l) => l.id !== id) : prev.map((l) => (l.id === id ? { ...l, qty } : l))));
  }, []);

  const removeFromCart = useCallback((id: string) => setCart((p) => p.filter((l) => l.id !== id)), []);
  const clearCart = useCallback(() => setCart([]), []);

  const addToQuote = useCallback(
    (item: { id: string; name: string; kind: "product" | "service"; qty?: number }) => {
      setQuote((prev) => {
        const found = prev.find((l) => l.id === item.id);
        if (found) return prev.map((l) => (l.id === item.id ? { ...l, qty: l.qty + (item.qty ?? 1) } : l));
        return [...prev, { id: item.id, name: item.name, kind: item.kind, qty: item.qty ?? 1 }];
      });
    },
    [],
  );

  const setQuoteQty = useCallback((id: string, qty: number) => {
    setQuote((prev) => (qty <= 0 ? prev.filter((l) => l.id !== id) : prev.map((l) => (l.id === id ? { ...l, qty } : l))));
  }, []);
  
  const removeFromQuote = useCallback((id: string) => setQuote((p) => p.filter((l) => l.id !== id)), []);
  const clearQuote = useCallback(() => setQuote([]), []);

  const value = useMemo<StoreCtx>(() => {
    const cartTotal = cart.reduce((sum, l) => {
      const p = products.find((x) => x.id === l.id);
      return sum + (p?.price ?? 0) * l.qty;
    }, 0);
    return {
      cart,
      quote,
      addToCart,
      setCartQty,
      removeFromCart,
      clearCart,
      addToQuote,
      setQuoteQty,
      removeFromQuote,
      clearQuote,
      cartCount: cart.reduce((s, l) => s + l.qty, 0),
      quoteCount: quote.reduce((s, l) => s + l.qty, 0),
      cartTotal,
    };
  }, [cart, quote, addToCart, setCartQty, removeFromCart, clearCart, addToQuote, setQuoteQty, removeFromQuote, clearQuote]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used inside StoreProvider");
  return ctx;
}

export function productById(id: string): Product | undefined {
  return products.find((p) => p.id === id);
}