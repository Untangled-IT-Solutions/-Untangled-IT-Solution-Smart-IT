// WEBSITE BACKEND ENTRY — server/index.ts
// Public commerce routes stay here. Legacy desktop routes are retained for
// compatibility; the canonical Nexus backend is ../untangled-nexus-api-main.
// See ../ARCHITECTURE.md before changing route ownership or deployments.

// Backend/server/index-desktop.ts
import { createServer } from 'node:http';
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import crypto from 'node:crypto';
import { randomUUID } from 'node:crypto';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { config as sharedConfig, assertProductionConfig } from './config/index.js';
import { securityMiddleware, rateLimitOrNull } from './middleware/security.js';
import { performanceMiddleware } from './middleware/performance.js';

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
    enum: [
      'received', 'in_review', 'quoted', 'closed', 'pending', 'waiting_feedback',
      'in_touch', 'approved', 'payment', 'assigned', 'accepted', 'in_progress',
      'awaiting_client', 'awaiting_payment', 'awaiting_director', 'paid',
      'completed', 'returned', 'rejected'
    ],
    default: 'received'
  },
  replyMessage: String,
  repliedAt: Date,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now },
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
  assignedEmployeeId: { type: mongoose.Schema.Types.Mixed, default: null },
  assignedAt: { type: Date },
  history: { type: [mongoose.Schema.Types.Mixed], default: [] },
  directorReview: { type: mongoose.Schema.Types.Mixed, default: null },
  progress: { type: Number },
  completed_at: { type: Date },
  completed_by: { type: String },
  accepted_at: { type: Date },
  accepted_by: { type: String },
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
    // Must match Work desktop Order Management statuses
    enum: [
      'pending',
      'confirmed',
      'processing',
      'assigned',
      'in_progress',
      'ready',
      'awaiting_payment',
      'paid',
      'shipped',
      'delivered',
      'completed',
      'cancelled',
    ],
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


async function ensurePerformanceIndexes() {
  const db = mongoose.connection.db;
  if (!db) return;

  // Atlas may already contain indexes created by the previous API version.
  // Match indexes by key pattern before creating anything, so a different
  // index name (for example status_1 vs approvals_status_1) never causes
  // IndexOptionsConflict and never forces the API into in-memory mode.
  const ensureIndex = async (collectionName: string, keys: Record<string, 1 | -1>, name: string) => {
    const collection = db.collection(collectionName);
    const existing = await collection.listIndexes().toArray();
    const key = JSON.stringify(keys);
    const sameKey = existing.find((index: any) => JSON.stringify(index.key) === key);
    if (sameKey) return sameKey.name;
    try {
      return await collection.createIndex(keys, { name });
    } catch (error: any) {
      // Another API process may create the same index at the same time.
      // Treat an existing equivalent index as success instead of falling
      // back to in-memory storage.
      if (error?.code === 85 || error?.codeName === 'IndexOptionsConflict' || error?.codeName === 'IndexKeySpecsConflict') {
        const after = await collection.listIndexes().toArray();
        const equivalent = after.find((index: any) => JSON.stringify(index.key) === key);
        if (equivalent) return equivalent.name;
      }
      throw error;
    }
  };

  await Promise.all([
    ensureIndex('users', { username: 1 }, 'users_username_1'),
    ensureIndex('users', { email: 1 }, 'users_email_1'),
    ensureIndex('users', { employee_id: 1 }, 'users_employee_id_1'),
    ensureIndex('api_sessions', { token: 1 }, 'api_sessions_token_1'),
    ensureIndex('api_sessions', { user_id: 1, status: 1 }, 'api_sessions_user_status'),
    ensureIndex('employees', { employee_id: 1 }, 'employees_employee_id_1'),
    ensureIndex('employees', { email: 1 }, 'employees_email_1'),
    ensureIndex('employees', { status: 1 }, 'employees_status_1'),
    ensureIndex('attendance', { employee_id: 1, work_date: 1 }, 'attendance_employee_date'),
    ensureIndex('attendance', { work_date: 1, clock_out_at: 1, status: 1 }, 'attendance_open_today'),
    ensureIndex('work_assignments', { due_date: 1, status: 1 }, 'work_due_status'),
    ensureIndex('approvals', { status: 1 }, 'approvals_status_1'),
  ]);
}

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
      maxPoolSize: Number(process.env.MONGODB_MAX_POOL_SIZE || 20),
      minPoolSize: Number(process.env.MONGODB_MIN_POOL_SIZE || 5),
      maxIdleTimeMS: Number(process.env.MONGODB_MAX_IDLE_TIME_MS || 30000),
      serverSelectionTimeoutMS: Number(process.env.MONGODB_SERVER_SELECTION_TIMEOUT_MS || 5000),
      socketTimeoutMS: Number(process.env.MONGODB_SOCKET_TIMEOUT_MS || 10000),
      connectTimeoutMS: Number(process.env.MONGODB_CONNECT_TIMEOUT_MS || 5000),
      family: 4,
      // Local MongoDB does not use TLS; Atlas SRV connections can enable it via
      // the connection URI itself. Keep TLS configurable instead of forcing it.
      ...(process.env.MONGODB_TLS === 'true' ? {
        tls: true,
        tlsAllowInvalidCertificates: false,
        tlsAllowInvalidHostnames: false,
      } : {}),
    };

    console.log('🔧 Connection options:', {
      tls: mongoOptions.tls,
      tlsAllowInvalidCertificates: mongoOptions.tlsAllowInvalidCertificates,
      tlsAllowInvalidHostnames: mongoOptions.tlsAllowInvalidHostnames,
      serverSelectionTimeoutMS: mongoOptions.serverSelectionTimeoutMS,
    });

    await mongoose.connect(config.mongoUri, mongoOptions);
    await ensurePerformanceIndexes();

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

