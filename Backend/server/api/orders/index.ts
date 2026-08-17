// server/api/orders/index.ts
import { defineEventHandler, readBody } from 'h3';
import { Order } from '../../db/index.js';

export default defineEventHandler(async (event) => {
  if (event.method === 'POST') {
    try {
      const body = await readBody(event);
      
      console.log('📥 Order received:', JSON.stringify(body, null, 2));
      
      // Validate required fields
      const { customerName, email, phone, address, items, total } = body;
      
      if (!customerName || !email || !phone || !address || !items || items.length === 0) {
        return {
          success: false,
          error: 'Missing required fields',
        };
      }
      
      // Create order with auto-generated reference
      const order = new Order({
        customerName,
        company: body.company || '',
        email: email.toLowerCase().trim(),
        phone,
        address,
        notes: body.notes || '',
        items: items.map((item: any) => ({
          id: item.id,
          name: item.name,
          qty: item.qty,
          price: item.price || 0,
        })),
        total: total || 0,
        status: 'pending',
      });
      
      await order.save();
      
      console.log(`✅ Order created with reference: ${order.reference}`);
      
      return {
        success: true,
        orderId: order._id,
        orderReference: order.reference, // Return the reference
      };
    } catch (error) {
      console.error('❌ Error creating order:', error);
      return {
        success: false,
        error: 'Failed to create order',
      };
    }
  }
  
  return { success: false, error: 'Method not allowed' };
});