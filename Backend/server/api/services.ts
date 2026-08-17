import { defineEventHandler, getQuery } from 'h3';
import { Service } from '../db/index.js';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const { group, search } = query;
    
    let filter: any = {};
    
    if (group) {
      filter.group = group;
    }
    
    let services;
    
    if (search && typeof search === 'string') {
      services = await Service.find(
        { $text: { $search: search } },
        { score: { $meta: 'textScore' } }
      )
      .sort({ score: { $meta: 'textScore' } })
      .lean();
    } else {
      services = await Service.find(filter).lean();
    }
    
    return {
      success: true,
      data: services,
    };
  } catch (error) {
    console.error('Error fetching services:', error);
    return {
      success: false,
      error: 'Failed to fetch services',
    };
  }
});