// Security middleware (CORS allow-list + security headers)
app.use(eventHandler(async (event) => {
  await securityMiddleware(event);
}));

app.use(eventHandler((event) => {
  performanceMiddleware(event);
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
  const limited = rateLimitOrNull(event, 'track');
  if (limited) {
    event.node.res.statusCode = limited.statusCode;
    return limited.body;
  }

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
  const limited = rateLimitOrNull(event, 'write');
  if (limited) {
    event.node.res.statusCode = limited.statusCode;
    return limited.body;
  }

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
          company: q.company || '',
          email: q.email,
          phone: q.phone || '',
          notes: q.notes || '',
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
  const limited = rateLimitOrNull(event, 'write');
  if (limited) {
    event.node.res.statusCode = limited.statusCode;
    return limited.body;
  }

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
          company: o.company || '',
          email: o.email,
          phone: o.phone || '',
          address: o.address || '',
          notes: o.notes || '',
          status: o.status,
          total: o.total,
          createdAt: o.createdAt,
          updatedAt: o.updatedAt || o.createdAt,
          items: o.items,
          trackingNumber: o.trackingNumber || null,
          carrier: o.carrier || null,
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
  // h3 may strip the mount prefix, so path can be either:
  //   /api/admin/quotes/UQ-XXX/assignment
  //   /UQ-XXX/assignment
  const pathname = rawUrl.split('?')[0];

  const match =
    pathname.match(
      /^\/api\/admin\/quotes\/([^/]+)\/(assignment|assign|assign-employee|assign_employee|assignment\/employee)\/?$/
    ) ||
    pathname.match(
      /^\/([^/]+)\/(assignment|assign|assign-employee|assign_employee|assignment\/employee)\/?$/
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
          error: `Employee is inactive: ${employeeDisplayName(employee)}`,
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
  // Desktop client tries PUT / POST / PATCH — accept all three.
  if (!['POST', 'PUT', 'PATCH'].includes(event.method || '')) {
    event.node.res.statusCode = 405;
    return { success: false, message: 'Method not allowed' };
  }
  try {
    const reference = event.context.params?.reference;
    const body = await readBody(event) || {};

    console.log(`🔄 Updating status for: ${reference} via ${event.method}`);

    if (!reference) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Reference is required' };
    }

    const status = body.status ?? body.newStatus ?? body.quoteStatus;
    if (!status) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Status is required' };
    }

    let quote = null;

    if (isMongoConnected) {
      quote = await Quote.findOne({ reference: String(reference).toUpperCase() });
      if (!quote) {
        event.node.res.statusCode = 404;
        return { success: false, message: 'Quote not found' };
      }

      const previous = quote.status;
      quote.status = status;
      quote.updatedAt = new Date();
      if (!Array.isArray((quote as any).history)) (quote as any).history = [];
      (quote as any).history.push({
        action: 'status_change',
        from: previous,
        to: status,
        by: body.by || body.username || 'api',
        time: new Date().toISOString(),
      });
      await quote.save();
      console.log(`✅ Status updated for ${reference}: ${previous} → ${status}`);
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
    event.node.res.statusCode = 500;
    return { success: false, message: 'Failed to update status' };
  }
}));

