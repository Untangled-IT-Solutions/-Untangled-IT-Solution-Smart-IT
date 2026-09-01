// src/pages/track-quote.tsx
import { useEffect, useState } from "react";
import { 
  CheckCircle2, Clock, FileSearch, MessageSquare, AlertCircle, 
  Package, User, Mail, Phone, ArrowLeft, Inbox, 
  RefreshCw, CreditCard, ThumbsUp, MessageCircle, PhoneCall, Send,
  Star, ExternalLink, Loader2, ImageOff
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { trackQuote, submitFeedback, initiatePayment, type TrackedQuote } from "../lib/api";

// Status configuration with icons and colors
const STATUS_CONFIG: Record<TrackedQuote['status'], { label: string; hint: string; color: string; icon: JSX.Element }> = {
  received: { 
    label: "Received ✅", 
    hint: "We have received your quote request and are looking at it.",
    color: "text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400",
    icon: <Inbox className="h-5 w-5" />
  },
  in_review: { 
    label: "In Review 🔍", 
    hint: "We're checking stock and pricing for your request.",
    color: "text-amber-600 bg-amber-100 dark:bg-amber-900/30 dark:text-amber-400",
    icon: <RefreshCw className="h-5 w-5" />
  },
  quoted: { 
    label: "Quoted 💰", 
    hint: "Your pricing is ready — see our reply below.",
    color: "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <CheckCircle2 className="h-5 w-5" />
  },
  closed: { 
    label: "Closed 📦", 
    hint: "This request has been completed.",
    color: "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
    icon: <Package className="h-5 w-5" />
  }
};

// Extended status options
const EXTENDED_STATUS: Record<string, { label: string; hint: string; color: string; icon: JSX.Element }> = {
  pending: { 
    label: "Pending ⏳", 
    hint: "Your quote request is pending review.",
    color: "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400",
    icon: <Clock className="h-5 w-5" />
  },
  waiting_feedback: { 
    label: "Waiting Feedback 💬", 
    hint: "We've sent you a response and are waiting for your feedback.",
    color: "text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400",
    icon: <MessageCircle className="h-5 w-5" />
  },
  in_touch: { 
    label: "In Touch 📞", 
    hint: "One of our team members is actively working on your request.",
    color: "text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400",
    icon: <PhoneCall className="h-5 w-5" />
  },
  approved: { 
    label: "Approved ✅", 
    hint: "Your quote has been approved!",
    color: "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <ThumbsUp className="h-5 w-5" />
  },
  payment: { 
    label: "Payment 💳", 
    hint: "Payment is being processed or has been received.",
    color: "text-teal-600 bg-teal-100 dark:bg-teal-900/30 dark:text-teal-400",
    icon: <CreditCard className="h-5 w-5" />
  }
};

// Get status display with fallback
const getStatusDisplay = (status: TrackedQuote['status']) => {
  const config = STATUS_CONFIG[status];
  if (config) return config;
  
  // Check extended status
  const extended = EXTENDED_STATUS[status];
  if (extended) return extended;
  
  // Fallback
  return {
    label: status.replace('_', ' ').toUpperCase(),
    hint: "Status update in progress.",
    color: "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
    icon: <Clock className="h-5 w-5" />
  };
};

// Feedback Form Component - Only shown after payment
function FeedbackForm({ 
  onSubmit, 
  isSubmitting 
}: { 
  onSubmit: (feedback: { rating: number; comment: string }) => Promise<void>;
  isSubmitting: boolean;
}) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (rating === 0) {
      setError('Please select a rating');
      return;
    }

    try {
      await onSubmit({ rating, comment });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          How would you rate our service?
        </label>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              onClick={() => setRating(star)}
              onMouseEnter={() => setHoveredRating(star)}
              onMouseLeave={() => setHoveredRating(0)}
              className="focus:outline-none transition-transform hover:scale-110"
            >
              <Star
                className={`h-8 w-8 ${
                  star <= (hoveredRating || rating)
                    ? 'fill-yellow-400 text-yellow-400'
                    : 'text-gray-300 dark:text-gray-600'
                }`}
              />
            </button>
          ))}
          <span className="text-sm text-muted-foreground self-center ml-2">
            {rating > 0 && `${rating} / 5`}
          </span>
        </div>
      </div>

      <div>
        <label htmlFor="feedback-comment" className="block text-sm font-medium text-foreground mb-2">
          Your feedback (optional)
        </label>
        <textarea
          id="feedback-comment"
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Tell us about your experience..."
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Submitting...
          </>
        ) : (
          <>
            <Send className="h-4 w-4" />
            Submit Feedback
          </>
        )}
      </button>
    </form>
  );
}

