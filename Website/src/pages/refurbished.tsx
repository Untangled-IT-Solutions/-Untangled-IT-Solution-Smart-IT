// src/pages/refurbished.tsx
import { useState, useMemo } from "react";
import { Search, Plus, Minus, ShoppingCart, FileText } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useStore } from "../lib/store-context";
import { REFURB_CATEGORIES, products, formatPrice, availabilityLabel } from "../lib/store-data";

interface RefurbishedPageProps {
  onNavigate?: (page: string) => void;
}

export default function RefurbishedPage({ onNavigate }: RefurbishedPageProps) {
  const { theme } = useTheme();
  const { addToCart, cart, setCartQty, removeFromCart, addToQuote, quote } = useStore();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("All");

  const list = products.filter((p) => p.segment === "refurbished");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return list.filter((p) => {
      const matchesCategory = category === "All" || p.category === category;
      const matchesSearch = !q || 
        p.name.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.shortDescription.toLowerCase().includes(q);
      return matchesCategory && matchesSearch;
    });
  }, [list, search, category]);

  const getCartQty = (id: string) => {
    const line = cart.find((l) => l.id === id);
    return line?.qty || 0;
  };

  const isInQuote = (id: string) => quote.some((l) => l.id === id);

  const handleQuoteClick = (productId: string, productName: string) => {
    if (!isInQuote(productId)) {
      addToQuote({ id: productId, name: productName, kind: "product" });
    }
    if (onNavigate) {
      onNavigate('quote');
    }
  };

  const handleRequestQuote = (productId: string, productName: string) => {
    if (!isInQuote(productId)) {
      addToQuote({ id: productId, name: productName, kind: "product" });
    }
    if (onNavigate) {
      onNavigate('quote');
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Tested, graded and warrantied devices
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Refurbished Devices
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Every device shows its grade, condition, specifications, warranty, price and availability. Buy now when it's in stock, or request a quote for multiple units.
        </p>
      </header>

      <div className="flex flex-wrap gap-3 mt-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search refurbished devices..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-border bg-background pl-9 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="All">All Categories</option>
          {REFURB_CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((product) => {
          const qty = getCartQty(product.id);
          const inCart = qty > 0;
          const isQuoteOnly = product.price === null || product.quoteOnly === true;
          const inQuote = isInQuote(product.id);

          return (
            <article
              key={product.id}
              className={`rounded-2xl border border-border bg-card p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
                theme === "light"
                  ? "hover:shadow-[0_8px_30px_rgb(0,0,0,0.08)]"
                  : "hover:shadow-[0_8px_30px_rgb(0,0,0,0.3)]"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-medium text-[#839705]">{product.brand}</span>
                  <h3 className="mt-1 text-sm font-semibold line-clamp-2 text-foreground">
                    {product.name}
                  </h3>
                </div>
                {product.grade && (
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    product.grade === "Grade A" 
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                      : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                  }`}>
                    {product.grade}
                  </span>
                )}
              </div>

              <p className="mt-2 text-xs line-clamp-2 text-muted-foreground">
                {product.shortDescription}
              </p>

              <div className="mt-2 flex flex-wrap gap-1">
                {product.specs.slice(0, 4).map((spec) => (
                  <span key={spec} className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                    {spec}
                  </span>
                ))}
                {product.specs.length > 4 && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                    +{product.specs.length - 4}
                  </span>
                )}
              </div>

              {product.condition && (
                <p className="mt-2 text-xs text-muted-foreground">{product.condition}</p>
              )}

              {product.warranty && (
                <p className="mt-2 text-xs font-medium text-foreground">
                  {product.warranty}
                </p>
              )}

              <div className="mt-3 flex items-center justify-between">
                <span className={`text-lg font-bold text-foreground`}>
                  {isQuoteOnly ? "Quote Only" : formatPrice(product.price || 0)}
                </span>
                <span className={`text-xs ${
                  product.availability === "in-stock" ? "text-green-600" :
                  product.availability === "low-stock" ? "text-amber-600" :
                  "text-red-600"
                }`}>
                  {availabilityLabel[product.availability]}
                </span>
              </div>

              {inCart ? (
                <div className="mt-4 flex items-center gap-2">
                  <button
                    onClick={() => setCartQty(product.id, qty - 1)}
                    className={`rounded-lg p-1.5 transition-colors ${
                      theme === "light" ? "hover:bg-[#EEF3E7]" : "hover:bg-[#2A2E24]"
                    }`}
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                  <span className="w-8 text-center text-sm font-semibold text-foreground">{qty}</span>
                  <button
                    onClick={() => setCartQty(product.id, qty + 1)}
                    className={`rounded-lg p-1.5 transition-colors ${
                      theme === "light" ? "hover:bg-[#EEF3E7]" : "hover:bg-[#2A2E24]"
                    }`}
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => removeFromCart(product.id)}
                    className="ml-auto rounded-lg p-1.5 text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    <ShoppingCart className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    if (isQuoteOnly) {
                      handleRequestQuote(product.id, product.name);
                    } else {
                      addToCart(product.id);
                    }
                  }}
                  className={`mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                    isQuoteOnly
                      ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                      : theme === "light"
                        ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                        : "bg-white text-black hover:bg-gray-200"
                  }`}
                >
                  {isQuoteOnly ? "Request Quote" : "Add to Cart"}
                </button>
              )}

              {/* Only show "Need several? Request Quote" for products that have a price (NOT quote-only) */}
              {!isQuoteOnly && product.price !== null && product.price > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <button
                    onClick={() => handleQuoteClick(product.id, product.name)}
                    className="text-sm text-[#839705] hover:underline flex items-center gap-2 w-full text-left"
                  >
                    <FileText className="h-4 w-4" />
                    {inQuote ? "In Quote List ✓" : "Need several? Request Quote"}
                  </button>
                </div>
              )}
            </article>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg font-medium">No refurbished devices found</p>
          <p className="mt-2 text-sm">Try adjusting your filters or search terms</p>
        </div>
      )}
    </div>
  );
}