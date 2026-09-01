import { defineEventHandler, getQuery } from 'h3';
import { CatalogItem } from '../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const { category } = query;
    
    let filter: any = {};
    
    if (category) {
      filter.category = category;
    }
    
    const items = await CatalogItem.find(filter).lean();
    
    return {
      success: true,
      data: items,
    };
  } catch (error) {
    console.error('Error fetching catalog:', error);
    return {
      success: false,
      error: 'Failed to fetch catalog',
    };
  }
});