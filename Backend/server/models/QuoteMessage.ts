import mongoose, { Schema, Document } from "mongoose";

export interface IQuoteMessage extends Document {
  quoteReference: string;
  senderType: "client" | "employee" | "assigner";
  senderName: string;
  recipientType: "client" | "employee" | "assigner";
  message: string;
  read: boolean;
  createdAt: Date;
}

const QuoteMessageSchema = new Schema<IQuoteMessage>({
  quoteReference: { type: String, index: true, required: true },
  senderType: {
    type: String,
    enum: ["client", "employee", "assigner"],
    required: true
  },
  senderName: String,
  recipientType: {
    type: String,
    enum: ["client", "employee", "assigner"],
    required: true
  },
  message: { type: String, required: true },
  read: { type: Boolean, default: false }
}, { timestamps: { createdAt: true, updatedAt: false } });

export default mongoose.models.QuoteMessage ||
mongoose.model<IQuoteMessage>("QuoteMessage", QuoteMessageSchema);