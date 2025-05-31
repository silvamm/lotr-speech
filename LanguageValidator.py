import fasttext

# Fasttext
MODEL_PATH = "lid.176.ftz"
fasttext_loaded = fasttext.load_model(MODEL_PATH)

class LanguageValidator:

    def validate(self, text):

        # numero de idiomas mais provaveis retornados
        predictions = fasttext_loaded.predict(text, k=2)

        first_language = predictions[0][0].replace("__label__", "")
        first_confidence = predictions[1][0]
        second_language = predictions[0][1].replace("__label__", "")
        second_confidence = predictions[1][1]

        predictions_string = f"{first_language} - {first_confidence} | {second_language} - {second_confidence}"

        if (first_language == "pt" and first_confidence > 0.70):
            return predictions_string, True

        if (first_language == "pt" and first_confidence > 0.50):
            if (second_language == "es" and second_confidence > 0.20):
                return predictions_string, True

        if first_language == "es" and first_confidence > 0.25:
            if (second_language == "pt" and second_confidence > 0.25):
                return predictions_string, True

        return predictions_string, False


language_validator = LanguageValidator()
