// server/api/orders/track.ts
import { defineEventHandler, getQuery } from 'h3';
import { Order } from '../../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const ref = query.ref as string;
    const email = query.email as string;
    
    console.log(`🔍 ===== TRACK ORDER REQUEST =====`);
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
    
    // Try exact match first
    let order = await Order.findOne({ 
      reference: cleanRef, 
      email: cleanEmail 
    });
    
    // If not found, try case insensitive
    if (!order) {
      console.log(`🔍 Trying case insensitive search...`);
      order = await Order.findOne({ 
        reference: { $regex: new RegExp(`^${cleanRef}$`, 'i') },
        email: { $regex: new RegExp(`^${cleanEmail}$`, 'i') }
      });
    }
    
    // If still not found, try just by reference
    if (!order) {
      console.log(`🔍 Trying search by reference only...`);
      order = await Order.findOne({ 
        reference: { $regex: new RegExp(`^${cleanRef}$`, 'i') }
      });
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
});