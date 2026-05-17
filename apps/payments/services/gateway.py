"""
KLA WasteNet Pro — Payment Service Layer
Handles MTN Mobile Money, Airtel Money, and Flutterwave integrations
"""
import uuid
import base64
import hashlib
import hmac
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('apps.payments')


class PaymentServiceError(Exception):
    pass


# ─── MTN Mobile Money Service ─────────────────────────────────────────────────

class MTNMoMoService:
    """
    MTN Mobile Money Collections API
    Docs: https://momodeveloper.mtn.com/docs/services/collection
    """

    BASE_URL = settings.MTN_MOMO_BASE_URL
    PRIMARY_KEY = settings.MTN_MOMO_PRIMARY_KEY
    API_USER = settings.MTN_MOMO_API_USER
    API_KEY = settings.MTN_MOMO_API_KEY
    CURRENCY = settings.MTN_MOMO_CURRENCY
    ENVIRONMENT = settings.MTN_MOMO_ENVIRONMENT

    def _get_token(self):
        """Get OAuth2 access token"""
        credentials = base64.b64encode(
            f"{self.API_USER}:{self.API_KEY}".encode()
        ).decode()

        resp = requests.post(
            f"{self.BASE_URL}/collection/token/",
            headers={
                "Authorization": f"Basic {credentials}",
                "Ocp-Apim-Subscription-Key": self.PRIMARY_KEY,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            raise PaymentServiceError(f"MTN token error: {resp.text}")

        return resp.json()['access_token']

    def request_to_pay(self, phone, amount, reference, payer_note="Waste Collection Fee"):
        """
        Initiate a Request to Pay from a subscriber's account.

        Args:
            phone: Subscriber phone in format 256XXXXXXXXX
            amount: Amount in UGX
            reference: Unique payment reference
            payer_note: Description shown to payer

        Returns:
            dict with 'status', 'reference_id', 'response'
        """
        token = self._get_token()
        ref_id = str(uuid.uuid4())

        payload = {
            "amount": str(int(amount)),
            "currency": self.CURRENCY,
            "externalId": reference,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone.replace('+', '').replace(' ', ''),
            },
            "payerMessage": f"KLA WasteNet - {payer_note}",
            "payeeNote": f"Payment ref: {reference}",
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": ref_id,
            "X-Target-Environment": self.ENVIRONMENT,
            "Ocp-Apim-Subscription-Key": self.PRIMARY_KEY,
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{self.BASE_URL}/collection/v1_0/requesttopay",
            json=payload,
            headers=headers,
            timeout=30,
        )

        logger.info(f"MTN RTP initiated: ref={ref_id} status={resp.status_code}")

        return {
            "status": "pending" if resp.status_code == 202 else "failed",
            "reference_id": ref_id,
            "response": resp.json() if resp.content else {},
            "http_status": resp.status_code,
        }

    def check_payment_status(self, reference_id):
        """Check the status of a Request to Pay transaction"""
        token = self._get_token()

        resp = requests.get(
            f"{self.BASE_URL}/collection/v1_0/requesttopay/{reference_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Target-Environment": self.ENVIRONMENT,
                "Ocp-Apim-Subscription-Key": self.PRIMARY_KEY,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            raise PaymentServiceError(f"MTN status check error: {resp.text}")

        data = resp.json()
        status_map = {
            "SUCCESSFUL": "successful",
            "FAILED": "failed",
            "PENDING": "pending",
        }

        return {
            "status": status_map.get(data.get("status", ""), "pending"),
            "data": data,
        }


# ─── Airtel Money Service ──────────────────────────────────────────────────────

class AirtelMoneyService:
    """
    Airtel Money API
    Docs: https://developers.airtel.africa/documentation
    """

    BASE_URL = settings.AIRTEL_BASE_URL
    CLIENT_ID = settings.AIRTEL_CLIENT_ID
    CLIENT_SECRET = settings.AIRTEL_CLIENT_SECRET
    CURRENCY = settings.AIRTEL_CURRENCY
    ENVIRONMENT = settings.AIRTEL_ENVIRONMENT

    def _get_token(self):
        """Get OAuth2 access token"""
        resp = requests.post(
            f"{self.BASE_URL}/auth/oauth2/token",
            json={
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        if resp.status_code != 200:
            raise PaymentServiceError(f"Airtel token error: {resp.text}")

        return resp.json()['access_token']

    def collect(self, phone, amount, reference, narration="Waste Collection Fee"):
        """Initiate Airtel Money collection"""
        token = self._get_token()

        payload = {
            "reference": reference,
            "subscriber": {
                "country": "UG",
                "currency": self.CURRENCY,
                "msisdn": phone.replace('+', '').replace(' ', ''),
            },
            "transaction": {
                "amount": int(amount),
                "country": "UG",
                "currency": self.CURRENCY,
                "id": str(uuid.uuid4()),
            },
        }

        resp = requests.post(
            f"{self.BASE_URL}/merchant/v1/payments/",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "X-Country": "UG",
                "X-Currency": self.CURRENCY,
            },
            timeout=30,
        )

        logger.info(f"Airtel collect: ref={reference} status={resp.status_code}")

        data = resp.json()
        return {
            "status": "pending" if data.get("status", {}).get("code") == "DP00800001000" else "failed",
            "reference": data.get("data", {}).get("transaction", {}).get("id", ""),
            "response": data,
        }

    def check_status(self, transaction_id):
        """Check Airtel payment status"""
        token = self._get_token()

        resp = requests.get(
            f"{self.BASE_URL}/standard/v1/payments/{transaction_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Country": "UG",
                "X-Currency": self.CURRENCY,
            },
            timeout=15,
        )

        data = resp.json()
        status_code = data.get("data", {}).get("transaction", {}).get("status", "")
        status_map = {
            "TS": "successful",  # Transaction Successful
            "TF": "failed",      # Transaction Failed
            "TP": "pending",     # Transaction Pending
        }

        return {
            "status": status_map.get(status_code, "pending"),
            "data": data,
        }


# ─── Flutterwave Service ───────────────────────────────────────────────────────

class FlutterwaveService:
    """
    Flutterwave Payment Gateway
    Docs: https://developer.flutterwave.com/docs
    """

    BASE_URL = settings.FLW_BASE_URL
    SECRET_KEY = settings.FLW_SECRET_KEY
    PUBLIC_KEY = settings.FLW_PUBLIC_KEY

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.SECRET_KEY}",
            "Content-Type": "application/json",
        }

    def initiate_payment(self, user, amount, reference, redirect_url, description="Waste Collection"):
        """Create a payment link for hosted checkout"""
        payload = {
            "tx_ref": reference,
            "amount": str(amount),
            "currency": "UGX",
            "redirect_url": redirect_url,
            "payment_options": "mobilemoneyuganda,card,ussd",
            "customer": {
                "email": user.email,
                "phonenumber": user.phone,
                "name": user.get_display_name(),
            },
            "customizations": {
                "title": "KLA WasteNet",
                "description": description,
                "logo": f"{settings.SITE_URL}/static/images/logo.png",
            },
            "meta": {
                "user_id": str(user.id),
                "source": "kla_wastenet",
            },
        }

        resp = requests.post(
            f"{self.BASE_URL}/payments",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )

        data = resp.json()
        logger.info(f"FLW payment init: ref={reference} status={data.get('status')}")

        if data.get("status") == "success":
            return {
                "status": "success",
                "payment_link": data["data"]["link"],
                "reference": reference,
                "response": data,
            }

        raise PaymentServiceError(f"FLW init failed: {data.get('message', 'Unknown error')}")

    def verify_transaction(self, transaction_id):
        """Verify a Flutterwave transaction by ID"""
        resp = requests.get(
            f"{self.BASE_URL}/transactions/{transaction_id}/verify",
            headers=self._headers(),
            timeout=15,
        )

        data = resp.json()
        if data.get("status") == "success":
            tx = data["data"]
            status_map = {
                "successful": "successful",
                "failed": "failed",
                "pending": "pending",
            }
            return {
                "status": status_map.get(tx.get("status", ""), "pending"),
                "amount": tx.get("amount"),
                "currency": tx.get("currency"),
                "data": data,
            }

        raise PaymentServiceError(f"FLW verify failed: {data.get('message')}")

    def verify_webhook_signature(self, payload, signature):
        """Verify that the webhook is from Flutterwave"""
        secret_hash = settings.FLW_ENCRYPTION_KEY
        expected = hmac.new(
            secret_hash.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# ─── Unified Payment Manager ───────────────────────────────────────────────────

class PaymentManager:
    """
    Unified interface for all payment gateways.
    Selects the appropriate service based on gateway choice.
    """

    def __init__(self):
        self.mtn = MTNMoMoService()
        self.airtel = AirtelMoneyService()
        self.flutterwave = FlutterwaveService()

    def initiate(self, gateway, user, amount, phone=None, reference=None,
                 redirect_url=None, description="Waste Collection Fee"):
        """
        Initiate payment through specified gateway.
        Returns standardized response dict.
        """
        if not reference:
            reference = f"KLA{str(uuid.uuid4().hex[:12]).upper()}"

        try:
            if gateway == 'mtn_momo':
                return self.mtn.request_to_pay(
                    phone or user.phone, amount, reference, description
                )
            elif gateway == 'airtel_money':
                return self.airtel.collect(
                    phone or user.phone, amount, reference, description
                )
            elif gateway == 'flutterwave':
                return self.flutterwave.initiate_payment(
                    user, amount, reference,
                    redirect_url or f"{settings.SITE_URL}/payments/verify/",
                    description
                )
            else:
                raise PaymentServiceError(f"Unknown gateway: {gateway}")

        except PaymentServiceError:
            raise
        except Exception as e:
            logger.error(f"Payment initiation error [{gateway}]: {str(e)}")
            raise PaymentServiceError(str(e))

    def verify(self, gateway, transaction_id):
        """Verify payment status through specified gateway"""
        try:
            if gateway == 'mtn_momo':
                return self.mtn.check_payment_status(transaction_id)
            elif gateway == 'airtel_money':
                return self.airtel.check_status(transaction_id)
            elif gateway == 'flutterwave':
                return self.flutterwave.verify_transaction(transaction_id)
            else:
                raise PaymentServiceError(f"Unknown gateway: {gateway}")

        except PaymentServiceError:
            raise
        except Exception as e:
            logger.error(f"Payment verify error [{gateway}]: {str(e)}")
            raise PaymentServiceError(str(e))


# ─── Simulation Service (for development) ─────────────────────────────────────

class SimulatedPaymentService:
    """
    Simulates payment flow in development/testing without real API calls.
    Replace with real services in production.
    """

    def initiate(self, gateway, user, amount, **kwargs):
        ref = f"{gateway.upper()}-SIM-{uuid.uuid4().hex[:10].upper()}"
        return {
            "status": "pending",
            "reference_id": ref,
            "response": {"simulated": True, "gateway": gateway},
        }

    def verify(self, gateway, transaction_id):
        return {
            "status": "successful",
            "data": {"simulated": True, "transaction_id": transaction_id},
        }


def get_payment_service():
    """Factory: returns real or simulated payment service based on settings"""
    if settings.DEBUG or not settings.MTN_MOMO_PRIMARY_KEY:
        return SimulatedPaymentService()
    return PaymentManager()
