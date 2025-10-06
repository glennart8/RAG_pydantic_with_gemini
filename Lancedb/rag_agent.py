from dotenv import load_dotenv
import os
import lancedb
from sentence_transformers import SentenceTransformer
from pydantic import ValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError 

from models import Restaurant, RestaurantList 

# --- SETUP ---
load_dotenv()

MODEL_NAME = "gemini-2.5-flash" 
DB_PATH = "my_restaurant_db"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initiera klienter´, databas, table och embeddingmodell
client = genai.Client(api_key=GEMINI_API_KEY)
db = lancedb.connect(DB_PATH)
table = db.open_table("restaurants_db")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 


# --- Kör agent ---

def run_rag_agent():
    print("================ RAG-AGENT STARTAD (Gemini)================")
    print(f"Modell: {MODEL_NAME} | Databas: {DB_PATH}")
    
    while True:
        user_input = input("Sök efter en restaurang. (Ex: 'Kinesiskt i Göteborg' eller 'q' för att avsluta):\n> ")
        
        if user_input.lower() == 'q':
            print("Avslutar RAG-agent.")
            break

        # HÄMTNINGSSTEGET: Bestäm stad och hämta 3 träffar
        input_lower = user_input.lower()
        
        city = None
        if "göteborg" in input_lower or "gbg" in input_lower:
            city = "Göteborg"
        elif "uddevalla" in input_lower:
            city = "Uddevalla"

        print("\n Söker i LanceDB ")
        
        try:
            query_vector = embedding_model.encode(user_input).tolist()
            search_query = table.search(query_vector)
            
            if city:
                search_query = search_query.where(f"city = '{city}'")
                print(f"-> Sökningen filtreras till staden: {city}")
            
            # Hämta de 3 bästa träffarna
            search_results = search_query.limit(3).to_list()

        except Exception as e:
            print(f"[FEL]: Kunde inte söka i LanceDB. Fel: {e}")
            continue # Återgå till sökprompt
        
        
        if search_results:
            context_blocks = []
            for i, result in enumerate(search_results, 1):
                # Skapar en tydlig avgränsning för varje restaurang
                context_blocks.append(f"KONTEXT #{i} (Stad: {result['city']}):\n{result['text']}")
            
            context_text = "\n---\n".join(context_blocks)
            print(f"Hittade {len(search_results)} potentiella fakta. Skickar till Gemini...")
            
        else:
            print("Ingen information tillgänglig i databasen för din sökning.")
            continue
        
        
        # --- GENERERINGSSTEGET ---
        print("\n--- Gör resultatet till strukturerat JSON med Gemini ---")
        
        # SYSTEM INSTRUKTION: Tvingar LLM:en att extrahera alla relevanta objekt
        system_instruction = (
            "Du är en expert på strukturerad JSON-extraktion. "
            "Analysera noga den angivna KONTEXTEN, som innehåller upp till 3 restaurangbeskrivningar. "
            "Ditt mål är att extrahera information för ALLA restauranger som är relevanta för användarens fråga. "
            "Fyll i JSON-schemat för **RestaurantList** genom att inkludera ALLA restauranger i 'results'-listan. "
            "Om ett fält saknas i kontexten, använd värdet 'Information saknas'."
        )
        
        rag_prompt = f"""
        ANVÄNDARENS FRÅGA: {user_input}

        KONTEXT FÖR ANALYS:
        ---
        {context_text}
        ---
        
        Extrahera information för ALLA relevanta restauranger från KONTEXTEN.
        """
        
        try:
            # Anropa Gemini med RestaurantList som schema i stället
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=rag_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json", 
                    response_schema=RestaurantList, # Använder list-schemat
                ),
            )

            # Validera och deserialisera mot RestaurantList
            json_string = response.text.strip()
            validated_output: RestaurantList = RestaurantList.model_validate_json(json_string)
            
            print("\n--- Strukturerade och Faktabaserade Resultat (Lista) ---")
            
            # Skriv ut resultaten genom att loopa igenom listan
            if validated_output.results:
                for i, restaurant in enumerate(validated_output.results, 1):
                    print(f"--- RESTAURANG #{i} ---")
                    print(f"Namn: {restaurant.name}")
                    print(f"Adress: {restaurant.address}")
                    print(f"Betyg: {restaurant.rating}")
                    print(f"Köksstilar: {restaurant.cuisines}")
                print("-----------------------------------------------------")
            else:
                print("Gemini kunde inte extrahera några relevanta restauranger från kontexten.")
            
        except ValidationError as e:
            print(f"\n[FEL]: Valideringsfel. AI:n svarade med fel format: {e}")
        except APIError as e:
            print(f"\n[KRITISKT FEL]: Ett Gemini API-fel uppstod. Kontrollera din nyckel och kvot: {e}")
        except Exception as e:
            print(f"\n[KRITISKT FEL]: Ett oväntat fel uppstod: {e}")


if __name__ == "__main__":
    run_rag_agent()