// Alias used by some desktop builds: /api/quotes/:reference/status
app.use('/api/quotes/:reference/status', eventHandler(async (event) => {
  if (!['POST', 'PUT', 'PATCH'].includes(event.method || '')) {
    event.node.res.statusCode = 405;
    return { success: false, message: 'Method not allowed' };
  }
  try {
    const reference = event.context.params?.reference;
    const body = await readBody(event) || {};
    if (!reference) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Reference is required' };
    }
    const status = body.status ?? body.newStatus ?? body.quoteStatus;
    if (!status) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Status is required', error: 'Missing required fields' };
    }
    let quote = null;
    if (isMongoConnected) {
      quote = await Quote.findOne({ reference: String(reference).toUpperCase() });
      if (!quote) {
        event.node.res.statusCode = 404;
        return { success: false, message: 'Quote not found' };
      }
      quote.status = status;
      quote.updatedAt = new Date();
      await quote.save();
    }
    return {
      success: true,
      message: `Status updated to ${status}`,
      quote: quote ? { reference: quote.reference, status: quote.status } : null,
    };
  } catch (error) {
    console.error('❌ Error updating quote status (public path):', error);
    event.node.res.statusCode = 500;
    return { success: false, message: 'Failed to update status' };
  }
}));

// Director review workflow used by desktop Quote Management
app.use('/api/admin/quotes/:reference/director-review/request', eventHandler(async (event) => {
  if (event.method !== 'POST') {
    event.node.res.statusCode = 405;
    return { success: false, message: 'Method not allowed' };
  }
  try {
    const reference = event.context.params?.reference;
    const body = await readBody(event) || {};
    if (!reference) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Reference is required' };
    }
    if (!isMongoConnected) {
      event.node.res.statusCode = 503;
      return { success: false, message: 'Database unavailable' };
    }
    const quote = await Quote.findOne({ reference: String(reference).toUpperCase() });
    if (!quote) {
      event.node.res.statusCode = 404;
      return { success: false, message: 'Quote not found' };
    }
    const previous = quote.status;
    quote.status = body.status || 'awaiting_director' || 'in_review';
    (quote as any).directorReview = {
      ...(quote as any).directorReview,
      requestedAt: new Date(),
      requestedBy: body.by || body.username || body.requestedBy || null,
      note: body.note || body.message || null,
      status: 'requested',
    };
    quote.updatedAt = new Date();
    if (!Array.isArray((quote as any).history)) (quote as any).history = [];
    (quote as any).history.push({
      action: 'director_review_requested',
      from: previous,
      to: quote.status,
      by: body.by || body.username || 'api',
      time: new Date().toISOString(),
    });
    await quote.save();
    return {
      success: true,
      message: 'Director review requested',
      quote: { reference: quote.reference, status: quote.status },
    };
  } catch (error) {
    console.error('❌ director-review/request error:', error);
    event.node.res.statusCode = 500;
    return { success: false, message: 'Failed to request director review' };
  }
}));

