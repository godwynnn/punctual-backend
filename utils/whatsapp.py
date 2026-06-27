import os
import sys
import logging
import requests
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def send_whatsapp_message(order_group_id, retry_count=0):
    from orders.models import Order
    from core.cron import scheduler

    # 1. Fetch the orders in this group
    orders = Order.objects.filter(order_group_id=order_group_id).select_related('product', 'store')
    if not orders.exists():
        logger.warning(f"[WhatsApp] No orders found with group ID {order_group_id}")
        return

    first_order = orders[0]
    store = first_order.store
    
    # 2. Check if the store owner has configured a WhatsApp phone number
    recipient_phone = store.whatsapp
    if not recipient_phone:
        logger.warning(f"[WhatsApp] Store '{store.name}' has no WhatsApp number configured.")
        return

    # Clean recipient phone number (remove leading +, other non-digits)
    if recipient_phone.startswith("+"):
        recipient_phone = recipient_phone[1:]
    recipient_phone = "".join(filter(str.isdigit, recipient_phone))
    

    # 3. Format order items details
    items_lines = []
    total_amount = 0
    for order in orders:
        qty = order.quantity
        prod_name = order.product.name
        price = order.amount
        total_amount += price
        
        # Extras formatting
        extras_text = ""
        if order.extras:
            extras_parts = []
            for ex in order.extras:
                extras_parts.append(f"{ex.get('selectedQty', 1)}x {ex.get('name')}")
            extras_text = f" (Extras: {', '.join(extras_parts)})"
            
        items_lines.append(f"• {qty}x {prod_name}{extras_text} - ₦{float(price):,}")

    items_text = "\n".join(items_lines)
    customer_name = first_order.customer_name
    table_number = first_order.table_number or "N/A"
    notes = first_order.notes or "None"
    created_at = first_order.created_at.strftime("%Y-%m-%d %H:%M:%S")

    # 4. Construct direct Link to dashboard
    frontend_url = os.getenv('FRONTEND_URL') or "http://localhost:3000"
    dashboard_url = f"{frontend_url.rstrip('/')}/dashboard/stores/{store.id}?tab=orders"

    # 5. Format the Markdown message body
    message_body = (
        f"🛍️ *New Order Received!*\n\n"
        f"*Store:* {store.name}\n"
        f"*Customer:* {customer_name}\n"
        f"*Table:* {table_number}\n"
        f"*Order ID:* {order_group_id}\n"
        f"*Date/Time:* {created_at}\n\n"
        f"*Items:*\n{items_text}\n\n"
        f"*Total Value:* ₦{float(total_amount):,}\n"
        f"*Special Notes:* {notes}\n\n"
        f"Manage this order in your dashboard:\n{dashboard_url}"
    )

    # 6. Development Fallback: Always print to console safely
    print("\n" + "="*50)
    print(f"--- WHATSAPP MESSAGE SENT TO {store.whatsapp} ---")
    try:
        print(message_body)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'ascii'
        print(message_body.encode(encoding, errors='replace').decode(encoding))
    print("="*50 + "\n")

    # 7. Meta Cloud API Send Logic
    phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID")
    access_token = os.getenv("META_WA_ACCESS_TOKEN")

    if phone_number_id and access_token:
        url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "body": message_body
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info(f"[WhatsApp] Successfully sent message for order {order_group_id} to {recipient_phone}.")
            else:
                logger.error(f"[WhatsApp] Meta API error (Status {response.status_code}): {response.text}")
                response.raise_for_status()
        except Exception as e:
            logger.error(f"[WhatsApp] Failed to send message (Attempt {retry_count + 1}/3): {str(e)}")
            
            # Reschedule retry using APScheduler in 5 minutes
            if retry_count < 2:
                next_run = timezone.now() + timedelta(minutes=5)
                job_id = f"whatsapp_retry_{order_group_id}_{retry_count + 1}"
                
                # Check if job already exists before scheduling
                if not scheduler.get_job(job_id):
                    try:
                        scheduler.add_job(
                            send_whatsapp_message,
                            'date',
                            run_date=next_run,
                            args=[order_group_id, retry_count + 1],
                            id=job_id
                        )
                        logger.info(f"[WhatsApp] Scheduled retry job {job_id} at {next_run}")
                    except Exception as schedule_err:
                        logger.error(f"[WhatsApp] Rescheduling error: {str(schedule_err)}")
            else:
                logger.error(f"[WhatsApp] Retries exhausted for order {order_group_id}. Message failed to send.")


def schedule_whatsapp_message(order_group_id):
    # 1. Run synchronously if in unit tests to make assertions simple and prevent async race conditions
    if 'test' in sys.argv or 'test_coverage' in sys.argv:
        send_whatsapp_message(order_group_id)
        return

    # 2. Otherwise run asynchronously in 2 seconds
    try:
        from core.cron import scheduler
        scheduler.add_job(
            send_whatsapp_message,
            'date',
            run_date=timezone.now() + timedelta(seconds=2),
            args=[order_group_id],
            id=f"whatsapp_{order_group_id}"
        )
        logger.info(f"[WhatsApp] Scheduled order notification job for {order_group_id}")
    except Exception as e:
        logger.error(f"[WhatsApp] Error adding schedule job: {str(e)}")
        # Fallback to synchronous in case of startup issues
        send_whatsapp_message(order_group_id)
