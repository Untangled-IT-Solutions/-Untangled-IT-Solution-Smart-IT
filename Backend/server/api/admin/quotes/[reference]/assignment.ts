// server/api/admin/quotes/[reference]/assignment.put.ts
import { eventHandler, readBody } from 'h3';
import mongoose from 'mongoose';

// Import your Quote model - adjust the path as needed
// Assuming you have a models directory
import { Quote } from '../../../models/Quote';

export default eventHandler(async (event) => {
  // Support PUT, POST, PATCH
  if (!["PUT", "POST", "PATCH"].includes(event.method || "")) {
    event.node.res.statusCode = 405;
    return { success: false, error: "Method not allowed" };
  }

  const reference = event.context.params?.reference;
  const body = await readBody(event);

  console.log(`📌 ASSIGNMENT: ${reference}`);

  if (!reference) {
    event.node.res.statusCode = 400;
    return { success: false, error: "Reference is required" };
  }

  // Find the quote
  const quote = await Quote.findOne({ 
    reference: { $regex: `^${reference}$`, $options: 'i' } 
  });

  if (!quote) {
    event.node.res.statusCode = 404;
    return { success: false, error: `Quote not found: ${reference}` };
  }

  // Get employee info
  const employeeId = body?.employee_id ?? body?.employeeId ?? body?.assigned_to ?? body?.assignedTo ?? null;
  let assignedTo = null;

  if (employeeId) {
    try {
      const db = mongoose.connection.db;
      const employee = await db.collection('employees').findOne({
        $or: [
          { employee_id: employeeId },
          { id: employeeId },
          { _id: new mongoose.Types.ObjectId(employeeId) }
        ]
      });
      if (employee) {
        assignedTo = {
          id: employee._id?.toString?.() || employee._id,
          employee_id: employee.employee_id || employee.id || employee._id?.toString?.() || null,
          full_name: employee.full_name || [employee.first_name, employee.surname || employee.last_name].filter(Boolean).join(' ') || 'Unknown',
          email: employee.email || employee.email_address || '',
          department: employee.department || '',
          position: employee.position || '',
          status: employee.status || 'Active'
        };
        console.log(`✅ Found employee: ${assignedTo.full_name}`);
      }
    } catch (err) {
      console.warn('⚠️ Could not find employee:', employeeId);
    }
  }

  // Update quote
  quote.assigned_to = assignedTo;
  quote.assigned_by = assignedTo ? { id: 'system', username: 'admin' } : null;
  
  if (assignedTo) {
    quote.status = 'assigned';
  }

  await quote.save();

  console.log(`✅ Quote ${reference} assigned successfully`);

  return {
    success: true,
    message: assignedTo ? "Quote assigned successfully" : "Quote unassigned",
    quote: {
      reference: quote.reference,
      assigned_to: quote.assigned_to,
      assigned_by: quote.assigned_by,
      status: quote.status
    }
  };
});