app.use('/api/admin/quotes/:reference/director-review', eventHandler(async (event) => {
  if (!['PUT', 'POST', 'PATCH'].includes(event.method || '')) {
    event.node.res.statusCode = 405;
    return { success: false, message: 'Method not allowed' };
  }
  try {
    const reference = event.context.params?.reference;
    const body = await readBody(event) || {};
    if (!reference) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Reference is required' };
    }
    if (!isMongoConnected) {
      event.node.res.statusCode = 503;
      return { success: false, message: 'Database unavailable' };
    }
    const quote = await Quote.findOne({ reference: String(reference).toUpperCase() });
    if (!quote) {
      event.node.res.statusCode = 404;
      return { success: false, message: 'Quote not found' };
    }
    const previous = quote.status;
    if (body.status) quote.status = body.status;
    (quote as any).directorReview = {
      ...(quote as any).directorReview,
      reviewedAt: new Date(),
      reviewedBy: body.by || body.username || body.reviewedBy || null,
      availability: body.availability || body.items || null,
      reply: body.reply || body.message || body.generalReply || null,
      status: body.reviewStatus || 'completed',
    };
    if (body.replyMessage) {
      quote.replyMessage = body.replyMessage;
      quote.repliedAt = new Date();
    }
    quote.updatedAt = new Date();
    if (!Array.isArray((quote as any).history)) (quote as any).history = [];
    (quote as any).history.push({
      action: 'director_review_submitted',
      from: previous,
      to: quote.status,
      by: body.by || body.username || 'api',
      time: new Date().toISOString(),
    });
    await quote.save();
    return {
      success: true,
      message: 'Director review submitted',
      quote: { reference: quote.reference, status: quote.status },
    };
  } catch (error) {
    console.error('❌ director-review error:', error);
    event.node.res.statusCode = 500;
    return { success: false, message: 'Failed to submit director review' };
  }
}));

