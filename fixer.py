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

# --- NEW, MORE INTELLIGENT SYSTEM INSTRUCTION ---
FIXER_SYSTEM_INSTRUCTION = """You are an expert JSON repair and data extraction AI. Your primary goal is to create a complete and valid JSON file from the provided HTML source.
- The user will provide the full original HTML and a piece of broken, INCOMPLETE JSON that was generated from it. This broken JSON failed during its creation.
- Your main task is to **re-process the ENTIRE HTML from the beginning** and generate a complete, valid JSON object according to the schema.
- Use the broken JSON and the associated error message as a **clue** to identify what kind of mistake you should avoid making this time (e.g., unescaped quotes, formatting errors).
- **Do not simply fix the incomplete JSON.** You must generate a new, complete one based on all the content in the HTML.
- **Return ONLY the corrected, complete, and valid JSON object.** Do not include any of your own commentary, notes, or apologies. Your entire output must be parsable JSON.
- CRITICAL RULE: All double quotes (") within any JSON string value MUST be escaped with a backslash (\\).
"""

def fix_broken_json():
    """
    Checks for a temporary broken JSON file. If it exists, it tells Gemini to
    re-process the original HTML to create a complete and valid JSON file.
    """
    if not os.path.exists(TEMP_INPUT_FILENAME):
        print("No temp file found. Scraper likely succeeded. Fixer is not needed.")
        return

    print(f"--- FIXER ACTIVATED: Found incomplete/broken data in '{TEMP_INPUT_FILENAME}' ---")

    if not API_KEY:
        print("Error: API_KEY environment variable not set. Cannot run fixer.")
        return

    # Read the broken data and the original HTML source
    with open(TEMP_INPUT_FILENAME, 'r', encoding='utf-8') as f:
        broken_json_text = f.read()
    with open(SOURCE_HTML_FILENAME, 'r', encoding='utf-8') as f:
        source_html = f.read()

    print("Initializing Gemini AI model to re-process the HTML and fix the JSON...")
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=FIXER_SYSTEM_INSTRUCTION)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")

        # Create the new, more detailed prompt for the fixer
        prompt = f"""The initial attempt to create JSON from the provided HTML failed.

Here is the full original HTML source. Your main task is to re-process this entire HTML file and generate a complete JSON object.
--- START HTML ---
{source_html}
--- END HTML ---

For context, here is the incomplete/broken JSON that was generated before the process failed. Use this as a clue for what kind of error to avoid.
--- START BROKEN JSON ---
{broken_json_text}
--- END BROKEN JSON ---

Now, please generate the complete and valid JSON from the HTML.
"""
        print("Sending full re-processing request to Gemini...")
        api_response = model.generate_content(prompt, generation_config=generation_config)
        
        fixed_json_text = api_response.text
        # We must validate the fixer's output
        parsed_json = json.loads(fixed_json_text)

        print("Success! Fixer generated a complete and valid JSON from the original source.")
        with open(FINAL_OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        print(f"Successfully repaired and saved data to '{FINAL_OUTPUT_FILENAME}'")

    except Exception as e:
        print(f"--- FIXER FAILED ---")
        print(f"The fixer was unable to create a valid JSON file. Error: {e}")
        print("The temporary files will be left for manual inspection.")

if __name__ == "__main__":
    fix_broken_json()
