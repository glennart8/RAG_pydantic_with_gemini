from dotenv import load_dotenv
import os
import lancedb
from sentence_transformers import SentenceTransformer
from pydantic import ValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError 

from models import Restaurant, RestaurantList 

# --- SETUP (Konstanter & Initiering) ---
load_dotenv()

MODEL_NAME = "gemini-2.5-flash" 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY saknas. Kontrollera din .env-fil.")

DB_PATH = "../my_restaurant_db"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 


# Initiera klienter, databas, table och embeddingmodell
client = genai.Client(api_key=GEMINI_API_KEY)
db = lancedb.connect(DB_PATH)
try:
    table = db.open_table("restaurants_db")
except Exception as e:
    print(f"FEL: Kunde inte öppna 'restaurants_db'. Har du kört setup_db.py? Fel: {e}")
    exit()

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 



# HANTERAR ANVÄNDARINPUT
# def get_user_query(input_prompt: str) -> str | None:
#     """
#     Hanterar inmatning från användaren och checkar för avslut.
#     Returnerar user_input eller None.
#     """
#     user_input = input(input_prompt)
#     if user_input.lower() == 'q':
#         return None
    
#     return user_input.strip()


# HANTERAR HÄMTNING (RAG: Retrieval)
def perform_vector_search(query: str, city_filter: str):
    """
    1. Frågar efter stad för filtrering.
    2. Hämtar de 5 bäst matchande recensionerna från LanceDB.
    3. Formaterar träffarna tydligt som kontext för LLM.
    4. Returnerar den formaterade kontexten.
    """

    # VEKTORISERING OCH SÖKNING
    try:
        query_vector = embedding_model.encode(query).tolist()
    except Exception as e:
        print(f"[FEL]: Kunde inte vektorisera sökfrågan. Fel: {e}")
        return None
        
    search_query = table.search(query_vector)
    search_query = search_query.where(f"city = '{city_filter}'")
    search_results = search_query.limit(5).to_list() 

    if not search_results:
        print(f"Hittade inga relevanta recensioner i databasen för {city_filter}.")
        return None

    print(f"Hittade {len(search_results)} potentiella fakta. Förbereder för Gemini...")
    
    # 3. AUGMENTATION - FÖRBÄTTRING - FORMULERA KONTEXTEN TYDLIGT (LÖSNINGEN MOT HALLUCINATIONER)
    context_text = []
    for result in search_results:
        # Tydlig etikettering hjälper LLM:en att korrekt extrahera Namn, Stad, etc.
        context_str = (
            f"--- START RESTAURANGFAKTA ---\n"
            f"Namn: {result['name']}\n"
            f"Stad: {result['city']}\n"
            f"Recension/Beskrivning: {result['text']}\n"
            f"--- SLUT RESTAURANGFAKTA ---\n"
        )
        context_text.append(context_str)
    
    rag_result = run_gemini_query(query, "\n".join(context_text))
    return rag_result

# HANTERAR GENERERING (RAG: Generation)
def run_gemini_query(user_query: str, context: str) -> RestaurantList | None: 
    """
    Skapar prompten, anropar Gemini och validerar svaret mot RestaurantList.
    Returnerar det validerade Pydantic-objektet.
    """

    # VIKTIGT: Skärp instruktionerna mot hallucinationer - fortsätt med det
    system_instruction = (
        """Din uppgift är att agera som en dataextraktionsrobot. 
        Du får INTE filtrera resultaten. 
        För VARJE separat restaurangfakta som du ser i KONTEXTEN (markerad av '--- START RESTAURANGFAKTA ---'), 
        MÅSTE du skapa en motsvarande post i JSON-listan. Om information saknas, fyll i 'Information saknas'.
        Adressen kan du alltid hitta på t.ex. Google Maps, uteslut postnummer och ort.
        Försök att främst matcha typ av kök/land/råvara och visa den restaurangen överst i listan.
        """
    )
    
    rag_prompt = f"""
    ANVÄNDARENS FRÅGA: {user_query}

    KONTEXT FÖR ANALYS:
    ---
    {context}
    ---
    
    Extrahera information för ALLA relevanta restauranger från KONTEXTEN.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=rag_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json", 
                response_schema=RestaurantList, 
            ),
        )

        json_string = response.text.strip()
        validated_output: RestaurantList = RestaurantList.model_validate_json(json_string)
        return validated_output
        
    except ValidationError as e:
        print(f"\n[FEL]: Valideringsfel. AI:n svarade med fel format. Kontrollera schemat. Fel: {e}")
    except APIError as e:
        print(f"\n[KRITISKT FEL]: Ett Gemini API-fel uppstod. Kontrollera din nyckel och kvot: {e}")
    except Exception as e:
        print(f"\n[KRITISKT FEL]: Ett oväntat fel uppstod: {e}")
    
    return None


def add_restaurant(restaurant_name: str, restaurant_city: str, review: str) -> bool:
    """
    En boleansk metod som lägger till en ny recension i databasen genom att först skapa en vektor.
    """
    if not (restaurant_name and restaurant_city and review):
        return False
        
    try:
        # VEKTORISERING: Skapa inbäddning (vektor)
        embedding = embedding_model.encode(review).tolist()
    except Exception as e:
        print(f"[FEL]: Kunde inte skapa inbäddning. Fel: {e}")
        return False

    # 2. DATABASSTRUKTUR & SPARA
    data_to_save = [
        {
            "name": restaurant_name,
            "city": restaurant_city,
            "text": review,
            "vector": embedding,
        }
    ]
    
    try:
        table.add(data_to_save)
        return True
    except Exception as e:
        print(f"[FEL]: Kunde inte spara data till LanceDB. Fel: {e}")
        return False


def list_all_unique_names():
    all_restaurants = table.to_pandas()
    unique_names = all_restaurants['name'].unique().tolist()
    return unique_names

def list_all_unique_cities():
    all_restaurants = table.to_pandas()
    unique_cities = all_restaurants['city'].unique().tolist()
    return unique_cities

def list_restaurants_by_city(city_name: str):
    all_restaurants = table.to_pandas()
    names_in_city = all_restaurants[all_restaurants['city'] == city_name]['name'].tolist()
    return names_in_city


def get_details_by_name(restaurant_name: str):
    
    try:
        # Sök, filtrera och ta ut 1 (den enda)
        search_result = table.search()
        search_result = search_result.where(f"name = '{restaurant_name}'")
        search_result = search_result.limit(1)
        
        # LanceDB returnerar en lista, även om den bara innehåller ett objekt.
        final_list = search_result.to_list() # Exekvera och hämta listan
        
        if final_list:
            return final_list[0] 
        else:
            return None
        
    except Exception as e:
        print(f"Fel vid hämtning av detaljer för {restaurant_name}: {e}")
        return None

def update_restaurant(restaurant_name: str, restaurant_city: str, review: str) -> bool:
    """
    Updates an existing restaurant review in the database.
    """
    if not (restaurant_name and restaurant_city and review):
        return False

    try:
        # Vectorize the updated review
        embedding = embedding_model.encode(review).tolist()

        #  Update data
        data_to_update = {
            "name": restaurant_name,
            "city": restaurant_city,
            "text": review,
            "vector": embedding,
        }

        table.delete(f"name = '{restaurant_name}' AND city = '{restaurant_city}'")
        table.add([data_to_update])
        return True

    except Exception as e:
        print(f"Failed to update restaurant {restaurant_name}: {e}")
        return False
    