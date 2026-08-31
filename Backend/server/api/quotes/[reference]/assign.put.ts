import { defineEventHandler, readBody, createError } from "h3";
import Quote from "../../../models/Quote";

export default defineEventHandler(async (event) => {
  const reference = event.context.params?.reference as string;
  const body = await readBody(event);

  const quote = await Quote.findOne({ reference });

  if (!quote) {
    throw createError({
      statusCode: 404,
      statusMessage: "Quote not found",
    });
  }

  quote.assigned_to = body.employee_id;
  quote.assigned_name = body.employee_name;
  quote.assigned_by = body.assigned_by;
  quote.assigned_at = new Date();
  quote.status = "assigned";

  await quote.save();

  return {
    success: true,
    message: "Quote assigned successfully",
    quote,
  };
});