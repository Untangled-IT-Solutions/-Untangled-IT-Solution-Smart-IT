import { defineEventHandler } from "h3";
import QuoteMessage from "./../../../models/QuoteMessage";

export default defineEventHandler(async(event)=>{

 const reference = event.context.params!.reference;

 const messages = await QuoteMessage
 .find({quoteReference:reference})
 .sort({createdAt:1});

 return{
   success:true,
   messages
 };

});