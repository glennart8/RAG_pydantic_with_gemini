from dotenv import load_dotenv
from pydantic_ai import Agent, exceptions
from models import Restaurant 

load_dotenv()
MODEL = "openai:mistral" 

agent = Agent(
    MODEL,
    output_type=Restaurant,
    retries=2,
    output_retries=2
)

# Den hallucinerar - hittar på gatan och restauranger som inte finns.
agent.system_prompt = """
DU MÅSTE agera som en expert på JSON-extraktion.
Ditt enda svar får ENDAST bestå av ett JSON-objekt som STRIKT MATCHAR Restaurant-schemat.
Inkludera inga kommentarer, inledande meningar, eller markdown-syntax som ```json.
Om information saknas, fyll i fälten med en lämplig gissning eller 'N/A'.
"""


def run_interactive_agent():
    print(f"AI-Agenten är redo (Modell: {MODEL})")

    user_input = input("Beskriv vilken typ av restaurang du vill ha (t.ex. 'En mysig italiensk restaurang i Majorna'):\n> ")
    
    if not user_input:
        print("Ingen input given. Avslutar.")
        return

    print("\nSkickar förfrågan till AI-modellen...")

    try:
        result = agent.run_sync(user_input)
        
        print(result.output.model_dump_json(indent=2))
        
        # r = result.output
        # print(f"AI föreslår: {r.name} ({r.rating} stjärnor)")
        # print(f"Adress: {r.address}")
        
    except exceptions.UnexpectedModelBehavior as e:
        print("\n[FEL]: Modellen levererade inte korrekt JSON-format. Försök igen med en tydligare prompt.")
        
    except Exception as e:
        print(f"\nEtt oväntat fel uppstod: {e}")


# Kör funktionen när skriptet startas
if __name__ == "__main__":
    run_interactive_agent()