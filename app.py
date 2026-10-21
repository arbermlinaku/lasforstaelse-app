import streamlit as st
from PIL import Image
from google import genai
from google.genai import errors
import time

# 1. Sidinställningar
st.set_page_config(page_title="Läsmästaren: Uppdraget", page_icon="📖", layout="centered")

st.title("📖 Läsmästaren: Uppdraget")
st.write("Läs ett kapitel i boken, ta ett foto eller skriv in texten och lös uppdragen!")

# 2. Hämta API-nyckel från Secrets
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("API-nyckel saknas! Konfigurera GEMINI_API_KEY i Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

# Håll reda på tillstånd i appen
if "fragor" not in st.session_state:
    st.session_state.fragor = None
if "boktext" not in st.session_state:
    st.session_state.boktext = None

# 3. Text- eller bildinmatning
st.subheader("Steg 1: Lägg in boksidan")
val = st.radio("Hur vill du lägga in texten?", ["Ta ett foto med kameran", "Skriv eller klistra in text"], horizontal=True)

bild_data = None
text_data = None

if val == "Ta ett foto med kameran":
    foto = st.camera_input("Rikta kameran mot boksidan och ta ett foto")
    if foto:
        raw_img = Image.open(foto)
        # Konvertera till RGB för att undvika färgrymdsfel hos API:et
        bild_data = raw_img.convert("RGB")
        # Begränsa maxupplösning för snabb och stabil överföring
        bild_data.thumbnail((1200, 1200))
        st.image(bild_data, caption="Ditt foto", width=300)
else:
    text_data = st.text_area("Skriv eller klistra in några rader från kapitlet:", height=150)

if st.button("Skapa mina läsuppdrag ✨"):
    if not bild_data and not text_data:
        st.warning("Du måste ta ett foto eller skriva in text först!")
    else:
        with st.spinner("Läsmästaren läser texten och skapar uppdrag..."):
            prompt_fragor = """
            Du är en uppmuntrande svensklärare för elever i årskurs 4 och 5.
            Läs texten på bilden eller i texten noggrant. 
            Skapa tre frågor anpassade efter Lgr22 för läsförståelse:
            
            1. [LÄTT] En faktafråga där svaret står rakt ut i texten ("på raderna").
            2. [MEDEL] En fråga där eleven måste dra en enkel slutsats eller förstå känslor/orsaker ("mellan raderna").
            3. [SVÅR] En fråga där eleven får reflektera, tolka budskap eller koppla handlingen till egna erfarenheter ("bortom raderna").
            
            Formulera frågorna enkelt, lekfullt och tydligt för en 10-11-åring.
            Svara strikt i följande format:
            LÄTT: [Fråga här]
            MEDEL: [Fråga här]
            SVÅR: [Fråga här]
            """
            
            innehall = [prompt_fragor]
            if bild_data:
                innehall.append(bild_data)
            if text_data:
                innehall.append(text_data)
            
            # Anropa med felhantering för tillfälliga serverstörningar
            lyckades = False
            for forsok in range(2):
                try:
                    respons = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=innehall
                    )
                    st.session_state.fragor = respons.text
                    st.session_state.boktext = text_data if text_data else "Bildanalys"
                    lyckades = True
                    break
                except errors.ServerError:
                    time.sleep(2)  # Vänta 2 sekunder och prova en gång till
                except Exception as e:
                    st.error(f"Ett fel uppstod: {e}")
                    break
            
            if not lyckades and "fragor" not in st.session_state:
                st.error("Googles servrar är tillfälligt överbelastade just nu. Vänta 10 sekunder och klicka på knappen igen!")

# 4. Svarsdel och formativ rättning
if st.session_state.fragor:
    st.divider()
    st.subheader("Steg 2: Välj uppdrag och svara")
    
    st.markdown(st.session_state.fragor)
    
    vald_niva = st.selectbox("Vilket uppdrag vill du svara på?", ["Lätt", "Medel", "Svår"])
    elev_svar = st.text_area("Ditt svar:")
    
    if st.button("Lämna in svar för rättning 🚀"):
        if not elev_svar.strip():
            st.warning("Skriv ett svar innan du lämnar in!")
        else:
            with st.spinner("Läsmästaren läser ditt svar..."):
                prompt_rattning = f"""
                Du är en varm och uppmuntrande svensklärare för mellanstadiet (åk 4-5).
                
                Här är uppdragen och källtexten:
                {st.session_state.fragor}
                
                Eleven har svarat på nivå: {vald_niva}
                Elevens svar: "{elev_svar}"
                
                Instruktioner för bedömning:
                - VIKTIGT: Ignorera helt stavfel, särskrivningar, talspråksdrag och grammatiska småfel. Fokusera uteslutande på om eleven visar förståelse för innehållet.
                - Ge alltid eleven beröm för att den försökt.
                - Avgör om svaret är:
                  * "Klarat!": Eleven har förstått och svarat rimligt utifrån frågan.
                  * "Nästan där!": Svaret är på rätt spår men saknar en viktig detalj. Ge en vänlig ledtråd.
                  * "Försök igen": Svaret visar inte förståelse för texten. Förklara kort och ge en ledtråd utan att avslöja hela svaret.
                - Håll tonen inspirerande med emojis.
                """
                
                try:
                    bedomning = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[prompt_rattning]
                    )
                    st.success("Här är Läsmästarens återkoppling:")
                    st.markdown(bedomning.text)
                except errors.ServerError:
                    st.error("Googles AI-server svarade inte just nu. Prova att klicka på 'Lämna in svar' igen om några sekunder!")
                except Exception as e:
                    st.error(f"Ett oväntat fel inträffade: {e}")