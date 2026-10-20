import abc


class SpeechProvider(abc.ABC):
    @abc.abstractmethod
    async def synthesize(self, text: str, language: str) -> str | None:
        raise NotImplementedError


class TextOnlySpeechProvider(SpeechProvider):
    async def synthesize(self, text: str, language: str) -> str | None:
        return None
