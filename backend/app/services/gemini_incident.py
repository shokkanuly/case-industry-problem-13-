import base64
import os
import httpx
import logging

logger = logging.getLogger("edge.gemini")

async def call_gemini_incident_description(image_bytes: bytes | None, label_summary: str) -> str:
    """
    Call Gemini API (gemini-2.5-flash v1beta) to generate a factual one-sentence incident description in Russian.
    Supports both webcam frames (image input) and simulated events (text-only input).
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Using fallback description.")
        return f"Зафиксировано нарушение СИЗ ({label_summary}). Направлен инспектор."

    # Using gemini-2.5-flash as verified by testing
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = (
        f"This is an industrial safety camera alert. "
        f"A computer vision model flagged: {label_summary}. "
        f"Write one short, factual sentence in Russian describing the safety violation incident, "
        f"suitable for an automated safety log. Keep it under 15 words. Do not speculate."
    )
    
    parts = [{"text": prompt}]
    if image_bytes:
        try:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode("utf-8")
                }
            })
        except Exception as e:
            logger.error(f"Failed to base64 encode image_bytes: {e}")

    payload = {
        "contents": [
            {
                "parts": parts
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                # Safely extract text from candidate parts
                candidates = data.get("candidates", [])
                if candidates:
                    parts_list = candidates[0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts_list if p.get("text")]
                    if text_parts:
                        # Return the first text part or join them
                        return text_parts[0].strip()
                logger.warning("Gemini response did not contain candidates/parts text.")
            else:
                logger.error(f"Gemini API returned error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to communicate with Gemini API: {e}")
        
    return f"Зафиксировано нарушение СИЗ ({label_summary}). Требуется проверка сотрудника на участке."
