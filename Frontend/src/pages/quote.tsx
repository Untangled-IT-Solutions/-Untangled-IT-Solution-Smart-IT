// src/pages/quote.tsx
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Mail,
  Minus,
  Plus,
  Trash2,
  FileText,
  ShoppingCart,
  Info,
  RotateCcw,
  Copy,
  CheckCircle2,
} from "lucide-react";
import { useStore, productById } from "../lib/store-context";
import type { Page } from "../lib/navigation";

interface QuotePageProps {
  onClose?: () => void;
  onNavigateToStore?: () => void;
  onNavigate?: (page: Page) => void;
  initialStep?: 1 | 2 | 3;
}

type Details = {
  fullName: string;
  cellphone: string;
  email: string;
  company?: string;
  message?: string;
};

const EMPTY: Details = {
  fullName: "",
  cellphone: "",
  email: "",
  company: "",
  message: "",
};

// Target email for quotes
const QUOTE_EMAIL = "siyanda.nkosi.developer@gmail.com";

export default function QuotePage({
  onClose,
  onNavigateToStore,
  onNavigate,
  initialStep = 1,
}: QuotePageProps) {
  const { quote, setQuoteQty, removeFromQuote, clearQuote } = useStore();
  const [step, setStep] = useState<1 | 2 | 3>(initialStep);
  const [details, setDetails] = useState<Details>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Details, string>>>(
    {}
  );
  const [isSending, setIsSending] = useState(false);
  const [specNotes, setSpecNotes] = useState<Record<string, string>>({});
  const [reference, setReference] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  // --- FIX: Store submitted items before clearing ---
  const [submittedItems, setSubmittedItems] = useState<
    { id: string; qty: number; kind: string; name: string }[]
  >([]);

  // --- FIXED: Build summary using quote or saved submittedItems ---
  const buildSummary = () => {
    const itemsToUse = quote.length > 0 ? quote : submittedItems;
    const lines = itemsToUse.map((item) => {
      const product = productById(item.id);
      const spec = specNotes[item.id] || "";
      const specs = product?.specs ? ` [${product.specs.join(", ")}]` : "";
      return `• ${item.name}${specs} — qty ${item.qty}${
        spec ? ` (${spec})` : ""
      }`;
    });
    return [
      "Hi Untangled IT Solutions, I'd like a quote.",
      "",
      ...(lines.length ? ["ITEMS:", ...lines] : ["ITEMS: (no items selected)"]),
      "",
      `Name: ${details.fullName}`,
      `Cell: ${details.cellphone}`,
      `Email: ${details.email}`,
      ...(details.company ? [`Company: ${details.company}`] : []),
      ...(details.message ? ["", `Additional Notes: ${details.message}`] : []),
    ].join("\n");
  };

  // --- FIXED: Build full formatted quote text for email ---
  // --- NEW: Copy ONLY the reference ---
  const handleCopyReference = async () => {
    if (!reference) return;
    
    try {
      await navigator.clipboard.writeText(reference);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = reference;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    }
  };

  const validateForm = () => {
    const newErrors: Partial<Record<keyof Details, string>> = {};

    if (!details.fullName.trim() || details.fullName.trim().length < 2) {
      newErrors.fullName = "Please enter your full name";
    } else if (details.fullName.trim().length > 80) {
      newErrors.fullName = "Name is too long";
    }

    if (!details.cellphone.trim() || details.cellphone.trim().length < 9) {
      newErrors.cellphone = "Enter a valid cellphone number";
    } else if (!/^[0-9+()\s-]+$/.test(details.cellphone.trim())) {
      newErrors.cellphone = "Only numbers, spaces and + are allowed";
    }

    if (!details.email.trim()) {
      newErrors.email = "Enter a valid email address";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(details.email.trim())) {
      newErrors.email = "Enter a valid email address";
    }

    if (details.company && details.company.trim().length > 80) {
      newErrors.company = "Company name is too long";
    }

    if (details.message && details.message.trim().length > 600) {
      newErrors.message = "Message is too long";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const submit = async () => {
    console.log("🚀 Submit function started");

    if (!validateForm()) {
      console.log("❌ Form validation failed");
      return;
    }

    setIsSending(true);
    setApiError(null);

    try {
      const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

      const payload = {
        customerName: details.fullName.trim(),
        company: details.company?.trim() || "",
        email: details.email.trim().toLowerCase(),
        phone: details.cellphone.trim(),
        notes: details.message?.trim() || "",
        items: quote.map((item) => {
          const product = productById(item.id);
          return {
            id: item.id,
            name: item.name,
            kind: item.kind || "product",
            qty: item.qty,
            image: product?.image || null,
          };
        }),
      };

      console.log("📤 Sending quote to API:", payload);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      try {
        const response = await fetch(`${API_BASE_URL}/quotes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        console.log("📥 Response status:", response.status);

        const data = await response.json();
        console.log("📥 API Response:", data);

        if (!response.ok || !data.success) {
          throw new Error(data.error || `Server error: ${response.status}`);
        }

        console.log("✅ Quote saved with reference:", data.reference);

        // --- FIX: Save items BEFORE clearing ---
        setSubmittedItems([...quote]);

        setReference(data.reference);

        // ============================================================
        // OPEN MAILTO IN SAME WINDOW (NO NEW TAB)
        // ============================================================
        const summary = buildSummary();
        const subject = `Quote Request ${data.reference} — ${details.fullName}`;
        const body = summary;

        const mailtoUrl = `mailto:${QUOTE_EMAIL}?cc=${encodeURIComponent(
          details.email
        )}&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(
          body
        )}`;

        window.location.href = mailtoUrl;

        setEmailSent(true);
        clearQuote();
        setSpecNotes({});
        setIsSending(false);
      } catch (fetchError: unknown) {
        clearTimeout(timeoutId);

        if (fetchError instanceof Error && fetchError.name === "AbortError") {
          throw new Error(
            "Request timed out. Please check your connection and try again.",
            { cause: fetchError }
          );
        }
        throw fetchError;
      }
    } catch (error) {
      console.error("❌ Error submitting quote:", error);

      let errorMessage = "There was an error sending your quote request.";

      if (error instanceof TypeError && error.message.includes("fetch")) {
        errorMessage =
          "Cannot connect to the server. Please make sure the backend is running on port 5000.";
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      setApiError(errorMessage);
      setIsSending(false);
    }
  };

  const field = (key: keyof Details, value: string) => {
    setDetails((d) => ({ ...d, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const handleBrowseStore = () => {
    if (onNavigateToStore) {
      onNavigateToStore();
    }
    if (onClose) {
      onClose();
    }
  };

  const handleSpecChange = (id: string, value: string) => {
    setSpecNotes((prev) => ({ ...prev, [id]: value }));
  };

  // ============================================================
  // SUCCESS SCREEN
  // ============================================================
  if (reference) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <Check className="mx-auto h-14 w-14 text-green-500" />
        <h1 className="mt-4 text-3xl font-extrabold text-foreground">
          Quotation request sent
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Free and no-obligation. We'll come back to you with pricing within 24
          hours.
        </p>
        {emailSent && (
          <p className="mt-1 text-xs text-green-600">
            ✓ Your email client has been opened. Please send the email to
            complete your quote request.
          </p>
        )}
        <div className="mx-auto mt-6 w-fit rounded-2xl border border-border bg-card px-6 py-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Your quote reference
          </p>
          <p className="text-2xl font-extrabold text-foreground">
            {reference}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Keep this — use it with your email to track the quote.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {/* --- FIXED: Copy ONLY the reference --- */}
          <button
            onClick={handleCopyReference}
            className={`h-12 rounded-xl px-6 text-sm font-semibold transition-colors inline-flex items-center gap-2 ${
              copySuccess
                ? "bg-green-500 text-white"
                : "border border-border bg-background text-foreground hover:bg-muted"
            }`}
          >
            {copySuccess ? (
              <>
                <CheckCircle2 className="h-4 w-4" /> Copied!
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" /> Copy reference
              </>
            )}
          </button>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              if (onClose) onClose();
              if (onNavigate) {
                onNavigate("track-quote");
              }
            }}
            className="h-12 rounded-xl bg-[#839705] px-6 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors"
          >
            Track this quote
          </button>

          <button
            onClick={() => {
              if (onClose) onClose();
              if (onNavigateToStore) {
                onNavigateToStore();
              } else {
                window.location.href = "/";
              }
            }}
            className="h-12 rounded-xl border border-border bg-background px-6 text-sm font-medium text-foreground hover:bg-muted transition-colors"
          >
            Back to the store
          </button>
        </div>
      </div>
    );
  }

  // ============================================================
  // EMPTY STATE
  // ============================================================
  const renderEmptyCart = () => (
    <div className="rounded-2xl border-2 border-dashed border-border bg-card p-12 text-center shadow-sm">
      <div className="mx-auto w-20 h-20 rounded-full bg-muted flex items-center justify-center mb-4">
        <FileText className="h-10 w-10 text-muted-foreground" />
      </div>
      <h3 className="text-xl font-bold text-foreground">No items selected</h3>
      <p className="mt-2 text-muted-foreground max-w-md mx-auto">
        You haven't added any items to your quote request yet. Browse our
        products or refurbished devices to get started.
      </p>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button
          onClick={handleBrowseStore}
          className="rounded-xl bg-[#839705] px-6 py-3 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center gap-2"
        >
          <ShoppingCart className="h-4 w-4" />
          Go to Products
        </button>
        <button
          onClick={() => {
            if (onNavigateToStore) onNavigateToStore();
            if (onClose) onClose();
            window.location.href = "/refurbished";
          }}
          className="rounded-xl border border-border bg-background px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
        >
          <RotateCcw className="h-4 w-4" />
          Go to Refurbished
        </button>
        <button
          onClick={() => {
            if (onClose) onClose();
          }}
          className="rounded-xl border border-border bg-background px-6 py-3 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
            Request your quote
          </h1>
          {quote.length > 0 && (
            <p className="mt-1 text-sm text-muted-foreground">
              {quote.length} {quote.length === 1 ? "item" : "items"} selected
            </p>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted transition-colors"
          >
            ✕
          </button>
        )}
      </div>

      {apiError && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
          <p className="font-semibold">Error:</p>
          <p>{apiError}</p>
          <button
            onClick={() => setApiError(null)}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {quote.length > 0 && (
        <>
          <p className="mt-2 text-muted-foreground">
            Step {step} of 3 · takes about 30 seconds.
          </p>
          <div className="mt-4 flex gap-2" aria-hidden>
            {[1, 2, 3].map((s) => (
              <span
                key={s}
                className={`h-1.5 flex-1 rounded-full ${
                  s <= step ? "bg-primary" : "bg-muted"
                }`}
              />
            ))}
          </div>
        </>
      )}

      {step === 1 && (
        <section className="mt-8 space-y-4">
          {quote.length === 0 ? (
            renderEmptyCart()
          ) : (
            <>
              <h2 className="text-lg font-bold text-foreground">
                What do you need quoted?
              </h2>
              {quote.map((item) => {
                const product = productById(item.id);
                return (
                  <article
                    key={item.id}
                    className="rounded-2xl border border-border bg-card p-4"
                  >
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
                      <div className="min-w-0">
                        <h3 className="text-sm font-bold leading-snug text-foreground">
                          {item.name}
                        </h3>
                        {product?.specs && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {product.specs.slice(0, 4).map((spec) => (
                              <span
                                key={spec}
                                className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
                              >
                                {spec}
                              </span>
                            ))}
                          </div>
                        )}
                        <p className="mt-1.5 text-xs text-muted-foreground">
                          {product?.price
                            ? `R ${product.price.toLocaleString()}`
                            : "Price on request"}
                          {product?.warranty && ` · ${product.warranty}`}
                        </p>
                      </div>
                      <button
                        type="button"
                        aria-label={`Remove ${item.name}`}
                        onClick={() => {
                          removeFromQuote(item.id);
                          setSpecNotes((prev) => {
                            const newNotes = { ...prev };
                            delete newNotes[item.id];
                            return newNotes;
                          });
                        }}
                        className="shrink-0 rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-destructive transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <div className="flex items-center rounded-lg border border-border">
                        <button
                          type="button"
                          aria-label="Decrease quantity"
                          onClick={() => setQuoteQty(item.id, item.qty - 1)}
                          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Minus className="h-4 w-4" />
                        </button>
                        <span className="w-10 text-center text-sm font-semibold text-foreground">
                          {item.qty}
                        </span>
                        <button
                          type="button"
                          aria-label="Increase quantity"
                          onClick={() => setQuoteQty(item.id, item.qty + 1)}
                          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>

                      <input
                        type="text"
                        value={specNotes[item.id] || ""}
                        onChange={(e) =>
                          handleSpecChange(item.id, e.target.value)
                        }
                        placeholder="Add specifications, condition or timeline (optional)"
                        className="h-10 flex-1 min-w-[200px] rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      />
                    </div>
                  </article>
                );
              })}

              <div className="flex flex-wrap gap-3 pt-2">
                <button
                  onClick={handleBrowseStore}
                  className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
                >
                  <ShoppingCart className="h-4 w-4" />
                  Add more items
                </button>
                <button
                  onClick={() => {
                    clearQuote();
                    setSpecNotes({});
                  }}
                  className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
                >
                  Clear all
                </button>
                <button
                  onClick={() => setStep(2)}
                  disabled={quote.length === 0}
                  className="rounded-xl bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-2 ml-auto"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {step === 2 && (
        <section className="mt-8">
          <h2 className="text-lg font-bold text-foreground">
            Where should we send the quote?
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            We'll open your email client so you can send the quote request
            directly.
          </p>
          <form
            className="mt-4 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <div>
              <label htmlFor="fullName" className="text-sm font-medium text-foreground">
                Full name *
              </label>
              <input
                id="fullName"
                type="text"
                value={details.fullName}
                onChange={(e) => field("fullName", e.target.value)}
                placeholder="Thandi Mokoena"
                className={`mt-1.5 h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                  errors.fullName ? "border-destructive" : "border-border"
                }`}
                autoComplete="name"
              />
              {errors.fullName && (
                <p className="mt-1 text-xs text-destructive">
                  {errors.fullName}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="cellphone" className="text-sm font-medium text-foreground">
                Cellphone (WhatsApp) *
              </label>
              <input
                id="cellphone"
                type="tel"
                value={details.cellphone}
                onChange={(e) => field("cellphone", e.target.value)}
                placeholder="082 123 4567"
                className={`mt-1.5 h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                  errors.cellphone ? "border-destructive" : "border-border"
                }`}
                autoComplete="tel"
              />
              {errors.cellphone && (
                <p className="mt-1 text-xs text-destructive">
                  {errors.cellphone}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                Email *
              </label>
              <input
                id="email"
                type="email"
                value={details.email}
                onChange={(e) => field("email", e.target.value)}
                placeholder="you@company.co.za"
                className={`mt-1.5 h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                  errors.email ? "border-destructive" : "border-border"
                }`}
                autoComplete="email"
              />
              {errors.email && (
                <p className="mt-1 text-xs text-destructive">{errors.email}</p>
              )}
            </div>

            <div>
              <label htmlFor="company" className="text-sm font-medium text-foreground">
                Company (optional)
              </label>
              <input
                id="company"
                type="text"
                value={details.company ?? ""}
                onChange={(e) => field("company", e.target.value)}
                className={`mt-1.5 h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                  errors.company ? "border-destructive" : "border-border"
                }`}
                autoComplete="organization"
              />
              {errors.company && (
                <p className="mt-1 text-xs text-destructive">
                  {errors.company}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="message"
                className="text-sm font-medium text-foreground flex items-center gap-2"
              >
                <Info className="h-4 w-4 text-[#839705]" />
                Anything else we should know?
              </label>
              <p className="text-xs text-muted-foreground mt-0.5">
                Let us know about your timeline, delivery preferences, budget
                range, or any special requirements.
              </p>
              <textarea
                id="message"
                value={details.message ?? ""}
                onChange={(e) => field("message", e.target.value)}
                placeholder="e.g., Need delivery by end of month, prefer Dell over HP, budget is around R50,000..."
                className={`mt-1.5 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
                  errors.message ? "border-destructive" : "border-border"
                }`}
                rows={4}
              />
              {errors.message && (
                <p className="mt-1 text-xs text-destructive">
                  {errors.message}
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="rounded-xl border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2"
              >
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
              <button
                type="submit"
                disabled={isSending}
                className="rounded-xl bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-2 flex-1 sm:flex-none justify-center"
              >
                <Mail className="h-5 w-5" />
                {isSending ? "Opening email..." : "Open email client"}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Your quote will be saved with a reference number. We'll open your
              email client so you can send the request.
            </p>
          </form>
        </section>
      )}
    </div>
  );
}
