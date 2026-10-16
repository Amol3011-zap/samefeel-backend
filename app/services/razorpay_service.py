from typing import Optional
from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET


class RazorpayService:

    @staticmethod
    def _get_client():
        import razorpay
        return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    @staticmethod
    def create_order(amount: int, currency: str = "INR", receipt: str = None, description: str = None) -> dict:
        try:
            client = RazorpayService._get_client()
            order = client.order.create({
                "amount": amount,
                "currency": currency,
                "receipt": receipt or "receipt#1",
                "description": description or "SoulConnect Payment"
            })
            return {"success": True, "order_id": order["id"], "amount": order["amount"], "currency": order["currency"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_payment(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        try:
            client = RazorpayService._get_client()
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            return True
        except Exception:
            return False

    @staticmethod
    def fetch_payment(payment_id: str) -> Optional[dict]:
        try:
            client = RazorpayService._get_client()
            return client.payment.fetch(payment_id)
        except Exception:
            return None
