// server/api/orders/status.ts
import { defineEventHandler, readBody } from 'h3';
import { Order } from '../../db/index.js';

export default defineEventHandler(async (event) => {
  if (event.method === 'PATCH' || event.method === 'POST') {
    try {
      const body = await readBody(event);
      const { reference, status, trackingNumber, carrier, estimatedDelivery } = body;
      
      console.log(`🔄 Updating order status: ${reference} -> ${status}`);
      
      if (!reference || !status) {
        return {
          success: false,
          message: 'Reference and status are required'
        };
      }
      
      const order = await Order.findOne({ reference: reference.toUpperCase() });
      
      if (!order) {
        return {
          success: false,
          message: 'Order not found'
        };
      }
      
      order.status = status;
      
      if (trackingNumber) order.trackingNumber = trackingNumber;
      if (carrier) order.carrier = carrier;
      if (estimatedDelivery) order.estimatedDelivery = new Date(estimatedDelivery);
      
      await order.save();
      
      console.log(`✅ Order ${reference} status updated to: ${status}`);
      
      return {
        success: true,
        message: 'Order status updated',
        order: {
          reference: order.reference,
          status: order.status,
          trackingNumber: order.trackingNumber,
          carrier: order.carrier,
          estimatedDelivery: order.estimatedDelivery,
        }
      };
    } catch (error) {
      console.error('❌ Error updating order status:', error);
      return {
        success: false,
        message: 'Failed to update order status'
      };
    }
  }
  
  return { success: false, message: 'Method not allowed' };
});