import os
import json
import requests
import google.generativeai as genai

# --- Configuration ---
# IMPORTANT: Set your Gemini API key as an environment variable named 'API_KEY'
# In your terminal on Mac/Linux: export API_KEY="YOUR_API_KEY"
# In your terminal on Windows:    set API_KEY="YOUR_API_KEY"
API_KEY = os.environ.get("API_KEY")
TICKETING_PAGE_URL = 'https://ticketing.oz.veezi.com/sessions/?siteToken=hrqx63mdmcnrd0x03w95trdshr'
VEEZI_BASE_URL = 'https://ticketing.oz.veezi.com'
OUTPUT_FILENAME = 'movies.json'
TEMP_OUTPUT_FILENAME = 'movies_temp.json'
SOURCE_HTML_FILENAME = 'source_page.html' # To pass HTML to the fixer
GEMINI_MODEL = 'gemini-2.5-flash'

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

# This system instruction guides the AI model.
SYSTEM_INSTRUCTION = f"""You are an expert web scraper and data extractor for cinema websites. Your task is to analyze the provided HTML content and extract all movie and session information.
- Return the data as a valid JSON object that strictly adheres to the provided JSON schema. The schema is provided in the user prompt for your reference.
- For each movie, find all its session times for all available days shown on the page.
- All URLs (poster images, booking links) MUST be absolute. If a relative URL is found (e.g., starts with '/'), convert it to an absolute URL using the base '{VEEZI_BASE_URL}'.
- The 'id' for movies and sessions should be a unique identifier extracted from the HTML, typically from a 'data-film-id' or similar attribute.
- Ensure 'startTime' is a full ISO 8601 string (e.g., "2024-07-31T20:30:00").
- If a movie has no available sessions on the page, do not include it in the output.
- The runtime is often in a format like "114 min". Extract only the number 114."""

def fetch_and_process_movies():
    """
    Fetches HTML and tries to generate a valid movies.json.
    If Gemini returns invalid JSON, it saves the broken text to a temp file
    for the fixer.py script to process.
    """
    if not API_KEY:
        print("Error: API_KEY environment variable not set.")
        return

    print(f"Fetching HTML from {TICKETING_PAGE_URL}...")
    try:
        response = requests.get(TICKETING_PAGE_URL, timeout=30)
        response.raise_for_status()
        html_content = response.text
        print("Successfully fetched HTML content.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching HTML: {e}")
        return

    print(f"Initializing Gemini AI model '{GEMINI_MODEL}'...")
    json_text = ""
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=SYSTEM_INSTRUCTION)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        
        prompt = f"Please extract the movie and session data from the following HTML content, adhering strictly to this JSON schema: {json.dumps(MOVIE_SCHEMA)}\n\nHTML Content begins below:\n{html_content}"
        
        print("Sending request to Gemini for data extraction...")
        api_response = model.generate_content(prompt, generation_config=generation_config)
        
        # Check for blocked responses
        if not api_response.candidates:
             print(f"CRITICAL ERROR: Gemini blocked the prompt. Reason: {api_response.prompt_feedback.block_reason}")
             return

        json_text = api_response.text
        parsed_json = json.loads(json_text)
        
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
            
        print(f"\nSuccessfully processed and saved data to '{OUTPUT_FILENAME}'")

    except json.JSONDecodeError as e:
        # --- THIS IS THE NEW FAILURE LOGIC ---
        print(f"\n--- SCRAPER FAILED: Invalid JSON received from Gemini ---")
        print(f"Error details: {e}")
        print(f"Saving broken response to '{TEMP_OUTPUT_FILENAME}' for the fixer script.")
        
        # Save the broken JSON text
        with open(TEMP_OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            f.write(json_text)
            
        # Also save the original HTML, which the fixer will need for context
        with open(SOURCE_HTML_FILENAME, 'w', encoding='utf-8') as f:
            f.write(html_content)

    except Exception as e:
        print(f"An unexpected error occurred during the Gemini API call: {e}")


if __name__ == "__main__":
    fetch_and_process_movies()
