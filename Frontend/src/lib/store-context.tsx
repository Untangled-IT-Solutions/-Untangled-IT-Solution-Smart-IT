// src/lib/store-context.tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// Re-export everything from store-data
export { products, productById, type Product } from "./store-data";

// Define Cart Item type
export interface CartItem {
  id: string;
  name: string;
  brand: string;
  category: string;
  segment: 'products' | 'business' | 'refurbished';
  shortDescription: string;
  specs: string[];
  price: number;
  availability: 'in-stock' | 'low-stock' | 'on-order';
  quoteOnly: boolean;
  image?: string;
  quantity: number;
}

export type QuoteLine = { id: string; qty: number; kind: "product" | "service"; name: string };

type StoreCtx = {
  cart: Record<string, CartItem>;
  quote: QuoteLine[];
  addToCart: (productId: string, quantity: number, product?: Omit<CartItem, 'quantity'>) => void;
  setCartQty: (productId: string, quantity: number) => void;
  removeFromCart: (productId: string) => void;
  clearCart: () => void;
  addToQuote: (item: { id: string; name: string; kind: "product" | "service"; qty?: number }) => void;
  setQuoteQty: (id: string, qty: number) => void;
  removeFromQuote: (id: string) => void;
  clearQuote: () => void;
  cartCount: number;
  quoteCount: number;
  cartTotal: number;
  getCartCount: () => number;
  getCartTotal: () => number;
  getCartItems: () => CartItem[];
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
  const [cart, setCart] = useState<Record<string, CartItem>>({});
  const [quote, setQuote] = useState<QuoteLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const savedCart = read<Record<string, CartItem>>(CART_KEY, {});
    setCart(savedCart);
    setQuote(read<QuoteLine[]>(QUOTE_KEY, []));
    setHydrated(true);
    console.log('📦 Cart loaded:', savedCart);
  }, []);

  useEffect(() => {
    if (hydrated) {
      localStorage.setItem(CART_KEY, JSON.stringify(cart));
    }
  }, [cart, hydrated]);

  useEffect(() => {
    if (hydrated) {
      localStorage.setItem(QUOTE_KEY, JSON.stringify(quote));
    }
  }, [quote, hydrated]);

  const addToCart = useCallback((productId: string, quantity: number, product?: Omit<CartItem, 'quantity'>) => {
    setCart(prevCart => {
      if (prevCart[productId]) {
        return {
          ...prevCart,
          [productId]: {
            ...prevCart[productId],
            quantity: prevCart[productId].quantity + quantity,
          },
        };
      }

      if (!product) return prevCart;

      const newItem: CartItem = {
        ...product,
        quantity: quantity,
      };

      return {
        ...prevCart,
        [productId]: newItem,
      };
    });
  }, []);

  const removeFromCart = useCallback((productId: string) => {
    setCart(prevCart => {
      const newCart = { ...prevCart };
      delete newCart[productId];
      return newCart;
    });
  }, []);

  const setCartQty = useCallback((productId: string, quantity: number) => {
    if (quantity <= 0) {
      removeFromCart(productId);
      return;
    }

    setCart(prevCart => {
      if (!prevCart[productId]) return prevCart;
      return {
        ...prevCart,
        [productId]: {
          ...prevCart[productId],
          quantity: quantity,
        },
      };
    });
  }, [removeFromCart]);

  const clearCart = useCallback(() => setCart({}), []);

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

  const getCartTotal = useCallback(() => {
    return Object.values(cart).reduce((sum, item) => sum + (item.price * item.quantity), 0);
  }, [cart]);

  const getCartCount = useCallback(() => {
    return Object.values(cart).reduce((sum, item) => sum + item.quantity, 0);
  }, [cart]);

  const getCartItems = useCallback(() => Object.values(cart), [cart]);

  const cartCount = useMemo(() => getCartCount(), [getCartCount]);
  const cartTotal = useMemo(() => getCartTotal(), [getCartTotal]);
  const quoteCount = quote.reduce((s, l) => s + l.qty, 0);

  const value = useMemo<StoreCtx>(() => ({
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
    cartCount,
    quoteCount,
    cartTotal,
    getCartCount,
    getCartTotal,
    getCartItems,
  }), [cart, quote, addToCart, setCartQty, removeFromCart, clearCart, addToQuote, setQuoteQty, removeFromQuote, clearQuote, cartCount, quoteCount, cartTotal, getCartCount, getCartTotal, getCartItems]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error("useStore must be used inside StoreProvider");
  }
  return ctx;
}
