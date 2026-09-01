// Backend/server/index-mongo.ts
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import { listen } from 'listhen';
import dotenv from 'dotenv';
import mongoose from 'mongoose';

dotenv.config();

// ============================================
// MONGODB CONNECTION
// ============================================

let isMongoConnected = false;

async function connectDB() {
  try {
    const MONGODB_URI = process.env.MONGODB_URI;
    
    if (!MONGODB_URI) {
      console.error('❌ MONGODB_URI is not defined in .env');
      return false;
    }

    console.log('📡 Connecting to MongoDB...');
    
    // Connection options to fix SSL issues
    await mongoose.connect(MONGODB_URI, {
      tls: true,
      tlsAllowInvalidCertificates: true,
      tlsAllowInvalidHostnames: true,
      serverSelectionTimeoutMS: 30000,
      socketTimeoutMS: 45000,
      connectTimeoutMS: 30000,
      retryWrites: true,
      w: 'majority'
    });
    
    isMongoConnected = true;
    console.log('✅ MongoDB connected successfully');
    console.log(`📊 Database: ${mongoose.connection.name}`);
    console.log(`🔗 Host: ${mongoose.connection.host}`);
    return true;
  } catch (error) {
    console.error('❌ MongoDB connection error:', error);
    console.log('⚠️ Falling back to in-memory storage...');
    isMongoConnected = false;
    return false;
  }
}

// ============================================
// MONGODB MODELS
// ============================================

// Quote Schema
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
    qty: Number
  }],
  status: { 
    type: String, 
    enum: ['received', 'in_review', 'quoted', 'closed'],
    default: 'received'
  },
  replyMessage: String,
  repliedAt: Date,
  createdAt: { type: Date, default: Date.now }
});

// Order Schema
const orderSchema = new mongoose.Schema({
  orderId: { type: String, unique: true, required: true },
  customerName: { type: String, required: true },
  company: String,
  email: { type: String, required: true },
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
    enum: ['received', 'processing', 'shipped', 'delivered', 'cancelled'],
    default: 'received'
  },
  createdAt: { type: Date, default: Date.now }
});

// Create models only if they don't exist
const Quote = mongoose.models.Quote || mongoose.model('Quote', quoteSchema);
const Order = mongoose.models.Order || mongoose.model('Order', orderSchema);

// ============================================
// HELPERS
// ============================================

function generateReference() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = 'UQ-';
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

// In-memory fallback storage
const inMemoryQuotes: any[] = [];
const inMemoryOrders: any[] = [];

// ============================================
// CREATE APP
// ============================================

const app = createApp();

// CORS middleware
app.use(eventHandler(async (event) => {
  const origin = event.node.req.headers.origin || '';
  const allowedOrigins = ['http://localhost:5173', 'http://localhost:5174', 'http://127.0.0.1:5173'];
  
  if (allowedOrigins.includes(origin)) {
    event.node.res.setHeader('Access-Control-Allow-Origin', origin);
  } else {
    event.node.res.setHeader('Access-Control-Allow-Origin', '*');
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
  db: isMongoConnected ? 'connected' : 'disconnected (using in-memory)',
  mode: isMongoConnected ? 'mongodb' : 'in-memory',
  quotes: isMongoConnected ? 'MongoDB' : inMemoryQuotes.length,
  orders: isMongoConnected ? 'MongoDB' : inMemoryOrders.length
})));

// ============================================
// QUOTE API
// ============================================

