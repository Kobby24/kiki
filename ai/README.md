# Sikapa AI/ML Communication Engine

This module contains the artificial intelligence pipeline for the Sikapa backend. It powers the core accessibility features of the app by allowing users to speak naturally in code-mixed Twi and English, understand their intent, and respond back in natural Twi voice.

## Core Services

The AI engine is built on three pillars:

1. **ASR (Speech-to-Text):** Powered by the remote HCI LAB API, this service takes raw audio recordings from the user (e.g. from the mobile app) and transcribes them into text.
2. **NLU (Natural Language Understanding):** A fast, local, regex-based slot extraction engine. It takes transcribed Twi text and pulls out the user's intent, the cash amount, and any mentioned phone numbers or names.
3. **TTS (Text-to-Speech):** A high-performance, multi-tiered caching voice engine. It synthesizes Twi and English responses using pre-baked audio assets and the HCI LAB API. All audio is hosted on **Cloudinary CDN** for instant, reliable playback.

## Frontend Integration Guide

This section is specifically for frontend and mobile developers integrating with the AI endpoints.

### Authentication
All `/ai/` endpoints are protected by the same JWT authentication as the rest of the application. You **must** include the `Authorization: Bearer <token>` header in all requests.

### 1. Sending Audio from the Frontend (The "Process Pipeline")

When the user taps the microphone button and speaks, record the audio and send it to the backend.

**Endpoint:** `POST /ai/process-pipeline`  
**Content-Type:** `multipart/form-data`

**Request:**
Send the recorded file using a standard form-data upload field named `file`. The engine supports `wav`, `mp3`, `m4a`, `aac`, and many other mobile-native formats.

**Response:**
```json
{
  "asr": {
    "transcript": "Me pɛ sɛ megye sika 100",
    "fallback_used": false
  },
  "nlu": {
    "intent": "withdraw",
    "amount": 100.0,
    "phone_number": null,
    "name": null
  }
}
```

*Note: You can also call `/ai/transcribe` and `/ai/extract-intent` separately, but `process-pipeline` is recommended for the standard voice flow to save an HTTP round-trip.*

### 2. Playing Voice Responses (Synthesis)

When the backend needs to speak back to the user (e.g., to confirm an amount or repeat a phone number), request a Cloudinary audio URL.

**Endpoint:** `POST /ai/synthesize`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "intent": "WITHDRAW",
  "amount": 100.0,
  "phone_number": "0241234567",
  "mode": "FULL"
}
```

**Supported Modes:**
- `FULL`: Complete sentence (e.g., "I want to withdraw 100 cedis...").
- `REPEAT_AMOUNT`: Just the amount (e.g., "100 Ghana cedis").
- `REPEAT_NUMBER_NORMAL`: Reads the phone number out loud at a natural pace.
- `REPEAT_NUMBER_BOKOO`: Reads the phone number slowly and deliberately for accessibility.
- `POLITENESS`: Standard polite fallback ("Please repeat that").

**Response:**
```json
{
  "audio_url": "https://res.cloudinary.com/your-cloud/video/upload/sikapa/amounts/100.mp3",
  "mode": "FULL"
}
```

**Frontend Handling:**
The response is standard JSON. Just take the `audio_url` and play it:
```javascript
const response = await fetch('https://api.sikapa.com/ai/synthesize', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ intent: 'WITHDRAW', amount: 100, mode: 'FULL' })
});

const { audio_url } = await response.json();
const audio = new Audio(audio_url);
audio.play();
```

No blob handling, no content-type guessing. The Cloudinary CDN URL supports full seeking and duration display in all browsers and mobile players.

## Architecture & Quota Protection

The upstream HCI LAB TTS API is strictly rate-limited (e.g., 15 calls/day). To protect our quota and ensure fast response times, the backend implements a **Multi-Tier Cache**:

1. **In-Memory URL Cache:** If the same audio was requested before in this server session, the Cloudinary URL is returned instantly with zero computation.
2. **Cloudinary CDN:** All generated audio lives permanently on Cloudinary. Even after a server restart, the same deterministic URL works.
3. **Local Disk Cache:** Pre-baked audio files for common phrases (politeness, digits 0-9, common cash-out amounts) are stored in `ai/assets/` and uploaded to Cloudinary on first use.
4. **HCI LAB TTS API:** Only called as an absolute last resort for completely new, unseen phrases.

## Setup (For Backend Developers)

### Cloudinary Credentials
Add these to your `.env`:
```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### Seeding Assets to Cloudinary
After setting up credentials, run the seeding script once to upload all pre-baked audio:
```bash
python ai/scripts/seed_cloudinary.py
```

**Important for Developers:** 
Do not delete the `ai/assets/` folder. These files are pre-generated using Edge TTS and the HCI LAB API. If you need to add new conversational Twi phrases, add them to `ai/scripts/seed_audio.py` and run it locally, then re-run `seed_cloudinary.py` to push them to the CDN.
