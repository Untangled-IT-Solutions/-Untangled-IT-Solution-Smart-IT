// Backend/server/index-working-v2.ts
import { createServer } from 'node:http';
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import crypto from 'node:crypto';
import { randomUUID } from 'node:crypto';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { ensureInMemoryDesktopDb } from './memoryDesktopDb.js';

// Load environment variables
dotenv.config();

// ============================================
// CONFIGURATION - ALL FROM ENV VARIABLES
// ============================================

const config = {
  port: parseInt(process.env.PORT || '5001'),
  mongoUri: process.env.MONGODB_URI || 'mongodb://localhost:27017/untangled_its',
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:5173',
  nodeEnv: process.env.NODE_ENV || 'development',
};

console.log('📋 Configuration:');
console.log(`   PORT: ${config.port}`);
const maskedUri = config.mongoUri ? config.mongoUri.replace(/\/\/.*@/, '//<credentials>@') : 'undefined';
console.log(`   MONGODB_URI: ${maskedUri}`);
console.log(`   FRONTEND_URL: ${config.frontendUrl}`);
console.log(`   NODE_ENV: ${config.nodeEnv}`);

// ============================================
// MONGODB MODELS
// ============================================

const quoteSchema = new mongoose.Schema({
  reference: { type: String, unique: true, required: true },
  customerName: { type: String, required: true },
  company: String,
  email: { type: String, required: true },
  phone: { type: String, required: true },
  notes: String,
  items: [{
    id: String,
    name: String,
    kind: String,
    qty: Number,
    image: String
  }],
  status: { 
    type: String, 
    enum: ['received', 'in_review', 'quoted', 'closed', 'pending', 'waiting_feedback', 'in_touch', 'approved', 'payment', 'assigned', 'accepted', 'in_progress', 'awaiting_client', 'awaiting_payment', 'paid', 'completed', 'returned'],
    default: 'received'
  },
  replyMessage: String,
  repliedAt: Date,
  createdAt: { type: Date, default: Date.now },
  paymentRequired: { type: Boolean, default: false },
  paymentAmount: { type: Number },
  paymentStatus: { 
    type: String, 
    enum: ['pending', 'paid', 'failed'],
    default: 'pending'
  },
  paymentReference: { type: String },
  assigned_to: { type: mongoose.Schema.Types.Mixed, default: null },
  assigned_by: { type: mongoose.Schema.Types.Mixed, default: null },
  feedback: {
    rating: { type: Number, min: 1, max: 5 },
    comment: { type: String },
    submitted: { type: Boolean, default: false },
    submittedAt: { type: Date }
  }
});

// ✅ FIXED: Removed orderId - using reference as unique identifier
const orderSchema = new mongoose.Schema({
  reference: { type: String, unique: true, required: true, index: true },
  customerName: { type: String, required: true },
  company: String,
  email: { type: String, required: true, index: true },
  phone: { type: String, required: true },
  address: { type: String, required: true },
  notes: String,
  items: [{
    id: String,
    name: String,
    qty: Number,
    price: Number
  }],
  total: { type: Number, required: true },
  status: { 
    type: String, 
    enum: ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'],
    default: 'pending'
  },
  trackingNumber: String,
  carrier: String,
  estimatedDelivery: Date,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now },
  assigned_to: { type: mongoose.Schema.Types.Mixed, default: null },
  assigned_by: { type: mongoose.Schema.Types.Mixed, default: null }
});

// Create models
const Quote = mongoose.models.Quote || mongoose.model('Quote', quoteSchema);
const Order = mongoose.models.Order || mongoose.model('Order', orderSchema);

// ============================================
// CONNECT TO MONGODB
// ============================================

let isMongoConnected = false;

async function connectDB() {
  try {
    console.log('📡 Connecting to MongoDB...');
    
    if (!config.mongoUri) {
      console.error('❌ MONGODB_URI is not defined in environment variables');
      console.log('⚠️ Falling back to in-memory storage...');
      isMongoConnected = false;
      return false;
    }
    
    const maskedUri = config.mongoUri.replace(/\/\/.*@/, '//<credentials>@');
    console.log(`🔗 Using URI: ${maskedUri}`);
    
    const mongoOptions: any = {
      serverSelectionTimeoutMS: 8000,
      socketTimeoutMS: 10000,
      tls: true,
      tlsAllowInvalidCertificates: false,
      tlsAllowInvalidHostnames: false,
    };

    console.log('🔧 Connection options:', {
      tls: mongoOptions.tls,
      tlsAllowInvalidCertificates: mongoOptions.tlsAllowInvalidCertificates,
      tlsAllowInvalidHostnames: mongoOptions.tlsAllowInvalidHostnames,
      serverSelectionTimeoutMS: mongoOptions.serverSelectionTimeoutMS,
    });

    await mongoose.connect(config.mongoUri, mongoOptions);
    
    isMongoConnected = true;
    console.log('✅ MongoDB connected successfully');
    console.log(`📊 Database: ${mongoose.connection.name}`);
    console.log(`🔗 Host: ${mongoose.connection.host}`);
    
    return true;
  } catch (error) {
    console.error('❌ MongoDB connection error:', error);
    if (error instanceof Error) {
      console.error(`🔍 Error details: ${error.message}`);
    }
    console.log('⚠️ Falling back to in-memory storage...');
    isMongoConnected = false;
    return false;
  }
}

// ============================================
// CREATE APP
// ============================================

const app = createApp();

// CORS middleware
app.use(eventHandler(async (event) => {
  const origin = event.node.req.headers.origin || '';
  const allowedOrigins = [config.frontendUrl, 'http://localhost:5173', 'http://localhost:5174'];
  
  if (allowedOrigins.includes(origin) || config.nodeEnv === 'development') {
    event.node.res.setHeader('Access-Control-Allow-Origin', origin || '*');
  }
  
  event.node.res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  event.node.res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  event.node.res.setHeader('Access-Control-Allow-Credentials', 'true');
  
  if (event.method === 'OPTIONS') {
    event.node.res.statusCode = 200;
    event.node.res.end();
    return;
  }
}));

// Health check
app.use('/api/health', eventHandler(() => ({
  status: 'ok',
  timestamp: new Date().toISOString(),
  environment: config.nodeEnv,
  database: {
    connected: isMongoConnected,
    host: mongoose.connection.host || 'not connected',
    name: mongoose.connection.name || 'not connected'
  }
})));

// ============================================
// IN-MEMORY FALLBACK STORAGE
// ============================================

const inMemoryQuotes: any[] = [];
const inMemoryOrders: any[] = [];

// ============================================
// HELPERS
// ============================================

function generateReference(prefix: string = 'UQ'): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = `${prefix}-`;
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function generateOrderReference(): string {
  const timestamp = Date.now().toString(36).toUpperCase();
  const random = Math.random().toString(36).substring(2, 6).toUpperCase();
  return `ORD-${timestamp}-${random}`;
}

function extractPaymentAmount(replyMessage: string): number | null {
  if (!replyMessage) return null;
  
  const patterns = [
    /R\s*([\d,]+)/i,
    /pay\s*R\s*([\d,]+)/i,
    /amount\s*R\s*([\d,]+)/i,
    /total\s*R\s*([\d,]+)/i,
    /cost\s*R\s*([\d,]+)/i,
    /price\s*R\s*([\d,]+)/i,
    /payment\s*R\s*([\d,]+)/i
  ];
  
  for (const pattern of patterns) {
    const match = replyMessage.match(pattern);
    if (match) {
      const amount = parseFloat(match[1].replace(/,/g, ''));
      if (!isNaN(amount) && amount > 0) {
        return amount;
      }
    }
  }
  return null;
}

// ============================================
// TRACK QUOTE API - MUST COME FIRST BEFORE /api/quotes
// ============================================

app.use('/api/quotes/track', eventHandler(async (event) => {
  console.log(`🔍 Track quote request received: ${event.method}`);
  
  try {
    const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
    const ref = url.searchParams.get('ref');
    const email = url.searchParams.get('email');
    
    console.log(`🔍 ===== TRACK QUOTE REQUEST =====`);
    console.log(`🔍 Reference: ${ref}`);
    console.log(`🔍 Email: ${email}`);
    
    if (!ref || !email) {
      return {
        success: false,
        error: 'Reference and email are required',
        quote: null
      };
    }
    
    const cleanRef = ref.trim().toUpperCase();
    const cleanEmail = email.trim().toLowerCase();
    
    console.log(`🔍 Cleaned Reference: ${cleanRef}`);
    console.log(`🔍 Cleaned Email: ${cleanEmail}`);
    console.log(`🔍 MongoDB connected: ${isMongoConnected}`);
    
    let quote = null;
    
    if (isMongoConnected) {
      console.log(`🔍 Searching MongoDB for quote...`);
      quote = await Quote.findOne({ reference: cleanRef, email: cleanEmail });
      
      if (quote) {
        console.log(`✅ Found exact match: ${quote.reference}`);
      }
    }
    
    if (!quote) {
      quote = inMemoryQuotes.find(q => q.reference === cleanRef && q.email === cleanEmail);
      if (quote) {
        console.log(`✅ Found in-memory match: ${quote.reference}`);
      }
    }
    
    if (!quote) {
      console.log(`❌ Quote NOT FOUND: ${cleanRef} | ${cleanEmail}`);
      return {
        success: false,
        error: 'Quote not found. Check your reference and email.',
        quote: null
      };
    }
    
    console.log(`✅ ===== QUOTE FOUND =====`);
    console.log(`✅ Reference: ${quote.reference}`);
    console.log(`✅ Customer: ${quote.customerName}`);
    console.log(`✅ Status: ${quote.status}`);
    console.log(`✅ Items: ${quote.items.length}`);
    
    let paymentRequired = quote.paymentRequired || false;
    let paymentAmount = quote.paymentAmount || 0;
    
    if (!paymentRequired && quote.replyMessage) {
      const extractedAmount = extractPaymentAmount(quote.replyMessage);
      if (extractedAmount) {
        paymentRequired = true;
        paymentAmount = extractedAmount;
        console.log(`💰 Auto-extracted payment amount: R${extractedAmount}`);
      }
    }
    
    return {
      success: true,
      quote: {
        id: quote._id?.toString() || `mem_${Date.now()}`,
        reference: quote.reference,
        customerName: quote.customerName,
        email: quote.email,
        phone: quote.phone,
        status: quote.status,
        items: quote.items.map((item: any) => ({
          id: item.id,
          name: item.name,
          qty: item.qty,
          image: item.image || null
        })),
        replyMessage: quote.replyMessage || null,
        repliedAt: quote.repliedAt || null,
        createdAt: quote.createdAt,
        paymentRequired: paymentRequired,
        paymentAmount: paymentAmount,
        paymentStatus: quote.paymentStatus || 'pending',
        feedback: quote.feedback || null
      }
    };
  } catch (error) {
    console.error('❌ Error tracking quote:', error);
    return {
      success: false,
      error: 'Failed to track quote',
      quote: null
    };
  }
}));

// ============================================
// QUOTES API - POST and GET
// ============================================

app.use('/api/quotes', eventHandler(async (event) => {
  console.log(`📋 Quotes request received: ${event.method}`);
  
  // Handle POST - Create quote
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Quote received:', JSON.stringify(body, null, 2));
      
      const { customerName, company, email, phone, notes, items } = body;
      
      if (!customerName || !email || !phone || !items || items.length === 0) {
        return { success: false, error: 'Missing required fields' };
      }
      
      const reference = generateReference('UQ');
      console.log(`🔑 Generated reference: ${reference}`);
      
      const quoteData = {
        reference,
        customerName,
        company: company || '',
        email: email.toLowerCase().trim(),
        phone,
        notes: notes || '',
        items: items.map((item: any) => ({
          id: item.id,
          name: item.name,
          kind: item.kind || 'product',
          qty: item.qty,
          image: item.image || null
        })),
        status: 'received',
        paymentRequired: false,
        paymentAmount: 0,
        paymentStatus: 'pending',
        feedback: { submitted: false }
      };
      
      let savedQuote;
      
      if (isMongoConnected) {
        try {
          const quote = new Quote(quoteData);
          savedQuote = await quote.save();
          console.log(`✅ Quote SAVED TO MONGODB with reference: ${reference}`);
        } catch (dbError) {
          console.error('❌ Failed to save to MongoDB:', dbError);
          savedQuote = { ...quoteData, _id: `mem_${Date.now()}` };
          inMemoryQuotes.push(savedQuote);
          console.log(`💾 Quote saved in-memory: ${reference}`);
        }
      } else {
        savedQuote = { ...quoteData, _id: `mem_${Date.now()}` };
        inMemoryQuotes.push(savedQuote);
        console.log(`💾 Quote saved in-memory: ${reference}`);
      }
      
      return { success: true, reference: savedQuote.reference };
    } catch (error) {
      console.error('❌ Error:', error);
      return { success: false, error: 'Failed to process quote' };
    }
  }
  
  // Handle GET - List all quotes
  if (event.method === 'GET') {
    try {
      let quotes = [];
      if (isMongoConnected) {
        quotes = await Quote.find({}).sort({ createdAt: -1 }).limit(50).lean();
        console.log(`📋 Found ${quotes.length} quotes in MongoDB`);
      } else {
        quotes = inMemoryQuotes;
        console.log(`📋 Found ${quotes.length} quotes in memory`);
      }
      
      return {
        success: true,
        count: quotes.length,
        quotes: quotes.map(q => ({
          reference: q.reference,
          customerName: q.customerName,
          email: q.email,
          status: q.status,
          createdAt: q.createdAt,
          items: q.items,
          paymentRequired: q.paymentRequired || false,
          paymentAmount: q.paymentAmount || 0,
          paymentStatus: q.paymentStatus || 'pending',
          feedback: q.feedback || { submitted: false },
          replyMessage: q.replyMessage || null,
          assigned_to: q.assigned_to || null,
          assigned_by: q.assigned_by || null
        }))
      };
    } catch (error) {
      console.error('❌ Error fetching quotes:', error);
      return { success: false, error: 'Failed to fetch quotes' };
    }
  }
  
  return { success: false, error: 'Method not allowed' };
}));

// ============================================
// TRACK ORDER API - MUST COME BEFORE /api/orders
// ============================================

app.use('/api/orders/track', eventHandler(async (event) => {
  console.log(`🔍 Track order request received: ${event.method}`);
  
  try {
    const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
    const ref = url.searchParams.get('ref');
    const email = url.searchParams.get('email');
    
    console.log(`🔍 ===== TRACK ORDER REQUEST =====`);
    console.log(`🔍 Method: ${event.method}`);
    console.log(`🔍 Reference: ${ref}`);
    console.log(`🔍 Email: ${email}`);
    
    if (!ref || !email) {
      return {
        success: false,
        error: 'Reference and email are required',
        order: null
      };
    }
    
    const cleanRef = ref.trim().toUpperCase();
    const cleanEmail = email.trim().toLowerCase();
    
    console.log(`🔍 Cleaned Reference: ${cleanRef}`);
    console.log(`🔍 Cleaned Email: ${cleanEmail}`);
    console.log(`🔍 MongoDB connected: ${isMongoConnected}`);
    
    let order = null;
    
    if (isMongoConnected) {
      console.log(`🔍 Searching MongoDB for order...`);
      
      order = await Order.findOne({ 
        reference: cleanRef, 
        email: cleanEmail 
      });
      
      if (order) {
        console.log(`✅ Found order: ${order.reference}`);
      }
      
      if (!order) {
        console.log(`🔍 Trying search by reference only...`);
        order = await Order.findOne({ reference: cleanRef });
        if (order) {
          console.log(`✅ Found by reference: ${order.reference}`);
        }
      }
      
      if (!order) {
        console.log(`🔍 Trying case insensitive search...`);
        order = await Order.findOne({ 
          reference: { $regex: new RegExp(`^${cleanRef}$`, 'i') }
        });
        if (order) {
          console.log(`✅ Found case insensitive: ${order.reference}`);
        }
      }
    }
    
    if (!order) {
      order = inMemoryOrders.find(o => o.reference === cleanRef);
      if (order) {
        console.log(`✅ Found in-memory match: ${order.reference}`);
      }
    }
    
    if (!order) {
      console.log(`❌ Order NOT FOUND: ${cleanRef} | ${cleanEmail}`);
      return {
        success: false,
        error: 'Order not found. Check your reference and email.',
        order: null
      };
    }
    
    console.log(`✅ ===== ORDER FOUND =====`);
    console.log(`✅ Reference: ${order.reference}`);
    console.log(`✅ Customer: ${order.customerName}`);
    console.log(`✅ Status: ${order.status}`);
    console.log(`✅ Total: R${order.total}`);
    
    return {
      success: true,
      order: {
        reference: order.reference,
        customerName: order.customerName,
        email: order.email,
        phone: order.phone,
        address: order.address,
        notes: order.notes || '',
        status: order.status,
        items: order.items.map((item: any) => ({
          id: item.id,
          name: item.name,
          qty: item.qty,
          price: item.price,
        })),
        total: order.total,
        trackingNumber: order.trackingNumber || null,
        carrier: order.carrier || null,
        estimatedDelivery: order.estimatedDelivery || null,
        createdAt: order.createdAt,
        updatedAt: order.updatedAt || order.createdAt,
      }
    };
  } catch (error) {
    console.error('❌ Error tracking order:', error);
    return {
      success: false,
      error: 'Failed to track order',
      order: null
    };
  }
}));

// ============================================
// ORDERS API - POST and GET
// ============================================