app.use('/api/quotes', eventHandler(async (event) => {
  // POST - Submit a quote
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Quote received:', JSON.stringify(body, null, 2));
      
      const { customerName, company, email, phone, notes, items } = body;
      
      // Validate
      if (!customerName || !email || !phone || !items || items.length === 0) {
        return { 
          success: false, 
          error: 'Missing required fields: customerName, email, phone, and items are required' 
        };
      }
      
      // Generate reference
      const reference = generateReference();
      
      // Prepare data
      const quoteData = {
        reference,
        customerName,
        company: company || '',
        email: email.toLowerCase(),
        phone,
        notes: notes || '',
        items: items.map((item: any) => ({
          id: item.id,
          name: item.name,
          kind: item.kind || 'product',
          qty: Number(item.qty) || 1
        })),
        status: 'received'
      };
      
      let savedQuote;
      
      // Try to save to MongoDB if connected
      if (isMongoConnected) {
        try {
          const quote = new Quote(quoteData);
          savedQuote = await quote.save();
          console.log(`✅ Quote saved to MongoDB with reference: ${reference}`);
        } catch (dbError) {
          console.error('❌ Failed to save to MongoDB:', dbError);
          // Fallback to in-memory
          savedQuote = { ...quoteData, _id: `mem_${Date.now()}` };
          inMemoryQuotes.push(savedQuote);
          console.log(`💾 Quote saved in-memory: ${reference}`);
        }
      } else {
        // In-memory storage
        savedQuote = { ...quoteData, _id: `mem_${Date.now()}` };
        inMemoryQuotes.push(savedQuote);
        console.log(`💾 Quote saved in-memory: ${reference}`);
      }
      
      return { 
        success: true, 
        reference: savedQuote.reference
      };
      
    } catch (error) {
      console.error('❌ Error processing quote:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to process quote' 
      };
    }
  }
  
  // GET - List all quotes (for debugging)
  if (event.method === 'GET') {
    try {
      let quotes = [];
      
      if (isMongoConnected) {
        quotes = await Quote.find({}).sort({ createdAt: -1 }).limit(50).lean();
      } else {
        quotes = inMemoryQuotes;
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
          items: q.items
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
// TRACK QUOTE API
// ============================================

app.use('/api/quotes/track', eventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const ref = query.ref as string;
    const email = query.email as string;
    
    console.log(`🔍 Tracking quote: ref=${ref}, email=${email}`);
    
    if (!ref || !email) {
      return {
        success: false,
        error: 'Reference and email are required',
        quote: null
      };
    }
    
    let quote = null;
    
    // Try to find in MongoDB if connected
    if (isMongoConnected) {
      quote = await Quote.findOne({ 
        reference: ref.toUpperCase(), 
        email: email.toLowerCase() 
      }).lean();
    }
    
    // If not found in MongoDB, try in-memory
    if (!quote && !isMongoConnected) {
      quote = inMemoryQuotes.find(q => 
        q.reference === ref.toUpperCase() && 
        q.email === email.toLowerCase()
      );
    }
    
    if (!quote) {
      console.log('❌ Quote not found');
      return {
        success: false,
        error: 'Quote not found',
        quote: null
      };
    }
    
    console.log(`✅ Quote found: ${quote.reference}`);
    
    return {
      success: true,
      quote: {
        reference: quote.reference,
        customerName: quote.customerName,
        email: quote.email,
        phone: quote.phone,
        status: quote.status,
        items: quote.items,
        replyMessage: quote.replyMessage || null,
        repliedAt: quote.repliedAt || null,
        createdAt: quote.createdAt
      }
    };
    
  } catch (error) {
    console.error('❌ Error tracking quote:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to track quote',
      quote: null
    };
  }
}));

// ============================================
// ORDER API
// ============================================

app.use('/api/orders', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Order received:', JSON.stringify(body, null, 2));
      
      const { customerName, company, email, phone, address, notes, items, total } = body;
      
      // Validate
      if (!customerName || !email || !phone || !address || !items || items.length === 0) {
        return {
          success: false,
          error: 'Missing required fields'
        };
      }
      
      const orderId = `ORD-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
      
      const orderData = {
        orderId,
        customerName,
        company: company || '',
        email: email.toLowerCase(),
        phone,
        address,
        notes: notes || '',
        items: items.map((item: any) => ({
          id: item.id,
          name: item.name,
          qty: Number(item.qty) || 1,
          price: Number(item.price) || 0
        })),
        total: Number(total) || 0,
        status: 'received'
      };
      
      let savedOrder;
      
      // Try to save to MongoDB if connected
      if (isMongoConnected) {
        try {
          const order = new Order(orderData);
          savedOrder = await order.save();
          console.log(`✅ Order saved to MongoDB with ID: ${orderId}`);
        } catch (dbError) {
          console.error('❌ Failed to save to MongoDB:', dbError);
          savedOrder = { ...orderData, _id: `mem_${Date.now()}` };
          inMemoryOrders.push(savedOrder);
          console.log(`💾 Order saved in-memory: ${orderId}`);
        }
      } else {
        savedOrder = { ...orderData, _id: `mem_${Date.now()}` };
        inMemoryOrders.push(savedOrder);
        console.log(`💾 Order saved in-memory: ${orderId}`);
      }
      
      return {
        success: true,
        orderId: savedOrder.orderId
      };
      
    } catch (error) {
      console.error('❌ Error processing order:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to process order'
      };
    }
  }
  
  return { success: false, error: 'Method not allowed' };
}));

// ============================================
// START SERVER
// ============================================

const PORT = process.env.PORT || 5001;

async function startServer() {
  // Connect to MongoDB
  await connectDB();
  
  await listen(toNodeListener(app), { 
    port: PORT,
    hostname: '0.0.0.0'
  });
  
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`📡 API available at http://localhost:${PORT}/api`);
  console.log(`🏥 Health check: http://localhost:${PORT}/api/health`);
  console.log(`📋 Quotes API: http://localhost:${PORT}/api/quotes`);
  console.log(`📋 Orders API: http://localhost:${PORT}/api/orders`);
  
  if (isMongoConnected) {
    console.log(`✅ Using MongoDB: ${mongoose.connection.name}`);
  } else {
    console.log(`💡 Using in-memory storage (MongoDB not connected)`);
  }
}

startServer();
