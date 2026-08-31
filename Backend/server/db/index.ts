// server/db/index.ts
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Product from '../models/Product.js';
import Service from '../models/Service.js';
import CatalogItem from '../models/CatalogItem.js';
import Order from '../models/Order.js';
import Quote from '../models/Quote.js';

// Load environment variables
dotenv.config();

const MONGODB_URI = process.env.MONGODB_URI || 'MONGODB_URI=mongodb+srv://siyandankosideveloper_db_user:EjWpFrL50jYq5Zdr@untangled-nexus.j0fmkag.mongodb.net/?retryWrites=true&w=majority&appName=untangled-nexus';

export async function connectDB() {
  try {
    console.log('📡 Connecting to MongoDB...');
    
    const logUri = MONGODB_URI.replace(/\/\/.*@/, '//<credentials>@');
    console.log(`🔗 URI: ${logUri}`);
    
    // FIX: Add SSL options to handle the SSL error
    await mongoose.connect(MONGODB_URI, {
      // These options help with SSL/TLS issues
      tls: true,
      tlsAllowInvalidCertificates: true, // For development only
      tlsAllowInvalidHostnames: true, // For development only
      serverSelectionTimeoutMS: 30000,
      socketTimeoutMS: 45000,
    });
    
    console.log('✅ MongoDB connected successfully');
    console.log(`📊 Database: ${mongoose.connection.name}`);
    console.log(`🔗 Host: ${mongoose.connection.host}`);
    
    // Check if we need to seed
    await checkAndSeed();
    
    return mongoose.connection;
  } catch (error) {
    console.error('❌ MongoDB connection error:', error);
    throw error;
  }
}

async function checkAndSeed() {
  try {
    const productCount = await Product.countDocuments();
    
    if (productCount === 0) {
      console.log('🌱 No products found. You may need to seed the database.');
      console.log('💡 Run: npm run seed');
    }
  } catch (error) {
    console.error('❌ Error checking database:', error);
  }
}

mongoose.connection.on('connected', () => {
  console.log('🔗 Mongoose connected to MongoDB');
});

mongoose.connection.on('error', (err) => {
  console.error('❌ Mongoose connection error:', err);
});

mongoose.connection.on('disconnected', () => {
  console.log('🔌 Mongoose disconnected from MongoDB');
});

process.on('SIGINT', async () => {
  await mongoose.connection.close();
  console.log('🔌 MongoDB connection closed through app termination');
  process.exit(0);
});

// ============================================
// EXPORT ALL MODELS
// ============================================
export default mongoose;
export { 
  Product, 
  Service, 
  CatalogItem, 
  Order, 
  Quote 
};

export { default as QuoteMessage } from "../models/QuoteMessage";
export { default as OrderMessage } from "../models/OrderMessage";