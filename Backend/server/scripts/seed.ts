import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Product, Service, CatalogItem } from '../db/index.js';

dotenv.config();

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/untangled-it';

async function seedDatabase() {
  try {
    await mongoose.connect(MONGODB_URI);
    console.log('Connected to MongoDB');

    // Import data from frontend
    const { products, services } = await import('../../../Frontend/src/lib/store-data.js');
    const { CATALOG } = await import('../../../Frontend/src/lib/catalog.js');

    // Clear existing data
    await Product.deleteMany({});
    await Service.deleteMany({});
    await CatalogItem.deleteMany({});
    console.log('Cleared existing data');

    // Insert data
    await Product.insertMany(products);
    console.log(`✅ Inserted ${products.length} products`);

    await Service.insertMany(services);
    console.log(`✅ Inserted ${services.length} services`);

    await CatalogItem.insertMany(CATALOG);
    console.log(`✅ Inserted ${CATALOG.length} catalog items`);

    console.log('✨ Seeding completed successfully');
    process.exit(0);
  } catch (error) {
    console.error('❌ Seeding failed:', error);
    process.exit(1);
  }
}

seedDatabase();
