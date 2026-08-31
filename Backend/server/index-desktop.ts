// Backend/server/index-desktop.ts
import { createServer } from 'node:http';
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import crypto from 'node:crypto';
import { randomUUID } from 'node:crypto';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// ============================================
// CONFIGURATION - ALL FROM ENV VARIABLES
// ============================================

const config = {
  port: parseInt(process.env.PORT || '5002'),
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
      isMongoConnected = false;
      return false;
    }
    
    const maskedUri = config.mongoUri.replace(/\/\/.*@/, '//<credentials>@');
    console.log(`🔗 Using URI: ${maskedUri}`);
    
    await mongoose.connect(config.mongoUri, {
      serverSelectionTimeoutMS: 8000,
      socketTimeoutMS: 10000,
      tls: true,
      tlsAllowInvalidCertificates: false,
      tlsAllowInvalidHostnames: false,
    });
    
    isMongoConnected = true;
    console.log('✅ MongoDB connected successfully');
    console.log(`📊 Database: ${mongoose.connection.name}`);
    console.log(`🔗 Host: ${mongoose.connection.host}`);
    return true;
  } catch (error) {
    console.error('❌ MongoDB connection error:', error);
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
// TRACK QUOTE API
// ============================================

app.use('/api/quotes/track', eventHandler(async (event) => {
  try {
    const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
    const ref = url.searchParams.get('ref');
    const email = url.searchParams.get('email');
    
    if (!ref || !email) {
      return { success: false, error: 'Reference and email are required', quote: null };
    }
    
    const cleanRef = ref.trim().toUpperCase();
    const cleanEmail = email.trim().toLowerCase();
    
    let quote = null;
    
    if (isMongoConnected) {
      quote = await Quote.findOne({ reference: cleanRef, email: cleanEmail });
    }
    
    if (!quote) {
      quote = inMemoryQuotes.find(q => q.reference === cleanRef && q.email === cleanEmail);
    }
    
    if (!quote) {
      return { success: false, error: 'Quote not found', quote: null };
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
        paymentRequired: quote.paymentRequired || false,
        paymentAmount: quote.paymentAmount || 0,
        paymentStatus: quote.paymentStatus || 'pending',
        feedback: quote.feedback || null,
        assigned_to: quote.assigned_to || null,
        assigned_by: quote.assigned_by || null
      }
    };
  } catch (error) {
    console.error('❌ Error tracking quote:', error);
    return { success: false, error: 'Failed to track quote', quote: null };
  }
}));

// ============================================
// QUOTES API
// ============================================

app.use('/api/quotes', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      const { customerName, company, email, phone, notes, items } = body;
      
      if (!customerName || !email || !phone || !items || items.length === 0) {
        return { success: false, error: 'Missing required fields' };
      }
      
      const reference = generateReference('UQ');
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
        const quote = new Quote(quoteData);
        savedQuote = await quote.save();
      } else {
        savedQuote = { ...quoteData, _id: `mem_${Date.now()}` };
        inMemoryQuotes.push(savedQuote);
      }
      
      return { success: true, reference: savedQuote.reference };
    } catch (error) {
      console.error('❌ Error:', error);
      return { success: false, error: 'Failed to process quote' };
    }
  }
  
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
// TRACK ORDER API
// ============================================

app.use('/api/orders/track', eventHandler(async (event) => {
  try {
    const url = new URL(event.node.req.url || '', `http://${event.node.req.headers.host}`);
    const ref = url.searchParams.get('ref');
    const email = url.searchParams.get('email');
    
    if (!ref || !email) {
      return { success: false, error: 'Reference and email are required', order: null };
    }
    
    const cleanRef = ref.trim().toUpperCase();
    const cleanEmail = email.trim().toLowerCase();
    
    let order = null;
    
    if (isMongoConnected) {
      order = await Order.findOne({ reference: cleanRef, email: cleanEmail });
    }
    
    if (!order) {
      order = inMemoryOrders.find(o => o.reference === cleanRef);
    }
    
    if (!order) {
      return { success: false, error: 'Order not found', order: null };
    }
    
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
        assigned_to: order.assigned_to || null,
        assigned_by: order.assigned_by || null
      }
    };
  } catch (error) {
    console.error('❌ Error tracking order:', error);
    return { success: false, error: 'Failed to track order', order: null };
  }
}));

