from dotenv import load_dotenv
import os
import lancedb
from sentence_transformers import SentenceTransformer
from pydantic import ValidationError

# Importera Geminis officiella bibliotek
from google import genai
from google.genai import types
from google.genai.errors import APIError 

from models import Restaurant  

# --- SETUP ---
load_dotenv()

MODEL_NAME = "gemini-2.5-flash" 
DB_PATH = "my_restaurant_db"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

db = lancedb.connect(DB_PATH)
table = db.open_table("restaurants_db")

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 

# --- Kör agent ---

def run_rag_agent():
    print("================ RAG-AGENT STARTAD (Gemini)================")
    print(f"Modell: {MODEL_NAME} | Databas: {DB_PATH}")
    
    user_input = input("Sök efter en restaurang. (Ex: 'Kinesiskt i Göteborg'):\n> ")

    # HÄMTNINGSSTEGET
    input_lower = user_input.lower()
    
    city = None
    if "göteborg" in input_lower or "gbg" in input_lower:
        city = "Göteborg"
    elif "uddevalla" in input_lower:
        city = "Uddevalla"

    print("\n Söker i LanceDB ")
    
    # Försök vektorisera inputen
    try:
        query_vector = embedding_model.encode(user_input).tolist()
        search_query = table.search(query_vector)
        
        if city:
            search_query = search_query.where(f"city = '{city}'")
            print(f"-> Sökningen filtreras till staden: {city}")
        
        search_results = search_query.limit(1).to_list()

    except Exception as e:
        print(f"[FEL]: Kunde inte söka i LanceDB. Fel: {e}")
        return

    context_text = search_results[0]['text'] if search_results else "Ingen information tillgänglig i databasen."
    print(f"Resultat från LanceDB: {context_text}")

    # --- GENERERINGSSTEGET ---
    print("\n--- Gör resultatet till strukturerat JSON med Gemini ---")
    
    # Beskrive rhur jag vill ha mitt svar, En JSON-sträng i pydanticklassen Restaurang
    schema_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Restaurant,
    )

    # System-prompten som instruerar modellen
    system_instruction = "Du är en expert på JSON-extraktion. Basera ditt svar strikt på den angivna KONTEXTEN. Om ett fält saknas, använd värdet 'Information saknas'."
    
    rag_prompt = f"""
    KONTEXT:
    ---
    {context_text}
    ---
    Baserat ENDAST på KONTEXTEN, fyll i JSON-schemat för Restaurang.
    """
    
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Content(role="user", parts=[types.Part(text=system_instruction)]),
                types.Content(role="user", parts=[types.Part(text=rag_prompt)]),
            ],
            config=schema_config,
        )

        # Resultatet är en ren JSON-sträng
        raw_json = response.text
        
        # Validera och deserialisera med Pydantic
        result = Restaurant.model_validate_json(raw_json)
        
        print("\n--- Strukturerat och Faktabaserat Resultat ---")
        print(result.model_dump_json(indent=2))
        
    except ValidationError as e:
        print(f"\n[FEL]: Valideringsfel. AI:n svarade med fel format: {e}")
    except APIError as e:
        print(f"\n[KRITISKT FEL]: Ett Gemini API-fel uppstod. Kontrollera din nyckel och kvot: {e}")
    except Exception as e:
        print(f"\n[KRITISKT FEL]: Ett oväntat fel uppstod: {e}")


if __name__ == "__main__":
    run_rag_agent()