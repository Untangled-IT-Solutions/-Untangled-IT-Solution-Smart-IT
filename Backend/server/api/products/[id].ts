import { defineEventHandler } from 'h3';
import { Product } from '../../db';

export default defineEventHandler(async (event) => {
  try {
    const id = event.context.params?.id;
    
    if (!id) {
      return {
        success: false,
        error: 'Product ID is required',
      };
    }
    
    const product = await Product.findOne({ id }).lean();
    
    if (!product) {
      return {
        success: false,
        error: 'Product not found',
      };
    }
    
    return {
      success: true,
      data: product,
    };
  } catch (error) {
    console.error('Error fetching product:', error);
    return {
      success: false,
      error: 'Failed to fetch product',
    };
  }
});