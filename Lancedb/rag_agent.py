from dotenv import load_dotenv
import os
import lancedb
from sentence_transformers import SentenceTransformer
from pydantic import ValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError 

from models import Restaurant, RestaurantList 


# Rådata (LanceDB) - RAG sökning - LLM tolkning - Pydantic - Restaurantobjekt



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
table = db.open_table("restaurants_db")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 


# HANTERAR ANVÄNDARINPUT (SRP: Input & Stadsdetektering)
def get_user_query(input_prompt: str) -> tuple[str | None, str | None]:
    """
    Hanterar inmatning från användaren, checkar för avslut, och detekterar stad.
    Returnerar (user_input, city)
    """
    user_input = input(input_prompt)
    if user_input.lower() == 'q':
        return None, None
    
    input_lower = user_input.lower()
    city = None
    if "göteborg" in input_lower or "gbg" in input_lower:
        city = "Göteborg"
    elif "uddevalla" in input_lower:
        city = "Uddevalla"
        
    return user_input, city


# HANTERAR HÄMTNING (SRP: Vektoriserar & Söker i LanceDB)
def perform_vector_search(query: str, city: str | None) -> str | None:
    """
    Vektoriserar frågan, söker i LanceDB och formaterar de 3 bästa träffarna.
    Returnerar den kombinerade kontextsträngen, eller None vid fel/ingen träff.
    """
    
    print("\n Söker i LanceDB ")

    try:
        query_vector = embedding_model.encode(query).tolist()
        search_query = table.search(query_vector)
        
        if city:
            search_query = search_query.where(f"city = '{city}'")
            print(f"-> Sökningen filtreras till staden: {city}")
        
        # Hämta de 3 bästa träffarna
        search_results = search_query.limit(3).to_list()

    except Exception as e:
        print(f"[FEL]: Kunde inte söka i LanceDB. Fel: {e}")
        return None
    
    # Förbered kontexten för Gemini
    if not search_results:
        print("Ingen information tillgänglig i databasen för din sökning.")
        return None
    
    context_blocks = []
    for i, result in enumerate(search_results, 1):
        context_blocks.append(f"KONTEXT #{i} (Stad: {result['city']}):\n{result['text']}")
    
    context_text = "\n---\n".join(context_blocks)
    print(f"Hittade {len(search_results)} potentiella fakta. Skickar till Gemini...")
    
    return context_text


