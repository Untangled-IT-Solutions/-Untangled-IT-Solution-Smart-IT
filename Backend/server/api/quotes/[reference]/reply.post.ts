import { defineEventHandler, readBody } from "h3";
import QuoteMessage from "../../../models/QuoteMessage";
import { Quote } from "../../../db";

export default defineEventHandler(async(event)=>{

 const reference = event.context.params!.reference;
 const body = await readBody(event);

 await QuoteMessage.create({
   quoteReference:reference,
   senderType:"client",
   senderName:body.customerName,
   recipientType:"employee",
   message:body.message
 });

 await Quote.updateOne(
   {reference},
   {$set:{status:"in_review"}}
 );

 return{success:true};

});