// ============================================
// ORDERS API
// ============================================

app.use('/api/orders', eventHandler(async (event) => {
  if (event.method === 'GET') {
    try {
      let orders = [];
      if (isMongoConnected) {
        orders = await Order.find({}).sort({ createdAt: -1 }).limit(50).lean();
      } else {
        orders = inMemoryOrders;
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
      return { success: false, error: 'Failed to fetch orders' };
    }
  }
  
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
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
        const order = new Order(orderData);
        savedOrder = await order.save();
      } else {
        savedOrder = { ...orderData, _id: `mem_${Date.now()}` };
        inMemoryOrders.push(savedOrder);
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
  
  return { success: false, error: 'Method not allowed' };
}));

// ============================================
// PAYMENT API
// ============================================

app.use('/api/quotes/payment', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      const { reference, email } = body;
      
      if (!reference || !email) {
        return { success: false, message: 'Reference and email are required' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase(), email: email.toLowerCase() });
        
        if (!quote) {
          return { success: false, message: 'Quote not found' };
        }
        
        if (!quote.paymentRequired || !quote.paymentAmount) {
          const extractedAmount = extractPaymentAmount(quote.replyMessage || '');
          if (extractedAmount) {
            quote.paymentRequired = true;
            quote.paymentAmount = extractedAmount;
            await quote.save();
          } else {
            return { success: false, message: 'No payment required for this quote' };
          }
        }
        
        const paymentRef = `PAY-${Date.now()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
        quote.paymentReference = paymentRef;
        quote.paymentStatus = 'pending';
        quote.status = 'payment';
        await quote.save();
        
        return {
          success: true,
          message: 'Payment initiated',
          paymentUrl: `${config.frontendUrl}/payment/${paymentRef}`,
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
      
      return { success: false, message: 'Payment service unavailable' };
    } catch (error) {
      console.error('❌ Error initiating payment:', error);
      return { success: false, message: 'Failed to initiate payment' };
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
      
      if (!reference || !email || !feedback) {
        return { success: false, message: 'Missing required fields' };
      }
      
      let quote = null;
      
      if (isMongoConnected) {
        quote = await Quote.findOne({ reference: reference.toUpperCase(), email: email.toLowerCase() });
        
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
        }
      }
      
      if (!quote) {
        return { success: false, message: 'Quote not found' };
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
      return { success: false, message: 'Failed to submit feedback' };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
}));

// ============================================
// EMPLOYEES API
// ============================================

app.use('/api/employees', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  try {
    if (!isMongoConnected) {
      return { success: true, count: 0, employees: [] };
    }
    
    const db = mongoose.connection.db;
    const employees = await db.collection('employees').find({}).limit(500).toArray();
    
    const safeEmployees = employees.map((employee: any) => ({
      id: employee._id?.toString?.() || employee._id || null,
      employee_id: employee.employee_id || employee.id || employee._id?.toString?.() || null,
      full_name: employee.full_name || [employee.first_name, employee.surname || employee.last_name].filter(Boolean).join(' ') || 'Unknown',
      first_name: employee.first_name || '',
      last_name: employee.surname || employee.last_name || '',
      email: employee.email || employee.email_address || '',
      department: employee.department || '',
      position: employee.position || '',
      status: employee.status || 'Active',
      clocked_in: employee.clocked_in || false
    }));
    
    return { success: true, count: safeEmployees.length, employees: safeEmployees };
  } catch (error: any) {
    event.node.res.statusCode = 500;
    return { success: false, error: error?.message || 'Failed to load employees' };
  }
}));

// ============================================
// DIRECT QUOTE ASSIGNMENT ROUTE - FIXED
// ============================================

app.use("/api/admin/quotes/:reference/assignment", eventHandler(async (event) => {
  // Support PUT, POST, PATCH
  if (!["PUT", "POST", "PATCH"].includes(event.method || "")) {
    event.node.res.statusCode = 405;
    return { success: false, error: "Method not allowed" };
  }

  const reference = event.context.params?.reference;
  const body = await readBody(event);

  console.log(`📌 DIRECT ASSIGNMENT ROUTE HIT: ${reference}`);

  if (!reference) {
    event.node.res.statusCode = 400;
    return { success: false, error: "Reference is required" };
  }

  let quote = null;

  if (isMongoConnected) {
    quote = await Quote.findOne({ 
      reference: { $regex: `^${reference}$`, $options: 'i' } 
    });
  } else {
    quote = inMemoryQuotes.find(q => String(q.reference).toUpperCase() === reference.toUpperCase());
  }

  if (!quote) {
    event.node.res.statusCode = 404;
    return { success: false, error: `Quote not found: ${reference}` };
  }

  // Get employee info
  const employeeId = body?.employee_id ?? body?.employeeId ?? body?.assigned_to ?? body?.assignedTo ?? null;
  let assignedTo = null;

  if (employeeId && isMongoConnected) {
    try {
      const db = mongoose.connection.db;
      const employee = await db.collection('employees').findOne({
        $or: [
          { employee_id: employeeId },
          { id: employeeId },
          { _id: new mongoose.Types.ObjectId(employeeId) }
        ]
      });
      if (employee) {
        assignedTo = {
          id: employee._id?.toString?.() || employee._id,
          employee_id: employee.employee_id || employee.id || employee._id?.toString?.() || null,
          full_name: employee.full_name || [employee.first_name, employee.surname || employee.last_name].filter(Boolean).join(' ') || 'Unknown',
          email: employee.email || employee.email_address || '',
          department: employee.department || '',
          position: employee.position || '',
          status: employee.status || 'Active'
        };
      }
    } catch (err) {
      console.warn('⚠️ Could not find employee:', employeeId);
    }
  }

  // Update quote
  quote.assigned_to = assignedTo;
  quote.assigned_by = assignedTo ? { id: 'system', username: 'admin' } : null;
  
  if (assignedTo) {
    quote.status = 'assigned';
  }

  if (isMongoConnected) {
    await quote.save();
  }

  console.log(`✅ Quote ${reference} assigned successfully`);

  return {
    success: true,
    message: assignedTo ? "Quote assigned successfully" : "Quote unassigned",
    quote: {
      reference: quote.reference,
      assigned_to: quote.assigned_to,
      assigned_by: quote.assigned_by,
      status: quote.status
    }
  };
}));

// ============================================
// DASHBOARD SUMMARY API
// ============================================

app.use('/api/dashboard/summary', eventHandler(async (event) => {
  if (event.method !== 'GET') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }

  try {
    let totalQuotes = 0;
    let totalOrders = 0;
    
    if (isMongoConnected) {
      totalQuotes = await Quote.countDocuments();
      totalOrders = await Order.countDocuments();
    } else {
      totalQuotes = inMemoryQuotes.length;
      totalOrders = inMemoryOrders.length;
    }

    return {
      success: true,
      summary: {
        total_quotes: totalQuotes,
        total_orders: totalOrders,
        quotes_by_status: {
          received: await (isMongoConnected ? Quote.countDocuments({ status: 'received' }) : Promise.resolve(inMemoryQuotes.filter(q => q.status === 'received').length)),
          assigned: await (isMongoConnected ? Quote.countDocuments({ status: 'assigned' }) : Promise.resolve(inMemoryQuotes.filter(q => q.status === 'assigned').length)),
          quoted: await (isMongoConnected ? Quote.countDocuments({ status: 'quoted' }) : Promise.resolve(inMemoryQuotes.filter(q => q.status === 'quoted').length)),
          approved: await (isMongoConnected ? Quote.countDocuments({ status: 'approved' }) : Promise.resolve(inMemoryQuotes.filter(q => q.status === 'approved').length)),
          payment: await (isMongoConnected ? Quote.countDocuments({ status: 'payment' }) : Promise.resolve(inMemoryQuotes.filter(q => q.status === 'payment').length))
        },
        orders_by_status: {
          pending: await (isMongoConnected ? Order.countDocuments({ status: 'pending' }) : Promise.resolve(inMemoryOrders.filter(o => o.status === 'pending').length)),
          processing: await (isMongoConnected ? Order.countDocuments({ status: 'processing' }) : Promise.resolve(inMemoryOrders.filter(o => o.status === 'processing').length)),
          shipped: await (isMongoConnected ? Order.countDocuments({ status: 'shipped' }) : Promise.resolve(inMemoryOrders.filter(o => o.status === 'shipped').length)),
          delivered: await (isMongoConnected ? Order.countDocuments({ status: 'delivered' }) : Promise.resolve(inMemoryOrders.filter(o => o.status === 'delivered').length))
        },
        recent_quotes: isMongoConnected ? await Quote.find({}).sort({ createdAt: -1 }).limit(5).lean() : inMemoryQuotes.slice(-5),
        recent_orders: isMongoConnected ? await Order.find({}).sort({ createdAt: -1 }).limit(5).lean() : inMemoryOrders.slice(-5)
      }
    };
  } catch (error) {
    console.error('❌ Error loading dashboard summary:', error);
    return { success: false, error: 'Failed to load dashboard summary' };
  }
}));

// ============================================
// AUTHENTICATION + ATTENDANCE
// ============================================

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
  return false;
}


function hashPassword(password: string): string {
  const iterations = 310000;
  const salt = crypto.randomBytes(16).toString('hex');
  const digest = crypto.pbkdf2Sync(
    Buffer.from(password, 'utf8'),
    Buffer.from(salt, 'utf8'),
    iterations,
    32,
    'sha256',
  ).toString('hex');
  return `pbkdf2_sha256$${iterations}$${salt}$${digest}`;
}

async function ensureDesktopDemoUser() {
  try {
    const db = mongoRequired();
    const employees = db.collection('employees');
    const users = db.collection('users');

    // Prefer the existing Demo Admin employee if present
    let employee = await employees.findOne({
      $or: [
        { email: { $regex: /^siyandan@untangled\.co\.za$/i } },
        { full_name: { $regex: /^Demo Admin$/i } },
        { employee_number: 'DEMO-001' },
      ],
    });

    if (!employee) {
      const insert = await employees.insertOne({
        employee_number: 'DEMO-001',
        first_name: 'Demo',
        last_name: 'Admin',
        full_name: 'Demo Admin',
        position: 'Director',
        department: 'Administration',
        role: 'Director',
        email: 'siyandan@untangled.co.za',
        status: 'Active',
        employment_type: 'Full-time',
        date_joined: new Date().toISOString(),
        clocked_in: false,
        created_at: new Date(),
        updated_at: new Date(),
      });
      employee = await employees.findOne({ _id: insert.insertedId });
      console.log('✅ Seeded Demo Admin employee');
    }

    const demoUsername = 'siyandan@untangled.co.za';
    const demoPassword = process.env.DEMO_PASSWORD || 'admin';

    let user = await users.findOne({
      $or: [
        { username: { $regex: new RegExp(`^${demoUsername.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, 'i') } },
        { email: { $regex: new RegExp(`^${demoUsername.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, 'i') } },
      ],
    });

    if (!user) {
      await users.insertOne({
        employee_id: employee._id,
        username: demoUsername,
        email: demoUsername,
        password_hash: hashPassword(demoPassword),
        role: 'Director',
        status: 'active',
        full_name: employee.full_name || 'Demo Admin',
        department: employee.department || 'Administration',
        require_password_change: false,
        created_at: new Date(),
        updated_at: new Date(),
        last_login_at: null,
      });
      console.log(`✅ Seeded demo user ${demoUsername} (password from DEMO_PASSWORD or "admin")`);
    } else {
      // Keep employee link and active status so desktop login works.
      // Always re-hash the known demo password so employer testing can log in
      // after deploys (override with DEMO_PASSWORD env).
      const updates: any = {
        status: 'active',
        employee_id: user.employee_id || employee._id,
        password_hash: hashPassword(demoPassword),
        role: user.role || 'Director',
        updated_at: new Date(),
      };
      await users.updateOne({ _id: user._id }, { $set: updates });
      console.log(`✅ Demo user linked and password synced for ${demoUsername}`);
    }
  } catch (error: any) {
    console.warn('⚠️ Demo user bootstrap skipped:', error?.message || error);
  }
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

function employeeDisplayName(employee: any, user: any): string {
  return employee?.full_name ||
    [employee?.first_name, employee?.surname || employee?.last_name].filter(Boolean).join(' ') ||
    user?.full_name || user?.username || user?.email || 'Employee';
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
    if (!isActive(user.status, true)) return { success: false, error: 'This user account is inactive.' };

    const employee = await findEmployeeForUser(user);
    if (!employee) return { success: false, error: 'Your login account is not linked to an employee record.' };
    if (!isActive(employee.status, true)) return { success: false, error: 'This employee is inactive.' };

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
// ADMIN: users + employees (desktop management)
// ============================================

function serialiseUser(user: any, employee: any = null) {
  return {
    id: user._id?.toString?.() ?? user._id,
    _id: user._id?.toString?.() ?? user._id,
    username: user.username || user.email || '',
    email: user.email || '',
    role: user.role || 'Staff',
    status: user.status || 'active',
    active: isActive(user.status, true),
    employee_id: (user.employee_id?.toString?.() ?? user.employee_id) || null,
    full_name: user.full_name || employee?.full_name || '',
    department: user.department || employee?.department || '',
    require_password_change: Boolean(user.require_password_change),
    last_login_at: user.last_login_at || null,
  };
}

app.use('/api/admin/employees', eventHandler(async (event) => {
  try {
    await requireDesktopSession(event);
    if (event.method !== 'GET') {
      event.node.res.statusCode = 405;
      return { success: false, error: 'Method not allowed' };
    }
    const db = mongoRequired();
    const employees = await db.collection('employees').find({}).limit(500).toArray();
    return {
      success: true,
      employees: employees.map((e: any) => ({
        id: e._id?.toString?.() ?? e._id,
        employee_id: e.employee_id || e.id || e._id?.toString?.() || null,
        full_name: e.full_name || [e.first_name, e.surname || e.last_name].filter(Boolean).join(' ') || 'Unknown',
        first_name: e.first_name || '',
        last_name: e.surname || e.last_name || '',
        email: e.email || e.email_address || '',
        department: e.department || '',
        position: e.position || '',
        role: e.role || 'Staff',
        status: e.status || 'Active',
      })),
    };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Failed to list employees' };
  }
}));

app.use('/api/admin/users', eventHandler(async (event) => {
  try {
    const session = await requireDesktopSession(event);
    const db = mongoRequired();
    const usersCol = db.collection('users');

    if (event.method === 'GET') {
      const users = await usersCol.find({}).limit(500).toArray();
      const result = [];
      for (const user of users) {
        const employee = await findEmployeeForUser(user);
        result.push(serialiseUser(user, employee));
      }
      return { success: true, users: result };
    }

    if (event.method === 'POST') {
      const body = await readBody(event);
      const username = normaliseLogin(body?.username || body?.email);
      const password = String(body?.password ?? '');
      const role = String(body?.role || 'Staff');
      const employeeId = body?.employee_id;
      if (!username || !password) {
        event.node.res.statusCode = 400;
        return { success: false, error: 'Username and password are required.' };
      }
      const existing = await usersCol.findOne({
        $or: [
          { username: { $regex: `^${username.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
          { email: { $regex: `^${username.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}$`, $options: 'i' } },
        ],
      });
      if (existing) {
        event.node.res.statusCode = 409;
        return { success: false, error: 'A user with that username already exists.' };
      }
      const employeeOid = safeObjectId(employeeId);
      const doc = {
        employee_id: employeeOid || employeeId || null,
        username,
        email: username,
        password_hash: hashPassword(password),
        role,
        status: body?.active === false ? 'inactive' : 'active',
        require_password_change: Boolean(body?.require_password_change),
        created_at: new Date(),
        updated_at: new Date(),
        last_login_at: null,
        created_by: session.user?._id || null,
      };
      const inserted = await usersCol.insertOne(doc);
      const user = await usersCol.findOne({ _id: inserted.insertedId });
      return { success: true, user: serialiseUser(user) };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'User administration failed' };
  }
}));

