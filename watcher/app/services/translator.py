import argostranslate.package
import argostranslate.translate
from langdetect import detect, LangDetectException

class TranslatorService:
    _installed_languages = set()

    @staticmethod
    def detect_language(text):
        try:
            # Returns 'en', 'ru', 'fa', etc.
            return detect(text)
        except LangDetectException:
            return 'en'

    @staticmethod
    def ensure_model_installed(from_code, to_code='en'):
        """
        Checks if the translation model exists locally. If not, downloads it.
        """
        # Optimization: Don't check repeatedly if we know we have it
        pair_key = f"{from_code}_{to_code}"
        if pair_key in TranslatorService._installed_languages:
            return

        print(f"Translation: Checking for model {from_code} -> {to_code}...")
        
        # Update package index (like apt-get update)
        argostranslate.package.update_package_index()
        
        available_packages = argostranslate.package.get_available_packages()
        package_to_install = next(
            filter(
                lambda x: x.from_code == from_code and x.to_code == to_code,
                available_packages
            ), None
        )
        
        if package_to_install:
            print(f"Translation: Downloading {package_to_install}...")
            argostranslate.package.install_from_path(package_to_install.download())
            TranslatorService._installed_languages.add(pair_key)
            print("Translation: Model installed.")
        else:
            print(f"Translation: No model found for {from_code} -> {to_code}")

    @staticmethod
    def translate(text, from_code):
        """
        Translates text to English.
        """
        if from_code == 'en':
            return text
            
        try:
            # 1. Ensure model exists
            TranslatorService.ensure_model_installed(from_code, 'en')
            
            # 2. Translate
            translation = argostranslate.translate.translate(text, from_code, 'en')
            return translation
        except Exception as e:
            print(f"Translation Error ({from_code}->en): {e}")
            return text  # Fallback to original if translation fails
