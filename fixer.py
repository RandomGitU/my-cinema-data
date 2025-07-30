# fixer.py
import os
import json
import time
import google.generativeai as genai

# --- Configuration ---
API_KEY = os.environ.get("API_KEY")
FINAL_OUTPUT_FILENAME = 'movies.json'
TEMP_INPUT_FILENAME = 'movies_temp.json'
SOURCE_HTML_FILENAME = 'source_page.html'
GEMINI_MODEL = 'gemini-1.5-flash-latest'
MAX_RETRIES = 2 # --- NEW: Give the fixer multiple chances to get it right ---

# System instruction remains the same
FIXER_SYSTEM_INSTRUCTION = """You are an expert JSON repair and data extraction AI...
# (Your full instruction text here)
"""

def fix_broken_json():
    """
    Checks for a temporary broken JSON file. If it exists, it enters a retry
    loop to ask Gemini to repair it, ensuring the final output is valid.
    """
    if not os.path.exists(TEMP_INPUT_FILENAME):
        print("No temp file found. Scraper likely succeeded. Fixer is not needed.")
        return

    print(f"--- FIXER ACTIVATED: Found incomplete/broken data in '{TEMP_INPUT_FILENAME}' ---")

    if not API_KEY:
        print("Error: API_KEY environment variable not set. Cannot run fixer.")
        return

    # Read the necessary files
    with open(TEMP_INPUT_FILENAME, 'r', encoding='utf-8') as f:
        broken_json_text = f.read()
    with open(SOURCE_HTML_FILENAME, 'r', encoding='utf-8') as f:
        source_html = f.read()

    print("Initializing Gemini AI model to re-process the HTML and fix the JSON...")
    
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=FIXER_SYSTEM_INSTRUCTION)
    generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
    
    # The initial prompt for the fixer
    prompt = f"""The initial attempt to create JSON from the provided HTML failed. Your main task is to re-process the entire HTML file and generate a complete and valid JSON object.
    
Here is the full original HTML source for your reference:
--- START HTML ---
{source_html}
--- END HTML ---

For context, here is the incomplete/broken JSON that was generated before the process failed. Use this as a clue for what kind of error to avoid.
--- START BROKEN JSON ---
{broken_json_text}
--- END BROKEN JSON ---

Now, please generate the complete and valid JSON from the HTML.
"""

    # --- NEW: THE SELF-HEALING RETRY LOOP FOR THE FIXER ---
    for attempt in range(MAX_RETRIES + 1):
        print(f"\nFixer Attempt {attempt + 1} of {MAX_RETRIES + 1} to get valid JSON...")
        
        try:
            api_response = model.generate_content(prompt, generation_config=generation_config)
            fixed_json_text = api_response.text

            # Validate the fixer's output
            parsed_json = json.loads(fixed_json_text)

            print("Success! Fixer generated a complete and valid JSON.")
            with open(FINAL_OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, indent=2, ensure_ascii=False)
            print(f"Successfully repaired and saved data to '{FINAL_OUTPUT_FILENAME}'")
            return # Exit the function successfully

        except json.JSONDecodeError as e:
            print(f"Fixer Error: The JSON response from Gemini was also invalid. Details: {e}")
            if attempt < MAX_RETRIES:
                print("Asking Gemini to correct its own fix...")
                # Create a new prompt telling it that its previous fix was also broken
                prompt = f"""Your previous attempt to fix the JSON was also invalid. The error was: '{e}'.
                
Please try again. Re-analyze the original HTML and generate a complete and valid JSON. Pay very close attention to escaping all double quotes within strings.

Here is the invalid text you just sent:
--- START INVALID FIX ---
{fixed_json_text}
--- END INVALID FIX ---

Now, please try one more time to generate the complete and valid JSON.
"""
                time.sleep(2) # Wait a moment before retrying
            else:
                print("--- FIXER FAILED ---")
                print("The fixer was unable to repair the JSON after multiple attempts.")
                return # Give up after all retries
        except Exception as e:
            print(f"--- FIXER FAILED ---")
            print(f"An unexpected error occurred during the fixer's API call: {e}")
            return


if __name__ == "__main__":
    fix_broken_json()
