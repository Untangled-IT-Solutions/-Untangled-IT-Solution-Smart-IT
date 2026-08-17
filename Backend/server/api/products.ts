import { defineEventHandler, getQuery } from 'h3';
import { Product } from '../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const { search, category, segment } = query;
    
    let filter: any = {};
    
    if (category) {
      filter.category = category;
    }
    
    if (segment) {
      filter.segment = segment;
    }
    
    let products;
    
    if (search && typeof search === 'string') {
      products = await Product.find(
        { $text: { $search: search } },
        { score: { $meta: 'textScore' } }
      )
      .sort({ score: { $meta: 'textScore' } })
      .lean();
    } else {
      products = await Product.find(filter).lean();
    }
    
    return {
      success: true,
      data: products,
    };
  } catch (error) {
    console.error('Error fetching products:', error);
    return {
      success: false,
      error: 'Failed to fetch products',
    };
  }
});