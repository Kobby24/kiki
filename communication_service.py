from decimal import Decimal


class CommunicationService:
    def agent_message(self, amount: Decimal, language: str) -> str:
        if language == "tw":
            return f"Mepa wo kyɛw, ɔpɛ sɛ ogye GHS {amount:.2f} fi ne Mobile Money so."
        return f"The customer wants to cash out GHS {amount:.2f}."

    def confirmation_message(self, amount: Decimal, language: str) -> str:
        if language == "tw":
            return (
                f"Wopɛ sɛ wogye GHS {amount:.2f}? Yɛsrɛ wo, si so dua ansa na yɛnkɔ so."
            )
        return (
            f"You want to cash out GHS {amount:.2f}. Please confirm before continuing."
        )

    def authorization_instructions(self, language: str) -> list[str]:
        if language == "tw":
            return [
                "Di Mobile Money interface no akwankyerɛ akyi.",
                "Wo ara na ɛsɛ sɛ wosi tua no so dua.",
                "Mma Sikapa obiara wo PIN.",
            ]
        return [
            "Follow the instructions on your Mobile Money interface.",
            "Complete the authorization yourself.",
            "Do not share your PIN with Sikapa.",
        ]
