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
DB_PATH = "../my_restaurant_db"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY saknas. Kontrollera din .env-fil.")

# Initiera klienter, databas, table och embeddingmodell
client = genai.Client(api_key=GEMINI_API_KEY)
db = lancedb.connect(DB_PATH)
try:
    table = db.open_table("restaurants_db")
except Exception as e:
    print(f"FEL: Kunde inte öppna 'restaurants_db'. Har du kört setup_db.py? Fel: {e}")
    exit()

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 


# --- FUNKTIONER ---

# HANTERAR ANVÄNDARINPUT
def get_user_query(input_prompt: str) -> str | None:
    """
    Hanterar inmatning från användaren och checkar för avslut.
    Returnerar user_input eller None.
    """
    user_input = input(input_prompt)
    if user_input.lower() == 'q':
        return None
    
    return user_input.strip()


# HANTERAR HÄMTNING (RAG: Retrieval)
def perform_vector_search(query: str, city_filter: str):
    """
    1. Frågar efter stad för filtrering.
    2. Hämtar de 5 bäst matchande recensionerna från LanceDB.
    3. Formaterar träffarna tydligt som kontext för LLM.
    4. Returnerar den formaterade kontexten.
    """
    
    # 1. HANTERING AV STADSFILTER (Manuell input)
    # city_filter = input("Ange staden att söka i (Göteborg/Uddevalla): ").strip() - TAS BORT PGA jag använder inparametern från fastapi/streamlit nu
    
    if city_filter.lower() in ["gbg", "göteborg"]:
        city_filter_db = "Göteborg"
    elif city_filter.lower() in ["uddevalla"]:
        city_filter_db = "Uddevalla"
    else:
        print("[AVBRUTEN]: Ogiltig stad angiven.")
        return None
        
    # 2. VEKTORISERING OCH SÖKNING
    print(f"\n Söker i LanceDB och filtrerar på {city_filter_db}")
    try:
        query_vector = embedding_model.encode(query).tolist()
    except Exception as e:
        print(f"[FEL]: Kunde inte vektorisera sökfrågan. Fel: {e}")
        return None
        
    search_query = table.search(query_vector)
    search_query = search_query.where(f"city = '{city_filter_db}'")
    search_results = search_query.limit(5).to_list() 

    if not search_results:
        print(f"Hittade inga relevanta recensioner i databasen för {city_filter_db}.")
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

    # # 4. RETURNERA DEN SAMMANSTÄLLDA KONTEXTEN
    # return "\n".join(context_text)
    
    rag_result = run_gemini_query(query, "\n".join(context_text))
    return rag_result

# HANTERAR GENERERING (RAG: Generation)
def run_gemini_query(user_query: str, context: str) -> RestaurantList | None: 
    """
    Skapar prompten, anropar Gemini och validerar svaret mot RestaurantList.
    Returnerar det validerade Pydantic-objektet.
    """
    
    print("\n--- Gör resultatet till strukturerat JSON med Gemini ---")

    # VIKTIGT: Skärp instruktionerna mot hallucinationer
    system_instruction = (
        """Din uppgift är att agera som en dataextraktionsrobot. 
        Du får INTE filtrera resultaten. 
        För VARJE separat restaurangfakta som du ser i KONTEXTEN (markerad av '--- START RESTAURANGFAKTA ---'), 
        MÅSTE du skapa en motsvarande post i JSON-listan. Om information saknas, fyll i 'Information saknas'."""
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


def add_restaurant():
    """
    Hanterar inmatning av ny restaurangdata, skapar inbäddningar och lagrar den 
    i LanceDB-tabellen.
    """
    print("\n--- LÄGG TILL NY RESTAURANG ---")
    
    # 1. INPUT-STEGET
    restaurant_name = input("Restaurangens namn: ").strip()
    restaurant_city = input("Stad: ").strip()
    review = input("Recensera restaurangen (T.ex. 'Bra mat, högt betyg 4.5, Thai-mat'): ").strip()
    
    if not (restaurant_name and restaurant_city and review):
        print("[AVBRUTEN]: Alla fält måste fyllas i.")
        return

    # Säkra att stadsnamnet är konsekvent
    if restaurant_city.lower() in ["gbg", "göteborg"]:
        final_city = "Göteborg"
    elif restaurant_city.lower() in ["uddevalla"]:
        final_city = "Uddevalla"
    else:
        print("[FEL]: Vald stad måste vara 'Göteborg' eller 'Uddevalla'. Avbryter.")
        return
        
    # 2. VEKTORISERINGS- & EMBEDDING-STEGET
    try:
        print("-> Skapar inbäddning (vektor) från recensionen...")
        embedding = embedding_model.encode(review).tolist()
    except Exception as e:
        print(f"[FEL]: Kunde inte skapa inbäddning. Avbryter. Fel: {e}")
        return

    # 3. DATABASSTRUKTUR & 4. SPARA-STEGET
    data_to_save = [
        {
            "name": restaurant_name,
            "city": final_city,
            "text": review,
            "vector": embedding, # Måste spara vektorn för att kunna söka och matcha i perform_vector_serach() sen
        }
    ]
    
    try:
        table.add(data_to_save)
        print(f"\n[KLART]: '{restaurant_name}' lades till i databasen för {final_city}.")
        print(f"Den nya recensionen kan nu sökas i RAG-agenten.")
    except Exception as e:
        print(f"[FEL]: Kunde inte spara data till LanceDB. Fel: {e}")
        
    return


# --- FUNKTION: VISA ALLA NAMN ---
def list_all_names():
    """
    Hämtar alla poster från databasen och skriver ut namnen.
    Använder to_pandas() direkt för maximal kompatibilitet.
    """
    print("\n--- ALLA RESTAURANGNAMN I DATABASEN ---")
    try:
        # Hämta all data och välj sedan kolumnerna i Pandas
        all_restaurants = table.to_pandas()
        
        if all_restaurants.empty:
            print("Databasen är tom.")
            return

        # Välj endast de nödvändiga kolumnerna och sortera
        restaurants_to_display = all_restaurants[['name', 'city']].sort_values(by='city')

        # Ingen nuvarande stad än
        current_city = None
        for _, row in restaurants_to_display.iterrows(): 
            if row['city'] != current_city: # Om city inte är None, t.ex. Göteborg
                print(f"\n[{row['city'].upper()}]:") # Skriv ut göteborg
                current_city = row['city'] # göteborg blir nuvarande stad
            
            print(f"- {row['name']}")   # skriv ut restauranger för göteborg (row)
            
            # Sedan börjar loopen om, nuvarande stad är göteborg, nästa restaurang skrivs ut. Sedan byts stad och loopen upprepas
        
        print("------------------------------------------")

    except Exception as e:
        print(f"[KRITISKT FEL]: Kunde inte läsa från databasen. Fel: {e}")