# HANTERAR GENERERING (SRP: LLM-anrop & Validering)
def generate_structured_response(user_query: str, context: str) -> RestaurantList | None:
    """
    Skapar prompten, anropar Gemini och validerar svaret mot RestaurantList.
    Returnerar det validerade Pydantic-objektet.
    """
    
    print("\n--- Gör resultatet till strukturerat JSON med Gemini ---")

    system_instruction = (
        "Du är en expert på strukturerad JSON-extraktion. "
        "Analysera noga den angivna KONTEXTEN, som innehåller upp till 3 restaurangbeskrivningar. "
        "Ditt mål är att extrahera information för ALLA restauranger som är relevanta för användarens fråga. "
        "Fyll i JSON-schemat för **RestaurantList** genom att inkludera ALLA restauranger i 'results'-listan. "
        "Om ett fält saknas i kontexten, använd värdet 'Information saknas'."
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

        # Validera och deserialisera mot RestaurantList
        json_string = response.text.strip()
        validated_output: RestaurantList = RestaurantList.model_validate_json(json_string)
        return validated_output
        
    except ValidationError as e:
        print(f"\n[FEL]: Valideringsfel. AI:n svarade med fel format: {e}")
    except APIError as e:
        print(f"\n[KRITISKT FEL]: Ett Gemini API-fel uppstod. Kontrollera din nyckel och kvot: {e}")
    except Exception as e:
        print(f"\n[KRITISKT FEL]: Ett oväntat fel uppstod: {e}")
    
    return None


def add_restaurant():
    """
    Hanterar inmatning av ny restaurangdata, skapar inbäddningar och lagrar den 
    i LanceDB-tabellen. Matchar det ursprungliga schemat (name, city, text, vector).
    """
    print("\n--- LÄGG TILL NY RESTAURANG ---")
    
    # 1. INPUT-STEGET
    restaurant_name = input("Restaurangens namn: ")
    restaurant_city = input("Stad: ")
    review = input("Recensera restaurangen (T.ex. 'Bra mat, högt betyg 4.5, Thai-mat'): ")
    
    if not (restaurant_name and restaurant_city and review):
        print("[AVBRUTEN]: Alla fält måste fyllas i.")
        return

    # 2. VEKTORISERINGS- & EMBEDDING-STEGET
    try:
        print("-> Skapar inbäddning (vektor) från recensionen...")
        embedding = embedding_model.encode(review).tolist()
    except Exception as e:
        print(f"[FEL]: Kunde inte skapa inbäddning. Avbryter. Fel: {e}")
        return

    # 3. DATABASSTRUKTUR & 4. SPARA-STEGET
    
    # Skicka BARA de fält som finns i det ursprungliga schemat från setup_db.py
    data_to_save = [
        {
            # OBS: 'id' är borttaget härifrån
            "name": restaurant_name,
            "city": restaurant_city,
            "text": review,
            "vector": embedding,
        }
    ]
    
    try:
        # table.add() lägger till den nya raden
        table.add(data_to_save)
        print(f"\n[KLART]: '{restaurant_name}' lades till i databasen.")
        print(f"Den nya recensionen kan nu sökas i RAG-agenten.")
    except Exception as e:
        print(f"[FEL]: Kunde inte spara data till LanceDB. Fel: {e}")
        
    return


# KÖR AGENT (Orkestrering och Menylogik)

def run_rag_agent():
    print("================ RAG-AGENT STARTAD (Gemini)================")
    print(f"Modell: {MODEL_NAME} | Databas: {DB_PATH}")
    
    
    while True:
        # VISA MENYN
        print("\n-----------------------------------------------------")
        print("Välj ett alternativ:")
        print("1: Sök restaurang")
        print("2: Lägg till restaurang")
        print("q: Avsluta")
        print("-----------------------------------------------------")
        
        choice = input("Val: ").lower().strip()
        
        # HANTERA VAL
        if choice == 'q':
            print("Avslutar RAG-agent.")
            break
            
        elif choice == '1':
            # --- SÖK ---
            prompt = "Sök efter en restaurang. (Ex: 'Kinesiskt i Göteborg' eller 'q' för att avbryta sökningen):\n> "
            
            # 1. Ta emot input
            user_query, city = get_user_query(prompt) 
            
            if user_query is None:
                # Användaren skrev 'q' i sökprompten, gå tillbaka till huvudmenyn
                continue
            
            # 2. Hämtningssteget
            context_text = perform_vector_search(user_query, city)
            if context_text is None:
                continue
            
            # 3. Genereringssteget
            validated_output = generate_structured_response(user_query, context_text)
            
            # 4. UTSKRIFTSSTEGET (Den kompletta logiken)
            if validated_output and validated_output.results:
                print("\n--- Strukturerade och Faktabaserade Resultat (Lista) ---")
                for i, restaurant in enumerate(validated_output.results, 1):
                    print(f"--- RESTAURANG #{i} ---")
                    print(f"Namn: {restaurant.name}")
                    print(f"Adress: {restaurant.address}")
                    print(f"Betyg: {restaurant.rating}")
                    # Säker utskrift av köksstilar som en kommaseparerad sträng
                    print(f"Köksstilar: {', '.join(restaurant.cuisines)}") 
                print("-----------------------------------------------------")
            elif validated_output:
                print("Gemini kunde inte extrahera några relevanta restauranger från kontexten trots funna träffar.")
            
        elif choice == '2':
            add_restaurant()
            
        else:
            print("Ogiltigt val. Vänligen välj 1, 2, eller 'q'.")

if __name__ == "__main__":
    run_rag_agent()