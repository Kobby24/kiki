import asyncio
import os
from pathlib import Path

import edge_tts

# We'll put these directly in en_digits alongside the 0-9 we already have.
# Or we can put them in en_amounts. Let's just use en_digits as the general English pool.
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "en_digits"

# en-NG-EzinneNeural is a female Nigerian English voice (West African accent)
# en-NG-AbeoNeural is a male Nigerian English voice
VOICE = "en-NG-EzinneNeural"

WORDS_TO_SEED = {
    # Base numbers (0-9 are probably already seeded by HCI, but Edge TTS sounds different. 
    # If we want a consistent voice for amounts, we should overwrite them with Edge TTS).
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen", "14": "fourteen",
    "15": "fifteen", "16": "sixteen", "17": "seventeen", "18": "eighteen", "19": "nineteen",
    
    # Tens
    "20": "twenty", "30": "thirty", "40": "forty", "50": "fifty",
    "60": "sixty", "70": "seventy", "80": "eighty", "90": "ninety",
    
    # Magnitudes & Currency
    "hundred": "hundred",
    "thousand": "thousand",
    "million": "million",
    "cedis": "cedis",
    "pesewas": "pesewas",
    "and": "and",
    "point": "point"
}

async def generate_word(key: str, text: str):
    filename = ASSETS_DIR / f"{key}.wav"
    print(f"Generating '{text}' -> {filename.name}...")
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(filename))

async def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Seeding {len(WORDS_TO_SEED)} English amount components using {VOICE}...")
    
    for key, text in WORDS_TO_SEED.items():
        await generate_word(key, text)
        
    print("\n✅ Done! All English number components seeded.")

if __name__ == "__main__":
    asyncio.run(main())
