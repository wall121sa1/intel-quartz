import os

import requests
from langdetect import detect, LangDetectException

class TranslatorService:
    _endpoint = os.getenv("LIBRETRANSLATE_URL", "http://localhost:4000")

    @staticmethod
    def detect_language(text):
        try:
            # Returns 'en', 'ru', 'fa', etc.
            return detect(text)
        except LangDetectException:
            return 'en'

    @staticmethod
    def translate(text, from_code):
        """
        Translates text to English.
        """
        if from_code == 'en':
            return text

        try:
            response = requests.post(
                f"{TranslatorService._endpoint}/translate",
                json={
                    "q": text,
                    "source": from_code,
                    "target": "en",
                    "format": "text",
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("translatedText", text)
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Translation Error ({from_code}->en): {e}")
            return text  # Fallback to original if translation fails