app.use('/api/admin/users/:id', eventHandler(async (event) => {
  try {
    await requireDesktopSession(event);
    const db = mongoRequired();
    const usersCol = db.collection('users');
    const id = event.context.params?.id;
    const oid = safeObjectId(id);
    if (!oid) {
      event.node.res.statusCode = 400;
      return { success: false, error: 'Invalid user id' };
    }

    if (event.method === 'PUT' || event.method === 'PATCH') {
      const body = await readBody(event);
      const updates: any = { updated_at: new Date() };
      if (body?.username !== undefined) updates.username = normaliseLogin(body.username);
      if (body?.role !== undefined) updates.role = String(body.role);
      if (body?.active !== undefined) updates.status = body.active ? 'active' : 'inactive';
      if (body?.employee_id !== undefined) updates.employee_id = safeObjectId(body.employee_id) || body.employee_id;
      await usersCol.updateOne({ _id: oid }, { $set: updates });
      const user = await usersCol.findOne({ _id: oid });
      return { success: true, user: serialiseUser(user) };
    }

    if (event.method === 'DELETE') {
      await usersCol.deleteOne({ _id: oid });
      return { success: true };
    }

    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'User update failed' };
  }
}));

app.use('/api/admin/users/:id/reset-password', eventHandler(async (event) => {
  try {
    await requireDesktopSession(event);
    if (event.method !== 'POST') {
      event.node.res.statusCode = 405;
      return { success: false, error: 'Method not allowed' };
    }
    const db = mongoRequired();
    const id = event.context.params?.id;
    const oid = safeObjectId(id);
    const body = await readBody(event);
    const password = String(body?.password ?? '');
    if (!oid || !password) {
      event.node.res.statusCode = 400;
      return { success: false, error: 'User id and password are required.' };
    }
    await db.collection('users').updateOne(
      { _id: oid },
      { $set: { password_hash: hashPassword(password), require_password_change: false, updated_at: new Date() } },
    );
    const user = await db.collection('users').findOne({ _id: oid });
    return { success: true, user: serialiseUser(user) };
  } catch (error: any) {
    event.node.res.statusCode = error?.statusCode || 500;
    return { success: false, error: error?.message || 'Password reset failed' };
  }
}));



