import os
import json
import requests
import google.generativeai as genai
import time

# --- Configuration ---
API_KEY = os.environ.get("API_KEY")
TICKETING_PAGE_URL = 'https://ticketing.oz.veezi.com/sessions/?siteToken=hrqx63mdmcnrd0x03w95trdshr'
VEEZI_BASE_URL = 'https://ticketing.oz.veezi.com'
OUTPUT_FILENAME = 'movies.json' # Changed to standard name
GEMINI_MODEL = 'gemini-1.5-flash-latest'
MAX_RETRIES = 2 # How many times to ask Gemini to fix its mistake

# This schema tells Gemini how to structure the output JSON.
# It matches the schema used in the web application.
MOVIE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING", "description": "A unique ID for the movie, extracted from a data attribute or similar."},
            "title": {"type": "STRING"},
            "synopsis": {"type": "STRING"},
            "rating": {"type": "STRING", "description": "e.g., PG, M, R16"},
            "runtime": {"type": "INTEGER", "description": "Runtime in minutes."},
            "posterUrl": {"type": "STRING", "description": "Absolute URL to the poster image."},
            "trailerUrl": {"type": "STRING", "description": "Absolute URL to the trailer, if available."},
            "sessions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "id": {"type": "STRING", "description": "A unique ID for the session time."},
                        "startTime": {"type": "STRING", "description": "Full ISO 8601 date-time string."},
                        "screenName": {"type": "STRING"},
                        "attributes": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "e.g., RECLINER, 3D"},
                        "bookingUrl": {"type": "STRING", "description": "Absolute URL to the booking page for this session."},
                    },
                    "required": ["id", "startTime", "screenName", "attributes", "bookingUrl"],
                },
            },
        },
        "required": ["id", "title", "synopsis", "rating", "runtime", "posterUrl", "sessions"],
    },
}
SYSTEM_INSTRUCTION = f"""You are an expert web scraper and data extractor for cinema websites. Your task is to analyze the provided HTML content and extract all movie and session information.
- Return the data as a valid JSON object that strictly adheres to the provided JSON schema.
- CRITICAL RULE: All double quotes (") within any JSON string value MUST be escaped with a backslash (\\). For example, if a synopsis is 'A "great" film', the JSON value must be "A \\"great\\" film". This is the most important rule to prevent errors.
- For each movie, find all its session times for all available days shown on the page.
- All URLs (poster images, booking links) MUST be absolute. If a relative URL is found (e.g., starts with '/'), convert it to an absolute URL using the base '{VEEZI_BASE_URL}'.
- The 'id' for movies and sessions should be a unique identifier extracted from the HTML, typically from a 'data-film-id' or similar attribute.
- Ensure 'startTime' is a full ISO 8601 string (e.g., "2024-07-31T20:30:00").
- If a movie has no available sessions on the page, do not include it in the output.
- The runtime is often in a format like "114 min". Extract only the number 114."""

# --- Main Function ---
def fetch_and_process_movies():
    """
    Fetches HTML, sends it to Gemini for data extraction with a retry/correction
    loop, and saves the structured JSON data.
    """
    if not API_KEY:
        print("Error: API_KEY environment variable not set.")
        return False # Return False on failure

    # --- STRATEGY 3: THE ULTIMATE FALLBACK ---
    # Try to load the last known good data. If the whole process fails,
    # we can use this to prevent the website from breaking.
    last_known_good_data = None
    try:
        with open(OUTPUT_FILENAME, 'r', encoding='utf-8') as f:
            last_known_good_data = json.load(f)
        print(f"Successfully loaded last known good data from '{OUTPUT_FILENAME}'.")
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Could not load last known good data. A new '{OUTPUT_FILENAME}' will be created.")

    print(f"Fetching HTML from {TICKETING_PAGE_URL}...")
    try:
        response = requests.get(TICKETING_PAGE_URL, timeout=30)
        response.raise_for_status()
        html_content = response.text
        print("Successfully fetched HTML content.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching HTML: {e}. Aborting run.")
        return False

    print(f"Initializing Gemini AI model '{GEMINI_MODEL}'...")
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_INSTRUCTION
        )
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        
        prompt = f"Please extract the movie and session data from the following HTML content, adhering strictly to this JSON schema: {json.dumps(MOVIE_SCHEMA)}\n\nHTML Content begins below:\n{html_content}"
        
        # --- STRATEGY 2: THE SELF-CORRECTION LOOP ---
        for attempt in range(MAX_RETRIES + 1):
            print(f"\nAttempt {attempt + 1} of {MAX_RETRIES + 1} to get valid JSON from Gemini...")
            
            try:
                api_response = model.generate_content(prompt)
                json_text = api_response.text
                
                # Try to parse the JSON. If it works, we succeed and break the loop.
                parsed_json = json.loads(json_text)
                
                print("Success! Gemini returned valid JSON.")
                with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                    json.dump(parsed_json, f, indent=2, ensure_ascii=False)
                print(f"Successfully processed and saved new data to '{OUTPUT_FILENAME}'")
                return True # Signal success

            except json.JSONDecodeError as e:
                print(f"Error: Gemini returned invalid JSON. Details: {e}")
                if attempt < MAX_RETRIES:
                    print("Asking Gemini to correct its mistake...")
                    # Construct a new prompt asking for a correction
                    prompt = f"The previous JSON you provided was invalid. The error was: '{e}'. Here is the invalid text you sent:\n\n```json\n{json_text}\n```\n\nPlease fix this JSON and return ONLY the corrected, valid JSON object that adheres to the schema. Do not add any commentary."
                    time.sleep(2) # Wait a moment before retrying
                else:
                    print("Max retries reached. Gemini failed to produce valid JSON.")
                    # Let the main exception handler take over.
                    raise e
            except Exception as e:
                 # Catch other potential API errors (e.g., safety blocks)
                 print(f"An unexpected Gemini API error occurred: {e}")
                 if hasattr(api_response, 'prompt_feedback'):
                     print(f"Prompt Feedback: {api_response.prompt_feedback}")
                 raise e # Re-raise the exception to be caught by the outer block

    except Exception as e:
        print(f"\n--- CRITICAL FAILURE ---")
        print(f"The process failed to get valid data from Gemini after all attempts. Error: {e}")
        # If we have old data, re-save it to ensure the website doesn't break.
        if last_known_good_data:
            print(f"Restoring the last known good version of '{OUTPUT_FILENAME}' to prevent website downtime.")
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(last_known_good_data, f, indent=2, ensure_ascii=False)
        else:
            print("No previous version of the data file was available to restore.")
        return False # Signal failure

if __name__ == "__main__":
    if fetch_and_process_movies():
        print("\nProcess completed successfully.")
    else:
        print("\nProcess finished with errors.")
