// src/pages/track-quote.tsx
// Client quote tracking — aligned with the professional ops workflow:
// Received → Assigned → Awaiting Details → Quoted → Awaiting Client Approval
// → Awaiting Payment → Paid → In Progress → Out for Delivery → Completed
import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock,
  FileSearch,
  MessageSquare,
  AlertCircle,
  Package,
  User,
  Mail,
  Phone,
  ArrowLeft,
  Inbox,
  RefreshCw,
  CreditCard,
  ThumbsUp,
  MessageCircle,
  PhoneCall,
  Send,
  Star,
  ExternalLink,
  Loader2,
  ImageOff,
  MapPin,
  Truck,
  FileText,
  Calendar,
} from "lucide-react";
import {
  trackQuote,
  submitFeedback,
  initiatePayment,
  formatQuoteStatus,
  type TrackedQuote,
} from "../lib/api";

// ---------------------------------------------------------------------------
// Status display — professional workflow + legacy
// ---------------------------------------------------------------------------

type StatusMeta = {
  label: string;
  hint: string;
  color: string;
  icon: JSX.Element;
};

const STATUS_DISPLAY: Record<string, StatusMeta> = {
  received: {
    label: "Received",
    hint: "We have received your quote request and will review it shortly.",
    color:
      "text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400",
    icon: <Inbox className="h-5 w-5" />,
  },
  pending: {
    label: "Pending",
    hint: "Your request is queued for review.",
    color:
      "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400",
    icon: <Clock className="h-5 w-5" />,
  },
  assigned: {
    label: "Assigned",
    hint: "A team member has been assigned and will contact you if anything is missing.",
    color:
      "text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400",
    icon: <User className="h-5 w-5" />,
  },
  awaiting_details: {
    label: "Awaiting Details",
    hint: "We need a bit more information (e.g. delivery address or preferred date) before we can finalise your quotation.",
    color:
      "text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400",
    icon: <FileText className="h-5 w-5" />,
  },
  in_review: {
    label: "In Review",
    hint: "We're checking stock and pricing for your request.",
    color:
      "text-amber-600 bg-amber-100 dark:bg-amber-900/30 dark:text-amber-400",
    icon: <RefreshCw className="h-5 w-5" />,
  },
  quoted: {
    label: "Quoted",
    hint: "Your pricing is ready — see our reply and quotation below.",
    color:
      "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <CheckCircle2 className="h-5 w-5" />,
  },
  awaiting_client_approval: {
    label: "Awaiting Your Approval",
    hint: "Please review the quotation and reply to accept or request changes.",
    color:
      "text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400",
    icon: <ThumbsUp className="h-5 w-5" />,
  },
  awaiting_client: {
    label: "Awaiting Your Approval",
    hint: "Please review the quotation and reply to accept or request changes.",
    color:
      "text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400",
    icon: <ThumbsUp className="h-5 w-5" />,
  },
  awaiting_payment: {
    label: "Awaiting Payment",
    hint: "Your quote was accepted. Complete payment to proceed with fulfilment.",
    color:
      "text-pink-600 bg-pink-100 dark:bg-pink-900/30 dark:text-pink-400",
    icon: <CreditCard className="h-5 w-5" />,
  },
  payment: {
    label: "Payment",
    hint: "Payment is being processed or has been received.",
    color:
      "text-teal-600 bg-teal-100 dark:bg-teal-900/30 dark:text-teal-400",
    icon: <CreditCard className="h-5 w-5" />,
  },
  paid: {
    label: "Paid",
    hint: "Payment received. We are preparing your order / work.",
    color:
      "text-teal-700 bg-teal-100 dark:bg-teal-900/30 dark:text-teal-300",
    icon: <CheckCircle2 className="h-5 w-5" />,
  },
  accepted: {
    label: "Accepted",
    hint: "The job has been accepted by our team.",
    color:
      "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <ThumbsUp className="h-5 w-5" />,
  },
  in_progress: {
    label: "In Progress",
    hint: "Work is underway on your order.",
    color:
      "text-amber-600 bg-amber-100 dark:bg-amber-900/30 dark:text-amber-400",
    icon: <RefreshCw className="h-5 w-5" />,
  },
  out_for_delivery: {
    label: "Out for Delivery",
    hint: "Your order is on the way. See delivery details below.",
    color:
      "text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400",
    icon: <Truck className="h-5 w-5" />,
  },
  completed: {
    label: "Completed",
    hint: "This request has been completed successfully.",
    color:
      "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
    icon: <Package className="h-5 w-5" />,
  },
  closed: {
    label: "Closed",
    hint: "This request has been closed.",
    color:
      "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
    icon: <Package className="h-5 w-5" />,
  },
  returned: {
    label: "Returned",
    hint: "This request was returned for reassignment.",
    color:
      "text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400",
    icon: <AlertCircle className="h-5 w-5" />,
  },
  waiting_feedback: {
    label: "Waiting Feedback",
    hint: "We've sent a response and are waiting for your feedback.",
    color:
      "text-purple-600 bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400",
    icon: <MessageCircle className="h-5 w-5" />,
  },
  in_touch: {
    label: "In Touch",
    hint: "One of our team members is actively working on your request.",
    color:
      "text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400",
    icon: <PhoneCall className="h-5 w-5" />,
  },
  approved: {
    label: "Approved",
    hint: "Your quote has been approved.",
    color:
      "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400",
    icon: <ThumbsUp className="h-5 w-5" />,
  },
};