app.use('/api/orders', eventHandler(async (event) => {
  console.log(`📋 Orders request received: ${event.method}`);
  
  // Handle GET - List all orders
  if (event.method === 'GET') {
    try {
      console.log('📋 Fetching all orders...');
      let orders = [];
      
      if (isMongoConnected) {
        orders = await Order.find({}).sort({ createdAt: -1 }).limit(50).lean();
        console.log(`📋 Found ${orders.length} orders in MongoDB`);
      } else {
        orders = inMemoryOrders;
        console.log(`📋 Found ${orders.length} orders in memory`);
      }
      
      return {
        success: true,
        count: orders.length,
        orders: orders.map(o => ({
          reference: o.reference,
          customerName: o.customerName,
          email: o.email,
          status: o.status,
          total: o.total,
          createdAt: o.createdAt,
          items: o.items,
          assigned_to: o.assigned_to || null,
          assigned_by: o.assigned_by || null
        }))
      };
    } catch (error) {
      console.error('❌ Error fetching orders:', error);
      return {
        success: false,
        error: 'Failed to fetch orders'
      };
    }
  }
  
  // Handle POST - Create new order
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Order received:', JSON.stringify(body, null, 2));
      
      const { customerName, company, email, phone, address, notes, items, total } = body;
      
      if (!customerName || !email || !phone || !address || !items || items.length === 0) {
        return { success: false, error: 'Missing required fields' };
      }
      
      const reference = generateOrderReference();
      
      const orderData = {
        reference,
        customerName,
        company: company || '',
        email: email.toLowerCase().trim(),
        phone,
        address,
        notes: notes || '',
        items: items.map((item: any) => ({
          id: item.id,
          name: item.name,
          qty: item.qty,
          price: item.price || 0
        })),
        total: total || 0,
        status: 'pending'
      };
      
      let savedOrder;
      
      if (isMongoConnected) {
        try {
          const order = new Order(orderData);
          savedOrder = await order.save();
          console.log(`✅ Order SAVED TO MONGODB with Reference: ${reference}`);
        } catch (dbError) {
          console.error('❌ Failed to save to MongoDB:', dbError);
          savedOrder = { ...orderData, _id: `mem_${Date.now()}` };
          inMemoryOrders.push(savedOrder);
          console.log(`💾 Order saved in-memory: ${reference}`);
        }
      } else {
        savedOrder = { ...orderData, _id: `mem_${Date.now()}` };
        inMemoryOrders.push(savedOrder);
        console.log(`💾 Order saved in-memory: ${reference}`);
      }
      
      return {
        success: true,
        orderId: savedOrder._id,
        orderReference: savedOrder.reference
      };
    } catch (error) {
      console.error('❌ Error:', error);
      return { success: false, error: 'Failed to process order' };
    }
  }
  
  return {
    success: false,
    error: `Method ${event.method} not allowed for /api/orders`
  };
}));

// ============================================
// PAYMENT API - Initiate Payment
// ============================================

