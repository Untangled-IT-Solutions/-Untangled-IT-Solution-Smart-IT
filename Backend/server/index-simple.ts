// Backend/server/index-simple.ts
import { createApp, eventHandler, toNodeListener, readBody, getQuery } from 'h3';
import { listen } from 'listhen';
import dotenv from 'dotenv';

dotenv.config();

// In-memory storage
const quotes: any[] = [];
const orders: any[] = [];

function generateReference() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = 'UQ-';
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

const app = createApp();

// CORS middleware
app.use(eventHandler(async (event) => {
  event.node.res.setHeader('Access-Control-Allow-Origin', '*');
  event.node.res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  event.node.res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  
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
  mode: 'in-memory',
  quotes: quotes.length,
  orders: orders.length
})));

// POST /api/quotes - Submit a quote
app.use('/api/quotes', eventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      console.log('📥 Quote received:', JSON.stringify(body, null, 2));
      
      const { customerName, company, email, phone, notes, items } = body;
      
      // Validate
      if (!customerName || !email || !phone || !items || items.length === 0) {
        return { 
          success: false, 
          error: 'Missing required fields: customerName, email, phone, and at least one item are required' 
        };
      }
      
      // Generate reference
      const reference = generateReference();
      
      // Create quote
      const quote = {
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
        status: 'received',
        createdAt: new Date().toISOString()
      };
      
      quotes.push(quote);
      console.log(`✅ Quote saved with reference: ${reference}`);
      console.log(`📊 Total quotes: ${quotes.length}`);
      
      return { 
        success: true, 
        reference: quote.reference 
      };
      
    } catch (error) {
      console.error('❌ Error processing quote:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to process quote' 
      };
    }
  }
  
  // GET /api/quotes - List all quotes (for debugging)
  if (event.method === 'GET') {
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
  }
  
  return { success: false, error: 'Method not allowed' };
}));

// GET /api/quotes/track - Track a quote
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
    
    const quote = quotes.find(q => 
      q.reference === ref.toUpperCase() && 
      q.email === email.toLowerCase()
    );
    
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
        ...quote,
        replyMessage: null,
        repliedAt: null
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

// POST /api/orders - Submit an order
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
      
      const order = {
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
        status: 'received',
        createdAt: new Date().toISOString()
      };
      
      orders.push(order);
      console.log(`✅ Order saved with ID: ${orderId}`);
      console.log(`📊 Total orders: ${orders.length}`);
      
      return {
        success: true,
        orderId: order.orderId
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

// Start server
const PORT = process.env.PORT || 5001;
try {
  await listen(toNodeListener(app), { 
    port: PORT,
    hostname: '0.0.0.0'
  });
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`📡 API available at http://localhost:${PORT}/api`);
  console.log(`🏥 Health check: http://localhost:${PORT}/api/health`);
  console.log(`📋 Quotes API: http://localhost:${PORT}/api/quotes`);
  console.log(`📋 Orders API: http://localhost:${PORT}/api/orders`);
  console.log(`💡 Using in-memory storage (no MongoDB needed)`);
} catch (error) {
  console.error('❌ Failed to start server:', error);
  process.exit(1);
}
