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
DB_PATH = "my_restaurant_db"
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
def perform_vector_search(query: str) -> str | None:
    """
    1. Frågar efter stad för filtrering.
    2. Hämtar de 5 bäst matchande recensionerna från LanceDB.
    3. Formaterar träffarna tydligt som kontext för LLM.
    4. Returnerar den formaterade kontexten.
    """
    
    # 1. HANTERING AV STADSFILTER (Manuell input)
    city_filter = input("Ange staden att söka i (Göteborg/Uddevalla): ").strip()
    
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

    # 4. RETURNERA DEN SAMMANSTÄLLDA KONTEXTEN
    return "\n".join(context_text)


# HANTERAR GENERERING (RAG: Generation)
def run_gemini_query(user_query: str, context: str) -> RestaurantList | None: 
    """
    Skapar prompten, anropar Gemini och validerar svaret mot RestaurantList.
    Returnerar det validerade Pydantic-objektet.
    """
    
    print("\n--- Gör resultatet till strukturerat JSON med Gemini ---")

    # VIKTIGT: Skärp instruktionerna mot hallucinationer
    system_instruction = (
        """Du är en expert på att extrahera strukturerad data. 
        Din uppgift är att läsa igenom den bifogade kontexten (recensionstexterna) och ENDAST returnera information som uttryckligen nämns i dessa texter. 
        Om ett fält (som 'Adress' eller 'Betyg') inte kan hittas i kontexten för en specifik restaurang, måste du sätta värdet till 'Information saknas'. 
        Du får ABSOLUT INTE gissa, fabricera, eller hämta information från ditt allmänna vetande.
        Namn och Stad finns redan explicit i kontexten; använd dessa värden direkt."""
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

# KÖR AGENT (Orkestrering och Menylogik)

def run_rag_agent():
    print("================ RAG-AGENT STARTAD (Gemini)================")
    print(f"Modell: {MODEL_NAME} | Databas: {DB_PATH}")
    
    
    while True:
        # VISA MENYN (NYTT ALTERNATIV)
        print("\n-----------------------------------------------------")
        print("Välj ett alternativ:")
        print("1: Sök restaurang")
        print("2: Lägg till restaurang")
        print("3: Visa alla namn") # NYTT
        print("q: Avsluta")
        print("-----------------------------------------------------")
        
        choice = input("Val: ").lower().strip()
        
        # HANTERA VAL
        if choice == 'q':
            print("Avslutar RAG-agent.")
            break
            
        elif choice == '1':
            # --- SÖK ---
            prompt = "Sök efter en restaurang. (Ex: 'Kinesiskt' eller 'q' för att avbryta sökningen):\n> "
            
            # 1. Ta emot input
            user_query = get_user_query(prompt)
            
            if user_query is None:
                continue
            
            # 2. Hämtningssteget (Retrieval)
            context_text = perform_vector_search(user_query) 
            
            if context_text is None:
                continue
            
            # 3. Genereringssteget (Generation)
            validated_output = run_gemini_query(user_query, context_text) 
            
            # 4. UTSKRIFTSSTEGET
            if validated_output and validated_output.results:
                print("\n--- Strukturerade och Faktabaserade Resultat (Lista) ---")
                for i, restaurant in enumerate(validated_output.results, 1):
                    print(f"--- RESTAURANG #{i} ---")
                    print(f"Namn: {restaurant.name}")
                    print(f"Adress: {restaurant.address}")
                    print(f"Betyg: {restaurant.rating}")
                    print(f"Köksstilar: {', '.join(restaurant.cuisines)}") 
                print("-----------------------------------------------------")
            elif validated_output:
                print("Gemini kunde inte extrahera några relevanta restauranger från kontexten trots funna träffar.")
            
        elif choice == '2':
            add_restaurant()
            
        elif choice == '3': # HANTERA NYTT VAL
            list_all_names()
            
        else:
            print("Ogiltigt val. Vänligen välj 1, 2, 3, eller 'q'.")

if __name__ == "__main__":
    run_rag_agent()