// src/pages/products.tsx
import { useState, useMemo } from "react";
import { Search, Plus, Minus, ShoppingCart, FileText, ChevronDown, ChevronUp } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useStore } from "../lib/store-context";
import { PRODUCT_CATEGORIES, products, formatPrice, availabilityLabel } from "../lib/store-data";

// Import product images directly from assets (same as home.tsx)
import laptop1 from '../assets/laptop-1.png';
import laptop2 from '../assets/laptop-2.png';
import laptop3 from '../assets/laptop-3.png';
import monitor1 from '../assets/monitor-1.png';

// Map product IDs to their imported images
const productImages: Record<string, string> = {
  'featured-lat-5410': laptop1,
  'featured-lat-5420': laptop2,
  'featured-lat-5440': laptop3,
  'featured-monitor': monitor1,
  // Map the quote products too if they have images
  'lat-5440': laptop3,
  'lat-7440': laptop3,
};

interface ProductsPageProps {
  onNavigate?: (page: string) => void;
}

export default function ProductsPage({ onNavigate }: ProductsPageProps) {
  const { theme } = useTheme();
  const { addToCart, cart, setCartQty, removeFromCart, addToQuote, quote } = useStore();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("All");
  const [expandedSpecs, setExpandedSpecs] = useState<string | null>(null);

  // Use products from store-data
  const list = products.filter((p) => p.segment === "products");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return list.filter((p) => {
      const matchesCategory = category === "All" || p.category === category;
      const matchesSearch = !q ||
        p.name.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.shortDescription.toLowerCase().includes(q) ||
        p.specs.some(spec => spec.toLowerCase().includes(q));
      return matchesCategory && matchesSearch;
    });
  }, [list, search, category]);

  // FIXED: cart is a Record, not an array
  const getCartQty = (id: string) => {
    const item = cart[id];
    return item?.quantity || 0;
  };

  // FIXED: quote is an array of QuoteLine objects
  const isInQuote = (id: string) => quote.some((l) => l.id === id);

  const handleQuoteClick = (productId: string, productName: string) => {
    if (!isInQuote(productId)) {
      addToQuote({
        id: productId,
        name: productName,
        kind: "product"
      });
    }
    if (onNavigate) {
      onNavigate('quote');
    }
  };

  const handleAddToCart = (productId: string) => {
    // Find the product to get its data
    const product = products.find(p => p.id === productId);
    if (!product) return;

    // Create product data for the cart
    const productData = {
      id: product.id,
      name: product.name,
      brand: product.brand,
      category: product.category,
      segment: product.segment,
      shortDescription: product.shortDescription,
      specs: product.specs,
      price: product.price || 0,
      availability: product.availability,
      quoteOnly: product.quoteOnly || false,
      image: product.image || '',
    };

    addToCart(productId, 1, productData);
  };

  const toggleSpecs = (id: string) => {
    setExpandedSpecs(expandedSpecs === id ? null : id);
  };

  // Get the correct image for a product
  const getProductImage = (product: any) => {
    // Check if we have a mapped image for this product ID
    if (product.id && productImages[product.id]) {
      return productImages[product.id];
    }
    // Fallback to the image from store-data if it exists
    return product.image || null;
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Enterprise-grade IT equipment
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          IT Products
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Browse our curated selection of business laptops, desktops, workstations, displays, and accessories. All products are enterprise-ready with professional support options.
        </p>
      </header>

      {/* Search and Filter */}
      <div className="flex flex-wrap gap-3 mt-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search products..."
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
          {PRODUCT_CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {/* Product Grid */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((product) => {
          const qty = getCartQty(product.id);
          const inCart = qty > 0;
          const isQuoteOnly = product.price === null || product.quoteOnly === true;
          const inQuote = isInQuote(product.id);
          const isExpanded = expandedSpecs === product.id;
          const hasPrice = product.price !== null && product.price > 0 && !product.quoteOnly;
          const productImage = getProductImage(product);

          return (
            <article
              key={product.id}
              className={`rounded-2xl border border-border bg-card p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
                theme === "light"
                  ? "hover:shadow-[0_8px_30px_rgb(0,0,0,0.08)]"
                  : "hover:shadow-[0_8px_30px_rgb(0,0,0,0.3)]"
              }`}
            >
              {/* --- PRODUCT IMAGE SECTION --- */}
              {productImage && (
                <div className="mb-4 overflow-hidden rounded-xl bg-muted/20">
                  <img
                    src={productImage}
                    alt={product.name}
                    className="h-48 w-full object-cover object-center transition-transform duration-300 hover:scale-105"
                  />
                </div>
              )}

              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-medium text-[#839705]">{product.brand}</span>
                  <h3 className="mt-1 text-base font-semibold text-foreground">
                    {product.name}
                  </h3>
                </div>
                {product.grade && (
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                    {product.grade}
                  </span>
                )}
              </div>

              {/* Product description */}
              <div className="mt-3">
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {product.shortDescription}
                </p>
              </div>

              {/* Specs - show first 3, toggle for more */}
              <div className="mt-3">
                <div className="flex flex-wrap gap-1">
                  {(isExpanded ? product.specs : product.specs.slice(0, 3)).map((spec) => (
                    <span key={spec} className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] text-muted-foreground">
                      {spec}
                    </span>
                  ))}
                </div>
                {product.specs.length > 3 && (
                  <button
                    onClick={() => toggleSpecs(product.id)}
                    className="mt-1.5 text-xs text-[#839705] hover:underline flex items-center gap-1"
                  >
                    {isExpanded ? (
                      <>Show less <ChevronUp className="h-3 w-3" /></>
                    ) : (
                      <>View specifications <ChevronDown className="h-3 w-3" /></>
                    )}
                  </button>
                )}
              </div>

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

              {/* BUTTON SECTION */}
              {hasPrice ? (
                inCart ? (
                  <div className="mt-4 flex items-center gap-2">
                    <button
                      onClick={() => setCartQty(product.id, qty - 1)}
                      className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-background text-foreground hover:bg-muted/50 transition-colors"
                      aria-label="Decrease quantity"
                    >
                      <Minus className="h-4 w-4" />
                    </button>
                    <span className="w-8 text-center text-sm font-semibold text-foreground">{qty}</span>
                    <button
                      onClick={() => setCartQty(product.id, qty + 1)}
                      className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-background text-foreground hover:bg-muted/50 transition-colors"
                      aria-label="Increase quantity"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => removeFromCart(product.id)}
                      className="ml-auto text-xs text-red-500 hover:text-red-700 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => handleAddToCart(product.id)}
                    className={`mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
                      theme === "light"
                        ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                        : "bg-[#839705] text-white hover:bg-[#98ab06]"
                    }`}
                  >
                    <ShoppingCart className="h-4 w-4" />
                    Add to cart
                  </button>
                )
              ) : (
                <button
                  onClick={() => handleQuoteClick(product.id, product.name)}
                  className={`mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
                    inQuote
                      ? "bg-green-600 text-white hover:bg-green-700"
                      : theme === "light"
                        ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                        : "bg-[#839705] text-white hover:bg-[#98ab06]"
                  }`}
                >
                  <FileText className="h-4 w-4" />
                  {inQuote ? "✓ In Quote List" : "Request Quote"}
                </button>
              )}
            </article>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg font-medium">No products found</p>
          <p className="mt-2 text-sm">Try adjusting your filters or search terms</p>
        </div>
      )}
    </div>
  );
}