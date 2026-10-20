import re
from decimal import Decimal
from app.schemas.intent import IntentRequest, IntentResponse

_AMOUNT_WORDS = {"ɔha": Decimal("100"), "aha": Decimal("100"), "aduasa": Decimal("50")}


class IntentService:
    def interpret(self, request: IntentRequest) -> IntentResponse:
        if request.amount is not None:
            return IntentResponse(
                intent="cash_out",
                amount=request.amount,
                currency="GHS",
                language=request.language,
                confidence=0.99,
                requires_confirmation=True,
            )
        text = (request.text or "").lower()
        looks_like_cashout = any(
            term in text
            for term in ("cash", "cash out", "yi", "sika", "withdraw", "mo mo")
        )
        amount = None
        match = re.search(r"(?:ghs|g\s*h\s*s|\$)?\s*(\d+(?:\.\d{1,2})?)", text)
        if match:
            amount = Decimal(match.group(1))
        else:
            for word, value in _AMOUNT_WORDS.items():
                if word in text:
                    amount = value
                    break
        if looks_like_cashout and amount is not None:
            return IntentResponse(
                intent="cash_out",
                amount=amount,
                currency="GHS",
                language=request.language,
                confidence=0.94,
                requires_confirmation=True,
            )
        return IntentResponse(
            intent=None,
            amount=None,
            currency="GHS",
            language=request.language,
            confidence=0.0,
            requires_confirmation=False,
            requires_clarification=True,
        )
