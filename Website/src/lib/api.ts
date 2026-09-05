// src/lib/api.ts
// API client aligned with the professional quote workflow:
// Pending → Assigned → Awaiting Details → Quoted → Awaiting Client Approval
// → Awaiting Payment → Paid → In Progress → Out for Delivery → Completed

// Default /api → Vite dev proxy forwards to Render (no browser CORS)
const _raw = (import.meta.env.VITE_API_URL ?? "/api").toString().trim();
const API_BASE_URL = (_raw || "/api").replace(/\/$/, "");

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({} as Record<string, unknown>));
    const message =
      (typeof error === "object" && error && (error as any).message) ||
      (typeof error === "object" && error && (error as any).error) ||
      `Request failed (${response.status})`;
    throw new Error(String(message));
  }
  return response.json();
}

export function connectionErrorMessage(err: unknown): string {
  if (err instanceof TypeError) {
    return (
      "Cannot connect to the API. If using direct Render URL, CORS must allow this origin. " +
      "Prefer VITE_API_URL=/api with the Vite proxy in dev."
    );
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong talking to the server.";
}

// ============================================
// Quote status — professional + legacy values
// ============================================

/** Backend / Mongo status codes */
export type QuoteStatusCode =
  | "received"
  | "pending"
  | "assigned"
  | "awaiting_details"
  | "quoted"
  | "awaiting_client_approval"
  | "awaiting_client" // legacy
  | "awaiting_payment"
  | "paid"
  | "in_progress"
  | "out_for_delivery"
  | "completed"
  | "returned"
  | "in_review"
  | "accepted"
  | "closed"
  | "waiting_feedback"
  | "in_touch"
  | "approved"
  | "payment";

/** Human-readable labels for the track page */
export const QUOTE_STATUS_LABELS: Record<string, string> = {
  received: "Received",
  pending: "Pending",
  assigned: "Assigned",
  awaiting_details: "Awaiting Details",
  quoted: "Quoted",
  awaiting_client_approval: "Awaiting Your Approval",
  awaiting_client: "Awaiting Your Approval",
  awaiting_payment: "Awaiting Payment",
  paid: "Paid",
  in_progress: "In Progress",
  out_for_delivery: "Out for Delivery",
  completed: "Completed",
  returned: "Returned",
  in_review: "In Review",
  accepted: "Accepted",
  closed: "Closed",
  waiting_feedback: "Waiting for Feedback",
  in_touch: "In Touch",
  approved: "Approved",
  payment: "Payment",
};

export function formatQuoteStatus(status: string | undefined | null): string {
  if (!status) return "Pending";
  return QUOTE_STATUS_LABELS[status] || status.replace(/_/g, " ");
}

// ============================================
// 1. QUOTE API
// ============================================

export interface SubmitQuotePayload {
  customerName: string;
  company?: string;
  email: string;
  phone: string;
  notes?: string;
  /** Delivery / site address */
  address?: string;
  delivery_address?: string;
  delivery_date?: string;
  preferred_delivery_date?: string;
  site_notes?: string;
  items: Array<{
    id: string;
    name: string;
    kind: "product" | "service";
    qty: number;
    image?: string | null;
    price?: number | null;
    specs?: string[];
    note?: string;
  }>;
  status?: string;
}

export interface SubmitQuoteResponse {
  success: boolean;
  reference: string;
  error?: string;
}

export async function submitQuote(
  payload: SubmitQuotePayload
): Promise<SubmitQuoteResponse> {
  console.log("📤 Submitting quote to:", `${API_BASE_URL}/quotes`);
  const response = await fetch(`${API_BASE_URL}/quotes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SubmitQuoteResponse>(response);
}

// ============================================
// 2. TRACK QUOTE API
// ============================================

export interface TrackedQuoteItem {
  id: string;
  name: string;
  qty: number;
  image?: string;
  kind?: "product" | "service";
  price?: number | null;
  specs?: string[];
  note?: string;
}

export interface TrackedQuoteDelivery {
  address?: string;
  date?: string;
  driver?: string;
  status?: string;
}

export interface TrackedQuote {
  id: string;
  reference: string;
  customerName: string;
  email: string;
  phone: string;
  company?: string;
  address?: string;
  delivery_address?: string;
  delivery_date?: string;
  preferred_delivery_date?: string;
  site_notes?: string;
  status: QuoteStatusCode | string;
  items: TrackedQuoteItem[];
  replyMessage: string | null;
  repliedAt: string | null;
  createdAt: string;
  updatedAt?: string;
  paymentRequired?: boolean;
  paymentAmount?: number;
  paymentStatus?: "pending" | "paid" | "failed";
  quotation_total?: number;
  total?: number;
  delivery?: TrackedQuoteDelivery;
  feedback?: {
    rating?: number;
    comment?: string;
    submitted?: boolean;
  };
}

export async function trackQuote(
  reference: string,
  email: string
): Promise<{ success: boolean; quote: TrackedQuote | null }> {
  const url = `${API_BASE_URL}/quotes/track?ref=${encodeURIComponent(
    reference
  )}&email=${encodeURIComponent(email)}`;
  console.log("🔍 Track URL:", url);

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });

  console.log("📥 Track response status:", response.status);
  const result = await handleResponse<{
    success: boolean;
    quote: TrackedQuote | null;
  }>(response);
  console.log("📥 Track result:", result);
  return result;
}

// ============================================
// 3. FEEDBACK API
// ============================================

export interface FeedbackResponse {
  success: boolean;
  message: string;
  quote?: TrackedQuote;
}

export async function submitFeedback(
  reference: string,
  email: string,
  feedback: { rating: number; comment: string }
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/quotes/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reference, email, feedback }),
  });
  return handleResponse<FeedbackResponse>(response);
}

// ============================================
// 4. PAYMENT API
// ============================================

export interface PaymentResponse {
  success: boolean;
  message: string;
  paymentUrl?: string;
  quote?: TrackedQuote;
}

export async function initiatePayment(
  reference: string,
  email: string
): Promise<PaymentResponse> {
  const response = await fetch(`${API_BASE_URL}/quotes/payment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reference, email }),
  });
  return handleResponse<PaymentResponse>(response);
}