// One-shot bootstrap for employer demo account (no auth; gated by env token)
app.use('/api/admin/bootstrap-demo', eventHandler(async (event) => {
  if (event.method !== 'POST') {
    event.node.res.statusCode = 405;
    return { success: false, error: 'Method not allowed' };
  }
  const expected = process.env.BOOTSTRAP_TOKEN || 'untangled-bootstrap';
  try {
    const body = await readBody(event);
    const token = String(body?.token || event.node.req.headers['x-bootstrap-token'] || '');
    if (token !== expected) {
      event.node.res.statusCode = 403;
      return { success: false, error: 'Invalid bootstrap token' };
    }
    await ensureDesktopDemoUser();
    return {
      success: true,
      message: 'Demo account ensured',
      username: 'siyandan@untangled.co.za',
      password_hint: 'DEMO_PASSWORD env or default "admin"',
    };
  } catch (error: any) {
    event.node.res.statusCode = 500;
    return { success: false, error: error?.message || 'Bootstrap failed' };
  }
}));

// ============================================
// START SERVER
// ============================================

async function startServer() {
  await connectDB();
  
  const server = createServer(toNodeListener(app));
  server.listen(config.port, '0.0.0.0', () => {
    console.log(`\n🚀 Desktop Server running on http://localhost:${config.port}`);
    console.log(`🛠️ Assignment API: PUT/POST/PATCH /api/admin/quotes/:reference/assignment`);
    console.log(`📡 API available at http://localhost:${config.port}/api`);
    console.log(`🏥 Health check: http://localhost:${config.port}/api/health`);
    console.log(`📊 Dashboard: http://localhost:${config.port}/api/dashboard/summary`);
    console.log(`💾 Storage mode: ${isMongoConnected ? 'MongoDB ✅' : 'In-Memory ⚠️'}`);
    console.log(`\n✅ Server is ready!\n`);
  });
}

startServer();
