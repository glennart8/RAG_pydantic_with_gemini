import streamlit as st
import requests
from typing import List
from urllib.parse import quote

BG_URL = "https://cdn.pixabay.com/photo/2018/06/27/22/08/restaurant-3502712_1280.jpg"
BASE_URL = "http://localhost:8000"

st.set_page_config(layout="wide")

st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)), url("{BG_URL}");
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    [data-testid="stSidebar"] {{
        background-color: rgb(240, 242, 246);
    }}
    .boxed {{
        border: 1px solid #ccc;
        border-radius: 10px;
        padding: 20px;
        background-color: rgba(240,242,246,0.8);  /* grå med lite transparens */
        margin-bottom: 20px;
    }}
    div[data-baseweb="input"] > div:first-child {{
        background-color: rgba(60,60,60,0.7) !important;  /* riktigt mörk grå med transparens */
    }}
    div[data-baseweb="select"] > div {{
        background-color: rgba(60,60,60,0.7) !important;  /* riktigt mörk grå med transparens */
    }}
    textarea {{
        background-color: rgba(60,60,60,0.7) !important;  /* riktigt mörk grå med transparens */
    }}
    </style>
    """,
    unsafe_allow_html=True
)



@st.cache_data(ttl=3600)
def load_all_cities() -> List[str]:
    try:
        response = requests.get(f"{BASE_URL}/cities")
        if response.status_code == 200:
            return response.json().get('cities', [])
        st.error(f"Kunde inte ladda städer. Status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.warning("API-anslutning misslyckades")

@st.cache_data(ttl=3600)
def load_restaurants_by_city(city_name: str) -> List[str]:
    try:
        response = requests.get(f"{BASE_URL}/restaurants_by_city?city_name={city_name}")
        if response.status_code == 200:
            return response.json().get('names', [])
        st.error(f"Kunde inte ladda restaurangnamn för {city_name}. Status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.warning("API-anslutning misslyckades")

st.header("🍽️ RestAuranGer", divider="rainbow")

all_cities = load_all_cities()

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("🔍 Sök restauranger")
        query = st.text_input("Beskriv vad du söker:")
        city = st.selectbox("Stad:", all_cities, key="search_city")

        if st.button("Sök"):
            with col2:
                if not query or not city:
                    st.error("⚠️ Vänligen fyll i båda fält.")
                else:
                    st.info(f"🔎 Söker efter '{query}' i {city}...")
                    response = requests.get(f"{BASE_URL}/search?query={query}&city={city}")
                    if response.status_code == 200:
                        json_data = response.json()
                        st.success("Sökningen lyckades!")
                        st.dataframe(json_data['results'])
                    else:
                        st.warning("Inga resultat hittades.")

with col3:
    with st.container(border=True):
        st.subheader("📄 Visa detaljer")
        chosen_city = st.selectbox("Välj stad:", all_cities, key="detail_city")
        restaurants_by_city = load_restaurants_by_city(chosen_city)
        # restaurants_by_city.sort() Hur sortera?

        if not restaurants_by_city:
            st.warning("Kunde inte ladda restauranglistan.")
            selected_name = None
        else:
            selected_name = st.selectbox(
                "Välj restaurang för detaljer:",
                ["— Välj Restaurang —"] + restaurants_by_city
            )
        with col2:
            if selected_name and selected_name != "— Välj Restaurang —":
                with st.spinner(f"Hämtar en recension för {selected_name}..."):
                    encoded_detail_name = quote(selected_name)
                    detail_response = requests.get(f"{BASE_URL}/details?restaurant_name={encoded_detail_name}")

                    if detail_response.status_code == 200:
                        detail_data = detail_response.json().get('details')
                        if detail_data:
                            st.markdown(f"**Om restaurangen: {selected_name}**")
                            st.info(detail_data.get('text', 'Ingen recensionstext tillgänglig.'))
                            
                            # För uppdatering
                            updated_name = st.text_input("Namn:", value=detail_data.get('name', ''))
                            updated_city = st.text_input("Stad:", value=detail_data.get('city', ''))
                            updated_text = st.text_area("Recension:", value=detail_data.get('text', ''))
                            updated_rating = st.slider(label="Omdöme",min_value=0.0, max_value=5.0, value=3.0, step=0.1, format="%.1f")

                            # Skapar knapp och kollar om den trycks på
                            if st.button("Ändra", key="edit_button"):
                                try:
                                    put_response = requests.put(
                                        f"{BASE_URL}/edit?restaurant_name={encoded_detail_name}",
                                        json={
                                            "name": updated_name,
                                            "city": updated_city,
                                            "text": f"{updated_text} Betyg: {updated_rating}"
                                        }
                                    )

                                    if put_response.status_code == 200:
                                        st.success("Restaurangen har uppdaterats!")
                                    else:
                                        st.error(f"Något gick fel vid uppdateringen: {put_response.status_code}")
                                except requests.exceptions.RequestException as e:
                                    st.error(f"Ett fel uppstod vid anropet till API:et: {e}")
                                    
                        else:
                            st.warning("Inga detaljer hittades för detta namn.")
                    else:
                        st.error("Kunde inte hämta detaljer.")

colleft, colright = st.columns(2)

with colleft:
    with st.container(border=True):
        st.subheader("➕ Lägg till en restaurang")
        name = st.text_input("Restaurangens namn:")
        city = st.selectbox("Stad:", all_cities, key="add_restaurant_city")
        text = st.text_area("Berätta om restaurangen:")
        rating = st.slider(label="Omdöme",min_value=0.0, max_value=5.0, value=3.0, step=0.1, format="%.1f")

        if st.button("Lägg till restaurang"):
            if name and city and text and rating:
                post_restaurant = requests.post(f"{BASE_URL}/add_restaurant", json={
                    "name": name,
                    "city": city,
                    "text": text + f" Betyg: {rating}"
                })
                if post_restaurant.status_code == 200:
                    st.success("Restaurangen har lagts till!")
                    # Tömmer all cachad data. Streamlit kommer att köra om appen och ladda de nya städerna/restaurangerna.
                    st.cache_data.clear() 
                else:
                    st.error(f"Något gick fel: {post_restaurant.status_code}")
            else:
                st.warning("Fyll i alla fält innan du lägger till restaurangen.")
                
with colright:
    pass