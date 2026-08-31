import { defineEventHandler } from "h3";
import OrderMessage from "../../../models/OrderMessage";

export default defineEventHandler(async(event)=>{

 const reference = event.context.params!.reference;

 const messages = await OrderMessage
 .find({orderReference:reference})
 .sort({createdAt:1});

 return{
   success:true,
   messages
 };

});