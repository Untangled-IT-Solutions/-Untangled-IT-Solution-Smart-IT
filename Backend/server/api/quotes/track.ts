import { defineEventHandler, getQuery } from 'h3';
import { Quote } from '../../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const reference = query.ref as string;
    const email = query.email as string;
    
    console.log(`🔍 Tracking quote: ${reference} - ${email}`);
    
    if (!reference || !email) {
      console.error('❌ Missing reference or email');
      return {
        success: false,
        error: 'Reference and email are required',
        quote: null,
      };
    }
    
    // Find quote by reference and email
    const quote = await Quote.findOne({ 
      reference: reference.toUpperCase(), 
      email: email.toLowerCase() 
    }).lean();
    
    if (!quote) {
      console.log(`❌ Quote not found: ${reference}`);
      return {
        success: false,
        error: 'Quote not found',
        quote: null,
      };
    }
    
    console.log(`✅ Quote found: ${reference}`);
    
    // Return quote data
    return {
      success: true,
      quote: {
        id: quote._id.toString(),
        reference: quote.reference,
        customerName: quote.customerName,
        email: quote.email,
        phone: quote.phone,
        status: quote.status,
        items: quote.items.map(item => ({
          id: item.id,
          name: item.name,
          qty: item.qty,
        })),
        replyMessage: quote.replyMessage || null,
        repliedAt: quote.repliedAt ? quote.repliedAt.toISOString() : null,
        createdAt: quote.createdAt.toISOString(),
      },
    };
  } catch (error) {
    console.error('❌ Error tracking quote:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to track quote',
      quote: null,
    };
  }
});