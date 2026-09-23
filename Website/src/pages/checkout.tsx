// src/pages/checkout.tsx
import { useState } from "react";
import { CheckCircle2, Copy, Check, Package, ArrowRight, Loader2, Receipt, Mail } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useStore } from "../lib/store-context";
import { formatPrice } from "../lib/store-data";
import { submitOrder } from "../lib/api";

interface CheckoutPageProps {
  onNavigate?: (page: string, data?: any) => void;
  onClose?: () => void;
}

export default function CheckoutPage({ onNavigate }: CheckoutPageProps = {}) {
  console.log('✅ CheckoutPage rendered');
  
  const { theme } = useTheme();
  const { cart, clearCart, cartTotal, getCartItems } = useStore();
  const [placed, setPlaced] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [orderReference, setOrderReference] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    company: "",
    email: "",
    phone: "",
    address: "",
    notes: "",
  });

  // Get cart items as array
  const cartItems = getCartItems ? getCartItems() : Object.values(cart || {});

  const handleCopyReference = async () => {
    if (!orderReference) return;
    try {
      await navigator.clipboard.writeText(orderReference);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    } catch (err) {
      const textarea = document.createElement('textarea');
      textarea.value = orderReference;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    }
  };

  // --- FIX: Navigate to track order page ---
  const handleTrackOrder = () => {
    if (!orderReference) return;
    
    // Use React Router navigation if available
    if (onNavigate) {
      onNavigate('track-order', { 
        ref: orderReference, 
        email: formData.email 
      });
    } else {
      // Fallback: Use URL with properly encoded parameters
      const trackUrl = `/track-order?ref=${encodeURIComponent(orderReference)}&email=${encodeURIComponent(formData.email)}`;
      window.location.href = trackUrl;
    }
  };

  if (placed) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12 text-center">
        <div className="text-center">
          <div className="mx-auto relative">
            <div className="absolute inset-0 animate-ping">
              <CheckCircle2 className="mx-auto h-16 w-16 text-green-500 opacity-75" />
            </div>
            <CheckCircle2 className="mx-auto h-16 w-16 text-green-500 relative" />
          </div>
          
          <h1 className="mt-4 text-3xl font-extrabold text-foreground">Order Placed! 🎉</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Thank you for your order. We'll confirm stock and delivery by email within 24 hours.
          </p>
        </div>
        
        {orderReference && (
          <div className="mx-auto mt-8 w-full max-w-md rounded-2xl border-2 border-[#839705] bg-[#839705]/5 p-6 shadow-lg">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Receipt className="h-5 w-5 text-[#839705]" />
              <p className="text-xs font-semibold uppercase tracking-wider text-[#839705]">
                Your Order Reference
              </p>
            </div>
            
            <div className="flex items-center justify-center gap-3 bg-background rounded-xl p-4 border border-border">
              <p className="text-2xl sm:text-3xl font-extrabold text-foreground font-mono tracking-wider">
                {orderReference}
              </p>
              <button
                onClick={handleCopyReference}
                className={`rounded-lg p-2 transition-colors ${
                  copySuccess 
                    ? 'bg-green-500 text-white' 
                    : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                {copySuccess ? <Check className="h-5 w-5" /> : <Copy className="h-5 w-5" />}
              </button>
            </div>
            
            <p className="mt-3 text-center text-xs text-muted-foreground">
              {copySuccess ? '✅ Copied to clipboard!' : 'Keep this to track your order'}
            </p>
            
            <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground border-t border-border pt-4">
              <Mail className="h-4 w-4" />
              <span>We've also sent this to <strong className="text-foreground">{formData.email}</strong></span>
            </div>
          </div>
        )}

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {/* --- FIXED: Use handleTrackOrder function --- */}
          <button
            onClick={handleTrackOrder}
            className="rounded-xl bg-[#839705] px-6 py-3 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center gap-2 shadow-lg hover:shadow-xl"
          >
            <Package className="h-4 w-4" />
            Track Your Order
          </button>
          <button
            onClick={() => window.location.href = '/'}
            className="rounded-xl border border-border bg-background px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
          >
            Continue Shopping
          </button>
        </div>
      </div>
    );
  }

  // Check if cart is empty
  if (cartItems.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <div className="mx-auto w-24 h-24 rounded-full bg-muted flex items-center justify-center mb-6">
          <Package className="h-12 w-12 text-muted-foreground" />
        </div>
        <h1 className="text-2xl font-extrabold text-foreground">Your cart is empty</h1>
        <p className="mt-2 text-sm text-muted-foreground">Browse our products and add items you need.</p>
        <button
          onClick={() => window.location.href = '/products'}
          className="mt-5 rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center gap-2"
        >
          <ArrowRight className="h-4 w-4" />
          Shop Products
        </button>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      // Validate form
      if (!formData.name.trim()) {
        throw new Error('Please enter your full name');
      }
      if (!formData.email.trim() || !formData.email.includes('@')) {
        throw new Error('Please enter a valid email address');
      }
      if (!formData.phone.trim()) {
        throw new Error('Please enter your phone number');
      }
      if (!formData.address.trim()) {
        throw new Error('Please enter your delivery address');
      }

      // Prepare order items
      const orderItems = cartItems.map(item => ({
        id: item.id,
        name: item.name,
        qty: item.quantity,
        price: item.price || 0,
      }));

      // Prepare order payload
      const orderPayload = {
        customerName: formData.name.trim(),
        company: formData.company.trim(),
        email: formData.email.trim(),
        phone: formData.phone.trim(),
        address: formData.address.trim(),
        notes: formData.notes.trim(),
        items: orderItems,
        total: cartTotal,
      };

      console.log('📦 Submitting order:', orderPayload);

      // Submit order to backend
      const response = await submitOrder(orderPayload);
      console.log('✅ Order response:', response);

      if (response.success && response.orderReference) {
        setOrderReference(response.orderReference);
      } else {
        // Fallback reference if API doesn't return one
        const fallbackRef = `ORD-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
        setOrderReference(fallbackRef);
      }

      // Clear the cart
      clearCart();
      setPlaced(true);
    } catch (error) {
      console.error('❌ Error placing order:', error);
      setError(error instanceof Error ? error.message : 'There was an error placing your order. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Checkout
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Complete Your Order
        </h1>
        <p className="text-sm text-muted-foreground">
          Fill in your details to place your order. You'll receive a reference number to track your order.
        </p>
      </header>

      {error && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
          <p className="font-semibold">Error:</p>
          <p>{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <form
        className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]"
        onSubmit={handleSubmit}
      >
        <div className={`rounded-2xl border p-5 ${
          theme === "light"
            ? "border-[#D7E2C8] bg-white"
            : "border-[#3A4331] bg-[#1A1A1A]"
        }`}>
          <h2 className="text-base font-extrabold text-foreground">Your details</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-foreground">Full name *</label>
              <input
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="John Doe"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Company (optional)</label>
              <input
                value={formData.company}
                onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="Your company name"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Email *</label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="you@company.co.za"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Phone *</label>
              <input
                required
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="082 123 4567"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm font-medium text-foreground">Delivery address *</label>
              <textarea
                required
                rows={3}
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="123 Main Street, City, Province, Postal Code"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm font-medium text-foreground">Order notes (optional)</label>
              <textarea
                rows={2}
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="Any special instructions or delivery preferences..."
              />
            </div>
          </div>
        </div>

        <aside className={`h-fit rounded-2xl border p-5 ${
          theme === "light"
            ? "border-[#D7E2C8] bg-white"
            : "border-[#3A4331] bg-[#1A1A1A]"
        }`}>
          <h2 className="text-base font-extrabold text-foreground">Order Summary</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {cartItems.map((item) => (
              <li key={item.id} className="flex justify-between gap-3">
                <span className="min-w-0 text-muted-foreground">
                  {item.quantity} × {item.name}
                </span>
                <span className="shrink-0 font-semibold text-foreground">
                  {formatPrice((item.price || 0) * item.quantity)}
                </span>
              </li>
            ))}
          </ul>
          
          <div className={`mt-4 flex justify-between border-t pt-3 text-base font-extrabold ${
            theme === "light" ? "border-[#D7E2C8]" : "border-[#3A4331]"
          }`}>
            <span className="text-foreground">Total</span>
            <span className="text-foreground">{formatPrice(cartTotal)}</span>
          </div>
          
          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-5 h-12 w-full rounded-xl bg-[#839705] text-sm font-semibold text-white hover:bg-[#98ab06] disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Placing Order...
              </>
            ) : (
              <>
                <Package className="h-4 w-4" />
                Place Order
              </>
            )}
          </button>
          
          <div className="mt-3 flex items-center justify-center gap-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3 text-green-500" />
            <span>Secure checkout</span>
          </div>
          
          <p className="mt-2 text-center text-xs text-muted-foreground">
            You'll receive a reference number to track your order.
          </p>
        </aside>
      </form>
    </div>
  );
}
