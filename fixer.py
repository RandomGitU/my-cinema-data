# fixer.py
import os
import json
import google.generativeai as genai

# --- Configuration ---
API_KEY = os.environ.get("API_KEY")
FINAL_OUTPUT_FILENAME = 'movies.json'
TEMP_INPUT_FILENAME = 'movies_temp.json'
SOURCE_HTML_FILENAME = 'source_page.html'
GEMINI_MODEL = 'gemini-1.5-flash-latest'

# New system instruction specifically for fixing
FIXER_SYSTEM_INSTRUCTION = """You are an expert JSON repair AI. Your task is to fix the provided broken JSON text.
- The user will provide broken JSON and the original HTML source it was generated from.
- Analyze the broken JSON and the error message to identify the problem.
- Your goal is to produce a 100% valid JSON object that corrects the errors.
- **Return ONLY the corrected, valid JSON object.** Do not include any of your own commentary, notes, or apologies. Your entire output must be parsable JSON.
- Use the original HTML as a reference if you need to re-extract a specific piece of data to fix the JSON.
"""

def fix_broken_json():
    """
    Checks for a temporary broken JSON file. If it exists, it sends the
    content to Gemini to be repaired and saves the result as the final file.
    """
    if not os.path.exists(TEMP_INPUT_FILENAME):
        print("No temp file found. Scraper likely succeeded. Fixer is not needed.")
        return

    print(f"--- FIXER ACTIVATED: Found broken data in '{TEMP_INPUT_FILENAME}' ---")

    if not API_KEY:
        print("Error: API_KEY environment variable not set. Cannot run fixer.")
        return

    # Read the broken data and the original HTML source
    with open(TEMP_INPUT_FILENAME, 'r', encoding='utf-8') as f:
        broken_json_text = f.read()
    with open(SOURCE_HTML_FILENAME, 'r', encoding='utf-8') as f:
        source_html = f.read()

    print("Initializing Gemini AI model to fix the JSON...")
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=FIXER_SYSTEM_INSTRUCTION)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")

        # Create a detailed prompt for the fixer
        prompt = f"""The following JSON is broken. Please fix it and return only the valid JSON.
        
Here is the original HTML source for your reference:
--- START HTML ---
{source_html}
--- END HTML ---

Here is the broken JSON text that needs to be fixed:
--- START BROKEN JSON ---
{broken_json_text}
--- END BROKEN JSON ---
"""
        print("Sending repair request to Gemini...")
        api_response = model.generate_content(prompt, generation_config=generation_config)
        
        fixed_json_text = api_response.text
        # We must validate the fixer's output too!
        parsed_json = json.loads(fixed_json_text)

        print("Success! Fixer received valid JSON from Gemini.")
        with open(FINAL_OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        print(f"Successfully repaired and saved data to '{FINAL_OUTPUT_FILENAME}'")

    except Exception as e:
        print(f"--- FIXER FAILED ---")
        print(f"The fixer was unable to repair the JSON. Error: {e}")
        print("The temporary files will be left for manual inspection.")

if __name__ == "__main__":
    fix_broken_json()
