# ai_utils.py file
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Optional, List, Any

# Load .env from current working dir, backend folder, and parent project root
load_dotenv()
_current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_current_dir, ".env"), override=False)
load_dotenv(dotenv_path=os.path.join(_current_dir, "..", ".env"), override=False)

# Standard models that we've verified work with the current API keys
# Prioritizing newer Gemini 2.5 models for better performance and quality
CANDIDATE_MODELS = [
    'gemini-2.5-flash',        # Newest, fastest model - try first
    'gemini-2.5-pro',          # Newest, most capable model
    'gemini-2.0-flash',        # Reliable fallback
    'gemini-2.0-flash-lite',   # Lightweight fallback
    'gemini-flash-latest',     # Latest flash variant
    'gemini-pro-latest'        # Latest pro variant
]

# Store the single key before scrubbing, so we can restore it for our own use
_single_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# Scrub any existing Gemini/Google keys from environment to prevent library auto-discovery
# of concatenated strings which causes 400 errors during Discovery.
for env_key in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
    if env_key in os.environ:
        del os.environ[env_key]

def get_api_keys() -> List[str]:
    """Helper to get all available API keys from environment."""
    # 1. Multi-key list (preferred) — RECRUITER_API_KEYS=key1,key2,...
    keys_str = os.getenv("RECRUITER_API_KEYS")
    
    # 2. Legacy multi-key name
    if not keys_str:
        keys_str = os.getenv("GEMINI_API_KEYS")

    if keys_str:
        return [k.strip() for k in keys_str.split(",") if k.strip()]

    # 3. Single key fallback — GEMINI_API_KEY=key (captured before scrub)
    if _single_key:
        return [_single_key.strip()]

    return []

def run_genai_with_rotation(
    prompt: Any, 
    is_json: bool = False, 
    multimodal_filepath: Optional[str] = None, # Path to local file
    custom_models: Optional[List[str]] = None
) -> str:
    """
    Executes a GenAI call with both Key Rotation and Model Rotation.
    If Key A hits a 429, it tries Key B with the same model series.
    """
    keys = get_api_keys()
    if not keys:
        raise ValueError("No GEMINI_API_KEY found in .env")
    
    models_to_try = custom_models or CANDIDATE_MODELS
    last_error = None
    
    # Outer Loop: Iterate through each API KEY
    for key_index, api_key in enumerate(keys):
        try:
            genai.configure(api_key=api_key)
            
            # If we have a multimodal file, upload it for THIS key
            multimodal_file = None
            if multimodal_filepath:
                try:
                    print(f"AI Call: Uploading multimodal file with Key[{key_index}]...")
                    multimodal_file = genai.upload_file(path=multimodal_filepath)
                except Exception as upload_err:
                    print(f" - Upload failed with Key[{key_index}]: {upload_err}")
                    if "429" in str(upload_err):
                        print(" - Quota hit on upload. Moving to NEXT KEY...")
                        continue # Try next key
                    last_error = upload_err
                    continue

            # Inner Loop: Iterate through each MODEL for the current key
            for model_index, model_name in enumerate(models_to_try):
                try:
                    # If this isn't the first attempt ever, add a tiny throttle to avoid burst limits
                    if key_index > 0 or model_index > 0:
                        time.sleep(1)
                        
                    print(f"AI Call: Key[{key_index}] Model[{model_name}]...")
                    
                    config = {"response_mime_type": "application/json"} if is_json else {}
                    model = genai.GenerativeModel(model_name, generation_config=config)
                    
                    content = [multimodal_file, prompt] if multimodal_file else prompt
                    response = model.generate_content(content)
                    
                    if response and response.text:
                        # Success! Cleanup and return
                        if multimodal_file:
                            try: genai.delete_file(multimodal_file.name)
                            except: pass
                        return response.text
                except Exception as e:
                    err_str = str(e)
                    print(f" - Failed with Key[{key_index}] Model[{model_name}]: {err_str[:100]}...")
                    last_error = e
                    
                    # If it's a 429 (Quota), we should definitely try the NEXT KEY immediately
                    if "429" in err_str:
                        print(" - Quota hit on this key or during gen. Moving to NEXT KEY...")
                        break # Break model loop to try next key
                    
                    # If it's a 404 (Model missing), we stay on the same key and try next model
                    if "404" in err_str:
                        continue
                        
                    # For other errors, we try the next model on the same key
                    continue
            
            # If we finished the model loop without success, cleanup for this key
            if multimodal_file:
                try: genai.delete_file(multimodal_file.name)
                except: pass

        except Exception as key_setup_err:
            print(f"CRITICAL: Failed to configure key {key_index}: {key_setup_err}")
            continue
            
    raise last_error or Exception("All API keys and models failed.")