// ============================================
// 5. ORDER / CHECKOUT API
// ============================================

export interface SubmitOrderPayload {
  customerName: string;
  company?: string;
  email: string;
  phone: string;
  address: string;
  notes?: string;
  items: Array<{
    id: string;
    name: string;
    qty: number;
    price: number;
  }>;
  total: number;
}

export interface SubmitOrderResponse {
  success: boolean;
  orderId: string;
  orderReference: string;
}

export async function submitOrder(
  payload: SubmitOrderPayload
): Promise<SubmitOrderResponse> {
  console.log("📤 Submitting order to:", `${API_BASE_URL}/orders`);
  const response = await fetch(`${API_BASE_URL}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SubmitOrderResponse>(response);
}

// ============================================
// 6. TRACK ORDER API
// ============================================

export interface TrackedOrder {
  reference: string;
  customerName: string;
  email: string;
  phone: string;
  address: string;
  notes?: string;
  status:
    | "pending"
    | "confirmed"
    | "processing"
    | "shipped"
    | "delivered"
    | "cancelled";
  items: Array<{
    id: string;
    name: string;
    qty: number;
    price: number;
  }>;
  total: number;
  createdAt: string;
  updatedAt: string;
  estimatedDelivery?: string;
  trackingNumber?: string;
  carrier?: string;
}

export async function trackOrder(
  reference: string,
  email: string
): Promise<{ success: boolean; order: TrackedOrder | null; error?: string }> {
  const url = `${API_BASE_URL}/orders/track?ref=${encodeURIComponent(
    reference
  )}&email=${encodeURIComponent(email)}`;
  console.log("🔍 Tracking order URL:", url);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
    });

    console.log("📥 Response status:", response.status);
    const result = await response.json();
    console.log("📥 Track result:", result);
    return result;
  } catch (error) {
    console.error("❌ Track error:", error);
    return {
      success: false,
      order: null,
      error: error instanceof Error ? error.message : "Failed to track order",
    };
  }
}

// ============================================
// 7. ORDER STATUS UPDATE (Admin)
// ============================================

export interface UpdateOrderStatusPayload {
  reference: string;
  status: TrackedOrder["status"];
  trackingNumber?: string;
  carrier?: string;
  estimatedDelivery?: string;
}

export async function updateOrderStatus(
  payload: UpdateOrderStatusPayload
): Promise<{ success: boolean; order: TrackedOrder }> {
  const response = await fetch(`${API_BASE_URL}/orders/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<{ success: boolean; order: TrackedOrder }>(response);
}

// ============================================
// 8. GET USER ORDERS
// ============================================

export async function getUserOrders(
  email: string
): Promise<{ success: boolean; orders: TrackedOrder[] }> {
  const url = `${API_BASE_URL}/orders/user?email=${encodeURIComponent(email)}`;
  console.log("📋 Fetching user orders:", url);

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });

  return handleResponse<{ success: boolean; orders: TrackedOrder[] }>(
    response
  );
}

// ============================================
// 9. HEALTH CHECK
// ============================================

export async function checkHealth(): Promise<{
  status: string;
  database: { connected: boolean };
}> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  return handleResponse<{ status: string; database: { connected: boolean } }>(
    response
  );
}