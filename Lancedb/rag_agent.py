from rag_logic import get_user_query, perform_vector_search, run_gemini_query, add_restaurant, list_all_names, MODEL_NAME, DB_PATH

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