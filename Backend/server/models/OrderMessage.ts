import mongoose, { Schema, Document } from "mongoose";

export interface IOrderMessage extends Document {
  orderReference: string;
  senderType: "client" | "employee" | "assigner";
  senderName: string;
  recipientType: "client" | "employee" | "assigner";
  message: string;
  read: boolean;
  createdAt: Date;
}

const OrderMessageSchema = new Schema<IOrderMessage>({
  orderReference: { type: String, required: true, index: true },
  senderType: String,
  senderName: String,
  recipientType: String,
  message: String,
  read: { type: Boolean, default: false }
},{timestamps:{createdAt:true,updatedAt:false}});

export default mongoose.models.OrderMessage ||
mongoose.model<IOrderMessage>("OrderMessage",OrderMessageSchema);