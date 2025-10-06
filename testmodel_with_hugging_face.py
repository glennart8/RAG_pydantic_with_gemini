from dotenv import load_dotenv
from pydantic_ai import Agent, exceptions
from models import Restaurant

# Ladda .env
load_dotenv()

# Ange Hugging Face-modellen
MODEL = "huggingface:mistralai/Mixtral-8x7B-Instruct-v0.1"


# Skapa agent
agent = Agent(
    MODEL,
    output_type=Restaurant,
    retries=2,
    output_retries=2
)

agent.system_prompt = """
Du ska alltid returnera ett ENDAST JSON-objekt som matchar Restaurant:
{"name": "X", "address": "Y", "rating": 4.5, "cuisines": ["Z"]}
"""



try:
    result = agent.run_sync(
        "Beskriv en mysig vegetarisk restaurang i Göteborg med namn, adress, rating och typer av mat."
    )
    print(result.output.model_dump())
except exceptions.UnexpectedModelBehavior as e:
    print("Modellen levererade inte korrekt format:", e)
