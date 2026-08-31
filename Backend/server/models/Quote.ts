// server/models/Quote.ts

import mongoose, { Schema, Document } from 'mongoose';

export interface IQuote extends Document {
  reference: string;
  customerName: string;
  company?: string;
  email: string;
  phone: string;
  notes?: string;

  items: Array<{
    id: string;
    name: string;
    kind: 'product' | 'service';
    qty: number;
  }>;

  status:
    | 'received'
    | 'in_review'
    | 'quoted'
    | 'closed'
    | 'pending'
    | 'waiting_feedback'
    | 'in_touch'
    | 'approved'
    | 'payment'
    | 'assigned'
    | 'awaiting_client'
    | 'awaiting_payment'
    | 'completed';

  replyMessage?: string;
  repliedAt?: Date;

  createdAt: Date;
  updatedAt: Date;

  // Payment
  paymentRequired?: boolean;
  paymentAmount?: number;
  paymentStatus?: 'pending' | 'paid' | 'failed';
  paymentReference?: string;
  paymentReady?: boolean;

  // Assignment
  assigned_to?: string | null;
  assigned_name?: string | null;
  assigned_by?: string | null;
  assigned_at?: Date | null;

  // Missing client information
  missing_details?: string[];

  // Client feedback
  feedback?: {
    rating?: number;
    comment?: string;
    submitted?: boolean;
    submittedAt?: Date;
  };
}

const QuoteSchema = new Schema<IQuote>(
  {
    reference: {
      type: String,
      required: true,
      unique: true,
      index: true,
    },

    customerName: {
      type: String,
      required: true,
    },

    company: String,

    email: {
      type: String,
      required: true,
      index: true,
    },

    phone: {
      type: String,
      required: true,
    },

    notes: String,

    items: [
      {
        id: {
          type: String,
          required: true,
        },
        name: {
          type: String,
          required: true,
        },
        kind: {
          type: String,
          enum: ['product', 'service'],
          required: true,
        },
        qty: {
          type: Number,
          required: true,
          min: 1,
        },
      },
    ],

    status: {
      type: String,
      enum: [
        'received',
        'in_review',
        'quoted',
        'closed',
        'pending',
        'waiting_feedback',
        'in_touch',
        'approved',
        'payment',
        'assigned',
        'awaiting_client',
        'awaiting_payment',
        'completed',
      ],
      default: 'received',
    },

    replyMessage: String,

    repliedAt: Date,

    // -------------------------
    // Assignment
    // -------------------------
    assigned_to: {
      type: String,
      default: null,
      index: true,
    },

    assigned_name: {
      type: String,
      default: null,
    },

    assigned_by: {
      type: String,
      default: null,
    },

    assigned_at: {
      type: Date,
      default: null,
    },

    // -------------------------
    // Missing client details
    // -------------------------
    missing_details: {
      type: [String],
      default: [],
    },

    // -------------------------
    // Payment
    // -------------------------
    paymentRequired: {
      type: Boolean,
      default: false,
    },

    paymentAmount: Number,

    paymentStatus: {
      type: String,
      enum: ['pending', 'paid', 'failed'],
      default: 'pending',
    },

    paymentReference: String,

    paymentReady: {
      type: Boolean,
      default: false,
    },

    // -------------------------
    // Customer feedback
    // -------------------------
    feedback: {
      rating: {
        type: Number,
        min: 1,
        max: 5,
      },

      comment: String,

      submitted: {
        type: Boolean,
        default: false,
      },

      submittedAt: Date,
    },
  },
  {
    timestamps: true,
  }
);

// Tracking index
QuoteSchema.index({ reference: 1, email: 1 });

// Employee assignment index
QuoteSchema.index({ assigned_to: 1, status: 1 });

const Quote =
  mongoose.models.Quote ||
  mongoose.model<IQuote>('Quote', QuoteSchema);

export default Quote;