// Backend/server/index-working-v2.ts
import { createServer } from 'node:http';
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import crypto from 'node:crypto';
import { randomUUID } from 'node:crypto';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { config as sharedConfig, assertProductionConfig } from './config/index.js';
import { securityMiddleware, rateLimitOrNull } from './middleware/security.js';
import { performanceMiddleware } from './middleware/performance.js';
import { createQuoteService } from './services/quote.service.js';

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
    enum: ['received', 'in_review', 'quoted', 'closed', 'pending', 'waiting_feedback', 'in_touch', 'approved', 'payment'],
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
  updatedAt: { type: Date, default: Date.now }
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
// QUOTE SERVICE (extracted business logic)
// ============================================

const quoteService = createQuoteService({
  QuoteModel: Quote,
  isMongoConnected: () => isMongoConnected,
  inMemoryQuotes,
  generateReference,
  extractPaymentAmount,
});

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
    const ref = url.searchParams.get('ref') || '';
    const email = url.searchParams.get('email') || '';

    const result = await quoteService.trackQuote(ref, email);
    if (!result.ok) {
      if (result.status) event.node.res.statusCode = result.status;
      return { success: false, error: result.error, quote: null };
    }
    return { success: true, quote: result.quote };
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

      const result = await quoteService.createQuote({
        customerName: body.customerName,
        company: body.company,
        email: body.email,
        phone: body.phone,
        notes: body.notes,
        items: body.items || [],
      });

      if (!result.ok) {
        if (result.status) event.node.res.statusCode = result.status;
        return { success: false, error: result.error };
      }
      console.log(`🔑 Generated reference: ${result.reference}`);
      return { success: true, reference: result.reference };
    } catch (error) {
      console.error('❌ Error:', error);
      return { success: false, error: 'Failed to process quote' };
    }
  }

  // Handle GET - List all quotes
  if (event.method === 'GET') {
    try {
      const result = await quoteService.listQuotes(50);
      return {
        success: true,
        count: result.count,
        quotes: result.quotes,
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
  const limited = rateLimitOrNull(event, 'track');
  if (limited) {
    event.node.res.statusCode = limited.statusCode;
    return limited.body;
  }

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
          carrier: o.carrier || null
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

  await db.collection('api_sessions').updateOne({ _id: session._id }, { $set: { last_activity_at: new Date() } });
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

// ============================================
// DESKTOP DASHBOARD
// ============================================
// Dashboard metrics are calculated on the server so the desktop client
// never connects directly to MongoDB.

async function dashboardSummary() {
  const db = mongoRequired();
  const today = todaySouthAfrica();
  const attendance = db.collection('attendance');
  const employees = db.collection('employees');
  const tasks = db.collection('work_assignments');
  const approvals = db.collection('approvals');

  // People working = distinct employees with a REAL open clock-in for TODAY only.
  // Do not count orphan rows, null employee_id, or sticky employee flags.
  const activeAttendanceQuery = {
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
          { status: { $in: ['clocked_in', 'on_break'] } },
          // Treat missing status as open only when clock_out is absent
          { status: { $exists: false } },
          { status: null },
          { status: '' },
        ],
      },
    ],
  };

  const activeAttendanceIds = await attendance.distinct('employee_id', activeAttendanceQuery);
  const peopleWorking = new Set(
    activeAttendanceIds
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
    if (record) await collection.updateOne({ _id: record._id }, { $set: doc });
    else { const inserted = await collection.insertOne(doc); record = await collection.findOne({ _id: inserted.insertedId }); }
    record = await getTodayAttendance(db, employeeId);
    return { success: true, message: 'Clocked in.', ...serialiseAttendance(record) };
  }

  if (action === 'clock_out') {
    if (!record?.clock_in_at) throw Object.assign(new Error('Employee has not clocked in.'), { statusCode: 400 });
    if (record.clock_out_at) throw Object.assign(new Error('Employee has already clocked out.'), { statusCode: 409 });
    if (record.break_started_at) throw Object.assign(new Error('End the active break before clocking out.'), { statusCode: 400 });
    if (record.lunch_started_at && !record.lunch_ended_at) throw Object.assign(new Error('End lunch before clocking out.'), { statusCode: 400 });
    const hours = Math.round((netElapsedSeconds(record, now) / 3600) * 100) / 100;
    await collection.updateOne({ _id: record._id }, { $set: { clock_out_at: now, hours_worked: hours, status: 'clocked_out', updated_at: now } });
    record = await getTodayAttendance(db, employeeId);
    return { success: true, message: 'Clocked out.', ...serialiseAttendance(record) };
  }

  if (action === 'break_start') {
    if (!record?.clock_in_at) throw Object.assign(new Error('Clock in before starting a break.'), { statusCode: 400 });
    if (record.clock_out_at) throw Object.assign(new Error('Employee has already clocked out.'), { statusCode: 400 });
    if (record.break_started_at) throw Object.assign(new Error('A break is already in progress.'), { statusCode: 409 });
    await collection.updateOne({ _id: record._id }, { $set: { break_started_at: now, break_ended_at: null, status: 'on_break', updated_at: now } });
    record = await getTodayAttendance(db, employeeId);
    return { success: true, message: 'Break started.', ...serialiseAttendance(record) };
  }

  if (action === 'break_end') {
    if (!record?.break_started_at) throw Object.assign(new Error('No active break was found.'), { statusCode: 400 });
    const extra = elapsedSeconds(record.break_started_at, now) / 60;
    const total = Math.round((Number(record.break_duration_minutes || 0) + extra) * 100) / 100;
    await collection.updateOne(
      { _id: record._id },
      { $set: { break_ended_at: now, break_duration_minutes: total, status: 'clocked_in', updated_at: now }, $unset: { break_started_at: '' } },
    );
    record = await getTodayAttendance(db, employeeId);
    return { success: true, message: 'Break ended.', ...serialiseAttendance(record) };
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