// Payment Button Component
function PaymentButton({ 
  onInitiate, 
  amount,
  isLoading,
  paymentStatus
}: { 
  onInitiate: () => Promise<void>;
  amount: number;
  isLoading: boolean;
  paymentStatus?: string;
}) {
  const [error, setError] = useState<string | null>(null);

  const handlePayment = async () => {
    setError(null);
    try {
      await onInitiate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initiate payment');
    }
  };

  // If payment is already paid, don't show the button
  if (paymentStatus === 'paid') {
    return null;
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handlePayment}
        disabled={isLoading || paymentStatus === 'paid'}
        className="w-full rounded-xl bg-[#839705] px-6 py-3 text-sm font-semibold text-white hover:bg-[#98ab06] disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : (
          <>
            <CreditCard className="h-4 w-4" />
            Pay Now - R{amount.toFixed(2)}
            <ExternalLink className="h-3 w-3" />
          </>
        )}
      </button>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-sm text-red-600 dark:text-red-400 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}
      <p className="text-xs text-muted-foreground text-center">
        You will be redirected to our secure payment gateway.
      </p>
    </div>
  );
}

export default function TrackQuotePage() {
  const { theme } = useTheme();
  
  const [initialRef, setInitialRef] = useState<string>("");
  
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const refParam = params.get('ref');
    if (refParam) {
      setInitialRef(refParam);
    }
  }, []);

  const [reference, setReference] = useState(initialRef);
  const [email, setEmail] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<TrackedQuote | null>(null);
  const [isTracking, setIsTracking] = useState(false);

  // Feedback states
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  // Payment states
  const [paymentProcessing, setPaymentProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setNotFound(false);
    setError(null);
    setQuote(null);
    setIsTracking(true);

    try {
      const response = await trackQuote(reference.trim().toUpperCase(), email.trim());

      if (response.success && response.quote) {
        setQuote(response.quote);
        setFeedbackSubmitted(false);
      } else {
        setNotFound(true);
      }
    } catch (err) {
      console.error('Error tracking quote:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect to server. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setQuote(null);
    setReference("");
    setEmail("");
    setNotFound(false);
    setError(null);
    setIsTracking(false);
    setFeedbackSubmitted(false);
  };

  const handleFeedbackSubmit = async (feedback: { rating: number; comment: string }) => {
    if (!quote) return;
    
    setFeedbackSubmitting(true);
    try {
      const response = await submitFeedback(quote.reference, quote.email, feedback);
      
      if (response.success) {
        setFeedbackSubmitted(true);
        if (response.quote) {
          setQuote(response.quote);
        }
      } else {
        throw new Error(response.message || 'Failed to submit feedback');
      }
    } catch (err) {
      console.error('Feedback submission error:', err);
      throw err;
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handlePaymentInitiate = async () => {
    if (!quote) return;
    
    setPaymentProcessing(true);
    try {
      const response = await initiatePayment(quote.reference, quote.email);
      
      if (response.success && response.paymentUrl) {
        window.open(response.paymentUrl, '_blank');
        if (response.quote) {
          setQuote(response.quote);
        }
        alert('Payment window opened. Complete the payment to finalize your quote.');
      } else {
        throw new Error(response.message || 'Payment initiation failed');
      }
    } catch (err) {
      console.error('Payment error:', err);
      alert(err instanceof Error ? err.message : 'Failed to initiate payment');
    } finally {
      setPaymentProcessing(false);
    }
  };

  const statusDisplay = quote ? getStatusDisplay(quote.status) : null;

  // Check if payment should be shown
  const showPayment = quote && 
    quote.paymentRequired && 
    quote.paymentAmount && 
    quote.paymentAmount > 0 &&
    quote.paymentStatus !== 'paid';

  // Check if feedback should be shown
  const showFeedback = quote && 
    quote.paymentStatus === 'paid' && 
    !feedbackSubmitted &&
    !quote.feedback?.submitted;

  // Check if feedback was already submitted
  const feedbackAlreadySubmitted = quote && quote.feedback?.submitted;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Quote tracking
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Track Your Quote
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Enter the reference we gave you and the email you used. No account needed.
        </p>
      </header>

      {/* Show form only when no quote is displayed */}
      {!quote && (
        <form
          className="mt-6 grid gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
          onSubmit={handleSubmit}
        >
          <div>
            <label htmlFor="t-ref" className="text-sm font-medium text-foreground">
              Quote reference
            </label>
            <input
              id="t-ref"
              required
              value={reference}
              onChange={(e) => setReference(e.target.value.toUpperCase())}
              placeholder="UQ-XXXXXX"
              className="mt-1.5 h-12 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label htmlFor="t-email" className="text-sm font-medium text-foreground">
              Email used
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
                Checking...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Track quote
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
          </div>
        </div>
      )}

      {notFound && !loading && (
        <div className="mt-6 rounded-2xl border border-dashed border-border p-10 text-center">
          <FileSearch className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 font-semibold text-foreground">We couldn't find that quote</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Double-check the reference and use the same email you submitted with.
          </p>
          <button
            onClick={handleReset}
            className="mt-4 text-sm text-[#839705] hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Quote Details - Display when found */}
      {quote && statusDisplay && (
        <div className="mt-6 space-y-4 animate-fade-in-up">
          {/* Success Message */}
          <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
            <p className="text-sm font-semibold text-green-700 dark:text-green-400">
              ✅ Quote found! Here are your details.
            </p>
          </div>

          {/* Quote Status Card */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Reference</p>
                <p className="text-2xl font-extrabold text-foreground">{quote.reference}</p>
              </div>
              <div className={`flex items-center gap-2 rounded-full px-4 py-2 font-bold ${statusDisplay.color}`}>
                {statusDisplay.icon}
                <span>{statusDisplay.label}</span>
              </div>
            </div>
            <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-lg">
              <Clock className="h-4 w-4 text-[#839705]" />
              {statusDisplay.hint}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full">
                📅 Submitted: {new Date(quote.createdAt).toLocaleDateString()}
              </span>
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full">
                🕐 {new Date(quote.createdAt).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Customer Details */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <User className="h-4 w-4" /> Customer Details
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground font-medium">{quote.customerName}</span>
              </div>
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground">{quote.email}</span>
              </div>
              {quote.phone && (
                <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg sm:col-span-2">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{quote.phone}</span>
                </div>
              )}
            </div>
          </div>

          {/* Items with Images */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <Package className="h-4 w-4" /> Items ({quote.items.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {quote.items.map((i, index) => (
                <li 
                  key={i.id} 
                  className={`flex items-center gap-4 py-2.5 px-3 rounded-lg ${
                    index % 2 === 0 ? 'bg-muted/30' : ''
                  }`}
                >
                  {/* Item Image */}
                  <div className="flex-shrink-0">
                    {i.image ? (
                      <img 
                        src={i.image} 
                        alt={i.name}
                        className="w-14 h-14 object-cover rounded-lg border border-border"
                        onError={(e) => {
                          // Fallback if image fails to load
                          (e.target as HTMLImageElement).style.display = 'none';
                          // Show fallback icon
                          const parent = (e.target as HTMLImageElement).parentElement;
                          if (parent) {
                            const fallback = document.createElement('div');
                            fallback.className = 'w-14 h-14 bg-muted rounded-lg flex items-center justify-center border border-border';
                            fallback.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect><circle cx="9" cy="9" r="2"></circle><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path></svg>`;
                            parent.appendChild(fallback);
                          }
                        }}
                      />
                    ) : (
                      <div className="w-14 h-14 bg-muted rounded-lg flex items-center justify-center border border-border">
                        <ImageOff className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  
                  {/* Item Details */}
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-foreground block truncate">
                      {i.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Item #{index + 1}
                    </span>
                  </div>
                  
                  {/* Quantity */}
                  <span className="shrink-0 text-muted-foreground bg-background px-3 py-0.5 rounded-full text-sm font-semibold">
                    ×{i.qty}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Reply Message */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="flex items-center gap-2 text-base font-extrabold text-foreground">
              <MessageSquare className="h-4 w-4" /> Our reply
            </h2>
            {quote.replyMessage ? (
              <>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-foreground bg-muted/30 p-4 rounded-lg">
                  {quote.replyMessage}
                </p>
                {quote.repliedAt && (
                  <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                    Replied {new Date(quote.repliedAt).toLocaleString()}
                  </p>
                )}
              </>
            ) : (
              <div className="mt-3 p-4 bg-muted/50 rounded-lg text-center border border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  No reply yet — we usually come back within 24 hours.
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  📧 Check your email for updates
                </p>
              </div>
            )}
          </div>

          {/* Payment Section - Show ONLY if payment is required AND not yet paid */}
          {showPayment && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-[#839705]" />
                Complete Your Payment
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Please complete your payment to finalize your quote. After payment, you can share your feedback.
              </p>
              
              {quote.paymentStatus === 'pending' && (
                <div className="mt-4">
                  <PaymentButton
                    onInitiate={handlePaymentInitiate}
                    amount={quote.paymentAmount || 0}
                    isLoading={paymentProcessing}
                    paymentStatus={quote.paymentStatus}
                  />
                </div>
              )}

              {quote.paymentStatus === 'pending' && paymentProcessing && (
                <div className="mt-3 text-center">
                  <p className="text-sm text-muted-foreground">
                    ⏳ Opening payment window...
                  </p>
                </div>
              )}

              {quote.paymentStatus === 'failed' && (
                <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-center">
                  <AlertCircle className="mx-auto h-8 w-8 text-red-500 mb-2" />
                  <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                    Payment Failed
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Please try again or contact support.
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="mt-2 text-sm text-[#839705] hover:underline"
                  >
                    Retry Payment
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Payment Completed Message - Show when payment is successful */}
          {quote.paymentStatus === 'paid' && (
            <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
              <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                ✅ Payment Completed!
              </p>
              <p className="text-xs text-muted-foreground">
                Your payment has been successfully processed. Please share your feedback below.
              </p>
            </div>
          )}

          {/* Feedback Section - ONLY SHOW AFTER PAYMENT IS COMPLETED */}
          {showFeedback && (
            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-500" />
                Share Your Feedback
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Thank you for your payment! We'd love to hear about your experience.
              </p>
              <div className="mt-4">
                <FeedbackForm
                  onSubmit={handleFeedbackSubmit}
                  isSubmitting={feedbackSubmitting}
                />
              </div>
            </div>
          )}

          {/* Feedback Already Submitted */}
          {feedbackAlreadySubmitted && (
            <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
              <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                Thank you for your feedback! 
              </p>
              {quote.feedback?.rating && (
                <p className="text-xs text-muted-foreground mt-1">
                  Rating: {'⭐'.repeat(quote.feedback.rating)}
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={handleReset}
              className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Track another quote
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