function getStatusDisplay(status: string | undefined | null): StatusMeta {
  if (!status) {
    return {
      label: "Pending",
      hint: "Status update in progress.",
      color:
        "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
      icon: <Clock className="h-5 w-5" />,
    };
  }
  const key = String(status).toLowerCase().replace(/\s+/g, "_");
  if (STATUS_DISPLAY[key]) return STATUS_DISPLAY[key];
  return {
    label: formatQuoteStatus(status),
    hint: "Status update in progress.",
    color:
      "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400",
    icon: <Clock className="h-5 w-5" />,
  };
}

function formatRand(value: number | undefined | null): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `R ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// ---------------------------------------------------------------------------
// Feedback form
// ---------------------------------------------------------------------------

function FeedbackForm({
  onSubmit,
  isSubmitting,
}: {
  onSubmit: (feedback: {
    rating: number;
    comment: string;
  }) => Promise<void>;
  isSubmitting: boolean;
}) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (rating === 0) {
      setError("Please select a rating");
      return;
    }
    try {
      await onSubmit({ rating, comment });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to submit feedback"
      );
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
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-gray-300 dark:text-gray-600"
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
        <label
          htmlFor="feedback-comment"
          className="block text-sm font-medium text-foreground mb-2"
        >
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

// ---------------------------------------------------------------------------
// Payment button
// ---------------------------------------------------------------------------

function PaymentButton({
  onInitiate,
  amount,
  isLoading,
  paymentStatus,
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
      setError(
        err instanceof Error ? err.message : "Failed to initiate payment"
      );
    }
  };

  if (paymentStatus === "paid") return null;

  return (
    <div className="space-y-2">
      <button
        onClick={handlePayment}
        disabled={isLoading || paymentStatus === "paid"}
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
            Pay Now — {formatRand(amount)}
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

// ---------------------------------------------------------------------------
// Progress steps (visual timeline)
// ---------------------------------------------------------------------------

const WORKFLOW_STEPS = [
  { key: "received", label: "Received" },
  { key: "quoted", label: "Quoted" },
  { key: "awaiting_client_approval", label: "Approval" },
  { key: "awaiting_payment", label: "Payment" },
  { key: "paid", label: "Paid" },
  { key: "out_for_delivery", label: "Delivery" },
  { key: "completed", label: "Done" },
] as const;

function stepIndexForStatus(status: string): number {
  const s = status.toLowerCase();
  if (["completed", "closed"].includes(s)) return 6;
  if (["out_for_delivery"].includes(s)) return 5;
  if (["paid", "in_progress", "accepted"].includes(s)) return 4;
  if (["awaiting_payment", "payment"].includes(s)) return 3;
  if (
    ["awaiting_client_approval", "awaiting_client", "approved"].includes(s)
  )
    return 2;
  if (["quoted", "in_review"].includes(s)) return 1;
  return 0; // received / pending / assigned / awaiting_details
}

function WorkflowTimeline({ status }: { status: string }) {
  const current = stepIndexForStatus(status);
  return (
    <div className="mt-4">
      <div className="flex gap-1">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.key} className="flex-1 min-w-0">
            <div
              className={`h-1.5 rounded-full ${
                i <= current ? "bg-[#839705]" : "bg-muted"
              }`}
            />
            <p
              className={`mt-1.5 text-[10px] sm:text-xs truncate text-center ${
                i <= current
                  ? "text-foreground font-medium"
                  : "text-muted-foreground"
              }`}
            >
              {step.label}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TrackQuotePage() {
  const [initialRef, setInitialRef] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const refParam = params.get("ref");
    if (refParam) setInitialRef(refParam);
  }, []);

  const [reference, setReference] = useState(initialRef);
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (initialRef) setReference(initialRef);
  }, [initialRef]);

  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<TrackedQuote | null>(null);

  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [paymentProcessing, setPaymentProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setNotFound(false);
    setError(null);
    setQuote(null);

    try {
      const response = await trackQuote(
        reference.trim().toUpperCase(),
        email.trim()
      );

      if (response.success && response.quote) {
        setQuote(response.quote);
        setFeedbackSubmitted(false);
      } else {
        setNotFound(true);
      }
    } catch (err) {
      console.error("Error tracking quote:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to connect to server. Please try again later."
      );
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
    setFeedbackSubmitted(false);
  };

  const handleFeedbackSubmit = async (feedback: {
    rating: number;
    comment: string;
  }) => {
    if (!quote) return;
    setFeedbackSubmitting(true);
    try {
      const response = await submitFeedback(
        quote.reference,
        quote.email,
        feedback
      );
      if (response.success) {
        setFeedbackSubmitted(true);
        if (response.quote) setQuote(response.quote);
      } else {
        throw new Error(response.message || "Failed to submit feedback");
      }
    } catch (err) {
      console.error("Feedback submission error:", err);
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
        window.open(response.paymentUrl, "_blank");
        if (response.quote) setQuote(response.quote);
      } else {
        throw new Error(response.message || "Payment initiation failed");
      }
    } catch (err) {
      console.error("Payment error:", err);
      alert(
        err instanceof Error ? err.message : "Failed to initiate payment"
      );
    } finally {
      setPaymentProcessing(false);
    }
  };

  const statusDisplay = quote ? getStatusDisplay(quote.status) : null;

  const paymentAmount =
    quote?.paymentAmount ??
    quote?.quotation_total ??
    quote?.total ??
    0;

  const showPayment =
    quote &&
    quote.paymentStatus !== "paid" &&
    paymentAmount > 0 &&
    (quote.paymentRequired ||
      ["awaiting_payment", "payment", "quoted", "awaiting_client_approval"].includes(
        String(quote.status).toLowerCase()
      ));

  const showFeedback =
    quote &&
    quote.paymentStatus === "paid" &&
    !feedbackSubmitted &&
    !quote.feedback?.submitted;

  const feedbackAlreadySubmitted = quote && quote.feedback?.submitted;

  const deliveryAddress =
    quote?.delivery?.address ||
    quote?.delivery_address ||
    quote?.address;
  const deliveryDate =
    quote?.delivery?.date ||
    quote?.delivery_date ||
    quote?.preferred_delivery_date;
  const deliveryDriver = quote?.delivery?.driver;
  const deliveryStatus = quote?.delivery?.status;

  const showDeliveryCard =
    quote &&
    (deliveryAddress ||
      deliveryDate ||
      ["paid", "in_progress", "out_for_delivery", "completed"].includes(
        String(quote.status).toLowerCase()
      ));

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
          Enter the reference we gave you and the email you used. No account
          needed.
        </p>
      </header>

      {!quote && (
        <form
          className="mt-6 grid gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
          onSubmit={handleSubmit}
        >
          <div>
            <label
              htmlFor="t-ref"
              className="text-sm font-medium text-foreground"
            >
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
            <label
              htmlFor="t-email"
              className="text-sm font-medium text-foreground"
            >
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
          <p className="mt-3 font-semibold text-foreground">
            We couldn&apos;t find that quote
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Double-check the reference and use the same email you submitted
            with.
          </p>
          <button
            onClick={handleReset}
            className="mt-4 text-sm text-[#839705] hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {quote && statusDisplay && (
        <div className="mt-6 space-y-4 animate-fade-in-up">
          <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
            <p className="text-sm font-semibold text-green-700 dark:text-green-400">
              Quote found — here are your details.
            </p>
          </div>

          {/* Status + timeline */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Reference
                </p>
                <p className="text-2xl font-extrabold text-foreground">
                  {quote.reference}
                </p>
              </div>
              <div
                className={`flex items-center gap-2 rounded-full px-4 py-2 font-bold ${statusDisplay.color}`}
              >
                {statusDisplay.icon}
                <span>{statusDisplay.label}</span>
              </div>
            </div>
            <p className="mt-3 flex items-start gap-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-lg">
              <Clock className="h-4 w-4 text-[#839705] shrink-0 mt-0.5" />
              {statusDisplay.hint}
            </p>
            <WorkflowTimeline status={String(quote.status)} />
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full">
                📅 Submitted:{" "}
                {new Date(quote.createdAt).toLocaleDateString("en-ZA")}
              </span>
              <span className="text-xs bg-muted/50 px-3 py-1 rounded-full">
                🕐 {new Date(quote.createdAt).toLocaleTimeString("en-ZA")}
              </span>
            </div>
          </div>

          {/* Customer */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <User className="h-4 w-4" /> Customer Details
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground font-medium">
                  {quote.customerName}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span className="text-foreground">{quote.email}</span>
              </div>
              {quote.phone && (
                <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{quote.phone}</span>
                </div>
              )}
              {quote.company && (
                <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{quote.company}</span>
                </div>
              )}
            </div>
          </div>

          {/* Items */}
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
              <Package className="h-4 w-4" /> Items ({quote.items.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {quote.items.map((i, index) => (
                <li
                  key={`${i.id}-${index}`}
                  className={`flex items-center gap-4 py-2.5 px-3 rounded-lg ${
                    index % 2 === 0 ? "bg-muted/30" : ""
                  }`}
                >
                  <div className="flex-shrink-0">
                    {i.image ? (
                      <img
                        src={i.image}
                        alt={i.name}
                        className="w-14 h-14 object-cover rounded-lg border border-border"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display =
                            "none";
                        }}
                      />
                    ) : (
                      <div className="w-14 h-14 bg-muted rounded-lg flex items-center justify-center border border-border">
                        <ImageOff className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-foreground block truncate">
                      {i.name}
                    </span>
                    {i.note && (
                      <span className="text-xs text-muted-foreground block truncate">
                        {i.note}
                      </span>
                    )}
                  </div>
                  <span className="shrink-0 text-muted-foreground bg-background px-3 py-0.5 rounded-full text-sm font-semibold">
                    ×{i.qty}
                  </span>
                  {i.price != null && i.price > 0 && (
                    <span className="shrink-0 text-sm font-medium text-foreground">
                      {formatRand(i.price * (i.qty || 1))}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {paymentAmount > 0 && (
              <div className="mt-4 flex items-center justify-between border-t border-border pt-3 px-1">
                <span className="text-sm font-semibold text-foreground">
                  Quotation total
                </span>
                <span className="text-lg font-extrabold text-[#839705]">
                  {formatRand(paymentAmount)}
                </span>
              </div>
            )}
          </div>

          {/* Delivery */}
          {showDeliveryCard && (
            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <Truck className="h-4 w-4" /> Delivery Details
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {deliveryAddress && (
                  <div className="flex items-start gap-2 text-sm bg-muted/50 p-2 rounded-lg sm:col-span-2">
                    <MapPin className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <span className="text-foreground">{deliveryAddress}</span>
                  </div>
                )}
                {deliveryDate && (
                  <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-foreground">{deliveryDate}</span>
                  </div>
                )}
                {deliveryDriver && (
                  <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="text-foreground">
                      Driver: {deliveryDriver}
                    </span>
                  </div>
                )}
                {deliveryStatus && (
                  <div className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-lg">
                    <Truck className="h-4 w-4 text-muted-foreground" />
                    <span className="text-foreground">{deliveryStatus}</span>
                  </div>
                )}
                {!deliveryAddress && !deliveryDate && (
                  <p className="text-sm text-muted-foreground sm:col-span-2">
                    Delivery details will appear here once scheduled.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Reply */}
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
                    Replied {new Date(quote.repliedAt).toLocaleString("en-ZA")}
                  </p>
                )}
              </>
            ) : (
              <div className="mt-3 p-4 bg-muted/50 rounded-lg text-center border border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  No reply yet — we usually come back within 24 hours.
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Check your email for updates
                </p>
              </div>
            )}
          </div>

          {/* Payment */}
          {showPayment && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-[#839705]" />
                Complete Your Payment
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Complete payment to finalise your order. After payment we
                prepare fulfilment and delivery.
              </p>
              <div className="mt-4">
                <PaymentButton
                  onInitiate={handlePaymentInitiate}
                  amount={paymentAmount}
                  isLoading={paymentProcessing}
                  paymentStatus={quote.paymentStatus}
                />
              </div>
              {quote.paymentStatus === "failed" && (
                <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-center">
                  <AlertCircle className="mx-auto h-8 w-8 text-red-500 mb-2" />
                  <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                    Payment Failed
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Please try again or contact support.
                  </p>
                </div>
              )}
            </div>
          )}

          {quote.paymentStatus === "paid" && (
            <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
              <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                Payment completed
              </p>
              <p className="text-xs text-muted-foreground">
                Your payment was processed successfully.
              </p>
            </div>
          )}

          {showFeedback && (
            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-500" />
                Share Your Feedback
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                We&apos;d love to hear about your experience.
              </p>
              <div className="mt-4">
                <FeedbackForm
                  onSubmit={handleFeedbackSubmit}
                  isSubmitting={feedbackSubmitting}
                />
              </div>
            </div>
          )}

          {feedbackAlreadySubmitted && (
            <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-green-500 mb-2" />
              <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                Thank you for your feedback!
              </p>
              {quote.feedback?.rating && (
                <p className="text-xs text-muted-foreground mt-1">
                  Rating: {"⭐".repeat(quote.feedback.rating)}
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={handleReset}
              className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Track another quote
            </button>
            <button
              onClick={() => {
                window.location.href = "/";
              }}
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
