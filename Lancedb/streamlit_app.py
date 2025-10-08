import streamlit as st
import requests
from typing import List
from urllib.parse import quote

BG_URL = "https://cdn.pixabay.com/photo/2018/06/27/22/08/restaurant-3502712_1280.jpg"
BASE_URL = "http://localhost:8000"


st.set_page_config(layout="wide")

# CSS - huvudapp-container
st.markdown(
        f"""
        <style>
        /* Sätter bakgrunden med en 40% svart overlay direkt på huvudcontainern */
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url("{BG_URL}");
            background-size: cover; /* Säkerställer att bilden täcker hela ytan */
            background-repeat: no-repeat;
            background-attachment: fixed; /* Håller bilden stilla vid scrollning */
        }}
        
        /* Säkerställer att sidebar har standard Streamlit-bakgrund för läsbarhet */
        [data-testid="stSidebar"] {{
            background-color: rgb(240, 242, 246); 
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Använder cache för att endast anropa API:et en gång, KOMMER IHÅG RESULTATET, ANROPAR INTE FUNKTIONEN IGEN VID INTERAKTION OM INTE TIDEN GÅTT UT
@st.cache_data(ttl=3600)
def load_all_names() -> List[str]:
    try:
        response = requests.get(f"{BASE_URL}/restaurants")
        if response.status_code == 200:
            return response.json().get('names', [])
        st.error(f"Kunde inte ladda restaurangnamn. Status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.warning("⚠️ API-anslutning misslyckades. Kontrollera att FastAPI-servern körs.")


st.header("Restaurants with RAG")

# Ladda alla namn
all_restaurant_names = load_all_names()
all_restaurant_names.sort()


cols = col1, col2 = st.columns(2)

with col1:
    query = st.text_input("Beskriv vad du söker: ")
    city = st.text_input("Stad: ")

    if st.button("Sök"):
        
        if not query or not city:
            st.error("⚠️ Vänligen fyll i båda fält.")
        else:
            st.info(f"🔎 Söker efter '{query}' i {city}...")
            response = requests.get(f"{BASE_URL}/search?query={query}&city={city}")
            
            if response.status_code == 200:
                json_data = response.json()
                st.success("Sökningen lyckades! ")
                
                # st.write(json_data)
                st.dataframe(json_data['results'])
            else:
                st.warning("Hittade inga resultat för den sökningen")

with col2:
    st.header("Hitta detaljer")
    
    # Skapa rullgardinsmenyn
    if not all_restaurant_names:
        st.warning("Kunde inte ladda restauranglistan.")
        selected_name = None
    else:
        selected_name = st.selectbox(
            "Välj restaurang för detaljer:", 
            options=["— Välj Restaurang —"] + all_restaurant_names
        )

    if selected_name and selected_name != "— Välj Restaurang —":
        with st.spinner(f"Hämtar en recension för {selected_name}..."):
            # Anropa /details endpointen
            encoded_detail_name = quote(selected_name)
            detail_response = requests.get(f"{BASE_URL}/details?restaurant_name={encoded_detail_name}")
            
            if detail_response.status_code == 200:
                detail_data = detail_response.json().get('details') 
                
                if detail_data: 
                    # Visa bara textfältet
                    st.markdown(f"**Om restaurangen: {selected_name}**")
                    st.info(detail_data.get('text', 'Ingen recensionstext tillgänglig.'))
                else:
                    st.warning("Inga detaljer hittades för detta namn.")
                
            else:
                st.error(f"Kunde inte hitta detaljer för {selected_name}. Kontrollera /details endpointen.")
