import base64
import os
import httpx
import logging

logger = logging.getLogger("edge.gemini")

async def call_gemini_incident_description(image_bytes: bytes, label_summary: str) -> str:
    """
    Call Gemini API to generate a factual one-sentence incident description in Russian.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Using fallback description.")
        return f"Зафиксировано нарушение СИЗ ({label_summary}). Направлен инспектор."

    # Using gemini-1.5-flash as the standard stable vision model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = (
        f"This is a frame from an industrial safety camera. "
        f"A computer vision model flagged: {label_summary}. "
        f"Write one short, factual sentence in Russian describing the safety violation incident, "
        f"suitable for an automated safety log. Keep it under 15 words. Do not speculate."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": base64.b64encode(image_bytes).decode("utf-8")
                        }
                    }
                ]
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["contents"][0]["parts"][0]["text"].strip()
                return text
            else:
                logger.error(f"Gemini API returned error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to communicate with Gemini API: {e}")
        
    return f"Зафиксировано нарушение СИЗ ({label_summary}). Требуется проверка сотрудника на участке."
