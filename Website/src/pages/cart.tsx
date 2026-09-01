// src/pages/cart.tsx
import { Minus, Plus, ShoppingCart, Trash2, ArrowRight, Package, Truck } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useStore } from "../lib/store-context";
import { formatPrice } from "../lib/store-data";

// Import product images directly from assets
import laptop1 from '../assets/laptop-1.png';
import laptop2 from '../assets/laptop-2.png';
import laptop3 from '../assets/laptop-3.png';
import monitor1 from '../assets/monitor-1.png';

// Map product IDs to their imported images - FIXED with ALL product IDs
const productImages: Record<string, string> = {
  // ============================================================
  // HOME PAGE FEATURED PRODUCTS (from home.tsx)
  // ============================================================
  'dell-latitude-5410': laptop1,      // From home.tsx
  'dell-latitude-5420': laptop2,      // From home.tsx
  'dell-latitude-5440': laptop3,      // From home.tsx
  'dell-monitor-p2422h': monitor1,    // From home.tsx - THIS WAS MISSING!
  
  // ============================================================
  // STORE-DATA FEATURED PRODUCTS
  // ============================================================
  'featured-lat-5410': laptop1,
  'featured-lat-5420': laptop2,
  'featured-lat-5440': laptop3,
  'featured-monitor': monitor1,
  
  // ============================================================
  // BUSINESS LAPTOPS (from store-data)
  // ============================================================
  'lat-5440': laptop3,
  'lat-7440': laptop3,
  'tp-t14': laptop2,
  
  // ============================================================
  // DESKTOPS AND WORKSTATIONS
  // ============================================================
  'opti-7010-new': laptop3,
  'ts-p3': laptop3,
  'prec-3660-new': laptop3,
  
  // ============================================================
  // MONITORS
  // ============================================================
  'dell-u2723qe-new': monitor1,
  'lenovo-p27h': monitor1,
  'dell-u3423we': monitor1,
  
  // ============================================================
  // ACCESSORIES - No images (will show placeholder)
  // ============================================================
  'dell-ud22': null,
  'lenovo-dock-gen2': null,
  'dell-headset': null,
  'lenovo-combo': null,
  
  // ============================================================
  // SERVICES - No images (will show placeholder)
  // ============================================================
  'service-deployment': null,
  'service-lifecycle': null,
  'service-troubleshooting': null,
};

interface CartPageProps {
  onNavigate?: (page: string) => void;
}

