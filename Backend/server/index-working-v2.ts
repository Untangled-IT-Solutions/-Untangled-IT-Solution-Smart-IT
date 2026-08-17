// Backend/server/index-working-v2.ts
import { createServer } from 'node:http';
import { createApp, eventHandler, toNodeListener, readBody } from 'h3';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

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
      serverSelectionTimeoutMS: 30000,
      socketTimeoutMS: 45000,
      tls: true,
      tlsAllowInvalidCertificates: true,
      tlsAllowInvalidHostnames: true,
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
          replyMessage: q.replyMessage || null
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
          items: o.items
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