// Order status updates (desktop uses PATCH /api/orders/status with body)
app.use('/api/orders/status', eventHandler(async (event) => {
  if (!['PATCH', 'POST', 'PUT'].includes(event.method || '')) {
    event.node.res.statusCode = 405;
    return { success: false, message: 'Method not allowed for /api/orders' };
  }
  try {
    const body = await readBody(event) || {};
    const reference = typeof body?.reference === 'string' ? body.reference.trim().toUpperCase() : '';
    const status = typeof body?.status === 'string' ? body.status.trim().toLowerCase() : '';
    if (!reference || !status) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Reference and status are required' };
    }
    const allowed = new Set(['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'received', 'in_progress', 'completed']);
    if (!allowed.has(status)) {
      event.node.res.statusCode = 400;
      return { success: false, message: 'Invalid order status' };
    }
    if (!isMongoConnected) {
      event.node.res.statusCode = 503;
      return { success: false, message: 'Database unavailable' };
    }
    const update: Record<string, unknown> = { status, updatedAt: new Date() };
    if (body.trackingNumber !== undefined) update.trackingNumber = body.trackingNumber || null;
    if (body.carrier !== undefined) update.carrier = body.carrier || null;
    const order = await Order.findOneAndUpdate(
      { reference },
      { $set: update },
      { new: true }
    );
    if (!order) {
      event.node.res.statusCode = 404;
      return { success: false, message: 'Order not found' };
    }
    return {
      success: true,
      message: 'Order status updated',
      order: {
        reference: order.reference,
        status: order.status,
        trackingNumber: (order as any).trackingNumber || null,
        carrier: (order as any).carrier || null,
      },
    };
  } catch (error) {
    console.error('❌ Order status update error:', error);
    event.node.res.statusCode = 500;
    return { success: false, message: 'Failed to update order status' };
  }
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


/** Close open attendance from previous work days (missed clock-out).
 *  Closes at 18:00 Africa/Johannesburg on that work_date (or now if earlier data missing).
 */
async function autoCloseStaleAttendance(db: any, employeeId: any) {
  const today = todaySouthAfrica();
  const values = employeeReferenceValues(employeeId);
  const open = await db.collection('attendance').find({
    employee_id: { $in: values },
    work_date: { $lt: today },
    clock_in_at: { $exists: true, $nin: [null, ''] },
    $or: [
      { clock_out_at: { $exists: false } },
      { clock_out_at: null },
      { clock_out_at: '' },
    ],
  }).toArray();

  for (const record of open) {
    const workDate = String(record.work_date || '').slice(0, 10);
    // Default end-of-day 18:00 SAST = 16:00 UTC
    let end = new Date(`${workDate}T16:00:00.000Z`);
    const clockIn = record.clock_in_at ? new Date(record.clock_in_at) : null;
    if (clockIn && end.getTime() <= clockIn.getTime()) {
      end = new Date(clockIn.getTime() + 8 * 3600 * 1000); // at least 8h after clock-in
    }
    const hours = Math.round((netElapsedSeconds(record, end) / 3600) * 100) / 100;
    await db.collection('attendance').updateOne(
      { _id: record._id },
      {
        $set: {
          clock_out_at: end,
          hours_worked: hours,
          status: 'clocked_out',
          auto_closed: true,
          updated_at: new Date(),
        },
        $unset: { break_started_at: '' },
      },
    );
    console.log(`⏱️ Auto-closed missed clock-out for employee ${employeeId} on ${workDate} (${hours}h)`);
  }
}

async function getTodayAttendance(db: any, employeeId: any) {
  const values = employeeReferenceValues(employeeId);
  return db.collection('attendance').findOne({
    employee_id: { $in: values },
    work_date: todaySouthAfrica(),
  });
}

function employeeDisplayName(employee: any, user: any = null): string {
  return employee?.full_name ||
    [employee?.first_name, employee?.surname || employee?.last_name].filter(Boolean).join(' ') ||
    user?.full_name || user?.username || user?.email || 'Employee';
}

app.use('/api/auth/login', eventHandler(async (event) => {
  const limited = rateLimitOrNull(event, 'auth');
  if (limited) {
    event.node.res.statusCode = limited.statusCode;
    return limited.body;
  }

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

async function attendanceAction(event: any, action: string) {
  const { db, employee, user } = await requireDesktopSession(event);
  const collection = db.collection('attendance');
  const employeeId = employee._id;
  const employeeName = employeeDisplayName(employee, user);
  const now = new Date();
  const workDate = todaySouthAfrica();
  let record = await getTodayAttendance(db, employeeId);

  if (action === 'status') {
    await autoCloseStaleAttendance(db, employeeId);
    record = await getTodayAttendance(db, employeeId);
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
    await autoCloseStaleAttendance(db, employeeId);
    record = await getTodayAttendance(db, employeeId);
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
// DASHBOARD SUMMARY (attendance = Mongo only)
// ============================================

async function dashboardSummary() {
  const db = mongoRequired();
  const today = todaySouthAfrica();
  const attendance = db.collection('attendance');
  const employees = db.collection('employees');
  const tasks = db.collection('work_assignments');
  const approvals = db.collection('approvals');

  // Strict: distinct employees with a real open clock-in TODAY.
  // Never use employees.clocked_in flags.
  const activeAttendanceQuery: any = {
    work_date: today,
    employee_id: { $exists: true, $nin: [null, ''] },
    clock_in_at: { $exists: true, $nin: [null, ''] },
    $and: [
      {
        $or: [
          { clock_out_at: { $exists: false } },
          { clock_out_at: null },
          { clock_out_at: '' },
        ],
      },
      {
        $or: [
          { status: { $in: ['clocked_in', 'on_break', 'Clocked In', 'On Break'] } },
          { status: { $exists: false } },
          { status: null },
          { status: '' },
        ],
      },
    ],
  };

  const activeIds = await attendance.distinct('employee_id', activeAttendanceQuery);
  const peopleWorking = new Set(
    (activeIds || [])
      .filter((id: any) => id !== null && id !== undefined && String(id).trim() !== '')
      .map((id: any) => String(id))
  ).size;

  const [
    totalEmployees,
    activeEmployees,
    tasksDueToday,
    tasksOverdue,
    tasksWaitingReview,
    tasksInProgress,
    pendingTasks,
    pendingApprovals,
  ] = await Promise.all([
    employees.countDocuments({}),
    employees.countDocuments({ status: { $in: ['Active', 'active', 'enabled', 'approved'] } }),
    tasks.countDocuments({
      due_date: { $gte: new Date(`${today}T00:00:00.000Z`), $lt: new Date(`${today}T23:59:59.999Z`) },
      status: { $nin: ['Completed', 'Cancelled', 'Canceled', 'Closed', 'closed', 'Done', 'done'] },
    }),
    tasks.countDocuments({
      due_date: { $lt: new Date() },
      status: { $nin: ['Completed', 'Cancelled', 'Canceled', 'Closed', 'closed', 'Done', 'done'] },
    }),
    tasks.countDocuments({ status: { $in: ['Waiting Review', 'waiting review', 'Waiting for Review', 'waiting_for_review'] } }),
    tasks.countDocuments({ status: { $in: ['In Progress', 'in progress', 'in_progress'] } }),
    tasks.countDocuments({ status: { $in: ['New', 'new', 'Assigned', 'assigned', 'In Progress', 'in progress', 'in_progress', 'Waiting Review', 'waiting review'] } }),
    approvals.countDocuments({ status: { $in: ['Pending', 'pending'] } }),
  ]);

  return {
    success: true,
    people_working: peopleWorking,
    people_on_leave: await employees.countDocuments({ status: { $in: ['On Leave', 'on leave', 'Leave', 'leave'] } }),
    people_on_site: peopleWorking,
    tasks_due_today: tasksDueToday,
    tasks_overdue: tasksOverdue,
    tasks_waiting_review: tasksWaitingReview,
    completed_this_week: 0,
    pending_approvals: pendingApprovals,
    upcoming_deadlines: tasksDueToday,
    latest_activity: [],
    total_employees: totalEmployees,
    active_employees: activeEmployees,
    tasks_in_progress: tasksInProgress,
    pending_tasks: pendingTasks,
    // Debug aid: how many open attendance docs matched (not distinct people)
    _debug_open_attendance_docs: await attendance.countDocuments(activeAttendanceQuery),
    _debug_work_date: today,
  };
}

app.use('/api/dashboard/summary', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  try {
    await requireDesktopSession(event);
    return await dashboardSummary();
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    console.error('Desktop dashboard summary error:', error?.message || error);
    return { success: false, error: error?.message || 'Unable to load dashboard.' };
  }
}));


app.use('/api/attendance/history', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  try {
    const { db, employee } = await requireDesktopSession(event);
    const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
    const daysParam = parseInt(url.searchParams.get('days') || '30', 10);
    const days = Number.isFinite(daysParam) ? Math.min(Math.max(daysParam, 1), 90) : 30;

    const today = todaySouthAfrica();
    // Inclusive window: today minus (days-1)
    const start = new Date(`${today}T12:00:00.000Z`);
    start.setUTCDate(start.getUTCDate() - (days - 1));
    const startDate = start.toISOString().slice(0, 10);

    const values = employeeReferenceValues(employee._id);
    const records = await db.collection('attendance')
      .find({
        employee_id: { $in: values },
        work_date: { $gte: startDate, $lte: today },
      })
      .sort({ work_date: -1, clock_in_at: -1 })
      .limit(90)
      .toArray();

    return {
      success: true,
      work_date_from: startDate,
      work_date_to: today,
      count: records.length,
      records: records.map((r: any) => serialiseAttendance(r)),
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to load attendance history.' };
  }
}));

app.use('/api/attendance/working-now', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  try {
    await requireDesktopSession(event);
    const db = mongoRequired();
    const today = todaySouthAfrica();
    const query: any = {
      work_date: today,
      employee_id: { $exists: true, $nin: [null, ''] },
      clock_in_at: { $exists: true, $nin: [null, ''] },
      $or: [
        { clock_out_at: { $exists: false } },
        { clock_out_at: null },
        { clock_out_at: '' },
      ],
    };
    const rows = await db.collection('attendance').find(query).limit(200).toArray();
    return {
      success: true,
      work_date: today,
      count: rows.length,
      records: rows.map((r: any) => ({
        employee_id: r.employee_id?.toString?.() ?? r.employee_id,
        employee_name: r.employee_name || null,
        status: r.status || null,
        clock_in_at: r.clock_in_at || null,
        clock_out_at: r.clock_out_at ?? null,
        work_date: r.work_date,
      })),
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Unable to list working attendance.' };
  }
}));

// ============================================
// START SERVER
// ============================================

async function startServer() {
  await connectDB();

  const server = createServer(toNodeListener(app));

// ============================================================
// ORDER ASSIGNMENT (same pattern as quotes; h3 strips mount prefix)
// ============================================================
app.use('/api/admin/orders', eventHandler(async (event) => {
  const method = String(event.method || '').toUpperCase();
  const rawUrl = String(event.node.req.url || '');
  const pathname = rawUrl.split('?')[0];

  const match =
    pathname.match(
      /^\/api\/admin\/orders\/([^/]+)\/(assignment|assign|assign-employee|assign_employee)\/?$/
    ) ||
    pathname.match(
      /^\/([^/]+)\/(assignment|assign|assign-employee|assign_employee)\/?$/
    );

  if (!match) return;

  console.log(`🚨 ORDER ASSIGNMENT HIT: ${method} ${rawUrl}`);

  if (!['PUT', 'POST', 'PATCH'].includes(method)) {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed for order assignment' };
  }

  try {
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
      `👤 ORDER ASSIGNMENT REQUEST: order=${reference} employee=${requested ?? 'UNASSIGN'} method=${method}`
    );

    let assignedTo: any = null;

    if (requested !== null && requested !== undefined && String(requested).trim() !== '') {
      // Same robust lookup as quote assignment (ObjectId, numeric id, email, etc.)
      const employee = await findEmployeeByReference(db, requested);

      if (!employee) {
        console.error(`❌ ORDER ASSIGNMENT EMPLOYEE NOT FOUND: ${String(requested)}`);
        return {
          success: false,
          error: `Employee not found: ${String(requested)}`,
          code: 'EMPLOYEE_NOT_FOUND',
        };
      }

      if (!isActive(employee.status, true)) {
        return {
          success: false,
          error: `Employee is inactive: ${employeeDisplayName(employee)}`,
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
        `👤 ORDER ASSIGNMENT EMPLOYEE FOUND: employee_id=${assignedTo.employee_id} name=${assignedTo.full_name}`
      );
    }

    let order: any = null;
    if (isMongoConnected) {
      const escaped = reference.replace(/[.*+?^${}()|[\]\\]/g, '\\\\$&');
      order = await Order.findOne({
        $or: [
          { reference },
          { reference: { $regex: `^${escaped}$`, $options: 'i' } },
        ],
      });
      if (!order) {
        const raw = await db.collection('orders').findOne({
          reference: { $regex: `^${escaped}$`, $options: 'i' },
        });
        if (raw) order = await Order.findById(raw._id);
      }
    } else {
      order = inMemoryOrders.find(
        (o: any) => String(o?.reference || '').trim().toUpperCase() === reference
      );
    }

    if (!order) {
      return {
        success: false,
        error: `Order not found: ${reference}`,
        code: 'ORDER_NOT_FOUND',
      };
    }

    const actor = {
      id: user?._id?.toString?.() ?? user?._id ?? null,
      username: user?.username || user?.email || '',
      full_name: user?.full_name || user?.username || user?.email || '',
    };

    order.assigned_to = assignedTo;
    order.assigned_by = assignedTo ? actor : null;
    if (assignedTo && String(order.status || '').toLowerCase() === 'pending') {
      order.status = 'assigned';
    }

    if (isMongoConnected) {
      order.updatedAt = new Date();
      await order.save();
    }

    console.log(
      `✅ ORDER ASSIGNMENT SUCCESS: order=${reference} employee=${assignedTo?.employee_id || 'UNASSIGNED'}`
    );

    return {
      success: true,
      message: assignedTo ? 'Order assigned successfully.' : 'Order unassigned successfully.',
      order: {
        reference: order.reference,
        status: order.status,
        assigned_to: order.assigned_to,
        assigned_by: order.assigned_by,
      },
    };
  } catch (error: any) {
    console.error('❌ Order assignment error:', error);
    const status = error?.statusCode || error?.status || 500;
    event.node.res.statusCode = status;
    return {
      success: false,
      error: error?.message || 'Order assignment failed',
      code: error?.code || 'ORDER_ASSIGNMENT_FAILED',
    };
  }
}));

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
