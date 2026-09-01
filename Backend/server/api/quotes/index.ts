import { defineEventHandler, readBody } from 'h3';
import { Quote } from '../../db/index.js';

function generateReference() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  let result = 'UQ-';
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export default defineEventHandler(async (event) => {
  console.log('🚀 QUOTE API CALLED!');
  console.log('📝 Method:', event.method);
  console.log('📝 Path:', event.path);
  
  try {
    console.log('📝 Reading body...');
    const body = await readBody(event);
    console.log('📦 Body received:', JSON.stringify(body, null, 2));
    
    const { customerName, email, phone, items } = body;
    
    if (!customerName || !email || !phone || !items || items.length === 0) {
      console.error('❌ Missing fields');
      return { 
        success: false, 
        error: 'Missing required fields' 
      };
    }
    
    // Generate reference
    const reference = generateReference();
    console.log('🔑 Generated reference:', reference);
    
    // Create quote object
    const quoteData = {
      reference,
      customerName,
      company: body.company || '',
      email: email.toLowerCase(),
      phone,
      notes: body.notes || '',
      items: items.map((item: any) => ({
        id: item.id,
        name: item.name,
        kind: item.kind || 'product',
        qty: Number(item.qty) || 1,
      })),
      status: 'received',
    };
    
    console.log('💾 Saving quote to MongoDB...');
    
    // Save to database
    const quote = new Quote(quoteData);
    await quote.save();
    
    console.log(`✅ Quote saved! Reference: ${reference}`);
    
    return { 
      success: true, 
      reference: quote.reference 
    };
    
  } catch (error) {
    console.error('❌ Error in quote API:', error);
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to create quote' 
    };
  }
});