app.use('/api/quotes/payment', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      const { reference, email } = body;
      
      console.log(`💳 Payment initiated for: ${reference}`);
      
      if (!reference || !email) {
        return {
          success: false,
          message: 'Reference and email are required'
        };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ 
          reference: reference.toUpperCase(), 
          email: email.toLowerCase() 
        });
        
        if (!quote) {
          return {
            success: false,
            message: 'Quote not found'
          };
        }
        
        if (!quote.paymentRequired || !quote.paymentAmount) {
          const extractedAmount = extractPaymentAmount(quote.replyMessage || '');
          if (extractedAmount) {
            quote.paymentRequired = true;
            quote.paymentAmount = extractedAmount;
            await quote.save();
          } else {
            return {
              success: false,
              message: 'No payment required for this quote'
            };
          }
        }
        
        const paymentRef = `PAY-${Date.now()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
        quote.paymentReference = paymentRef;
        quote.paymentStatus = 'pending';
        quote.status = 'payment';
        await quote.save();
        
        const paymentUrl = `${config.frontendUrl}/payment/${paymentRef}`;
        
        return {
          success: true,
          message: 'Payment initiated',
          paymentUrl: paymentUrl,
          quote: {
            id: quote._id.toString(),
            reference: quote.reference,
            customerName: quote.customerName,
            email: quote.email,
            phone: quote.phone,
            status: quote.status,
            items: quote.items.map((item: any) => ({
              id: item.id,
              name: item.name,
              qty: item.qty,
              image: item.image || null
            })),
            replyMessage: quote.replyMessage || null,
            repliedAt: quote.repliedAt || null,
            createdAt: quote.createdAt,
            paymentRequired: quote.paymentRequired || false,
            paymentAmount: quote.paymentAmount || 0,
            paymentStatus: quote.paymentStatus || 'pending',
            feedback: quote.feedback || null
          }
        };
      }
      
      return {
        success: false,
        message: 'Payment service unavailable'
      };
    } catch (error) {
      console.error('❌ Error initiating payment:', error);
      return {
        success: false,
        message: 'Failed to initiate payment'
      };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// PAYMENT WEBHOOK
// ============================================

app.use('/api/payment/webhook', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Payment webhook received:', JSON.stringify(body, null, 2));
      
      const { paymentReference, status } = body;
      
      if (!paymentReference) {
        return {
          success: false,
          message: 'Payment reference is required'
        };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ paymentReference });
        
        if (quote) {
          if (status === 'completed' || status === 'paid') {
            quote.paymentStatus = 'paid';
            quote.status = 'payment';
          } else if (status === 'failed' || status === 'cancelled') {
            quote.paymentStatus = 'failed';
            quote.status = 'quoted';
          }
          
          await quote.save();
          console.log(`✅ Payment status updated for ${quote.reference}: ${quote.paymentStatus}`);
        }
      }
      
      return {
        success: true,
        message: 'Webhook processed successfully'
      };
    } catch (error) {
      console.error('❌ Error processing webhook:', error);
      return {
        success: false,
        message: 'Failed to process webhook'
      };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// SIMULATE PAYMENT COMPLETION
// ============================================

app.use('/api/payment/simulate/:reference', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const reference = event.context.params?.reference;
      
      console.log(`🔄 Simulating payment completion for: ${reference}`);
      
      if (!reference) {
        return {
          success: false,
          message: 'Reference is required'
        };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase() });
        
        if (!quote) {
          return {
            success: false,
            message: 'Quote not found'
          };
        }
        
        quote.paymentStatus = 'paid';
        quote.status = 'payment';
        await quote.save();
        
        console.log(`✅ Payment simulated for ${reference}: PAID`);
      }
      
      return {
        success: true,
        message: 'Payment simulated successfully',
        quote: quote ? {
          reference: quote.reference,
          paymentStatus: quote.paymentStatus,
          status: quote.status
        } : null
      };
    } catch (error) {
      console.error('❌ Error simulating payment:', error);
      return {
        success: false,
        message: 'Failed to simulate payment'
      };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// FEEDBACK API
// ============================================

app.use('/api/quotes/feedback', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      const { reference, email, feedback } = body;
      
      console.log(`📝 Feedback received for: ${reference}`);
      console.log(`📊 Rating: ${feedback.rating}`);
      console.log(`💬 Comment: ${feedback.comment}`);
      
      if (!reference || !email || !feedback) {
        return {
          success: false,
          message: 'Missing required fields'
        };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ 
          reference: reference.toUpperCase(), 
          email: email.toLowerCase() 
        });
        
        if (quote) {
          quote.feedback = {
            rating: feedback.rating,
            comment: feedback.comment,
            submitted: true,
            submittedAt: new Date()
          };
          
          if (feedback.rating >= 4) {
            quote.status = 'approved';
          } else {
            quote.status = 'waiting_feedback';
          }
          
          await quote.save();
          console.log(`✅ Feedback saved for ${reference}`);
        }
      }
      
      if (!quote) {
        return {
          success: false,
          message: 'Quote not found'
        };
      }
      
      return {
        success: true,
        message: 'Feedback submitted successfully',
        quote: {
          id: quote._id.toString(),
          reference: quote.reference,
          customerName: quote.customerName,
          email: quote.email,
          phone: quote.phone,
          status: quote.status,
          items: quote.items.map((item: any) => ({
            id: item.id,
            name: item.name,
            qty: item.qty,
            image: item.image || null
          })),
          replyMessage: quote.replyMessage || null,
          repliedAt: quote.repliedAt || null,
          createdAt: quote.createdAt,
          paymentRequired: quote.paymentRequired || false,
          paymentAmount: quote.paymentAmount || 0,
          paymentStatus: quote.paymentStatus || 'pending',
          feedback: quote.feedback || null
        }
      };
    } catch (error) {
      console.error('❌ Error submitting feedback:', error);
      return {
        success: false,
        message: 'Failed to submit feedback'
      };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// DESKTOP MANAGEMENT API - EMPLOYEES + ASSIGNMENTS
// ============================================

const MANAGEMENT_ROLES = new Set([
  'director', 'branch manager', 'business lead', 'operations manager',
  'manager', 'admin', 'administrator', 'super admin'
]);

function isManagementUser(user: any, employee: any): boolean {
  const role = normaliseLogin(user?.role || employee?.role || '');
  return MANAGEMENT_ROLES.has(role);
}

function safeEmployeePayload(employee: any, user: any = null) {
  const fullName = employeeDisplayName(employee, user);
  return {
    id: employee?._id?.toString?.() ?? employee?._id ?? employee?.id ?? null,
    employee_id: employee?.employee_id ?? employee?.id ?? employee?._id?.toString?.() ?? null,
    full_name: fullName,
    first_name: employee?.first_name || '',
    last_name: employee?.last_name || employee?.surname || '',
    email: employee?.email || employee?.email_address || user?.email || '',
    username: user?.username || user?.email || employee?.username || employee?.email || '',
    role: employee?.role || user?.role || 'Staff',
    department: employee?.department || user?.department || '',
    position: employee?.position || user?.position || '',
    status: employee?.status || user?.status || 'Active',
  };
}

async function requireManagementSession(event: any) {
  const session = await requireDesktopSession(event);
  if (!isManagementUser(session.user, session.employee)) {
    const error = new Error('Manager permission is required for this operation.');
    (error as any).statusCode = 403;
    throw error;
  }
  return session;
}

app.use('/api/employees', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  try {
    const { db, user } = await requireDesktopSession(event);
    const employees = await db.collection('employees').find({}).sort({ full_name: 1, first_name: 1, surname: 1 }).limit(500).toArray();
    const userDocs = await db.collection('users').find({}).project({ password: 0, password_hash: 0, hashed_password: 0 }).limit(2000).toArray();
    const usersByEmployee = new Map<string, any>();
    const usersByEmail = new Map<string, any>();
    for (const u of userDocs) {
      if (u.employee_id !== undefined && u.employee_id !== null) usersByEmployee.set(String(u.employee_id), u);
      const email = normaliseLogin(u.email || u.username);
      if (email) usersByEmail.set(email, u);
    }
    const safeEmployees = employees
      .filter((employee: any) => isActive(employee.status, true))
      .map((employee: any) => {
        const employeeKeys = [employee._id?.toString?.(), employee.employee_id, employee.id].filter(Boolean).map(String);
        const linked = employeeKeys.map(k => usersByEmployee.get(k)).find(Boolean)
          || usersByEmail.get(normaliseLogin(employee.email || employee.email_address));
        return safeEmployeePayload(employee, linked);
      });
    return { success: true, count: safeEmployees.length, employees: safeEmployees };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Failed to load employees' };
  }
}));



function safeAdminUserPayload(user: any, employee: any = null) {
  const fullName = employeeDisplayName(employee, user);
  return {
    id: user?._id?.toString?.() ?? user?._id ?? null,
    employee_id: user?.employee_id?.toString?.() ?? employee?.employee_id?.toString?.() ?? employee?._id?.toString?.() ?? null,
    username: user?.username || user?.email || '',
    email: user?.email || employee?.email || employee?.email_address || '',
    role: user?.role || employee?.role || 'Staff',
    status: user?.status || 'active',
    full_name: fullName,
    first_name: employee?.first_name || '',
    surname: employee?.surname || employee?.last_name || '',
    department: user?.department || employee?.department || '',
    position: user?.position || employee?.position || '',
    last_login_at: user?.last_login_at || null,
    created_at: user?.created_at || null,
    updated_at: user?.updated_at || null,
    has_account: true,
  };
}

async function findEmployeeByReference(db: any, reference: unknown) {
  const value = String(reference ?? '').trim();
  if (!value) return null;

  const employees = db.collection('employees');

  // First try the normal indexed fields.
  const clauses: any[] = [{ employee_id: value }, { id: value }];
  const oid = safeObjectId(value);
  if (oid) clauses.push({ _id: oid });

  // If employee_id is stored as a number/ObjectId in MongoDB, also try a
  // numeric representation where applicable.
  if (/^-?\\d+$/.test(value)) {
    const numericValue = Number(value);
    if (Number.isSafeInteger(numericValue)) {
      clauses.push({ employee_id: numericValue }, { id: numericValue });
    }
  }

  let employee = await employees.findOne({ $or: clauses });
  if (employee) return employee;

  // Final compatibility fallback: compare the string representation of the
  // common employee identifiers. This handles old records where the same
  // employee ID was stored with a different BSON type.
  const candidates = await employees.find({}).limit(5000).toArray();
  const wanted = value.toLowerCase();

  employee = candidates.find((item: any) => {
    const values = [
      item?.employee_id,
      item?.id,
      item?._id?.toString?.(),
      item?._id,
      item?.user_id,
      item?.username,
      item?.email,
    ].filter(v => v !== undefined && v !== null);

    return values.some(v => String(v).trim().toLowerCase() === wanted);
  }) || null;

  return employee;
}

async function findUserByReference(db: any, reference: unknown) {
  const value = String(reference ?? '').trim();
  if (!value) return null;
  const clauses: any[] = [{ username: value }, { email: value }];
  const oid = safeObjectId(value);
  if (oid) clauses.push({ _id: oid });
  return db.collection('users').findOne({ $or: clauses });
}

function hashPbkdf2Sha256(password: string): string {
  const iterations = 310_000;
  const salt = crypto.randomBytes(16).toString('hex');
  const digest = crypto.pbkdf2Sync(Buffer.from(password, 'utf8'), Buffer.from(salt, 'utf8'), iterations, 32, 'sha256').toString('hex');
  return `pbkdf2_sha256$${iterations}$${salt}$${digest}`;
}

app.use('/api/admin/employees', eventHandler(async (event) => {
  if (event.method !== 'GET') { event.node.res.statusCode = 405; return { success: false, error: 'Method not allowed' }; }
  try {
    const { db } = await requireManagementSession(event);
    const employees = await db.collection('employees').find({}).sort({ full_name: 1, first_name: 1, surname: 1 }).limit(2000).toArray();
    const users = await db.collection('users').find({}).project({ password: 0, password_hash: 0, hashed_password: 0 }).limit(5000).toArray();
    const byEmployee = new Map<string, any>();
    const byEmail = new Map<string, any>();
    for (const user of users) {
      if (user.employee_id !== undefined && user.employee_id !== null) byEmployee.set(String(user.employee_id), user);
      const email = normaliseLogin(user.email || user.username);
      if (email) byEmail.set(email, user);
    }
    const result = employees.map((employee: any) => {
      const keys = [employee.employee_id, employee.id, employee._id?.toString?.()].filter(Boolean).map(String);
      const linked = keys.map(k => byEmployee.get(k)).find(Boolean) || byEmail.get(normaliseLogin(employee.email || employee.email_address));
      const payload = safeEmployeePayload(employee, linked);
      return {
        ...payload,
        _id: payload.id,
        mongo_id: payload.id,
        has_account: !!linked,
        user_id: linked?._id?.toString?.() ?? linked?._id ?? null,
        last_login_at: linked?.last_login_at || null,
      };
    });
    return { success: true, count: result.length, employees: result };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Failed to load employees' };
  }
}));

app.use('/api/admin/users', eventHandler(async (event) => {
  try {
    const { db } = await requireManagementSession(event);
    if (event.method === 'GET') {
      const users = await db.collection('users').find({}).project({ password: 0, password_hash: 0, hashed_password: 0 }).sort({ username: 1 }).limit(5000).toArray();
      const employees = await db.collection('employees').find({}).limit(5000).toArray();
      const byEmployee = new Map<string, any>();
      const byEmail = new Map<string, any>();
      for (const employee of employees) {
        for (const key of [employee.employee_id, employee.id, employee._id?.toString?.()].filter(Boolean)) byEmployee.set(String(key), employee);
        const email = normaliseLogin(employee.email || employee.email_address);
        if (email) byEmail.set(email, employee);
      }
      const result = users.map((user: any) => {
        const employee = byEmployee.get(String(user.employee_id ?? '')) || byEmail.get(normaliseLogin(user.email || user.username));
        return safeAdminUserPayload(user, employee);
      });
      return { success: true, count: result.length, users: result };
    }

    if (event.method === 'POST') {
      const body = await readBody(event);
      const employee = await findEmployeeByReference(db, body?.employee_id);
      if (!employee) { event.node.res.statusCode = 404; return { success: false, error: 'Employee not found.' }; }
      const username = normaliseLogin(body?.username);
      const password = String(body?.password ?? '');
      if (!username || !password) { event.node.res.statusCode = 400; return { success: false, error: 'Username and password are required.' }; }
      if (password.length < 8) { event.node.res.statusCode = 400; return { success: false, error: 'Password must be at least 8 characters.' }; }
      const existingUsername = await findUserByReference(db, username);
      if (existingUsername) { event.node.res.statusCode = 409; return { success: false, error: `Username '${username}' is already in use.` }; }
      const employeeKeys = [employee.employee_id, employee.id, employee._id].filter(v => v !== undefined && v !== null);
      const existingEmployeeAccount = await db.collection('users').findOne({ employee_id: { $in: employeeKeys } });
      if (existingEmployeeAccount) { event.node.res.statusCode = 409; return { success: false, error: 'This employee already has a user account.', code: 'ACCOUNT_EXISTS' }; }
      const now = new Date();
      const doc: any = {
        employee_id: employee.employee_id ?? employee.id ?? employee._id,
        username,
        email: body?.email || employee.email || employee.email_address || username,
        role: String(body?.role || 'Staff'),
        status: body?.active === false ? 'inactive' : 'active',
        password_hash: hashPbkdf2Sha256(password),
        require_password_change: !!body?.require_password_change,
        created_at: now,
        updated_at: now,
      };
      const inserted = await db.collection('users').insertOne(doc);
      const created = await db.collection('users').findOne({ _id: inserted.insertedId }, { projection: { password: 0, password_hash: 0, hashed_password: 0 } });
      return { success: true, user: safeAdminUserPayload(created, employee) };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'User administration failed.' };
  }
}));

app.use('/api/admin/users/:id/reset-password', eventHandler(async (event) => {
  if (event.method !== 'POST') { event.node.res.statusCode = 405; return { success: false, error: 'Method not allowed' }; }
  try {
    const { db } = await requireManagementSession(event);
    const id = String(event.context.params?.id || '').trim();
    const oid = safeObjectId(id);
    if (!oid) { event.node.res.statusCode = 404; return { success: false, error: 'User not found.' }; }
    const target = await db.collection('users').findOne({ _id: oid });
    if (!target) { event.node.res.statusCode = 404; return { success: false, error: 'User not found.' }; }
    const body = await readBody(event);
    const password = String(body?.password ?? '');
    if (password.length < 8) { event.node.res.statusCode = 400; return { success: false, error: 'Password must be at least 8 characters.' }; }
    await db.collection('users').updateOne({ _id: oid }, { $set: { password_hash: hashPbkdf2Sha256(password), updated_at: new Date(), require_password_change: true } });
    const updated = await db.collection('users').findOne({ _id: oid }, { projection: { password: 0, password_hash: 0, hashed_password: 0 } });
    const employee = await findEmployeeByReference(db, updated?.employee_id);
    return { success: true, user: safeAdminUserPayload(updated, employee) };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Password reset failed.' };
  }
}));

app.use('/api/admin/users/:id', eventHandler(async (event) => {
  try {
    const { db, user: actor } = await requireManagementSession(event);
    const id = String(event.context.params?.id || '').trim();
    const oid = safeObjectId(id);
    if (!oid) { event.node.res.statusCode = 404; return { success: false, error: 'User not found.' }; }
    const target = await db.collection('users').findOne({ _id: oid });
    if (!target) { event.node.res.statusCode = 404; return { success: false, error: 'User not found.' }; }

    if (event.method === 'PUT') {
      const body = await readBody(event);
      const update: any = { updated_at: new Date() };
      if (body?.username !== undefined) {
        const username = normaliseLogin(body.username);
        if (!username) { event.node.res.statusCode = 400; return { success: false, error: 'Username cannot be empty.' }; }
        const owner = await db.collection('users').findOne({ username, _id: { $ne: oid } });
        if (owner) { event.node.res.statusCode = 409; return { success: false, error: `Username '${username}' is already in use.` }; }
        update.username = username;
      }
      if (body?.role !== undefined) update.role = String(body.role || 'Staff');
      if (body?.active !== undefined) update.status = body.active ? 'active' : 'inactive';
      if (body?.employee_id !== undefined) {
        const employee = await findEmployeeByReference(db, body.employee_id);
        if (!employee) { event.node.res.statusCode = 404; return { success: false, error: 'Employee not found.' }; }
        update.employee_id = employee.employee_id ?? employee.id ?? employee._id;
        update.email = employee.email || employee.email_address || target.email || update.username || target.username;
      }
      if (body?.password) {
        const password = String(body.password);
        if (password.length < 8) { event.node.res.statusCode = 400; return { success: false, error: 'Password must be at least 8 characters.' }; }
        update.password_hash = hashPbkdf2Sha256(password);
        update.require_password_change = !!body?.require_password_change;
      }
      await db.collection('users').updateOne({ _id: oid }, { $set: update });
      const updated = await db.collection('users').findOne({ _id: oid }, { projection: { password: 0, password_hash: 0, hashed_password: 0 } });
      const employee = await findEmployeeByReference(db, updated?.employee_id);
      return { success: true, user: safeAdminUserPayload(updated, employee) };
    }

    if (event.method === 'POST' && event.context.params?.id && event.node.req.url?.includes('/reset-password')) {
      const body = await readBody(event);
      const password = String(body?.password ?? '');
      if (password.length < 8) { event.node.res.statusCode = 400; return { success: false, error: 'Password must be at least 8 characters.' }; }
      await db.collection('users').updateOne({ _id: oid }, { $set: { password_hash: hashPbkdf2Sha256(password), updated_at: new Date(), require_password_change: true } });
      const updated = await db.collection('users').findOne({ _id: oid }, { projection: { password: 0, password_hash: 0, hashed_password: 0 } });
      const employee = await findEmployeeByReference(db, updated?.employee_id);
      return { success: true, user: safeAdminUserPayload(updated, employee) };
    }

    if (event.method === 'DELETE') {
      if (String(actor?._id) === id) { event.node.res.statusCode = 400; return { success: false, error: 'You cannot delete your own account while logged in.' }; }
      await db.collection('users').deleteOne({ _id: oid });
      return { success: true, message: 'User deleted.' };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'User administration failed.' };
  }
}));

async function handleQuoteAssignment(event: any) {
  const { db, user } = await requireManagementSession(event);
  const reference = String(event.context.params?.reference || '').trim().toUpperCase();
  const body = await readBody(event);

  if (!reference) {
    event.node.res.statusCode = 400;
    return { success: false, error: 'Reference is required' };
  }

  // Accept every payload shape used by the desktop clients.
  const requested = body?.employee_id ?? body?.employeeId ?? body?.assigned_to ?? body?.assignedTo ?? null;
  let assignedTo: any = null;

  if (requested !== null && requested !== undefined && String(requested).trim() !== '') {
    const employee = await findEmployeeByReference(db, requested);
    if (!employee || !isActive(employee.status, true)) {
      console.error(`❌ Assignment failed: employee not found: ${requested}`);
      return { success: false, error: 'Employee not found or inactive' };
    }

    const linkedUser = await db.collection('users').findOne({ $or: [
      { employee_id: employee.employee_id },
      { employee_id: employee._id },
      ...(employee.email ? [{ email: employee.email }] : []),
    ] });

    assignedTo = safeEmployeePayload(employee, linkedUser);
  }

  const actor = {
    id: user._id?.toString?.() ?? user._id,
    username: user.username || user.email || '',
    full_name: user.full_name || user.username || user.email || '',
  };

  console.log(`👤 Assignment request: quote=${reference} employee=${requested ?? 'UNASSIGN'} method=${event.method} url=${event.node.req.url}`);

  if (isMongoConnected) {
    const quote = await Quote.findOne({
      $or: [
        { reference },
        { reference: { $regex: `^${reference.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}$`, $options: 'i' } },
      ],
    });

    if (!quote) {
      console.error(`❌ Assignment failed: quote not found: ${reference}`);
      return { success: false, error: 'Quote not found' };
    }

    quote.assigned_to = assignedTo;
    quote.assigned_by = assignedTo ? actor : null;
    if (assignedTo) quote.status = 'assigned';
    await quote.save();

    console.log(`✅ Quote ${quote.reference} assigned to ${assignedTo?.employee_id || assignedTo?.id || 'UNASSIGNED'}`);
    return {
      success: true,
      message: assignedTo ? 'Quote assigned successfully.' : 'Quote unassigned successfully.',
      quote: {
        reference: quote.reference,
        assigned_to: quote.assigned_to,
        assigned_by: quote.assigned_by,
        status: quote.status,
      },
    };
  }

  const quote = inMemoryQuotes.find(q => String(q.reference).toUpperCase() === reference);
  if (!quote) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'Quote not found' };
  }
  quote.assigned_to = assignedTo;
  quote.assigned_by = assignedTo ? actor : null;
  if (assignedTo) quote.status = 'assigned';
  return { success: true, message: 'Quote assigned successfully.', quote };
}

// ============================================================
// UNIVERSAL DESKTOP QUOTE ASSIGNMENT DISPATCHER
// ============================================================
// The Windows desktop client historically used more than one assignment
// URL.  Handle the request at the /api/admin/quotes level and inspect the
// actual URL so a router parameter mismatch cannot produce a false 404.
// This handler is registered BEFORE the generic /api/admin/quotes/:reference
// update handler below.
//
// Supported examples:
//   PUT/POST/PATCH /api/admin/quotes/UQ-XXXXXX/assignment
//   PUT/POST/PATCH /api/admin/quotes/UQ-XXXXXX/assign
//   PUT/POST/PATCH /api/admin/quotes/UQ-XXXXXX/assign-employee
//   PUT/POST/PATCH /api/admin/quotes/UQ-XXXXXX/assignment/employee
// ============================================================

app.use('/api/admin/quotes', eventHandler(async (event) => {
  const method = String(event.method || '').toUpperCase();
  const rawUrl = String(event.node.req.url || '');
  const pathname = rawUrl.split('?')[0];

  const match = pathname.match(
    /^\/api\/admin\/quotes\/([^/]+)\/(assignment|assign|assign-employee|assign_employee|assignment\/employee)\/?$/
  );

  // Not an assignment request: let the normal quote handlers continue.
  if (!match) return;

  console.log(`🚨 ASSIGNMENT ENDPOINT HIT: ${method} ${rawUrl}`);

  if (!['PUT', 'POST', 'PATCH'].includes(method)) {
    event.node.res.statusCode = 405;
    return {
      success: false,
      error: 'Method not allowed for quote assignment',
      endpoint: pathname,
    };
  }

  try {
    // Do not rely on event.context.params here. Extract the reference directly
    // from the actual URL so this works even when h3 mounted middleware does
    // not populate dynamic params.
    const reference = decodeURIComponent(match[1]).trim().toUpperCase();
    const body = await readBody(event);
    const { db, user } = await requireManagementSession(event);

    const requested =
      body?.employee_id ??
      body?.employeeId ??
      body?.assigned_to ??
      body?.assignedTo ??
      body?.employee ??
      body?.employeeID ??
      null;

    console.log(
      `👤 ASSIGNMENT REQUEST: quote=${reference} employee=${requested ?? 'UNASSIGN'} method=${method} url=${rawUrl}`
    );

    let assignedTo: any = null;

    if (requested !== null && requested !== undefined && String(requested).trim() !== '') {
      const employee = await findEmployeeByReference(db, requested);

      if (!employee) {
        // Return a normal JSON response instead of an HTTP 404 so the desktop
        // client can display the actual reason instead of "Backend returned HTTP 404".
        console.error(`❌ ASSIGNMENT EMPLOYEE NOT FOUND: ${String(requested)}`);
        return {
          success: false,
          error: `Employee not found: ${String(requested)}`,
          code: 'EMPLOYEE_NOT_FOUND',
        };
      }

      if (!isActive(employee.status, true)) {
        console.error(`❌ ASSIGNMENT EMPLOYEE INACTIVE: ${String(requested)}`);
        return {
          success: false,
          error: `Employee is inactive: ${employeeDisplayName(employee, null)}`,
          code: 'EMPLOYEE_INACTIVE',
        };
      }

      const linkedUser = await db.collection('users').findOne({
        $or: [
          { employee_id: employee.employee_id },
          { employee_id: employee._id },
          ...(employee.email ? [{ email: employee.email }] : []),
        ],
      });

      assignedTo = safeEmployeePayload(employee, linkedUser);

      console.log(
        `👤 ASSIGNMENT EMPLOYEE FOUND: employee_id=${assignedTo.employee_id} name=${assignedTo.full_name}`
      );
    }

    // Quote lookup is deliberately case-insensitive and whitespace-tolerant.
    let quote: any = null;

    if (isMongoConnected) {
      const escaped = reference.replace(/[.*+?^${}()|[\]\\]/g, '\\\\$&');

      quote = await Quote.findOne({
        $or: [
          { reference },
          { reference: { $regex: `^${escaped}$`, $options: 'i' } },
        ],
      });

      if (!quote) {
        // Last-resort collection lookup for legacy documents.
        const rawQuote = await db.collection('quotes').findOne({
          reference: { $regex: `^${escaped}$`, $options: 'i' },
        });

        if (rawQuote) {
          quote = await Quote.findById(rawQuote._id);
        }
      }
    } else {
      quote = inMemoryQuotes.find(
        (q: any) => String(q?.reference || '').trim().toUpperCase() === reference
      );
    }

    if (!quote) {
      // Again, keep business-level failures as JSON instead of HTTP 404.
      console.error(`❌ ASSIGNMENT QUOTE NOT FOUND: ${reference}`);
      return {
        success: false,
        error: `Quote not found: ${reference}`,
        code: 'QUOTE_NOT_FOUND',
      };
    }

    const actor = {
      id: user?._id?.toString?.() ?? user?._id ?? null,
      username: user?.username || user?.email || '',
      full_name: user?.full_name || user?.username || user?.email || '',
    };

    quote.assigned_to = assignedTo;
    quote.assigned_by = assignedTo ? actor : null;

    if (assignedTo) {
      quote.status = 'assigned';
    }

    if (isMongoConnected) {
      quote.updatedAt = new Date();
      await quote.save();
    }

    console.log(
      `✅ ASSIGNMENT SUCCESS: quote=${reference} employee=${assignedTo?.employee_id || assignedTo?.id || 'UNASSIGNED'} status=${quote.status}`
    );

    return {
      success: true,
      message: assignedTo
        ? 'Quote assigned successfully.'
        : 'Quote unassigned successfully.',
      quote: {
        reference: quote.reference,
        assigned_to: quote.assigned_to,
        assigned_by: quote.assigned_by,
        status: quote.status,
      },
    };
  } catch (error: any) {
    const status = error?.statusCode || 500;
    console.error(
      `❌ ASSIGNMENT EXCEPTION [${method} ${rawUrl}] HTTP ${status}:`,
      error?.stack || error?.message || error
    );

    event.node.res.statusCode = status;

    return {
      success: false,
      error: error?.message || 'Quote assignment failed.',
      code: 'ASSIGNMENT_EXCEPTION',
    };
  }
}));

// Compatibility routes: older/newer desktop builds used different assignment URLs.
for (const path of [
  '/api/admin/quotes/:reference/assignment',
  '/api/admin/quotes/:reference/assign',
  '/api/quotes/:reference/assignment',
  '/api/quotes/:reference/assign',
]) {
  app.use(path, eventHandler(async (event) => {
    // Support both PUT and POST so the backend cannot 404/405 solely because
    // the desktop build uses the other assignment convention.
    if (event.method !== 'PUT' && event.method !== 'POST') {
      event.node.res.statusCode = 405;
      return { success: false, error: 'Method not allowed' };
    }
    try {
      return await handleQuoteAssignment(event);
    } catch (error: any) {
      event.node.res.statusCode = error?.statusCode || 500;
      console.error(`❌ Quote assignment error [${event.method} ${event.node.req.url}]:`, error?.message || error);
      return { success: false, error: error?.message || 'Failed to assign quote' };
    }
  }));
}

async function handleOrderAssignment(event: any) {
  const { db, user } = await requireManagementSession(event);
  const reference = String(event.context.params?.reference || '').trim().toUpperCase();
  const body = await readBody(event);
  if (!reference) { event.node.res.statusCode = 400; return { success: false, error: 'Reference is required' }; }

  const requested = body?.employee_id ?? body?.employeeId ?? body?.assigned_to ?? body?.assignedTo ?? null;
  let assignedTo: any = null;
  if (requested !== null && requested !== undefined && String(requested).trim() !== '') {
    const employee = await findEmployeeByReference(db, requested);
    if (!employee || !isActive(employee.status, true)) { event.node.res.statusCode = 404; return { success: false, error: 'Employee not found or inactive' }; }
    const linkedUser = await db.collection('users').findOne({ $or: [
      { employee_id: employee.employee_id }, { employee_id: employee._id }, ...(employee.email ? [{ email: employee.email }] : [])
    ] });
    assignedTo = safeEmployeePayload(employee, linkedUser);
  }

  const actor = { id: user._id?.toString?.() ?? user._id, username: user.username || user.email || '', full_name: user.full_name || user.username || user.email || '' };
  const order = isMongoConnected ? await Order.findOne({ reference }) : inMemoryOrders.find(o => String(o.reference).toUpperCase() === reference);
  if (!order) { event.node.res.statusCode = 404; return { success: false, error: 'Order not found' }; }
  order.assigned_to = assignedTo;
  order.assigned_by = assignedTo ? actor : null;
  if (assignedTo && String(order.status || '').toLowerCase() === 'pending') order.status = 'assigned';
  order.updatedAt = new Date();
  if (isMongoConnected) await order.save();
  return { success: true, message: assignedTo ? 'Order assigned successfully.' : 'Order unassigned successfully.', order: { reference: order.reference, assigned_to: order.assigned_to, assigned_by: order.assigned_by, status: order.status } };
}

for (const path of [
  '/api/admin/orders/:reference/assignment',
  '/api/admin/orders/:reference/assign',
  '/api/orders/:reference/assignment',
  '/api/orders/:reference/assign',
]) {
  app.use(path, eventHandler(async (event) => {
    if (event.method !== 'PUT' && event.method !== 'POST') { event.node.res.statusCode = 405; return { success: false, error: 'Method not allowed' }; }
    try { return await handleOrderAssignment(event); }
    catch (error: any) { event.node.res.statusCode = error?.statusCode || 500; console.error(`❌ Order assignment error [${event.method} ${event.node.req.url}]:`, error?.message || error); return { success: false, error: error?.message || 'Failed to assign order' }; }
  }));
}

// ============================================
// ADMIN API - Update Quote
// ============================================

app.use('/api/admin/quotes/:reference', eventHandler(async (event) => {
  if (event.method === 'PUT') {
    try {
      const reference = event.context.params?.reference;
      const body = await readBody(event);
      
      console.log(`🔧 Updating quote: ${reference}`);
      
      if (!reference) {
        return { success: false, message: 'Reference is required' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase() });
        
        if (!quote) {
          return { success: false, message: 'Quote not found' };
        }
        
        if (body.status) quote.status = body.status;
        if (body.replyMessage) {
          quote.replyMessage = body.replyMessage;
          quote.repliedAt = new Date();
          
          const extractedAmount = extractPaymentAmount(body.replyMessage);
          if (extractedAmount) {
            quote.paymentRequired = true;
            quote.paymentAmount = extractedAmount;
            quote.paymentStatus = 'pending';
            console.log(`💰 Auto-extracted payment amount: R${extractedAmount} from reply`);
          }
        }
        if (body.repliedAt) quote.repliedAt = new Date(body.repliedAt);
        if (body.paymentRequired !== undefined) quote.paymentRequired = body.paymentRequired;
        if (body.paymentAmount !== undefined) quote.paymentAmount = body.paymentAmount;
        if (body.paymentStatus) quote.paymentStatus = body.paymentStatus;
        if (body.items) quote.items = body.items;
        
        await quote.save();
        console.log(`✅ Quote updated: ${reference}`);
      }
      
      return {
        success: true,
        message: 'Quote updated successfully',
        quote: quote ? {
          reference: quote.reference,
          status: quote.status,
          replyMessage: quote.replyMessage,
          paymentRequired: quote.paymentRequired,
          paymentAmount: quote.paymentAmount,
          paymentStatus: quote.paymentStatus,
          items: quote.items
        } : null
      };
    } catch (error) {
      console.error('❌ Error updating quote:', error);
      return { success: false, message: 'Failed to update quote' };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// ADMIN API - Set Payment for Quote
// ============================================

app.use('/api/admin/quotes/:reference/payment', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const reference = event.context.params?.reference;
      const body = await readBody(event);
      
      console.log(`💳 Setting payment for: ${reference}`);
      
      if (!reference) {
        return { success: false, message: 'Reference is required' };
      }
      
      const { amount } = body;
      
      if (!amount || amount <= 0) {
        return { success: false, message: 'Valid payment amount is required' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase() });
        
        if (!quote) {
          return { success: false, message: 'Quote not found' };
        }
        
        quote.paymentRequired = true;
        quote.paymentAmount = amount;
        quote.paymentStatus = 'pending';
        
        await quote.save();
        console.log(`✅ Payment set for ${reference}: R${amount}`);
      }
      
      return {
        success: true,
        message: `Payment of R${amount} set for quote ${reference}`,
        quote: quote ? {
          reference: quote.reference,
          paymentRequired: quote.paymentRequired,
          paymentAmount: quote.paymentAmount,
          paymentStatus: quote.paymentStatus
        } : null
      };
    } catch (error) {
      console.error('❌ Error setting payment:', error);
      return { success: false, message: 'Failed to set payment' };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// ADMIN API - Extract Payment from Reply
// ============================================

app.use('/api/admin/quotes/:reference/extract-payment', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const reference = event.context.params?.reference;
      
      console.log(`💰 Extracting payment for: ${reference}`);
      
      if (!reference) {
        return { success: false, message: 'Reference is required' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase() });
        
        if (!quote) {
          return { success: false, message: 'Quote not found' };
        }
        
        const amount = extractPaymentAmount(quote.replyMessage || '');
        
        if (amount) {
          quote.paymentRequired = true;
          quote.paymentAmount = amount;
          quote.paymentStatus = 'pending';
          await quote.save();
          
          return {
            success: true,
            message: `Payment extracted: R${amount}`,
            quote: {
              reference: quote.reference,
              paymentRequired: quote.paymentRequired,
              paymentAmount: quote.paymentAmount,
              paymentStatus: quote.paymentStatus
            }
          };
        }
        
        return { success: false, message: 'No payment amount found in reply message' };
      }
      
      return { success: false, message: 'Database not connected' };
    } catch (error) {
      console.error('❌ Error extracting payment:', error);
      return { success: false, message: 'Failed to extract payment' };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// ADMIN API - Force Update Quote Status
// ============================================

app.use('/api/admin/quotes/:reference/status', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const reference = event.context.params?.reference;
      const body = await readBody(event);
      
      console.log(`🔄 Updating status for: ${reference}`);
      
      if (!reference) {
        return { success: false, message: 'Reference is required' };
      }
      
      const { status } = body;
      
      if (!status) {
        return { success: false, message: 'Status is required' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase() });
        
        if (!quote) {
          return { success: false, message: 'Quote not found' };
        }
        
        quote.status = status;
        await quote.save();
        console.log(`✅ Status updated for ${reference}: ${status}`);
      }
      
      return {
        success: true,
        message: `Status updated to ${status}`,
        quote: quote ? {
          reference: quote.reference,
          status: quote.status
        } : null
      };
    } catch (error) {
      console.error('❌ Error updating status:', error);
      return { success: false, message: 'Failed to update status' };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));


// ============================================
// DESKTOP EXE API - AUTHENTICATION + ATTENDANCE
// ============================================
// The Windows EXE talks to these endpoints instead of connecting directly
// to MongoDB. MongoDB credentials therefore remain on the server.

const ACTIVE_STATUS_VALUES = new Set(['active', 'enabled', 'approved', 'true', '1', 'yes']);
const SESSION_HOURS = 8;

function normaliseLogin(value: unknown): string {
  return String(value ?? '').trim().toLowerCase();
}

function isActive(value: unknown, defaultValue = true): boolean {
  if (value === undefined || value === null) return defaultValue;
  if (typeof value === 'boolean') return value;
  return ACTIVE_STATUS_VALUES.has(String(value).trim().toLowerCase());
}

function mongoRequired() {
  if (!isMongoConnected || !mongoose.connection.db) {
    if (config.nodeEnv === 'development') {
      return ensureInMemoryDesktopDb();
    }
    const error = new Error('MongoDB is unavailable.');
    (error as any).statusCode = 503;
    throw error;
  }
  return mongoose.connection.db;
}

function safeObjectId(value: unknown): any {
  if (value === undefined || value === null) return null;
  if (value instanceof mongoose.Types.ObjectId) return value;
  const text = String(value);
  return mongoose.isValidObjectId(text) ? new mongoose.Types.ObjectId(text) : null;
}

function employeeReferenceValues(value: any): any[] {
  const values: any[] = [];
  if (value !== undefined && value !== null) values.push(value);
  if (value instanceof mongoose.Types.ObjectId) values.push(value.toString());
  else if (typeof value === 'string') {
    const oid = safeObjectId(value);
    if (oid) values.push(oid);
  }
  return values.filter((v, i, a) => a.findIndex(x => String(x) === String(v)) === i);
}

async function findEmployeeForUser(user: any) {
  const db = mongoRequired();
  const employees = db.collection('employees');
  const employeeId = user?.employee_id;

  if (employeeId !== undefined && employeeId !== null) {
    const refs = employeeReferenceValues(employeeId);
    if (refs.length) {
      const employee = await employees.findOne({
        $or: [
          { _id: { $in: refs.filter(v => v instanceof mongoose.Types.ObjectId) } },
          { employee_id: { $in: refs } },
          { id: { $in: refs } },
        ],
      });
      if (employee) return employee;
    }
  }

  const email = normaliseLogin(user?.email || user?.username);
  if (email) {
    return employees.findOne({
      $or: [
        { email: { $regex: `^${email.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
        { email_address: { $regex: `^${email.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
      ],
    });
  }
  return null;
}

function verifyPbkdf2Sha256(password: string, stored: string): boolean {
  try {
    const parts = stored.split('$');
    if (parts.length !== 4 || parts[0] !== 'pbkdf2_sha256') return false;
    const iterations = Number(parts[1]);
    if (!Number.isInteger(iterations) || iterations < 1 || iterations > 5_000_000) return false;
    const derived = crypto.pbkdf2Sync(
      Buffer.from(password, 'utf8'),
      Buffer.from(parts[2], 'utf8'),
      iterations,
      32,
      'sha256',
    ).toString('hex');
    return crypto.timingSafeEqual(Buffer.from(derived), Buffer.from(parts[3]));
  } catch {
    return false;
  }
}

function verifyPassword(password: string, storedHash: unknown): boolean {
  if (typeof storedHash !== 'string' || !storedHash) return false;
  if (storedHash.startsWith('pbkdf2_sha256$')) return verifyPbkdf2Sha256(password, storedHash);
  if (/^[a-f0-9]{64}$/i.test(storedHash)) {
    const digest = crypto.createHash('sha256').update(password, 'utf8').digest('hex');
    return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(storedHash));
  }
  // Werkzeug's pbkdf2/scrypt and bcrypt are intentionally rejected unless the
  // backend is built with the corresponding verifier. This prevents accepting
  // plaintext passwords or silently changing password semantics.
  return false;
}

function makeToken(): string {
  return `${randomUUID().replace(/-/g, '')}.${crypto.randomBytes(32).toString('hex')}`;
}

function bearerToken(event: any): string | null {
  const header = String(event.node.req.headers.authorization || '');
  if (!header.toLowerCase().startsWith('bearer ')) return null;
  const token = header.slice(7).trim();
  return token || null;
}

function todaySouthAfrica(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Johannesburg',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
}

function asDate(value: any): Date | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function elapsedSeconds(start: any, end: any = new Date()): number {
  const a = asDate(start);
  const b = asDate(end);
  if (!a || !b) return 0;
  return Math.max(0, (b.getTime() - a.getTime()) / 1000);
}

function netElapsedSeconds(record: any, end: Date = new Date()): number {
  if (!record?.clock_in_at) return 0;
  const total = elapsedSeconds(record.clock_in_at, end);
  const fixedPause = (Number(record.break_duration_minutes) || 0) + (Number(record.lunch_duration_minutes) || 0);
  const activeBreak = record.break_started_at ? elapsedSeconds(record.break_started_at, end) / 60 : 0;
  return Math.max(0, total - (fixedPause + activeBreak) * 60);
}

function serialiseAttendance(record: any) {
  if (!record) return null;
  return {
    ...record,
    _id: record._id?.toString?.() ?? record._id,
    employee_id: record.employee_id?.toString?.() ?? record.employee_id,
  };
}

async function requireDesktopSession(event: any) {
  const token = bearerToken(event);
  if (!token) {
    const error = new Error('Authentication token is required.');
    (error as any).statusCode = 401;
    throw error;
  }

  const db = mongoRequired();
  const session = await db.collection('api_sessions').findOne({
    token,
    status: 'active',
    expires_at: { $gt: new Date() },
  });
  if (!session) {
    const error = new Error('Session expired or invalid. Please log in again.');
    (error as any).statusCode = 401;
    throw error;
  }

  const users = db.collection('users');
  const user = await users.findOne({ _id: session.user_id });
  if (!user || !isActive(user.status, true)) {
    await db.collection('api_sessions').updateOne({ _id: session._id }, { $set: { status: 'revoked', revoked_at: new Date() } });
    const error = new Error('Your user account is inactive.');
    (error as any).statusCode = 403;
    throw error;
  }

  const employee = await findEmployeeForUser(user);
  if (!employee || !isActive(employee.status, true)) {
    const error = new Error(!employee ? 'Your account is not linked to an employee record.' : 'Your employee record is inactive.');
    (error as any).statusCode = 403;
    throw error;
  }

  // Do not write to MongoDB on every attendance/status request. Session
  // activity is only refreshed periodically; attendance state itself is
  // refreshed by the explicit status endpoint or state-changing actions.
  const now = Date.now();
  const lastActivity = session.last_activity_at ? new Date(session.last_activity_at).getTime() : 0;
  if (now - lastActivity >= 5 * 60 * 1000) {
    await db.collection('api_sessions').updateOne(
      { _id: session._id },
      { $set: { last_activity_at: new Date(now) } },
    );
  }
  return { db, session, user, employee };
}

async function getTodayAttendance(db: any, employeeId: any) {
  const values = employeeReferenceValues(employeeId);
  return db.collection('attendance').findOne({
    employee_id: { $in: values },
    work_date: todaySouthAfrica(),
  });
}

function employeeDisplayName(employee: any, user: any): string {
  return employee?.full_name ||
    [employee?.first_name, employee?.surname || employee?.last_name].filter(Boolean).join(' ') ||
    user?.full_name || user?.username || user?.email || 'Employee';
}

function roleName(user: any, employee: any): string {
  return String(user?.role || employee?.role || employee?.position || 'Staff');
}

function canDumpTasks(role: string): boolean {
  return ['Director', 'Business Lead', 'Operations Manager'].includes(role);
}

function canTriageTasks(role: string): boolean {
  return ['Operations Manager', 'Director'].includes(role);
}

function canViewAllTasks(role: string): boolean {
  return ['Director', 'Business Lead', 'Operations Manager'].includes(role);
}

function canReviewApprovals(role: string): boolean {
  return ['Operations Manager', 'Business Lead', 'Director'].includes(role);
}

function canReviewApprovalStage(role: string, stage: string): boolean {
  if (role === 'Director') return stage === 'Director';
  return role === stage;
}

function employeeIdValues(employee: any): any[] {
  return employeeReferenceValues(employee?._id)
    .concat(employeeReferenceValues(employee?.employee_id))
    .concat(employeeReferenceValues(employee?.id))
    .filter((v, i, a) => a.findIndex(x => String(x) === String(v)) === i);
}

function taskIdentity(value: any) {
  const values = employeeReferenceValues(value);
  return values.length ? values[0] : value;
}

function taskObjectId(value: any) {
  if (value instanceof mongoose.Types.ObjectId) return value;
  if (typeof value === 'string' && mongoose.Types.ObjectId.isValid(value)) {
    return new mongoose.Types.ObjectId(value);
  }
  return null;
}

function taskFilter(id: any) {
  const oid = taskObjectId(id);
  return oid ? { _id: oid } : { task_number: String(id) };
}

function apiSubpath(event: any, prefix: string): string[] {
  const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
  const pathname = url.pathname.replace(/\/+$/, '');
  const cleanPrefix = prefix.replace(/\/+$/, '');
  if (pathname === cleanPrefix) return [];
  if (pathname.startsWith(`${cleanPrefix}/`)) {
    return pathname.slice(cleanPrefix.length + 1).split('/').filter(Boolean).map(decodeURIComponent);
  }

  const mountedPath = pathname.replace(/^\/+/, '');
  return mountedPath ? mountedPath.split('/').filter(Boolean).map(decodeURIComponent) : [];
}

function cleanTaskStatus(status: any, fallback = 'Dumped'): string {
  const value = String(status || fallback).trim();
  const allowed = new Set([
    'Dumped',
    'Needs Triage',
    'New',
    'Assigned',
    'In Progress',
    'Waiting Review',
    'Completed',
    'Cancelled',
  ]);
  return allowed.has(value) ? value : fallback;
}

function cleanApprovalType(value: any): string {
  const requestType = String(value || 'General').trim();
  const allowed = new Set([
    'General',
    'Office Supplies',
    'Equipment',
    'Leave',
    'Sick Leave',
    'Software',
    'Purchases',
    'Budget',
    'Task Approval',
    'Director Review',
  ]);
  return allowed.has(requestType) ? requestType : 'General';
}

function cleanApprovalStatus(value: any, fallback = 'Pending'): string {
  const status = String(value || fallback).trim();
  return ['Pending', 'Approved', 'Rejected', 'Cancelled'].includes(status) ? status : fallback;
}

function nextApprovalStage(request: any, stage: string): string {
  if (stage === 'Operations Manager') return 'Business Lead';
  if (stage === 'Business Lead') return request.requires_director ? 'Director' : 'Completed';
  return 'Completed';
}

function serialiseApproval(request: any) {
  if (!request) return null;
  return {
    id: request._id?.toString?.() ?? request._id,
    title: request.title || '',
    request_type: request.request_type || 'General',
    description: request.description || '',
    requested_by: request.requested_by || request.created_by_name || '',
    department: request.department || '',
    amount: Number(request.amount || 0),
    status: request.status || 'Pending',
    current_stage: request.current_stage || 'Operations Manager',
    requires_director: Boolean(request.requires_director),
    due_date: request.due_date || '',
    reference_type: request.reference_type || '',
    reference_id: request.reference_id?.toString?.() ?? request.reference_id ?? null,
    manager_approved_by: request.manager_approved_by || '',
    business_approved_by: request.business_approved_by || '',
    director_approved_by: request.director_approved_by || '',
    rejection_reason: request.rejection_reason || '',
    submitted_at: request.submitted_at || request.created_at || request.createdAt || null,
    updated_at: request.updated_at || request.updatedAt || null,
    history: request.history || [],
  };
}

const OFFICE_REQUEST_ITEMS = [
  'Printer Paper',
  'Pens',
  'Staples',
  'Printer Toner',
  'RFQ Dividers',
  'Stationery',
  'Ethernet Cable',
  'Mouse',
  'Keyboard',
  'Laptop',
  'Monitor',
];

function serialiseOfficeRequest(request: any, approval: any = null) {
  if (!request) return null;
  const approvalStatus = approval?.status || request.approval_status || 'Pending';
  return {
    id: request._id?.toString?.() ?? request._id,
    item_name: request.item_name || '',
    quantity: Number(request.quantity || 0),
    requested_by: request.requested_by || '',
    department: request.department || '',
    notes: request.notes || '',
    approval_id: request.approval_id?.toString?.() ?? request.approval_id ?? null,
    approval_status: approvalStatus,
    requires_director: Boolean(request.requires_director),
    created_at: request.created_at || request.createdAt || null,
    updated_at: request.updated_at || request.updatedAt || null,
  };
}

function cleanPriority(priority: any): string {
  const value = String(priority || 'Medium').trim();
  return ['Low', 'Medium', 'High', 'Critical'].includes(value) ? value : 'Medium';
}

function serialiseTask(task: any) {
  if (!task) return null;
  const activeSeconds = task.active_timer_started_at ? elapsedSeconds(task.active_timer_started_at) : 0;
  const actualHours = Number(task.actual_hours || 0) + (activeSeconds / 3600);
  return {
    id: task._id?.toString?.() ?? task._id,
    task_number: task.task_number || '',
    title: task.title || '',
    description: task.description || '',
    category: task.category || 'Administration',
    department: task.department || '',
    priority: task.priority || 'Medium',
    status: task.status || 'Dumped',
    assigned_employee: task.assigned_employee || '',
    assigned_employee_id: task.assigned_employee_id?.toString?.() ?? task.assigned_employee_id ?? null,
    assigned_by: task.assigned_by || '',
    dumped_by: task.dumped_by || task.created_by_name || '',
    evaluated_by: task.evaluated_by || '',
    director_approval_id: task.director_approval_id?.toString?.() ?? task.director_approval_id ?? null,
    director_approval_status: task.director_approval_status || '',
    returned_reason: task.returned_reason || '',
    due_date: task.due_date || '',
    start_date: task.start_date || '',
    estimated_hours: Number(task.estimated_hours || 0),
    actual_hours: Math.round(actualHours * 100) / 100,
    active_timer_started_at: task.active_timer_started_at || null,
    comments: task.comments || '',
    checklist: task.checklist || [],
    attachments: task.attachments || [],
    created_at: task.created_at || task.createdAt || null,
    updated_at: task.updated_at || task.updatedAt || null,
    history: task.history || [],
  };
}

function taskTimeEntry(action: string, by: string, role: string, note: string, hours = 0) {
  return {
    action,
    by,
    role,
    note,
    hours: Math.round(Number(hours || 0) * 100) / 100,
    at: new Date(),
  };
}

function taskEventType(task: any): string {
  const category = String(task?.category || '');
  const map: Record<string, string> = {
    RFQ: 'RFQ Deadline',
    Tender: 'RFQ Deadline',
    Technical: 'Technical Visit',
    Software: 'Software Milestone',
    Website: 'Software Milestone',
    'Supplier Registration': 'Supplier Deadline',
    Training: 'Training',
    HR: 'HR Deadline',
    Leave: 'Leave',
  };
  return map[category] || 'Work Due';
}

function serialiseCalendarEvent(event: any) {
  if (!event) return null;
  return {
    id: event._id?.toString?.() ?? event.id ?? event.source_id ?? null,
    title: event.title || '',
    event_type: event.event_type || 'Other',
    start_date: event.start_date || '',
    end_date: event.end_date || '',
    department: event.department || '',
    details: event.details || '',
    source_type: event.source_type || 'Manual',
    source_id: event.source_id?.toString?.() ?? event.source_id ?? null,
    recurrence: event.recurrence || 'None',
    created_at: event.created_at || event.createdAt || null,
  };
}

function canReviewHr(role: string): boolean {
  return ['Operations Manager', 'Director'].includes(role);
}

function cleanHrType(value: any): string {
  const requestType = String(value || 'Leave').trim();
  return ['Leave', 'Sick Leave'].includes(requestType) ? requestType : 'Leave';
}

function cleanHrStatus(value: any, fallback = 'Pending'): string {
  const status = String(value || fallback).trim();
  return ['Pending', 'Approved', 'Rejected', 'Cancelled'].includes(status) ? status : fallback;
}

function serialiseHrRequest(request: any) {
  if (!request) return null;
  return {
    id: request._id?.toString?.() ?? request._id,
    title: request.title || `${request.request_type || 'Leave'} request`,
    request_type: request.request_type || 'Leave',
    employee_id: request.employee_id?.toString?.() ?? request.employee_id ?? null,
    employee_name: request.employee_name || '',
    department: request.department || '',
    start_date: request.start_date || '',
    end_date: request.end_date || '',
    reason: request.reason || '',
    status: request.status || 'Pending',
    current_stage: request.current_stage || 'Operations Manager',
    reviewed_by: request.reviewed_by || '',
    reviewed_at: request.reviewed_at || null,
    evaluation_notes: request.evaluation_notes || '',
    sick_note: request.sick_note || null,
    created_at: request.created_at || request.createdAt || null,
    updated_at: request.updated_at || request.updatedAt || null,
  };
}

function dateInRange(value: any, start: string, end: string): boolean {
  const text = String(value || '');
  return Boolean(text) && text >= start && text <= end;
}

async function handleApprovalById(event: any, approvalId: any) {
  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  const oid = taskObjectId(approvalId);
  if (!oid) {
    event.node.res.statusCode = 400;
    return { success: false, error: 'Approval id is invalid.' };
  }

  const collection = db.collection('approvals');
  const existing = await collection.findOne({ _id: oid });
  if (!existing) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'Approval request not found.' };
  }

  const me = employeeDisplayName(employee, user);

  if (event.method === 'GET') {
    return { success: true, approval: serialiseApproval(existing) };
  }

  if (event.method === 'PATCH' || event.method === 'PUT') {
    if (!canReviewApprovals(role)) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Only management can review approvals.' };
    }

    const body = await readBody(event);
    const decision = String(body?.decision || body?.action || '').trim().toLowerCase();
    const stage = String(body?.stage || existing.current_stage || 'Operations Manager');
    const note = String(body?.reason || body?.note || '').trim();
    const now = new Date();

    if (existing.status !== 'Pending') {
      event.node.res.statusCode = 409;
      return { success: false, error: 'Only pending approval requests can be reviewed.' };
    }
    if (!canReviewApprovalStage(role, stage) || existing.current_stage !== stage) {
      event.node.res.statusCode = 403;
      return { success: false, error: `This request is awaiting ${existing.current_stage} review.` };
    }

    if (decision === 'approve' || decision === 'approved') {
      const approvalField: Record<string, string> = {
        'Operations Manager': 'manager_approved_by',
        'Business Lead': 'business_approved_by',
        Director: 'director_approved_by',
      };
      const nextStage = nextApprovalStage(existing, stage);
      const status = nextStage === 'Completed' ? 'Approved' : 'Pending';
      const update: any = {
        current_stage: nextStage,
        status,
        updated_at: now,
      };
      update[approvalField[stage]] = me;

      await collection.updateOne(
        { _id: oid },
        {
          $set: update,
          $push: {
            history: {
              action: 'approved',
              by: me,
              role,
              stage,
              next_stage: nextStage,
              at: now,
            },
          },
        } as any,
      );

      if (existing.reference_type === 'Task' && status === 'Approved' && existing.reference_id) {
        await db.collection('work_assignments').updateOne(
          taskFilter(existing.reference_id),
          {
            $set: {
              director_approval_status: 'Approved',
              status: 'Completed',
              updated_at: now,
            },
            $push: {
              history: {
                action: 'director_approved',
                by: me,
                role,
                note: 'Director approval completed.',
                at: now,
              },
            },
          } as any,
        );
      }

      return { success: true, approval: serialiseApproval(await collection.findOne({ _id: oid })) };
    }

    if (decision === 'reject' || decision === 'rejected') {
      if (!note) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'A rejection reason is required.' };
      }

      await collection.updateOne(
        { _id: oid },
        {
          $set: {
            status: 'Rejected',
            current_stage: 'Completed',
            rejection_reason: `${me}: ${note}`,
            updated_at: now,
          },
          $push: {
            history: {
              action: 'rejected',
              by: me,
              role,
              stage,
              note,
              at: now,
            },
          },
        } as any,
      );

      if (existing.reference_type === 'Task' && existing.reference_id) {
        await db.collection('work_assignments').updateOne(
          taskFilter(existing.reference_id),
          {
            $set: {
              director_approval_status: 'Rejected',
              status: 'In Progress',
              returned_reason: note,
              updated_at: now,
            },
            $push: {
              history: {
                action: 'director_rejected',
                by: me,
                role,
                note,
                at: now,
              },
            },
          } as any,
        );
      }

      return { success: true, approval: serialiseApproval(await collection.findOne({ _id: oid })) };
    }

    event.node.res.statusCode = 400;
    return { success: false, error: 'Unknown approval decision.' };
  }

  event.node.res.statusCode = 405;
  return { success: false, error: 'Method not allowed' };
}

async function handleWorkTaskById(event: any, taskId: any) {
  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  const collection = db.collection('work_assignments');
  const filter = taskFilter(taskId);
  const task = await collection.findOne(filter);

  if (!task) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'Task not found.' };
  }

  const me = employeeDisplayName(employee, user);
  const mine = task.assigned_employee === me || employeeIdValues(employee).some(v => String(v) === String(task.assigned_employee_id));
  if (!canViewAllTasks(role) && !mine) {
    event.node.res.statusCode = 403;
    return { success: false, error: 'You can only view your assigned tasks.' };
  }

  if (event.method === 'GET') {
    return { success: true, task: serialiseTask(task) };
  }

  if (event.method === 'PUT' || event.method === 'PATCH') {
    const body = await readBody(event);
    const now = new Date();
    const update: any = { updated_at: now };
    const history: any = {
      action: 'updated',
      by: me,
      role,
      at: now,
      note: 'Task details updated.',
    };

    const managerFields = ['title', 'description', 'category', 'department', 'priority', 'due_date', 'start_date', 'estimated_hours', 'comments'];
    if (canTriageTasks(role)) {
      for (const key of managerFields) {
        if (body[key] !== undefined) update[key] = key === 'estimated_hours' ? Number(body[key] || 0) : body[key];
      }
      if (body.checklist !== undefined) update.checklist = Array.isArray(body.checklist) ? body.checklist : [];
      if (body.attachments !== undefined) update.attachments = Array.isArray(body.attachments) ? body.attachments : [];
    } else if (!mine) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Only Operations Manager or Director can edit task details.' };
    }

    if (body.status !== undefined) {
      const next = cleanTaskStatus(body.status, task.status || 'Assigned');
      if (!canTriageTasks(role) && !['In Progress', 'Waiting Review', 'Completed'].includes(next)) {
        event.node.res.statusCode = 403;
        return { success: false, error: 'Staff can only move assigned work through progress/review/completed states.' };
      }
      update.status = next;
      history.action = 'status_changed';
      history.note = `Status changed to ${next}.`;
    }

    if (body.actual_hours !== undefined) {
      update.actual_hours = Math.max(0, Number(body.actual_hours || 0));
      history.action = 'time_updated';
      history.note = `Actual hours updated to ${update.actual_hours}.`;
    }

    await collection.updateOne(filter, { $set: update, $push: { history } });
    return { success: true, task: serialiseTask(await collection.findOne(filter)) };
  }

  if (event.method === 'DELETE') {
    if (!canTriageTasks(role)) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Only Operations Manager or Director can delete tasks.' };
    }
    await collection.deleteOne(filter);
    return { success: true };
  }

  event.node.res.statusCode = 405;
  return { success: false, error: 'Method not allowed' };
}

async function handleWorkTaskAssign(event: any, taskId: any) {
  if (event.method !== 'POST') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  if (!canTriageTasks(role)) {
    event.node.res.statusCode = 403;
    return { success: false, error: 'Only Operations Manager or Director can assign tasks.' };
  }

  const body = await readBody(event);
  const now = new Date();
  const me = employeeDisplayName(employee, user);
  const filter = taskFilter(taskId);
  const assignedName = String(body?.assigned_employee || body?.employee_name || '').trim();

  if (!assignedName) {
    event.node.res.statusCode = 400;
    return { success: false, error: 'Assigned employee is required.' };
  }

  const assignedEmployee = await db.collection('employees').findOne({
    $or: [
      { full_name: assignedName },
      { email: normaliseLogin(body?.username || body?.email || assignedName) },
      { employee_id: taskIdentity(body?.employee_id || body?.assigned_employee_id) },
    ],
  });

  const assignedUser = assignedEmployee
    ? await db.collection('users').findOne({
        $or: [
          { employee_id: assignedEmployee._id },
          { employee_id: assignedEmployee.employee_id },
          { email: assignedEmployee.email },
        ],
      })
    : null;

  const assignedDisplay = assignedEmployee ? employeeDisplayName(assignedEmployee, assignedUser) : assignedName;
  await db.collection('work_assignments').updateOne(
    filter,
    {
      $set: {
        assigned_employee: assignedDisplay,
        assigned_employee_id: assignedEmployee?._id || taskIdentity(body?.employee_id || body?.assigned_employee_id),
        assigned_by: me,
        status: 'Assigned',
        evaluated_by: me,
        updated_at: now,
      },
      $push: {
        history: {
          action: 'assigned',
          by: me,
          role,
          employee: assignedDisplay,
          note: `Assigned to ${assignedDisplay}.`,
          at: now,
        },
      },
    } as any,
  );

  return { success: true, task: serialiseTask(await db.collection('work_assignments').findOne(filter)) };
}

async function handleWorkTaskDecision(event: any, taskId: any) {
  if (event.method !== 'POST') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }

  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  if (!canTriageTasks(role)) {
    event.node.res.statusCode = 403;
    return { success: false, error: 'Only Operations Manager or Director can make task decisions.' };
  }

  const collection = db.collection('work_assignments');
  const filter = taskFilter(taskId);
  const task = await collection.findOne(filter);

  if (!task) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'Task not found.' };
  }

  const body = await readBody(event);
  const action = String(body?.action || '').trim().toLowerCase();
  const note = String(body?.note || body?.reason || '').trim();
  const now = new Date();
  const me = employeeDisplayName(employee, user);
  const update: any = { updated_at: now };
  const unset: any = {};
  let history: any = {
    action: 'decision_recorded',
    by: me,
    role,
    note: note || 'Task decision recorded.',
    at: now,
  };

  if (action === 'approve_review' || action === 'approve') {
    if (task.status !== 'Waiting Review' && task.status !== 'In Progress') {
      event.node.res.statusCode = 409;
      return { success: false, error: 'Only reviewed or active work can be approved.' };
    }
    update.status = 'Completed';
    update.evaluated_by = me;
    update.completed_at = now;
    unset.active_timer_started_at = '';
    history = { action: 'review_approved', by: me, role, note: note || 'Reviewed work approved and completed.', at: now };
  } else if (action === 'return_to_work' || action === 'return') {
    if (!note) {
      event.node.res.statusCode = 400;
      return { success: false, error: 'A return reason is required.' };
    }
    update.status = 'In Progress';
    update.returned_reason = note;
    update.evaluated_by = me;
    unset.active_timer_started_at = '';
    history = { action: 'returned_to_work', by: me, role, note, at: now };
  } else if (action === 'needs_triage') {
    update.status = 'Needs Triage';
    update.assigned_employee = '';
    update.assigned_employee_id = null;
    update.assigned_by = '';
    update.evaluated_by = me;
    unset.active_timer_started_at = '';
    history = { action: 'marked_needs_triage', by: me, role, note: note || 'Moved back to operations triage.', at: now };
  } else if (action === 'cancel') {
    update.status = 'Cancelled';
    update.evaluated_by = me;
    update.cancelled_at = now;
    unset.active_timer_started_at = '';
    history = { action: 'cancelled', by: me, role, note: note || 'Task cancelled.', at: now };
  } else if (action === 'escalate_director' || action === 'escalate') {
    const existingApproval = task.director_approval_id
      ? await db.collection('approvals').findOne(taskFilter(task.director_approval_id))
      : null;
    const approvalDoc = {
      title: `Director review: ${task.title || task.task_number || 'Task'}`,
      request_type: 'Director Review',
      description: note || task.description || 'Task requires director approval.',
      requested_by: me,
      department: task.department || employee?.department || '',
      amount: 0,
      status: 'Pending',
      current_stage: 'Director',
      requires_director: true,
      due_date: task.due_date || '',
      reference_type: 'Task',
      reference_id: task._id,
      manager_approved_by: me,
      business_approved_by: '',
      director_approved_by: '',
      rejection_reason: '',
      created_by: user?._id || null,
      created_by_name: me,
      submitted_at: now,
      created_at: now,
      updated_at: now,
      history: [{ action: 'submitted', by: me, role, next_stage: 'Director', at: now }],
    };

    let approvalId = existingApproval?._id || null;
    if (!approvalId || existingApproval?.status !== 'Pending') {
      const inserted = await db.collection('approvals').insertOne(approvalDoc);
      approvalId = inserted.insertedId;
    }

    update.status = 'Waiting Review';
    update.director_approval_id = approvalId;
    update.director_approval_status = 'Pending';
    update.director_approval_requested_at = now;
    update.evaluated_by = me;
    unset.active_timer_started_at = '';
    history = {
      action: 'director_review_requested',
      by: me,
      role,
      note: note || 'Escalated to director for approval.',
      approval_id: approvalId,
      at: now,
    };
  } else {
    event.node.res.statusCode = 400;
    return { success: false, error: 'Unknown task decision.' };
  }

  const operation: any = { $set: update, $push: { history } };
  if (Object.keys(unset).length) operation.$unset = unset;
  await collection.updateOne(filter, operation);
  return { success: true, task: serialiseTask(await collection.findOne(filter)) };
}

async function handleWorkTaskTime(event: any, taskId: any) {
  if (event.method !== 'POST') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }

  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  const collection = db.collection('work_assignments');
  const filter = taskFilter(taskId);
  const task = await collection.findOne(filter);

  if (!task) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'Task not found.' };
  }

  const me = employeeDisplayName(employee, user);
  const mine = task.assigned_employee === me || employeeIdValues(employee).some(v => String(v) === String(task.assigned_employee_id));
  if (!canTriageTasks(role) && !mine) {
    event.node.res.statusCode = 403;
    return { success: false, error: 'You can only track time on your assigned tasks.' };
  }

  const body = await readBody(event);
  const action = String(body?.action || '').trim().toLowerCase();
  const note = String(body?.note || '').trim();
  const now = new Date();
  const baseHours = Math.max(0, Number(task.actual_hours || 0));
  const update: any = { updated_at: now };
  const unset: any = {};
  let history = taskTimeEntry('time_updated', me, role, note || 'Time updated.');

  if (action === 'start') {
    if (task.active_timer_started_at) {
      return { success: true, task: serialiseTask(task), message: 'Task timer is already running.' };
    }
    update.status = 'In Progress';
    update.active_timer_started_at = now;
    if (!task.start_date) update.start_date = todaySouthAfrica();
    history = taskTimeEntry('work_started', me, role, note || 'Work timer started.');
  } else if (action === 'pause' || action === 'stop') {
    if (!task.active_timer_started_at) {
      return { success: true, task: serialiseTask(task), message: 'Task timer is not running.' };
    }
    const addedHours = elapsedSeconds(task.active_timer_started_at, now) / 3600;
    update.actual_hours = Math.round((baseHours + addedHours) * 100) / 100;
    unset.active_timer_started_at = '';
    history = taskTimeEntry('work_paused', me, role, note || 'Work timer paused.', addedHours);
  } else if (action === 'log') {
    const hours = Math.max(0, Number(body?.hours || 0));
    if (!hours) {
      event.node.res.statusCode = 400;
      return { success: false, error: 'Hours must be greater than zero.' };
    }
    update.actual_hours = Math.round((baseHours + hours) * 100) / 100;
    history = taskTimeEntry('time_logged', me, role, note || `Logged ${hours} hours.`, hours);
  } else if (action === 'submit_review') {
    let totalHours = baseHours;
    if (task.active_timer_started_at) {
      const addedHours = elapsedSeconds(task.active_timer_started_at, now) / 3600;
      totalHours += addedHours;
      unset.active_timer_started_at = '';
    }
    update.actual_hours = Math.round(totalHours * 100) / 100;
    update.status = 'Waiting Review';
    history = taskTimeEntry('submitted_review', me, role, note || 'Submitted for review.');
  } else if (action === 'complete') {
    if (!canTriageTasks(role) && task.status !== 'Waiting Review') {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Submit the task for review before completing it.' };
    }
    let totalHours = baseHours;
    if (task.active_timer_started_at) {
      const addedHours = elapsedSeconds(task.active_timer_started_at, now) / 3600;
      totalHours += addedHours;
      unset.active_timer_started_at = '';
    }
    update.actual_hours = Math.round(totalHours * 100) / 100;
    update.status = 'Completed';
    history = taskTimeEntry('completed', me, role, note || 'Task completed.');
  } else {
    event.node.res.statusCode = 400;
    return { success: false, error: 'Unknown time action.' };
  }

  const operation: any = { $set: update, $push: { history } };
  if (Object.keys(unset).length) operation.$unset = unset;
  await collection.updateOne(filter, operation);
  return { success: true, task: serialiseTask(await collection.findOne(filter)) };
}

async function handleHrRequestById(event: any, requestId: any) {
  const { db, user, employee } = await requireDesktopSession(event);
  const role = roleName(user, employee);
  const oid = taskObjectId(requestId);
  if (!oid) {
    event.node.res.statusCode = 400;
    return { success: false, error: 'HR request id is invalid.' };
  }

  const collection = db.collection('hr_leave_requests');
  const existing = await collection.findOne({ _id: oid });
  if (!existing) {
    event.node.res.statusCode = 404;
    return { success: false, error: 'HR request not found.' };
  }

  if (event.method === 'GET') {
    return { success: true, request: serialiseHrRequest(existing) };
  }

  if (event.method === 'PATCH' || event.method === 'PUT') {
    if (!canReviewHr(role)) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Only Operations Manager or Director can review HR requests.' };
    }

    const body = await readBody(event);
    const status = cleanHrStatus(body?.status, existing.status || 'Pending');
    const now = new Date();
    const reviewer = employeeDisplayName(employee, user);
    const update: any = {
      status,
      current_stage: status === 'Pending' ? 'Operations Manager' : 'Completed',
      reviewed_by: reviewer,
      reviewed_at: now,
      evaluation_notes: String(body?.evaluation_notes || body?.review_notes || ''),
      updated_at: now,
    };

    if (existing.request_type === 'Sick Leave' && existing.sick_note) {
      update['sick_note.status'] = status === 'Approved' ? 'Accepted' : status === 'Rejected' ? 'Rejected' : existing.sick_note.status;
      update['sick_note.evaluated_by'] = reviewer;
      update['sick_note.evaluated_at'] = now;
    }

    await collection.updateOne(
      { _id: oid },
      {
        $set: update,
        $push: {
          history: {
            action: status.toLowerCase(),
            by: reviewer,
            role,
            note: update.evaluation_notes,
            at: now,
          },
        },
      } as any,
    );
    return { success: true, request: serialiseHrRequest(await collection.findOne({ _id: oid })) };
  }

  if (event.method === 'DELETE') {
    const requesterValues = employeeIdValues(employee).concat(employeeReferenceValues(user?._id));
    const isOwnRequest = requesterValues.some(value => String(value) === String(existing.employee_id));
    if (!canReviewHr(role) && !isOwnRequest) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'You can only cancel your own HR requests.' };
    }
    await collection.updateOne(
      { _id: oid },
      {
        $set: { status: 'Cancelled', current_stage: 'Completed', updated_at: new Date() },
        $push: { history: { action: 'cancelled', by: employeeDisplayName(employee, user), role, at: new Date() } },
      } as any,
    );
    return { success: true };
  }

  event.node.res.statusCode = 405;
  return { success: false, error: 'Method not allowed' };
}

async function nextTaskNumber(db: any): Promise<string> {
  const counter = await db.collection('counters').findOneAndUpdate(
    { _id: 'work_assignment_number' },
    { $inc: { seq: 1 } },
    { upsert: true, returnDocument: 'after' },
  );
  const seq = Number(counter?.value?.seq || 1);
  return `TASK-${String(seq).padStart(5, '0')}`;
}

app.use('/api/auth/login', eventHandler(async (event) => {
  if (event.method !== 'POST') return { success: false, error: 'Method not allowed' };
  try {
    const body = await readBody(event);
    const username = normaliseLogin(body?.username || body?.email);
    const password = String(body?.password ?? '');
    if (!username || !password) return { success: false, error: 'Username and password are required.' };

    const db = mongoRequired();
    const users = db.collection('users');
    const user = await users.findOne({
      $or: [
        { username },
        { email: username },
        { username: { $regex: `^${username.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
        { email: { $regex: `^${username.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
      ],
    });

    if (!user) return { success: false, error: 'Invalid username or password.' };
    if (!isActive(user.status, true)) return { success: false, error: 'This user account is inactive. Contact a manager.', code: 'USER_INACTIVE' };

    const employee = await findEmployeeForUser(user);
    if (!employee) return { success: false, error: 'Your login account is not linked to an employee record in MongoDB.', code: 'EMPLOYEE_NOT_FOUND' };
    if (!isActive(employee.status, true)) return { success: false, error: 'This employee is inactive and cannot log in. Contact a manager.', code: 'EMPLOYEE_INACTIVE' };

    const storedHash = user.password_hash || user.hashed_password || user.password;
    if (!verifyPassword(password, storedHash)) return { success: false, error: 'Invalid username or password.' };

    const token = makeToken();
    const now = new Date();
    const expires = new Date(now.getTime() + SESSION_HOURS * 60 * 60 * 1000);
    await db.collection('api_sessions').insertOne({
      token,
      user_id: user._id,
      employee_id: employee._id,
      status: 'active',
      created_at: now,
      last_activity_at: now,
      expires_at: expires,
    });

    await users.updateOne({ _id: user._id }, { $set: { last_login_at: now, updated_at: now } });

    return {
      success: true,
      token,
      expires_at: expires.toISOString(),
      user: {
        id: user._id.toString(),
        username: user.username || user.email || username,
        email: user.email || employee.email || '',
        role: user.role || 'Staff',
        status: user.status || 'active',
      },
      employee: {
        id: employee._id.toString(),
        employee_id: employee.employee_id ?? employee.id ?? employee._id.toString(),
        full_name: employeeDisplayName(employee, user),
        email: employee.email || employee.email_address || user.email || '',
        department: employee.department || user.department || '',
        position: employee.position || user.position || '',
        status: employee.status || 'Active',
      },
    };
  } catch (error: any) {
    console.error('Desktop login error:', error?.message || error);
    const status = error?.statusCode || 500;
    event.node.res.statusCode = status;
    return { success: false, error: status === 503 ? 'Authentication service is temporarily unavailable.' : 'Authentication failed.' };
  }
}));

app.use('/api/auth/me', eventHandler(async (event) => {
  try {
    const { user, employee } = await requireDesktopSession(event);
    return {
      success: true,
      user: { id: user._id.toString(), username: user.username || user.email, email: user.email || '' },
      employee: {
        id: employee._id.toString(),
        employee_id: employee.employee_id ?? employee.id ?? employee._id.toString(),
        full_name: employeeDisplayName(employee, user),
        status: employee.status || 'Active',
      },
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 401;
    return { success: false, error: error?.message || 'Unauthorized' };
  }
}));

app.use('/api/auth/logout', eventHandler(async (event) => {
  if (event.method !== 'POST') return { success: false, error: 'Method not allowed' };
  try {
    const token = bearerToken(event);
    if (token && isMongoConnected && mongoose.connection.db) {
      await mongoose.connection.db.collection('api_sessions').updateOne(
        { token },
        { $set: { status: 'logged_out', logout_at: new Date() } },
      );
    }
    return { success: true };
  } catch {
    return { success: true };
  }
}));

// ============================================
// DESKTOP EXE API - PHASE 1 WORK SPINE
// ============================================

app.use('/api/approvals', eventHandler(async (event) => {
  try {
    const subpath = apiSubpath(event, '/api/approvals');
    if (subpath[0]) {
      return await handleApprovalById(event, subpath[0]);
    }

    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const collection = db.collection('approvals');
    const me = employeeDisplayName(employee, user);

    if (event.method === 'POST') {
      const body = await readBody(event);
      const now = new Date();
      const title = String(body?.title || '').trim();
      const requestedBy = String(body?.requested_by || me).trim();
      const department = String(body?.department || employee?.department || '').trim();

      if (!title) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Approval title is required.' };
      }
      if (!requestedBy || !department) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Requestor and department are required.' };
      }

      const doc = {
        title,
        request_type: cleanApprovalType(body?.request_type),
        description: String(body?.description || '').trim(),
        requested_by: requestedBy,
        department,
        amount: Math.max(0, Number(body?.amount || 0)),
        status: 'Pending',
        current_stage: 'Operations Manager',
        requires_director: Boolean(body?.requires_director),
        due_date: String(body?.due_date || '').trim(),
        reference_type: String(body?.reference_type || '').trim(),
        reference_id: body?.reference_id || null,
        manager_approved_by: '',
        business_approved_by: '',
        director_approved_by: '',
        rejection_reason: '',
        created_by: user?._id || null,
        created_by_name: me,
        submitted_at: now,
        created_at: now,
        updated_at: now,
        history: [{
          action: 'submitted',
          by: me,
          role,
          next_stage: 'Operations Manager',
          at: now,
        }],
      };

      const inserted = await collection.insertOne(doc);
      return { success: true, approval: serialiseApproval({ ...doc, _id: inserted.insertedId }) };
    }

    if (event.method === 'GET') {
      const query = getQuery(event);
      const status = String(query.status || 'All');
      const stage = String(query.stage || 'All');
      const scope = String(query.scope || 'auto');
      const filter: any = {};

      if (status !== 'All') filter.status = cleanApprovalStatus(status);
      if (stage !== 'All') filter.current_stage = stage;

      if (!canReviewApprovals(role) || scope === 'mine') {
        filter.$or = [
          { requested_by: me },
          { created_by: user?._id },
          { created_by_name: me },
        ];
      }

      const rows = await collection.find(filter).sort({ updated_at: -1, submitted_at: -1 }).limit(300).toArray();
      return { success: true, approvals: rows.map(serialiseApproval), count: rows.length, role };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Approval operation failed.' };
  }
}));

app.use('/api/office-requests', eventHandler(async (event) => {
  try {
    const subpath = apiSubpath(event, '/api/office-requests');
    if (subpath[0] === 'items') {
      if (event.method !== 'GET') {
        event.node.res.statusCode = 405;
        return { success: false, error: 'Method not allowed' };
      }
      return { success: true, items: OFFICE_REQUEST_ITEMS };
    }

    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const collection = db.collection('office_requests');
    const approvals = db.collection('approvals');
    const me = employeeDisplayName(employee, user);

    if (event.method === 'POST') {
      const body = await readBody(event);
      const itemName = String(body?.item_name || body?.item || '').trim();
      const quantity = Number(body?.quantity || 0);
      const requestedBy = String(body?.requested_by || me).trim();
      const department = String(body?.department || employee?.department || '').trim();
      const notes = String(body?.notes || '').trim();
      const requiresDirector = Boolean(body?.requires_director);

      if (!OFFICE_REQUEST_ITEMS.includes(itemName)) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Select a valid office item.' };
      }
      if (!Number.isFinite(quantity) || quantity < 1) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Quantity must be at least one.' };
      }
      if (!requestedBy || !department) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Requestor and department are required.' };
      }

      const now = new Date();
      const approvalDoc = {
        title: `Office request: ${quantity} x ${itemName}`,
        request_type: 'Office Supplies',
        description: notes || `Request for ${quantity} x ${itemName}`,
        requested_by: requestedBy,
        department,
        amount: 0,
        status: 'Pending',
        current_stage: 'Operations Manager',
        requires_director: requiresDirector,
        due_date: '',
        reference_type: 'OfficeRequest',
        reference_id: null,
        manager_approved_by: '',
        business_approved_by: '',
        director_approved_by: '',
        rejection_reason: '',
        created_by: user?._id || null,
        created_by_name: me,
        submitted_at: now,
        created_at: now,
        updated_at: now,
        history: [{
          action: 'submitted',
          by: me,
          role,
          next_stage: 'Operations Manager',
          at: now,
        }],
      };

      const approvalInsert = await approvals.insertOne(approvalDoc);
      const doc = {
        item_name: itemName,
        quantity,
        requested_by: requestedBy,
        department,
        notes,
        approval_id: approvalInsert.insertedId,
        approval_status: 'Pending',
        requires_director: requiresDirector,
        created_by: user?._id || null,
        created_by_name: me,
        created_at: now,
        updated_at: now,
      };
      const inserted = await collection.insertOne(doc);
      await approvals.updateOne(
        { _id: approvalInsert.insertedId },
        { $set: { reference_id: inserted.insertedId, updated_at: now } },
      );

      return {
        success: true,
        request: serialiseOfficeRequest(
          { ...doc, _id: inserted.insertedId },
          { ...approvalDoc, _id: approvalInsert.insertedId },
        ),
      };
    }

    if (event.method === 'GET') {
      const query = getQuery(event);
      const status = String(query.status || 'All');
      const filter: any = {};

      if (!canReviewApprovals(role)) {
        filter.$or = [
          { requested_by: me },
          { created_by: user?._id },
          { created_by_name: me },
        ];
      }

      const rows = await collection.find(filter).sort({ updated_at: -1, created_at: -1 }).limit(300).toArray();
      const approvalRows = await Promise.all(
        rows.map((row: any) => row.approval_id ? approvals.findOne({ _id: taskObjectId(row.approval_id) || row.approval_id }) : null),
      );
      const requests = rows
        .map((row: any, index: number) => serialiseOfficeRequest(row, approvalRows[index]))
        .filter((row: any) => status === 'All' || row.approval_status === cleanApprovalStatus(status));

      return { success: true, requests, count: requests.length, role };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Office request operation failed.' };
  }
}));

app.use('/api/work/decision-queue', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }

  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const today = todaySouthAfrica();
    const tasks = db.collection('work_assignments');
    const approvals = db.collection('approvals');
    const hr = db.collection('hr_leave_requests');

    const [
      operationsInbox,
      waitingReview,
      overdue,
      businessApprovals,
      directorApprovals,
      hrReviews,
    ] = await Promise.all([
      canTriageTasks(role)
        ? tasks.find({
            status: { $in: ['Dumped', 'Needs Triage', 'New'] },
            $or: [{ assigned_employee: { $in: ['', null] } }, { assigned_employee: { $exists: false } }],
          }).sort({ priority: -1, due_date: 1, created_at: -1 }).limit(50).toArray()
        : [],
      canViewAllTasks(role)
        ? tasks.find({ status: 'Waiting Review' }).sort({ due_date: 1, updated_at: -1 }).limit(50).toArray()
        : [],
      canViewAllTasks(role)
        ? tasks.find({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: { $lt: today, $ne: '' } }).sort({ due_date: 1 }).limit(50).toArray()
        : [],
      canReviewApprovals(role)
        ? approvals.find({ status: 'Pending', current_stage: 'Business Lead' }).sort({ updated_at: -1 }).limit(50).toArray()
        : [],
      canReviewApprovals(role)
        ? approvals.find({ status: 'Pending', current_stage: 'Director' }).sort({ updated_at: -1 }).limit(50).toArray()
        : [],
      canReviewHr(role)
        ? hr.find({ status: 'Pending' }).sort({ updated_at: -1 }).limit(50).toArray()
        : [],
    ]);

    const myStage = role === 'Director' ? 'Director' : role === 'Business Lead' ? 'Business Lead' : role === 'Operations Manager' ? 'Operations Manager' : '';
    const myApprovalItems = myStage
      ? await approvals.find({ status: 'Pending', current_stage: myStage }).sort({ updated_at: -1 }).limit(50).toArray()
      : [];

    return {
      success: true,
      role,
      summary: {
        operations_inbox: operationsInbox.length,
        waiting_review: waitingReview.length,
        overdue: overdue.length,
        my_approvals: myApprovalItems.length,
        business_approvals: businessApprovals.length,
        director_approvals: directorApprovals.length,
        hr_reviews: hrReviews.length,
      },
      queues: {
        operations_inbox: operationsInbox.map(serialiseTask),
        waiting_review: waitingReview.map(serialiseTask),
        overdue: overdue.map(serialiseTask),
        my_approvals: myApprovalItems.map(serialiseApproval),
        business_approvals: businessApprovals.map(serialiseApproval),
        director_approvals: directorApprovals.map(serialiseApproval),
        hr_reviews: hrReviews.map(serialiseHrRequest),
      },
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to load decision queue.' };
  }
}));

app.use('/api/work/tasks', eventHandler(async (event) => {
  try {
    const subpath = apiSubpath(event, '/api/work/tasks');
    if (subpath[0]) {
      const [taskId, action] = subpath;
      if (!action) return await handleWorkTaskById(event, taskId);
      if (action === 'assign') return await handleWorkTaskAssign(event, taskId);
      if (action === 'decision') return await handleWorkTaskDecision(event, taskId);
      if (action === 'time') return await handleWorkTaskTime(event, taskId);
      event.node.res.statusCode = 404;
      return { success: false, error: 'Task endpoint not found.' };
    }

    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const collection = db.collection('work_assignments');
    const me = employeeDisplayName(employee, user);
    const myIds = employeeIdValues(employee);

    if (event.method === 'POST') {
      if (!canDumpTasks(role)) {
        event.node.res.statusCode = 403;
        return { success: false, error: 'Only the Director, Business Lead, or Operations Manager can create dumped tasks.' };
      }

      const body = await readBody(event);
      const now = new Date();
      const assignedEmployee = String(body?.assigned_employee || '').trim();
      const status = assignedEmployee ? 'Assigned' : cleanTaskStatus(body?.status, 'Dumped');
      const doc = {
        task_number: await nextTaskNumber(db),
        title: String(body?.title || '').trim(),
        description: String(body?.description || '').trim(),
        category: String(body?.category || 'Administration').trim(),
        department: String(body?.department || employee?.department || '').trim(),
        priority: cleanPriority(body?.priority),
        status,
        assigned_employee: assignedEmployee,
        assigned_employee_id: taskIdentity(body?.assigned_employee_id || null),
        assigned_by: assignedEmployee ? me : '',
        dumped_by: me,
        dumped_by_role: role,
        created_by: user?._id,
        created_by_name: me,
        evaluated_by: status === 'Assigned' ? me : '',
        due_date: String(body?.due_date || '').trim(),
        start_date: String(body?.start_date || '').trim(),
        estimated_hours: Number(body?.estimated_hours || 0),
        actual_hours: 0,
        comments: String(body?.comments || '').trim(),
        checklist: Array.isArray(body?.checklist) ? body.checklist : [],
        attachments: Array.isArray(body?.attachments) ? body.attachments : [],
        created_at: now,
        updated_at: now,
        history: [
          {
            action: 'dumped',
            by: me,
            role,
            note: 'Task created in the operations inbox.',
            at: now,
          },
        ],
      };

      if (!doc.title) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Task title is required.' };
      }

      const inserted = await collection.insertOne(doc);
      const task = await collection.findOne({ _id: inserted.insertedId });
      return { success: true, task: serialiseTask(task) };
    }

    if (event.method === 'GET') {
      const query = getQuery(event);
      const scope = String(query.scope || (canViewAllTasks(role) ? 'all' : 'mine')).toLowerCase();
      const filter: any = {};

      if (scope === 'inbox' || scope === 'dumped') {
        if (!canTriageTasks(role)) {
          event.node.res.statusCode = 403;
          return { success: false, error: 'Only Operations Manager or Director can view the operations inbox.' };
        }
        filter.status = { $in: ['Dumped', 'Needs Triage', 'New'] };
        filter.$or = [
          { assigned_employee: { $in: ['', null] } },
          { assigned_employee: { $exists: false } },
        ];
      } else if (scope === 'mine' || scope === 'personal') {
        filter.$or = [
          { assigned_employee_id: { $in: myIds } },
          { assigned_employee: me },
          { assigned_to: user?.username || user?.email },
        ];
      } else if (scope === 'department') {
        filter.department = employee?.department || user?.department || '';
      } else if (!canViewAllTasks(role)) {
        filter.$or = [
          { assigned_employee_id: { $in: myIds } },
          { assigned_employee: me },
        ];
      }

      for (const key of ['status', 'priority', 'category', 'department'] as const) {
        if (query[key] && String(query[key]) !== 'All') filter[key] = String(query[key]);
      }

      const search = String(query.search || '').trim();
      if (search) {
        filter.$and = [
          ...(filter.$and || []),
          {
            $or: [
              { title: { $regex: search, $options: 'i' } },
              { description: { $regex: search, $options: 'i' } },
              { comments: { $regex: search, $options: 'i' } },
              { task_number: { $regex: search, $options: 'i' } },
            ],
          },
        ];
      }

      const tasks = await collection
        .find(filter)
        .sort({ due_date: 1, priority: -1, created_at: -1 })
        .limit(300)
        .toArray();

      return { success: true, tasks: tasks.map(serialiseTask), scope, count: tasks.length };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    console.error('Work tasks API error:', error?.message || error);
    return { success: false, error: error?.message || 'Work task operation failed.' };
  }
}));

app.use('/api/work/workload', eventHandler(async (event) => {
  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    if (!canViewAllTasks(role)) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Only management can view team workload.' };
    }

    const activeStatuses = ['Assigned', 'In Progress', 'Waiting Review'];
    const rows = await db.collection('work_assignments').aggregate([
      { $match: { status: { $in: activeStatuses } } },
      {
        $group: {
          _id: '$assigned_employee',
          task_count: { $sum: 1 },
          estimated_hours: { $sum: { $ifNull: ['$estimated_hours', 0] } },
          actual_hours: { $sum: { $ifNull: ['$actual_hours', 0] } },
          active_now: { $sum: { $cond: [{ $ifNull: ['$active_timer_started_at', false] }, 1, 0] } },
          waiting_review: { $sum: { $cond: [{ $eq: ['$status', 'Waiting Review'] }, 1, 0] } },
          overdue: { $sum: { $cond: [{ $and: [{ $ne: ['$due_date', ''] }, { $lt: ['$due_date', todaySouthAfrica()] }] }, 1, 0] } },
        },
      },
      { $sort: { task_count: -1, estimated_hours: -1 } },
    ]).toArray();

    const activeAssignments = await db.collection('work_assignments')
      .find({ status: { $in: activeStatuses } })
      .project({
        task_number: 1,
        title: 1,
        status: 1,
        assigned_employee: 1,
        due_date: 1,
        estimated_hours: 1,
        actual_hours: 1,
        active_timer_started_at: 1,
      })
      .sort({ active_timer_started_at: -1, due_date: 1 })
      .limit(100)
      .toArray();

    return {
      success: true,
      workload: rows
        .filter((row: any) => row._id)
        .map((row: any) => ({
          employee: row._id,
          task_count: row.task_count,
          estimated_hours: row.estimated_hours,
          actual_hours: row.actual_hours,
          active_now: row.active_now,
          waiting_review: row.waiting_review,
          overdue: row.overdue,
          variance_hours: Math.round((Number(row.actual_hours || 0) - Number(row.estimated_hours || 0)) * 100) / 100,
        })),
      active_assignments: activeAssignments.map(serialiseTask),
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to read workload.' };
  }
}));

app.use('/api/hr/leave-requests', eventHandler(async (event) => {
  try {
    const subpath = apiSubpath(event, '/api/hr/leave-requests');
    if (subpath[0]) {
      return await handleHrRequestById(event, subpath[0]);
    }

    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const collection = db.collection('hr_leave_requests');

    if (event.method === 'POST') {
      const body = await readBody(event);
      const requestType = cleanHrType(body?.request_type);
      const startDate = String(body?.start_date || '').trim();
      const endDate = String(body?.end_date || startDate).trim();
      const reason = String(body?.reason || body?.description || '').trim();

      if (!startDate) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Start date is required.' };
      }
      if (endDate && endDate < startDate) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'End date cannot be before start date.' };
      }
      if (!reason) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Reason is required.' };
      }

      const note = body?.sick_note && typeof body.sick_note === 'object' ? body.sick_note : null;
      const sickNote = requestType === 'Sick Leave' && note ? {
        file_name: String(note.file_name || note.name || ''),
        file_type: String(note.file_type || note.type || ''),
        file_size: Number(note.file_size || note.size || 0),
        status: String(note.status || 'Pending Evaluation'),
        uploaded_at: new Date(),
      } : null;

      const now = new Date();
      const doc = {
        title: `${requestType}: ${employeeDisplayName(employee, user)}`,
        request_type: requestType,
        employee_id: employee?._id || user?._id || null,
        employee_name: employeeDisplayName(employee, user),
        department: String(body?.department || employee?.department || ''),
        start_date: startDate,
        end_date: endDate || startDate,
        reason,
        status: 'Pending',
        current_stage: 'Operations Manager',
        reviewed_by: '',
        reviewed_at: null,
        evaluation_notes: '',
        sick_note: sickNote,
        created_by: user?._id || null,
        created_at: now,
        updated_at: now,
        history: [{
          action: 'submitted',
          by: employeeDisplayName(employee, user),
          role,
          at: now,
        }],
      };

      const inserted = await collection.insertOne(doc);
      return { success: true, request: serialiseHrRequest({ ...doc, _id: inserted.insertedId }) };
    }

    if (event.method === 'GET') {
      const query = getQuery(event);
      const status = String(query.status || 'All');
      const scope = String(query.scope || 'auto');
      const filter: any = {};
      if (status !== 'All') filter.status = cleanHrStatus(status);

      if (!canReviewHr(role) || scope === 'mine') {
        filter.employee_id = { $in: employeeIdValues(employee).concat(employeeReferenceValues(user?._id)) };
      }

      const rows = await collection.find(filter).sort({ updated_at: -1, created_at: -1 }).limit(300).toArray();
      return {
        success: true,
        requests: rows.map(serialiseHrRequest),
        count: rows.length,
        role,
      };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'HR request operation failed.' };
  }
}));

app.use('/api/dashboard/summary', eventHandler(async (event) => {
  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const tasks = db.collection('work_assignments');
    const today = todaySouthAfrica();
    const activeStatuses = ['Assigned', 'In Progress', 'Waiting Review'];
    const hrRequests = db.collection('hr_leave_requests');

    const [
      totalEmployees,
      activeEmployees,
      operationsInbox,
      pendingTasks,
      inProgress,
      waitingReview,
      overdue,
      dueToday,
      completedThisWeek,
      pendingApprovals,
      operationsApprovalStage,
      businessApprovalStage,
      directorApprovalStage,
      pendingHrReviews,
      sickNotesPending,
      peopleOnLeave,
    ] = await Promise.all([
      db.collection('employees').countDocuments({}),
      db.collection('employees').countDocuments({ status: { $in: ['active', 'Active', true] } }),
      tasks.countDocuments({ status: { $in: ['Dumped', 'Needs Triage', 'New'] } }),
      tasks.countDocuments({ status: { $in: activeStatuses } }),
      tasks.countDocuments({ status: 'In Progress' }),
      tasks.countDocuments({ status: 'Waiting Review' }),
      tasks.countDocuments({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: { $lt: today, $ne: '' } }),
      tasks.countDocuments({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: today }),
      tasks.countDocuments({
        status: 'Completed',
        updated_at: { $gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) },
      }),
      db.collection('approvals').countDocuments({ status: { $in: ['Pending', 'pending'] } }).catch(() => 0),
      db.collection('approvals').countDocuments({ status: 'Pending', current_stage: 'Operations Manager' }).catch(() => 0),
      db.collection('approvals').countDocuments({ status: 'Pending', current_stage: 'Business Lead' }).catch(() => 0),
      db.collection('approvals').countDocuments({ status: 'Pending', current_stage: 'Director' }).catch(() => 0),
      hrRequests.countDocuments({ status: 'Pending' }).catch(() => 0),
      hrRequests.countDocuments({ request_type: 'Sick Leave', status: 'Pending' }).catch(() => 0),
      hrRequests.countDocuments({ status: 'Approved', start_date: { $lte: today }, end_date: { $gte: today } }).catch(() => 0),
    ]);

    const latestTasks = await tasks.find({})
      .sort({ updated_at: -1, created_at: -1 })
      .limit(8)
      .toArray();

    return {
      success: true,
      role,
      summary: {
        total_employees: totalEmployees,
        active_employees: activeEmployees,
        operations_inbox: operationsInbox,
        pending_tasks: pendingTasks,
        tasks_in_progress: inProgress,
        tasks_waiting_review: waitingReview,
        tasks_overdue: overdue,
        tasks_due_today: dueToday,
        completed_this_week: completedThisWeek,
        pending_approvals: pendingApprovals + pendingHrReviews,
        operations_approval_queue: operationsApprovalStage,
        business_lead_approval_queue: businessApprovalStage,
        director_approval_queue: directorApprovalStage,
        total_decision_queue: operationsInbox + waitingReview + overdue + pendingApprovals + pendingHrReviews,
        pending_hr_reviews: pendingHrReviews,
        sick_notes_pending: sickNotesPending,
        people_working: 0,
        people_on_leave: peopleOnLeave,
        people_on_site: 0,
        upcoming_deadlines: dueToday + overdue,
        latest_activity: latestTasks.map((task: any) => ({
          title: task.title,
          category: task.category || 'Work',
          description: `${task.status || 'Task'}${task.assigned_employee ? ` - ${task.assigned_employee}` : ''}`,
          created_at: task.updated_at || task.created_at,
        })),
      },
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to load dashboard summary.' };
  }
}));

app.use('/api/dashboard/business-lead', eventHandler(async (event) => {
  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const tasks = db.collection('work_assignments');
    const today = todaySouthAfrica();
    const [
      activeTasks,
      waitingReview,
      overdue,
      inbox,
      workload,
      pendingHrReviews,
      sickNotesPending,
    ] = await Promise.all([
      tasks.countDocuments({ status: { $in: ['Assigned', 'In Progress', 'Waiting Review'] } }),
      tasks.countDocuments({ status: 'Waiting Review' }),
      tasks.countDocuments({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: { $lt: today, $ne: '' } }),
      tasks.countDocuments({ status: { $in: ['Dumped', 'Needs Triage', 'New'] } }),
      tasks.aggregate([
        { $match: { status: { $in: ['Assigned', 'In Progress', 'Waiting Review'] } } },
        {
          $group: {
            _id: '$assigned_employee',
            task_count: { $sum: 1 },
            estimated_hours: { $sum: { $ifNull: ['$estimated_hours', 0] } },
            actual_hours: { $sum: { $ifNull: ['$actual_hours', 0] } },
            active_now: { $sum: { $cond: [{ $ifNull: ['$active_timer_started_at', false] }, 1, 0] } },
            waiting_review: { $sum: { $cond: [{ $eq: ['$status', 'Waiting Review'] }, 1, 0] } },
            overdue: { $sum: { $cond: [{ $and: [{ $ne: ['$due_date', ''] }, { $lt: ['$due_date', today] }] }, 1, 0] } },
          },
        },
        { $sort: { task_count: -1 } },
        { $limit: 8 },
      ]).toArray(),
      db.collection('hr_leave_requests').countDocuments({ status: 'Pending' }).catch(() => 0),
      db.collection('hr_leave_requests').countDocuments({ request_type: 'Sick Leave', status: 'Pending' }).catch(() => 0),
    ]);

    return {
      success: true,
      summary: {
        active_tasks: activeTasks,
        tasks_waiting_review: waitingReview,
        tasks_overdue: overdue,
        operations_inbox: inbox,
        pending_approvals: (await db.collection('approvals').countDocuments({ status: { $in: ['Pending', 'pending'] } }).catch(() => 0)) + pendingHrReviews,
        pending_hr_reviews: pendingHrReviews,
        sick_notes_pending: sickNotesPending,
        workload: workload.filter((row: any) => row._id).map((row: any) => ({
          employee: row._id,
          task_count: row.task_count,
          estimated_hours: row.estimated_hours,
          actual_hours: row.actual_hours,
          active_now: row.active_now,
          waiting_review: row.waiting_review,
          overdue: row.overdue,
          variance_hours: Math.round((Number(row.actual_hours || 0) - Number(row.estimated_hours || 0)) * 100) / 100,
        })),
        business_metrics: `${activeTasks} active tasks | ${waitingReview} waiting review | ${pendingHrReviews} HR reviews | ${overdue} overdue`,
        role: roleName(user, employee),
      },
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to load Business Lead dashboard.' };
  }
}));

app.use('/api/dashboard/director', eventHandler(async (event) => {
  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const tasks = db.collection('work_assignments');
    const today = todaySouthAfrica();
    const [
      inbox,
      overdue,
      dueToday,
      waitingReview,
      pendingApprovals,
      activeEmployees,
      pendingHrReviews,
      sickNotesPending,
      peopleOnLeave,
    ] = await Promise.all([
      tasks.countDocuments({ status: { $in: ['Dumped', 'Needs Triage', 'New'] } }),
      tasks.countDocuments({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: { $lt: today, $ne: '' } }),
      tasks.countDocuments({ status: { $nin: ['Completed', 'Cancelled'] }, due_date: today }),
      tasks.countDocuments({ status: 'Waiting Review' }),
      db.collection('approvals').countDocuments({ status: { $in: ['Pending', 'pending'] } }).catch(() => 0),
      db.collection('employees').countDocuments({ status: { $in: ['active', 'Active', true] } }),
      db.collection('hr_leave_requests').countDocuments({ status: 'Pending' }).catch(() => 0),
      db.collection('hr_leave_requests').countDocuments({ request_type: 'Sick Leave', status: 'Pending' }).catch(() => 0),
      db.collection('hr_leave_requests').countDocuments({ status: 'Approved', start_date: { $lte: today }, end_date: { $gte: today } }).catch(() => 0),
    ]);

    const approvalsTotal = pendingApprovals + pendingHrReviews;
    const attention = approvalsTotal + overdue + inbox;
    return {
      success: true,
      summary: {
        executive_brief: attention
          ? `${attention} items need executive or operations attention.`
          : 'No urgent executive actions are pending.',
        company_health: overdue > 0 ? 'Watch' : 'Stable',
        compliance: approvalsTotal,
        business_metrics: `${inbox} in operations inbox | ${dueToday} due today | ${pendingHrReviews} HR reviews | ${overdue} overdue`,
        inventory_alerts: 0,
        upcoming_deadlines: dueToday + overdue,
        attendance_summary: `${activeEmployees} active employees in the system | ${peopleOnLeave} on leave today`,
        financial_requests_waiting: pendingApprovals,
        pending_approvals: approvalsTotal,
        pending_hr_reviews: pendingHrReviews,
        sick_notes_pending: sickNotesPending,
        people_on_leave: peopleOnLeave,
        operations_inbox: inbox,
        tasks_overdue: overdue,
        tasks_due_today: dueToday,
        tasks_waiting_review: waitingReview,
        role: roleName(user, employee),
      },
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to load Director dashboard.' };
  }
}));

app.use('/api/calendar/events', eventHandler(async (event) => {
  try {
    const { db, user, employee } = await requireDesktopSession(event);
    const role = roleName(user, employee);
    const events = db.collection('calendar_events');

    if (event.method === 'POST') {
      const body = await readBody(event);
      const now = new Date();
      const title = String(body?.title || '').trim();
      const startDate = String(body?.start_date || '').trim();
      if (!title || !startDate) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Title and start date are required.' };
      }

      const doc = {
        title,
        event_type: String(body?.event_type || 'Other'),
        start_date: startDate,
        end_date: String(body?.end_date || ''),
        department: String(body?.department || employee?.department || ''),
        details: String(body?.details || ''),
        source_type: 'Manual',
        source_id: null,
        recurrence: String(body?.recurrence || 'None'),
        created_by: user?._id,
        created_by_name: employeeDisplayName(employee, user),
        created_at: now,
        updated_at: now,
      };
      const inserted = await events.insertOne(doc);
      return { success: true, event: serialiseCalendarEvent({ ...doc, _id: inserted.insertedId }) };
    }

    if (event.method === 'GET') {
      const query = getQuery(event);
      const year = Number(query.year || new Date().getFullYear());
      const month = Number(query.month || new Date().getMonth() + 1);
      const start = String(query.start || `${year}-${String(month).padStart(2, '0')}-01`);
      const lastDay = new Date(year, month, 0).getDate();
      const end = String(query.end || `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`);
      const department = String(query.department || '');

      const manualFilter: any = {
        start_date: { $lte: end },
        $or: [{ end_date: { $gte: start } }, { end_date: '' }, { end_date: { $exists: false } }],
      };
      if (department && department !== 'All') manualFilter.department = department;

      const manual = await events.find(manualFilter).sort({ start_date: 1 }).limit(300).toArray();
      const taskFilter: any = {
        status: { $nin: ['Completed', 'Cancelled'] },
        due_date: { $gte: start, $lte: end },
      };
      if (department && department !== 'All') taskFilter.department = department;

      const tasks = await db.collection('work_assignments').find(taskFilter).limit(500).toArray();
      const approvals = await db.collection('approvals')
        .find({ status: { $in: ['Pending', 'pending'] }, due_date: { $gte: start, $lte: end } })
        .limit(200)
        .toArray()
        .catch(() => []);
      const leaveRequests = await db.collection('hr_leave_requests')
        .find({
          status: 'Approved',
          start_date: { $lte: end },
          end_date: { $gte: start },
        })
        .limit(300)
        .toArray()
        .catch(() => []);

      const derivedTaskEvents = tasks
        .filter((task: any) => dateInRange(task.due_date, start, end))
        .map((task: any) => serialiseCalendarEvent({
          _id: task._id,
          title: task.title,
          event_type: taskEventType(task),
          start_date: task.due_date,
          end_date: '',
          department: task.department,
          details: task.description || `${task.status || 'Task'}${task.assigned_employee ? ` - ${task.assigned_employee}` : ''}`,
          source_type: 'Task',
          source_id: task._id,
          recurrence: 'None',
          created_at: task.created_at,
        }));

      const approvalEvents = approvals.map((approval: any) => serialiseCalendarEvent({
        _id: approval._id,
        title: approval.title || approval.request_type || 'Approval Required',
        event_type: 'Approval Deadline',
        start_date: approval.due_date,
        end_date: '',
        department: approval.department || '',
        details: approval.description || 'Approval waiting for action.',
        source_type: 'Approval',
        source_id: approval._id,
        recurrence: 'None',
        created_at: approval.created_at || approval.submitted_at,
      }));

      const leaveEvents = leaveRequests.map((request: any) => serialiseCalendarEvent({
        _id: request._id,
        title: `${request.request_type || 'Leave'}: ${request.employee_name || 'Employee'}`,
        event_type: request.request_type === 'Sick Leave' ? 'Sick Leave' : 'Leave',
        start_date: request.start_date,
        end_date: request.end_date || request.start_date,
        department: request.department || '',
        details: request.reason || '',
        source_type: 'HR',
        source_id: request._id,
        recurrence: 'None',
        created_at: request.created_at,
      }));

      const all = manual.map(serialiseCalendarEvent).concat(derivedTaskEvents, approvalEvents, leaveEvents)
        .filter(Boolean)
        .sort((a: any, b: any) => String(a.start_date).localeCompare(String(b.start_date)) || String(a.title).localeCompare(String(b.title)));

      return { success: true, events: all, count: all.length, role };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Calendar operation failed.' };
  }
}));

app.use('/api/calendar/events/:id', eventHandler(async (event) => {
  try {
    const { db } = await requireDesktopSession(event);
    const id = event.context.params?.id;
    const oid = taskObjectId(id);
    if (!oid) {
      event.node.res.statusCode = 400;
      return { success: false, error: 'Manual event id is invalid.' };
    }

    const collection = db.collection('calendar_events');
    const existing = await collection.findOne({ _id: oid, source_type: 'Manual' });
    if (!existing) {
      event.node.res.statusCode = 404;
      return { success: false, error: 'Manual calendar event not found.' };
    }

    if (event.method === 'PUT' || event.method === 'PATCH') {
      const body = await readBody(event);
      const update = {
        title: String(body?.title || existing.title || '').trim(),
        event_type: String(body?.event_type || existing.event_type || 'Other'),
        start_date: String(body?.start_date || existing.start_date || '').trim(),
        end_date: String(body?.end_date || ''),
        department: String(body?.department || existing.department || ''),
        details: String(body?.details || ''),
        recurrence: String(body?.recurrence || 'None'),
        updated_at: new Date(),
      };
      await collection.updateOne({ _id: oid }, { $set: update });
      return { success: true, event: serialiseCalendarEvent(await collection.findOne({ _id: oid })) };
    }

    if (event.method === 'DELETE') {
      await collection.deleteOne({ _id: oid, source_type: 'Manual' });
      return { success: true };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Calendar event operation failed.' };
  }
}));

async function attendanceAction(event: any, action: string) {
  const { db, employee, user } = await requireDesktopSession(event);
  const collection = db.collection('attendance');
  const employeeId = employee._id;
  const employeeName = employeeDisplayName(employee, user);
  const now = new Date();
  const workDate = todaySouthAfrica();
  let record = await getTodayAttendance(db, employeeId);

  if (action === 'status') {
    let state = 'not_started';
    let elapsed = 0;
    if (record?.clock_out_at) {
      state = 'completed';
      elapsed = Number(record.hours_worked || 0) * 3600;
    } else if (record?.break_started_at) {
      state = 'on_break';
      elapsed = netElapsedSeconds(record, now);
    } else if (record?.clock_in_at) {
      state = 'working';
      elapsed = netElapsedSeconds(record, now);
    }
    return {
      success: true,
      server_time: now.toISOString(),
      state,
      status: record?.status || 'not_started',
      elapsed_seconds: Math.round(elapsed * 100) / 100,
      elapsed_hours: Math.round((elapsed / 3600) * 100) / 100,
      clock_in_at: record?.clock_in_at || null,
      clock_out_at: record?.clock_out_at || null,
      break_started_at: record?.break_started_at || null,
      break_duration_minutes: Number(record?.break_duration_minutes || 0),
      record: serialiseAttendance(record),
    };
  }

  if (action === 'clock_in') {
    if (record?.clock_in_at && !record?.clock_out_at) throw Object.assign(new Error('Employee is already clocked in.'), { statusCode: 409 });
    if (record?.clock_out_at) throw Object.assign(new Error('Employee has already clocked out today.'), { statusCode: 409 });
    const doc = {
      employee_id: employeeId,
      employee_name: employeeName,
      work_date: workDate,
      clock_in_at: now,
      clock_out_at: null,
      break_started_at: null,
      break_ended_at: null,
      break_duration_minutes: 0,
      lunch_started_at: null,
      lunch_ended_at: null,
      lunch_duration_minutes: 0,
      hours_worked: 0,
      status: 'clocked_in',
      created_at: now,
      updated_at: now,
    };
    if (record) {
      await collection.updateOne({ _id: record._id }, { $set: doc });
      record = { ...record, ...doc };
    } else {
      const inserted = await collection.insertOne(doc);
      record = { ...doc, _id: inserted.insertedId };
    }
    return { success: true, server_time: now.toISOString(), message: 'Clocked in.', record: serialiseAttendance(record) };
  }

  if (action === 'clock_out') {
    if (!record?.clock_in_at) throw Object.assign(new Error('Employee has not clocked in.'), { statusCode: 400 });
    if (record.clock_out_at) throw Object.assign(new Error('Employee has already clocked out.'), { statusCode: 409 });
    if (record.break_started_at) throw Object.assign(new Error('End the active break before clocking out.'), { statusCode: 400 });
    if (record.lunch_started_at && !record.lunch_ended_at) throw Object.assign(new Error('End lunch before clocking out.'), { statusCode: 400 });
    const hours = Math.round((netElapsedSeconds(record, now) / 3600) * 100) / 100;
    const update = { clock_out_at: now, hours_worked: hours, status: 'clocked_out', updated_at: now };
    await collection.updateOne({ _id: record._id }, { $set: update });
    record = { ...record, ...update };
    return { success: true, server_time: now.toISOString(), message: 'Clocked out.', record: serialiseAttendance(record) };
  }

  if (action === 'break_start') {
    if (!record?.clock_in_at) throw Object.assign(new Error('Clock in before starting a break.'), { statusCode: 400 });
    if (record.clock_out_at) throw Object.assign(new Error('Employee has already clocked out.'), { statusCode: 400 });
    if (record.break_started_at) throw Object.assign(new Error('A break is already in progress.'), { statusCode: 409 });
    const update = { break_started_at: now, break_ended_at: null, status: 'on_break', updated_at: now };
    await collection.updateOne({ _id: record._id }, { $set: update });
    record = { ...record, ...update };
    return { success: true, server_time: now.toISOString(), message: 'Break started.', record: serialiseAttendance(record) };
  }

  if (action === 'break_end') {
    if (!record?.break_started_at) throw Object.assign(new Error('No active break was found.'), { statusCode: 400 });
    const extra = elapsedSeconds(record.break_started_at, now) / 60;
    const total = Math.round((Number(record.break_duration_minutes || 0) + extra) * 100) / 100;
    const update = { break_ended_at: now, break_duration_minutes: total, status: 'clocked_in', updated_at: now };
    await collection.updateOne(
      { _id: record._id },
      { $set: update, $unset: { break_started_at: '' } },
    );
    record = { ...record, ...update, break_started_at: null };
    return { success: true, server_time: now.toISOString(), message: 'Break ended.', record: serialiseAttendance(record) };
  }

  throw Object.assign(new Error('Unknown attendance action.'), { statusCode: 400 });
}

for (const [path, action, method] of [
  ['/api/attendance/status', 'status', 'GET'],
  ['/api/attendance/clock-in', 'clock_in', 'POST'],
  ['/api/attendance/clock-out', 'clock_out', 'POST'],
  ['/api/attendance/break/start', 'break_start', 'POST'],
  ['/api/attendance/break/end', 'break_end', 'POST'],
] as const) {
  app.use(path, eventHandler(async (event) => {
    if (event.method !== method) {
      event.node.res.statusCode = 405;
      return { success: false, error: 'Method not allowed' };
    }
    try {
      return await attendanceAction(event, action);
    } catch (error: any) {
      event.node.res.statusCode = error?.statusCode || 500;
      console.error(`Desktop attendance ${action} error:`, error?.message || error);
      return { success: false, error: error?.message || 'Attendance operation failed.' };
    }
  }));
}

app.use('/api/attendance/today', eventHandler(async (event) => {
  try {
    const { db, employee } = await requireDesktopSession(event);
    const record = await getTodayAttendance(db, employee._id);
    return { success: true, attendance: serialiseAttendance(record) };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to read attendance.' };
  }
}));

// ============================================
// START SERVER
// ============================================

async function startServer() {
  await connectDB();
  
  const server = createServer(toNodeListener(app));
  server.listen(config.port, '0.0.0.0', () => {
    console.log(`\n🚀 Server running on http://localhost:${config.port}`);
    console.log(`🛠️ Assignment API: PUT/POST/PATCH /api/admin/quotes/:reference/assignment`);
    console.log(`🛠️ Assignment aliases: /assign, /assign-employee, /assignment/employee`);
    console.log(`🧩 Assignment dispatcher: UNIVERSAL-FIXED-v2`);
    console.log(`📡 API available at http://localhost:${config.port}/api`);
    console.log(`🏥 Health check: http://localhost:${config.port}/api/health`);
    console.log(`🔍 Track Quote API: http://localhost:${config.port}/api/quotes/track?ref=UQ-XXXXXX&email=you@email.com`);
    console.log(`📋 Quotes API: http://localhost:${config.port}/api/quotes`);
    console.log(`💬 Feedback API: http://localhost:${config.port}/api/quotes/feedback`);
    console.log(`💳 Payment API: http://localhost:${config.port}/api/quotes/payment`);
    console.log(`🔍 Track Order API: http://localhost:${config.port}/api/orders/track?ref=ORD-XXXXXX&email=you@email.com`);
    console.log(`📋 Orders API: http://localhost:${config.port}/api/orders`);
    console.log(`🔧 Admin API: http://localhost:${config.port}/api/admin/quotes/:reference`);
    console.log(`💳 Set Payment: http://localhost:${config.port}/api/admin/quotes/:reference/payment`);
    console.log(`💰 Extract Payment: http://localhost:${config.port}/api/admin/quotes/:reference/extract-payment`);
    console.log(`🔄 Set Status: http://localhost:${config.port}/api/admin/quotes/:reference/status`);
    console.log(`🔄 Simulate Payment: http://localhost:${config.port}/api/payment/simulate/:reference`);
    console.log(`💾 Storage mode: ${isMongoConnected ? 'MongoDB ✅' : 'In-Memory ⚠️'}`);
    console.log(`\n✅ Server is ready!\n`);
  });
}

startServer();
