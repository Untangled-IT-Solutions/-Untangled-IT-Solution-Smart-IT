import mongoose, { Schema, Document } from 'mongoose';

export interface IService extends Document {
  id: string;
  name: string;
  description: string;
  group: 'software' | 'support' | 'solutions';
  createdAt: Date;
  updatedAt: Date;
}

const ServiceSchema = new Schema<IService>(
  {
    id: { type: String, required: true, unique: true },
    name: { type: String, required: true },
    description: { type: String, required: true },
    group: { 
      type: String, 
      enum: ['software', 'support', 'solutions'], 
      required: true 
    },
  },
  {
    timestamps: true,
  }
);

ServiceSchema.index({ name: 'text', description: 'text' });

const Service = mongoose.model<IService>('Service', ServiceSchema);
export default Service;