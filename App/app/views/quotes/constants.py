"""Quote workflow constants – no UI, no I/O."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Assign → Collect Details → Quote → Client Approves → Payment → Delivery → Complete
STATUS_OPTIONS = [
    "Pending",
    "Assigned",
    "Awaiting Details",
    "Quoted",
    "Awaiting Client Approval",
    "Awaiting Payment",
    "Paid",
    "In Progress",
    "Out for Delivery",
    "Completed",
    "Returned",
    # Legacy (still supported for existing jobs)
    "In Review",
    "Accepted",
    "Awaiting Client",
]

STATUS_COLORS = {
    "Pending": "#FFC107",
    "Assigned": "#2196F3",
    "Awaiting Details": "#FF9800",
    "Quoted": "#4CAF50",
    "Awaiting Client Approval": "#9C27B0",
    "Awaiting Payment": "#E91E63",
    "Paid": "#00BCD4",
    "In Progress": "#FF9800",
    "Out for Delivery": "#3F51B5",
    "Completed": "#9E9E9E",
    "Returned": "#F44336",
    "In Review": "#FF9800",
    "Accepted": "#4CAF50",
    "Awaiting Client": "#9C27B0",
}

STATUS_ICONS = {
    "Pending": "⏳",
    "Assigned": "📋",
    "Awaiting Details": "📝",
    "Quoted": "💰",
    "Awaiting Client Approval": "🤝",
    "Awaiting Payment": "💳",
    "Paid": "✅",
    "In Progress": "🔧",
    "Out for Delivery": "🚚",
    "Completed": "🏁",
    "Returned": "↩️",
    "In Review": "📝",
    "Accepted": "✅",
    "Awaiting Client": "⏳",
}

STATUS_HELP = {
    "Pending": "Client submitted a request. Review and assign if needed.",
    "Assigned": "Job assigned. Contact the client and collect any missing details.",
    "Awaiting Details": "Missing address, measurements, or other info. Collect from client.",
    "Quoted": "Quotation prepared with pricing. Send to the client.",
    "Awaiting Client Approval": "Client is reviewing the quote. Wait for accept/reject.",
    "Awaiting Payment": "Client accepted the quote. Waiting for payment.",
    "Paid": "Payment received. Schedule work or delivery.",
    "In Progress": "Manufacturing or service is underway. Update progress.",
    "Out for Delivery": "Item is being delivered. Track until delivered.",
    "Completed": "Delivered successfully. Job closed.",
    "Returned": "Returned to manager for reassignment.",
    "In Review": "Legacy: pricing and details being worked out.",
    "Accepted": "Legacy: job accepted by employee.",
    "Awaiting Client": "Legacy: waiting for client response.",
}

# Next-step guidance for the primary action button
WORKFLOW_NEXT = {
    "Pending": {"label": "📋 Assign / Start", "action": "assign_start", "color": "#2196F3"},
    "Assigned": {"label": "📝 Request Details", "action": "request_details", "color": "#FF9800"},
    "Awaiting Details": {"label": "💰 Generate Quote", "action": "generate_quote", "color": "#4CAF50"},
    "Quoted": {"label": "📤 Send for Approval", "action": "send_approval", "color": "#9C27B0"},
    "Awaiting Client Approval": {"label": "💳 Mark Awaiting Payment", "action": "await_payment", "color": "#E91E63"},
    "Awaiting Payment": {"label": "✅ Mark Paid", "action": "mark_paid", "color": "#00BCD4"},
    "Paid": {"label": "🔧 Start Work", "action": "start_work", "color": "#FF9800"},
    "In Progress": {"label": "🚚 Out for Delivery", "action": "out_for_delivery", "color": "#3F51B5"},
    "Out for Delivery": {"label": "🏁 Mark Completed", "action": "complete", "color": "#9E9E9E"},
    "Accepted": {"label": "🔧 Start Work", "action": "start_work", "color": "#FF9800"},
    "In Review": {"label": "💰 Generate Quote", "action": "generate_quote", "color": "#4CAF50"},
    "Awaiting Client": {"label": "💳 Mark Awaiting Payment", "action": "await_payment", "color": "#E91E63"},
}

MANAGER_ROLES = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]
STAFF_ROLES = ["Staff", "Intern"]

# Map display status to MongoDB / API status
DISPLAY_TO_MONGO = {
    "Pending": "received",
    "Assigned": "assigned",
    "Awaiting Details": "awaiting_details",
    "Quoted": "quoted",
    "Awaiting Client Approval": "awaiting_client_approval",
    "Awaiting Payment": "awaiting_payment",
    "Paid": "paid",
    "In Progress": "in_progress",
    "Out for Delivery": "out_for_delivery",
    "Completed": "completed",
    "Returned": "returned",
    "In Review": "in_review",
    "Accepted": "accepted",
    "Awaiting Client": "awaiting_client",
}

MONGO_TO_DISPLAY = {
    "received": "Pending",
    "pending": "Pending",
    "assigned": "Assigned",
    "awaiting_details": "Awaiting Details",
    "quoted": "Quoted",
    "awaiting_client_approval": "Awaiting Client Approval",
    "awaiting_client": "Awaiting Client Approval",  # map legacy to new name
    "awaiting_payment": "Awaiting Payment",
    "paid": "Paid",
    "in_progress": "In Progress",
    "in progress": "In Progress",
    "out_for_delivery": "Out for Delivery",
    "completed": "Completed",
    "returned": "Returned",
    "in_review": "In Review",
    "accepted": "Accepted",
    "awaiting_director": "In Review",
    "awaiting director": "In Review",
}

