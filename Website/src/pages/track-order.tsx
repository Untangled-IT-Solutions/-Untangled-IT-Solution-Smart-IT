// src/pages/track-order.tsx
import { useState, useEffect } from "react";
import { 
  CheckCircle2, 
  Clock, 
  Package, 
  User, 
  Mail, 
  Phone, 
  ArrowLeft, 
  AlertCircle, 
  Loader2, 
  Copy, 
  Calendar, 
  MapPin, 
  ShoppingBag, 
  Truck, 
  Box,
  X,
  RefreshCw
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { trackOrder, type TrackedOrder } from "../lib/api";

const ORDER_STATUSES: Record<string, { label: string; color: string; icon: JSX.Element }> = {
  pending: { 
    label: "Pending", 
    color: "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400",
    icon: <Clock className="h-5 w-5" />
  },
  confirmed: { 
    label: "Confirmed ✅", 
    color: "text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400",
    icon: <CheckCircle2 className="h-5 w-5" />
  },
  processing: { 
    label: "Processing", 
    color: "text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400",
    icon: <RefreshCw className="h-5 w-5" />
  },
  shipped: { 
    label: "Shipped 🚚", 
    color: "text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400",
    icon: <Truck className="h-5 w-5" />
  },
  delivered: { 
    label: "Delivered ✅", 
    color: "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <CheckCircle2 className="h-5 w-5" />
  },
  cancelled: { 
    label: "Cancelled ❌", 
    color: "text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400",
    icon: <X className="h-5 w-5" />
  }
};

export default function TrackOrderPage() {
  const { theme } = useTheme();
  
  const [reference, setReference] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<TrackedOrder | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const refParam = params.get('ref');
    const emailParam = params.get('email');
    
    if (refParam) {
      setReference(refParam);
    }
    if (emailParam) {
      setEmail(emailParam);
    }
    
    // Auto-track if both params are present
    if (refParam && emailParam) {
      setTimeout(() => {
        handleTrack(refParam, emailParam);
      }, 500);
    }
  }, []);

  const handleCopyReference = async () => {
    if (!order?.reference) return;
    try {
      await navigator.clipboard.writeText(order.reference);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    } catch (err) {
      const textarea = document.createElement('textarea');
      textarea.value = order.reference;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    }
  };

  const handleTrack = async (ref?: string, emailAddress?: string) => {
    const trackRef = ref || reference;
    const trackEmail = emailAddress || email;
    
    if (!trackRef.trim() || !trackEmail.trim()) {
      setError('Please enter both reference number and email');
      return;
    }
    
    console.log('🔍 Tracking order:', { ref: trackRef, email: trackEmail });
    
    setLoading(true);
    setNotFound(false);
    setError(null);
    setOrder(null);

    try {
      const response = await trackOrder(trackRef.trim().toUpperCase(), trackEmail.trim());
      console.log('📦 Track response:', response);

      if (response.success && response.order) {
        setOrder(response.order);
      } else {
        setNotFound(true);
        if (response.error) {
          setError(response.error);
        }
      }
    } catch (err) {
      console.error('Error tracking order:', err);
      setError(err instanceof Error ? err.message : 'Failed to track order. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleTrack();
  };

  const handleReset = () => {
    setOrder(null);
    setReference("");
    setEmail("");
    setNotFound(false);
    setError(null);
  };

  const statusDisplay = order ? ORDER_STATUSES[order.status] || ORDER_STATUSES.pending : null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Order tracking
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Track Your Order
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Enter your order reference number and email to track your order status.
        </p>
      </header>

      {!order && (
        <form
          className="mt-6 grid gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
          onSubmit={handleSubmit}
        >
          <div>
            <label htmlFor="t-ref" className="text-sm font-medium text-foreground">
              Order reference *
            </label>
            <input
              id="t-ref"
              required
              value={reference}
              onChange={(e) => setReference(e.target.value.toUpperCase())}
              placeholder="ORD-XXXXXX"
              className="mt-1.5 h-12 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 font-mono"
            />
          </div>
          <div>
            <label htmlFor="t-email" className="text-sm font-medium text-foreground">
              Email used *
            </label>
            <input
              id="t-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.co.za"
              className="mt-1.5 h-12 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="h-12 rounded-xl bg-[#839705] px-6 text-sm font-semibold text-white hover:bg-[#98ab06] disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Package className="h-4 w-4" />
                Track Order
              </>
            )}
          </button>
        </form>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Error:</p>
            <p>{error}</p>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-xs underline hover:no-underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {notFound && !loading && (
        <div className="mt-6 rounded-2xl border border-dashed border-border p-10 text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 font-semibold text-foreground">Order not found</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Double-check your reference number and email address.
          </p>
          <button
            onClick={handleReset}
            className="mt-4 text-sm text-[#839705] hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {order && statusDisplay && (
        <div className="mt-6 space-y-4 animate-fade-in-up">
          <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
            <p className="text-sm font-semibold text-green-700 dark:text-green-400">
              ✅ Order found! Here are your details.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Order Reference</p>
                  <p className="text-2xl font-extrabold text-foreground font-mono">{order.reference}</p>
                </div>
                <button
                  onClick={handleCopyReference}
                  className={`rounded-lg p-2 transition-colors ${
                    copySuccess 
                      ? 'bg-green-500 text-white' 
                      : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {copySuccess ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
              <div className={`flex items-center gap-2 rounded-full px-4 py-2 font-bold ${statusDisplay.color}`}>
                {statusDisplay.icon}
                <span>{statusDisplay.label}</span>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Placed: {new Date(order.createdAt).toLocaleDateString()}
              </span>
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {new Date(order.createdAt).toLocaleTimeString()}
              </span>
              {order.estimatedDelivery && (
                <span className="text-xs bg-muted/50 px-3 py-1 rounded-full flex items-center gap-1">
                  <Truck className="h-3 w-3" />
                  Est. Delivery: {new Date(order.estimatedDelivery).toLocaleDateString()}
                </span>
              )}
              {order.trackingNumber && (
                <span className="text-xs bg-muted/50 px-3 py-1 rounded-full">
                  Tracking: {order.trackingNumber}
                </span>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <User className="h-4 w-4" /> Customer Details
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground font-medium">{order.customerName}</span>
              </div>
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground">{order.email}</span>
              </div>
              {order.phone && (
                <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{order.phone}</span>
                </div>
              )}
              {order.address && (
                <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg sm:col-span-2">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{order.address}</span>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <ShoppingBag className="h-4 w-4" /> Items ({order.items.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {order.items.map((item, index) => (
                <li 
                  key={item.id} 
                  className={`flex items-center justify-between gap-4 py-2.5 px-3 rounded-lg ${
                    index % 2 === 0 ? 'bg-muted/30' : ''
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-foreground block truncate">
                      {item.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Unit Price: R{item.price.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground bg-background px-3 py-0.5 rounded-full font-semibold">
                      ×{item.qty}
                    </span>
                    <span className="text-sm font-semibold text-foreground">
                      R{(item.price * item.qty).toLocaleString()}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-4 pt-3 border-t border-border flex justify-between font-extrabold">
              <span className="text-foreground">Total</span>
              <span className="text-foreground">R{order.total.toLocaleString()}</span>
            </div>
          </div>

          {order.notes && (
            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <Box className="h-4 w-4" /> Order Notes
              </h2>
              <p className="mt-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-lg">
                {order.notes}
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={handleReset}
              className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Track another order
            </button>
            <button
              onClick={() => window.location.href = '/'}
              className="rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors"
            >
              Back to store
            </button>
          </div>
        </div>
      )}
    </div>
  );
}