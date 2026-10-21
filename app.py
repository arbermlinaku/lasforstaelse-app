import streamlit as st
from PIL import Image
from google import genai
from google.genai import errors
import json
import re

# 1. Sidinställningar
st.set_page_config(page_title="Läsmästaren: Uppdraget", page_icon="📖", layout="centered")

st.title("📖 Läsmästaren: Bokäventyret")
st.write("Läs ett kapitel i boken, ta ett foto eller skriv in texten och klara alla 6 nivåer!")

# 2. Hämta API-nyckel
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("API-nyckel saknas! Konfigurera GEMINI_API_KEY i Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

# 3. Sessionsvariabler för att hålla reda på nivåer och framsteg
if "uppdrag_lista" not in st.session_state:
    st.session_state.uppdrag_lista = []
if "aktuellt_index" not in st.session_state:
    st.session_state.aktuellt_index = 0
if "senaste_feedback" not in st.session_state:
    st.session_state.senaste_feedback = None
if "boktext" not in st.session_state:
    st.session_state.boktext = None

# Funktion för att starta om äventyret
def nollstall():
    st.session_state.uppdrag_lista = []
    st.session_state.aktuellt_index = 0
    st.session_state.senaste_feedback = None
    st.session_state.boktext = None

# 4. Inmatning: Visa bara om uppdrag inte har skapats än
if not st.session_state.uppdrag_lista:
    st.subheader("Steg 1: Lägg in boksidan")
    val = st.radio("Hur vill du lägga in texten?", ["Ta ett foto med kameran", "Skriv eller klistra in text"], horizontal=True)

    bild_data = None
    text_data = None

    if val == "Ta ett foto med kameran":
        foto = st.camera_input("Rikta kameran mot boksidan och ta ett foto")
        if foto:
            raw_img = Image.open(foto)
            bild_data = raw_img.convert("RGB")
            bild_data.thumbnail((1200, 1200))
            st.image(bild_data, caption="Ditt foto", width=300)
    else:
        text_data = st.text_area("Skriv eller klistra in några rader från kapitlet:", height=150)

    if st.button("Starta läsäventyret ✨"):
        if not bild_data and not text_data:
            st.warning("Du måste ta ett foto eller skriva in text först!")
        else:
            with st.spinner("Läsmästaren läser och förbereder dina 6 uppdrag..."):
                prompt = """
                Du är en svensklärare för årskurs 4 och 5. Läs bifogad text eller bild noggrant.
                Skapa exakt 6 läsförståelsefrågor anpassade efter Lgr22 i följande ordning:
                - Fråga 1 till 3: LÄTT (faktafrågor där svaret står rakt ut i texten, 'på raderna')
                - Fråga 4 till 5: MEDEL (inferensfrågor om känslor, orsaker eller varför, 'mellan raderna')
                - Fråga 6: SVÅR (tolkning, budskap eller reflektion till egna livet, 'bortom raderna')

                Svara ENDAST med ett giltigt JSON-format (en lista med 6 objekt). Inget annat!
                Format:
                [
                  {"nummer": 1, "niva": "Lätt", "fraga": "..."},
                  {"nummer": 2, "niva": "Lätt", "fraga": "..."},
                  {"nummer": 3, "niva": "Lätt", "fraga": "..."},
                  {"nummer": 4, "niva": "Medel", "fraga": "..."},
                  {"nummer": 5, "niva": "Medel", "fraga": "..."},
                  {"nummer": 6, "niva": "Svår", "fraga": "..."}
                ]
                """
                innehall = [prompt]
                if bild_data:
                    innehall.append(bild_data)
                if text_data:
                    innehall.append(text_data)

                try:
                    respons = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=innehall
                    )
                    # Tvätta bort eventuella markdown-block så att JSON kan tolkas rent
                    ren_json = respons.text.strip()
                    ren_json = re.sub(r"^```(?:json)?\n?|```$", "", ren_json, flags=re.MULTILINE).strip()
                    st.session_state.uppdrag_lista = json.loads(ren_json)
                    st.session_state.aktuellt_index = 0
                    st.session_state.boktext = text_data if text_data else "Bildanalys"
                    st.rerun()
                except Exception as e:
                    st.error("Kunde inte läsa in uppdragen automatiskt. Försök ta en skarpare bild eller klistra in texten direkt.")

# 5. Spelet: En fråga i taget
else:
    idx = st.session_state.aktuellt_index
    total = len(st.session_state.uppdrag_lista)

    # Om alla 6 frågor är besvarade:
    if idx >= total:
        st.balloons()
        st.success("🎉 HURRA! Du har klarat alla 6 uppdrag i detta kapitel!")
        st.markdown("Du har visat att du kan läsa på raderna, mellan raderna och bortom raderna! Grymt jobbat!")
        if st.button("Börja om med ett nytt kapitel 🔄"):
            nollstall()
            st.rerun()

    # Annars visas aktuell fråga
    else:
        uppdrag = st.session_state.uppdrag_lista[idx]
        
        # Framstegsmätare (t.ex. 1 av 6, 2 av 6)
        framsteg = (idx) / total
        st.progress(framsteg)
        
        farg_ikon = "🟢" if uppdrag["niva"] == "Lätt" else ("🟡" if uppdrag["niva"] == "Medel" else "🔴")
        st.subheader(f"{farg_ikon} Uppdrag {uppdrag['nummer']} av {total}: Nivå {uppdrag['niva']}")
        
        st.info(f"**Fråga:** {uppdrag['fraga']}")

        # Svarsfält för eleven
        elev_svar = st.text_area("Skriv ditt svar här:", key=f"svar_{idx}", height=100)

        kol1, kol2 = st.columns([1, 1])

        with kol1:
            if st.button("Lämna in svar 🚀"):
                if not elev_svar.strip():
                    st.warning("Skriv ett svar innan du lämnar in!")
                else:
                    with st.spinner("Läsmästaren läser ditt svar..."):
                        prompt_rattning = f"""
                        Du är en varm och uppmuntrande svensklärare för årskurs 4-5.
                        Fråga: {uppdrag['fraga']}
                        Nivå: {uppdrag['niva']}
                        Elevens svar: "{elev_svar}"

                        Regler:
                        - Ignorera helt stavfel, särskrivningar och grammatiska fel. Bedöm bara om eleven förstått innehållet.
                        - Beröm alltid försöket.
                        - Ge formativ återkoppling: Är det 'Klarat! ⭐', 'Nästan där! 💡' eller 'Försök igen'?
                        - Håll det kort (max 3-4 meningar), varmt och barnvänligt.
                        """
                        try:
                            bedomning = client.models.generate_content(
                                model="gemini-3.8-flash",
                                contents=[prompt_rattning]
                            )
                            st.session_state.senaste_feedback = bedomning.text
                        except Exception:
                            st.session_state.senaste_feedback = "Kunde inte ansluta till Läsmästaren just nu. Försök klicka igen!"

        # Visa återkopplingen och knappen för att gå vidare
        if st.session_state.senaste_feedback:
            st.divider()
            st.markdown(st.session_state.senaste_feedback)
            
            # Knapp för att gå till nästa fråga
            if st.button("Gå till nästa uppdrag ➡️"):
                st.session_state.aktuellt_index += 1
                st.session_state.senaste_feedback = None
                st.rerun()

        st.divider()
        if st.button("Avbryt och välj ny text / nytt foto"):
            nollstall()
            st.rerun()