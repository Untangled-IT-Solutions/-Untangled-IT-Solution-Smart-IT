import { defineEventHandler, readBody } from "h3";
import QuoteMessage from "../../../models/QuoteMessage";

export default defineEventHandler(async(event)=>{

 const reference = event.context.params!.reference;
 const body = await readBody(event);

 const msg = await QuoteMessage.create({
   quoteReference:reference,
   senderType:body.senderType,
   senderName:body.senderName,
   recipientType:body.recipientType,
   message:body.message
 });

 return {success:true,message:msg};

});