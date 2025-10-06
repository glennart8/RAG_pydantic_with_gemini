import lancedb
import pandas as pd
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 
DB_PATH = "my_restaurant_db"
db = lancedb.connect(DB_PATH)

raw_data = [
    {"text": "Den kinesiska restaurangen i Uddevalla heter **China Palace**. De ligger på Kilbäcksgatan 18, 451 84 Uddevalla. De har ett betyg på 4.0 och är kända för sin lunchbuffé. Köksstilar: Kinesisk, Buffé.", 
     "city": "Uddevalla"},
    
    {"text": "I Göteborg kan du hitta den vegetariska restaurangen **Blackbird** på Storgatan 45. De har en rating på 4.8 och fokus på vegansk fine dining. Köksstilar: Vegansk, Fine Dining.", 
     "city": "Göteborg"},
     
    {"text": "En välkänd kinesisk restaurang i Göteborg är **Röda Draken**. Adress: Kungsportsavenyn 15. Rating: 4.5. Köksstilar: Kinesisk, Kantonesisk.", 
     "city": "Göteborg"},
     
    {"text": "En italiensk restaurang i Majorna är **Pizzeria Venezia**. Adress: Slottsskogsgatan 10. Ratingen är 4.3. Köksstilar: Pizza, Italiensk, Pasta.", 
     "city": "Göteborg"},
]
df = pd.DataFrame(raw_data)

# 3. Vektorisera och spara i LanceDB
print(f"Skapar vektorer och sparar i LanceDB...")
df["vector"] = df["text"].apply(lambda x: embedding_model.encode(x).tolist())

table = db.create_table(
    "restaurants_db", 
    data=df, 
    mode="overwrite" 
)

print(f"LanceDB-tabellen 'restaurants_db' uppdaterad med 'city'-kolumnen.")
