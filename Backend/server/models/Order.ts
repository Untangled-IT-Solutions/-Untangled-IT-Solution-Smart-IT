// server/models/Order.ts

import mongoose, { Schema, Document } from 'mongoose';

export interface IOrder extends Document {
  reference: string;

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

  status:
    | 'pending'
    | 'confirmed'
    | 'processing'
    | 'assigned'
    | 'awaiting_client'
    | 'awaiting_payment'
    | 'ready_for_collection'
    | 'shipped'
    | 'delivered'
    | 'completed'
    | 'cancelled';

  trackingNumber?: string;
  carrier?: string;
  estimatedDelivery?: Date;

  // Assignment
  assigned_to?: string | null;
  assigned_name?: string | null;
  assigned_by?: string | null;
  assigned_at?: Date | null;

  // Client information requests
  missing_details?: string[];

  // Employee workflow
  stockAvailable?: boolean;
  paymentReady?: boolean;

  createdAt: Date;
  updatedAt: Date;
}

const OrderSchema = new Schema<IOrder>(
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

    address: {
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
        qty: {
          type: Number,
          required: true,
          min: 1,
        },
        price: {
          type: Number,
          required: true,
          min: 0,
        },
      },
    ],

    total: {
      type: Number,
      required: true,
      min: 0,
    },

    status: {
      type: String,
      enum: [
        'pending',
        'confirmed',
        'processing',
        'assigned',
        'awaiting_client',
        'awaiting_payment',
        'ready_for_collection',
        'shipped',
        'delivered',
        'completed',
        'cancelled',
      ],
      default: 'pending',
    },

    trackingNumber: String,

    carrier: String,

    estimatedDelivery: Date,

    // -------------------------
    // Employee Assignment
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
    // Internal workflow
    // -------------------------
    stockAvailable: {
      type: Boolean,
      default: false,
    },

    paymentReady: {
      type: Boolean,
      default: false,
    },
  },
  {
    timestamps: true,
  }
);

// Generate reference before saving
OrderSchema.pre('save', function (next) {
  if (!this.reference) {
    const timestamp = Date.now().toString(36).toUpperCase();
    const random = Math.random().toString(36).substring(2, 6).toUpperCase();
    this.reference = `ORD-${timestamp}-${random}`;
  }
  next();
});

// Indexes
OrderSchema.index({ reference: 1, email: 1 });
OrderSchema.index({ assigned_to: 1, status: 1 });

const Order =
  mongoose.models.Order ||
  mongoose.model<IOrder>('Order', OrderSchema);

export default Order;