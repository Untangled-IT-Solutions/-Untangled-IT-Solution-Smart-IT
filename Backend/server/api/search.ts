import { defineEventHandler, getQuery } from 'h3';
import { Product, Service } from '../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const searchTerm = query.q as string;
    
    if (!searchTerm || searchTerm.trim().length === 0) {
      return {
        success: true,
        data: { products: [], services: [] },
      };
    }
    
    const products = await Product.find(
      { $text: { $search: searchTerm } },
      { score: { $meta: 'textScore' } }
    )
    .sort({ score: { $meta: 'textScore' } })
    .limit(20)
    .lean();
    
    const services = await Service.find(
      { $text: { $search: searchTerm } },
      { score: { $meta: 'textScore' } }
    )
    .sort({ score: { $meta: 'textScore' } })
    .limit(20)
    .lean();
    
    return {
      success: true,
      data: { products, services },
    };
  } catch (error) {
    console.error('Error searching:', error);
    return {
      success: false,
      error: 'Search failed',
    };
  }
});