export default function CartPage({ onNavigate }: CartPageProps) {
  const { theme } = useTheme();
  const { cart, setCartQty, removeFromCart, cartTotal, cartCount, clearCart, getCartItems } = useStore();

  const handleContinueShopping = () => {
    if (onNavigate) {
      onNavigate('products');
    } else {
      window.history.back();
    }
  };

  const handleTrackOrder = () => {
    if (onNavigate) {
      onNavigate('track-order');
    } else {
      window.location.href = '/track-order';
    }
  };

  const handleCheckout = () => {
    if (onNavigate) {
      onNavigate('checkout');
    } else {
      window.location.href = '/checkout';
    }
  };

  // Get product image
  const getProductImage = (productId: string) => {
    // Check if we have a mapped image
    if (productImages[productId]) {
      return productImages[productId];
    }
    // If not found, return null (will show placeholder)
    return null;
  };

  // Convert cart object to array
  const cartItems = getCartItems ? getCartItems() : Object.values(cart || {});

  // Debug: Log cart contents
  console.log('🛒 Cart in CartPage:', cart);
  console.log('📦 Cart items:', cartItems);

  if (!cartItems || cartItems.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <div className={`mx-auto w-24 h-24 rounded-full flex items-center justify-center mb-6 ${
          theme === "light" ? "bg-[#EEF3E7]" : "bg-[#2A2E24]"
        }`}>
          <ShoppingCart className={`h-12 w-12 ${
            theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
          }`} />
        </div>
        <h1 className={`text-2xl font-extrabold ${
          theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
        }`}>Your cart is empty</h1>
        <p className={`mt-2 text-sm ${
          theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
        }`}>Browse our products and add items you need.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <button
            onClick={handleContinueShopping}
            className="rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center gap-2"
          >
            <Package className="h-4 w-4" />
            Continue Shopping
          </button>
        </div>

        <div className={`mt-6 pt-6 border-t ${
          theme === "light" ? "border-[#D7E2C8]" : "border-[#3A4331]"
        }`}>
          <p className={`text-sm ${
            theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
          } mb-3`}>Already placed an order?</p>
          <button
            onClick={handleTrackOrder}
            className="rounded-xl border border-[#839705] px-6 py-2.5 text-sm font-semibold text-[#839705] hover:bg-[#839705] hover:text-white transition-colors inline-flex items-center gap-2"
          >
            <Truck className="h-4 w-4" />
            Track Your Order
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className={`text-3xl font-black tracking-tight sm:text-4xl ${
            theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
          }`}>
            Your Cart
          </h1>
          <p className={`text-sm ${
            theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
          }`}>
            {cartCount || cartItems.length} {cartCount === 1 ? 'item' : 'items'} in your cart
          </p>
        </div>
        <button
          onClick={clearCart}
          className="text-sm text-red-500 hover:text-red-700 transition-colors"
        >
          Clear cart
        </button>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <ul className="space-y-3">
          {cartItems.map((item) => {
            const productImage = getProductImage(item.id);
            
            return (
              <li
                key={item.id}
                className={`grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 rounded-2xl border p-4 ${
                  theme === "light"
                    ? "border-[#D7E2C8] bg-white"
                    : "border-[#3A4331] bg-[#1A1A1A]"
                }`}
              >
                {/* Product Image */}
                {productImage ? (
                  <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-muted/20">
                    <img
                      src={productImage}
                      alt={item.name}
                      className="h-full w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className={`h-16 w-16 shrink-0 rounded-lg flex items-center justify-center ${
                    theme === "light" ? "bg-[#EEF3E7]" : "bg-[#2A2E24]"
                  }`}>
                    <Package className={`h-6 w-6 ${
                      theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
                    }`} />
                  </div>
                )}
                
                {/* Product Info */}
                <div className="min-w-0">
                  <p className={`truncate text-sm font-bold ${
                    theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                  }`}>{item.name}</p>
                  <p className={`text-xs ${
                    theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
                  }`}>{item.shortDescription || item.specs?.slice(0, 2).join(', ') || ''}</p>
                  <p className={`mt-1 text-sm font-semibold ${
                    theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                  }`}>
                    {formatPrice ? formatPrice(item.price || 0) : `R${(item.price || 0).toFixed(2)}`}
                  </p>
                </div>
                
                {/* Quantity Controls */}
                <div className="flex shrink-0 items-center gap-2">
                  <div className={`flex items-center rounded-full border ${
                    theme === "light" ? "border-[#D7E2C8]" : "border-[#3A4331]"
                  }`}>
                    <button
                      aria-label="Decrease quantity"
                      className={`grid h-9 w-9 place-items-center rounded-l-full ${
                        theme === "light" ? "hover:bg-[#EEF3E7]" : "hover:bg-[#2A2E24]"
                      }`}
                      onClick={() => setCartQty(item.id, item.quantity - 1)}
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                    <span className={`w-8 text-center text-sm font-semibold ${
                      theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                    }`}>{item.quantity}</span>
                    <button
                      aria-label="Increase quantity"
                      className={`grid h-9 w-9 place-items-center rounded-r-full ${
                        theme === "light" ? "hover:bg-[#EEF3E7]" : "hover:bg-[#2A2E24]"
                      }`}
                      onClick={() => setCartQty(item.id, item.quantity + 1)}
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <button
                    aria-label="Remove item"
                    className={`rounded-lg p-2 ${
                      theme === "light" ? "hover:bg-red-50" : "hover:bg-red-900/20"
                    }`}
                    onClick={() => removeFromCart(item.id)}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <aside className={`h-fit rounded-2xl border p-5 ${
          theme === "light"
            ? "border-[#D7E2C8] bg-white"
            : "border-[#3A4331] bg-[#1A1A1A]"
        }`}>
          <h2 className={`text-base font-extrabold ${
            theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
          }`}>Order summary</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className={theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"}>Subtotal ({cartCount || cartItems.length} items)</dt>
              <dd className={`font-semibold ${
                theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
              }`}>{formatPrice ? formatPrice(cartTotal) : `R${(cartTotal || 0).toFixed(2)}`}</dd>
            </div>
            <div className="flex justify-between">
              <dt className={theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"}>Delivery</dt>
              <dd className={`font-semibold ${
                theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
              }`}>Calculated at checkout</dd>
            </div>
            <div className={`flex justify-between border-t pt-3 text-base font-extrabold ${
              theme === "light" ? "border-[#D7E2C8]" : "border-[#3A4331]"
            }`}>
              <dt className={theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"}>Total</dt>
              <dd className={theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"}>{formatPrice ? formatPrice(cartTotal) : `R${(cartTotal || 0).toFixed(2)}`}</dd>
            </div>
          </dl>

          <button
            onClick={handleCheckout}
            className="mt-5 h-12 w-full rounded-xl bg-[#839705] text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center justify-center gap-2"
          >
            Proceed to Checkout
            <ArrowRight className="h-4 w-4" />
          </button>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              onClick={handleContinueShopping}
              className={`h-11 w-full rounded-xl border text-sm font-medium transition-colors ${
                theme === "light"
                  ? "border-[#D7E2C8] hover:bg-[#EEF3E7] text-[#111111]"
                  : "border-[#3A4331] hover:bg-[#2A2E24] text-[#F9FAFB]"
              }`}
            >
              Continue shopping
            </button>
            <button
              onClick={handleTrackOrder}
              className={`h-11 w-full rounded-xl border text-sm font-medium transition-colors inline-flex items-center justify-center gap-1.5 ${
                theme === "light"
                  ? "border-[#839705] text-[#839705] hover:bg-[#839705] hover:text-white"
                  : "border-[#839705] text-[#839705] hover:bg-[#839705] hover:text-white"
              }`}
            >
              <Truck className="h-3.5 w-3.5" />
              Track Order
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}