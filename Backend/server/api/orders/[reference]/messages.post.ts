import { defineEventHandler, readBody } from "h3";
import OrderMessage from "../../../models/OrderMessage";

export default defineEventHandler(async(event)=>{

 const reference = event.context.params!.reference;
 const body = await readBody(event);

 const message = await OrderMessage.create({
   orderReference:reference,
   senderType:body.senderType,
   senderName:body.senderName,
   recipientType:body.recipientType,
   message:body.message
 });

 return{
   success:true,
   message
 };

});