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
  status: 'received' | 'in_review' | 'quoted' | 'closed' | 'pending' | 'waiting_feedback' | 'in_touch' | 'approved' | 'payment';
  replyMessage?: string;
  repliedAt?: Date;
  createdAt: Date;
  updatedAt: Date;
  // New fields for payment
  paymentRequired?: boolean;
  paymentAmount?: number;
  paymentStatus?: 'pending' | 'paid' | 'failed';
  paymentReference?: string;
  // New fields for feedback
  feedback?: {
    rating?: number;
    comment?: string;
    submitted?: boolean;
    submittedAt?: Date;
  };
}

const QuoteSchema = new Schema<IQuote>(
  {
    reference: { type: String, required: true, unique: true },
    customerName: { type: String, required: true },
    company: { type: String },
    email: { type: String, required: true },
    phone: { type: String, required: true },
    notes: { type: String },
    items: [{
      id: { type: String, required: true },
      name: { type: String, required: true },
      kind: { type: String, enum: ['product', 'service'], required: true },
      qty: { type: Number, required: true, min: 1 },
    }],
    status: { 
      type: String, 
      enum: ['received', 'in_review', 'quoted', 'closed', 'pending', 'waiting_feedback', 'in_touch', 'approved', 'payment'],
      default: 'received'
    },
    replyMessage: { type: String },
    repliedAt: { type: Date },
    // Payment fields
    paymentRequired: { type: Boolean, default: false },
    paymentAmount: { type: Number },
    paymentStatus: { 
      type: String, 
      enum: ['pending', 'paid', 'failed'],
      default: 'pending'
    },
    paymentReference: { type: String },
    // Feedback fields
    feedback: {
      rating: { type: Number, min: 1, max: 5 },
      comment: { type: String },
      submitted: { type: Boolean, default: false },
      submittedAt: { type: Date }
    }
  },
  {
    timestamps: true,
  }
);

// Compound index for tracking
QuoteSchema.index({ reference: 1, email: 1 });

const Quote = mongoose.model<IQuote>('Quote', QuoteSchema);
export default Quote;