import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
import json
import os
import re
import time

# 1. Sidkonfiguration
st.set_page_config(page_title="Läsmästaren: Bokäventyret", page_icon="🎮", layout="centered")

SPARFIL = "framsteg.json"

def ladda_framsteg():
    if os.path.exists(SPARFIL):
        try:
            with open(SPARFIL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def spara_framsteg(data):
    with open(SPARFIL, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 2. Initiering av Gemini API
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("API-nyckel saknas! Konfigurera GEMINI_API_KEY i Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

# Endast aktiva och moderna modeller i prioritetsordning
MODELL_KEDJA = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite"
]

def anropa_gemini_med_fallback(client, contents, config=None):
    """Testar modellerna i turordning. Om en modell är överbelastad (503) eller otillgänglig prövas nästa direkt."""
    senaste_fel = None
    for modell_namn in MODELL_KEDJA:
        try:
            return client.models.generate_content(
                model=modell_namn,
                contents=contents,
                config=config
            )
        except Exception as e:
            senaste_fel = e
            # Om modellen har hög belastning eller inte svarar, ta en kort paus och prova nästa i kedjan
            time.sleep(1.0)
            continue
            
    # Om alla modeller i listan misslyckades
    raise senaste_fel

# 3. Sessionsvariabler för spelet
if "spelar_data" not in st.session_state:
    st.session_state.spelar_data = ladda_framsteg()
if "aktivt_kapitel" not in st.session_state:
    st.session_state.aktivt_kapitel = None
if "uppdrag_lista" not in st.session_state:
    st.session_state.uppdrag_lista = []
if "aktuellt_index" not in st.session_state:
    st.session_state.aktuellt_index = 0
if "senaste_feedback" not in st.session_state:
    st.session_state.senaste_feedback = None

st.title("🎮 Läsmästaren: Bokäventyret")

# 4. Spelarprofil & Inloggning
st.sidebar.header("👤 Spelarprofil")
elev_namn = st.sidebar.text_input("Ditt namn eller alias:").strip().lower()
bok_titel = st.sidebar.text_input("Bokens titel:").strip().lower()

if not elev_namn or not bok_titel:
    st.info("👋 Välkommen! Skriv in ditt namn och bokens titel i menyn till vänster för att starta.")
    st.stop()

profil_nyckel = f"{elev_namn}###{bok_titel}"
framsteg_db = ladda_framsteg()

if profil_nyckel not in framsteg_db:
    framsteg_db[profil_nyckel] = {
        "namn": elev_namn,
        "bok": bok_titel,
        "klarade_kapitel": []
    }
    spara_framsteg(framsteg_db)

elev_profil = framsteg_db[profil_nyckel]
klarade = set(elev_profil.get("klarade_kapitel", []))

# ---------------------------------------------------------------------
# VY 1: SPELKARTAN
# ---------------------------------------------------------------------
if st.session_state.aktivt_kapitel is None:
    st.subheader(f"🗺️ Kapitelkarta för: *{bok_titel.title()}*")
    st.write(f"Inloggad som: **{elev_namn.title()}** | Klarade kapitel: **{len(klarade)} st**")
    st.divider()

    antal_kapitel = max(10, max(klarade) + 2 if klarade else 5)
    
    for kap_nr in range(1, antal_kapitel + 1):
        kol1, kol2, kol3 = st.columns([1, 3, 2])
        
        with kol1:
            if kap_nr in klarade:
                st.write("⭐ 🏆")
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                st.write("🔓 🎯")
            else:
                st.write("🔒")

        with kol2:
            if kap_nr in klarade:
                st.write(f"**Kapitel {kap_nr}** (Klarat!)")
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                st.write(f"**Kapitel {kap_nr}** – Redo att spela!")
            else:
                st.write(f"Kapitel {kap_nr} – Låst")

        with kol3:
            if kap_nr in klarade:
                if st.button("Spela igen 🔁", key=f"spela_{kap_nr}"):
                    st.session_state.aktivt_kapitel = kap_nr
                    st.session_state.uppdrag_lista = []
                    st.session_state.aktuellt_index = 0
                    st.rerun()
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                if st.button("Starta nivå 🚀", key=f"starta_{kap_nr}", type="primary"):
                    st.session_state.aktivt_kapitel = kap_nr
                    st.session_state.uppdrag_lista = []
                    st.session_state.aktuellt_index = 0
                    st.rerun()

# ---------------------------------------------------------------------
# VY 2: SPELA ETT KAPITEL
# ---------------------------------------------------------------------
else:
    nuvarande_kap = st.session_state.aktivt_kapitel
    st.header(f"🎯 Utmaning: Kapitel {nuvarande_kap}")

    if not st.session_state.uppdrag_lista:
        st.write("Läs kapitlet i boken och fota sidan eller klistra in text från handlingen för att starta utmaningen.")
        
        val = st.radio("Välj metod:", ["Ta ett foto med kameran", "Skriv eller klistra in text"], horizontal=True)
        bild_data = None
        text_data = None

        if val == "Ta ett foto med kameran":
            foto = st.camera_input("Rikta kameran mot boksidan")
            if foto:
                raw_img = Image.open(foto)
                bild_data = raw_img.convert("RGB")
                bild_data.thumbnail((1200, 1200))
                st.image(bild_data, caption="Din bild", width=300)
        else:
            text_data = st.text_area("Klistra in några rader eller ett stycke från kapitlet:", height=150)

        kol_start, kol_avbryt = st.columns(2)
        with kol_start:
            if st.button("Lås upp uppdragen ✨", type="primary"):
                if not bild_data and (not text_data or len(text_data.strip()) < 15):
                    st.warning("Klistra in några rader ur boken eller ta ett foto först!")
                else:
                    with st.spinner("Läsmästaren skapar dina 6 uppdrag..."):
                        prompt = f"""
                        Du är en svensklärare för årskurs 4 och 5. Eleven läser kapitel {nuvarande_kap}.
                        Läs texten eller bilden noggrant. Skapa exakt 6 frågor anpassade efter Lgr22:
                        - Fråga 1 till 3: LÄTT (faktafrågor på raderna)
                        - Fråga 4 till 5: MEDEL (känslor, orsaker, slutsatser mellan raderna)
                        - Fråga 6: SVÅR (budskap, reflektion bortom raderna)

                        Svara som en strikt JSON-lista:
                        [
                          {{"nummer": 1, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 2, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 3, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 4, "niva": "Medel", "fraga": "..."}},
                          {{"nummer": 5, "niva": "Medel", "fraga": "..."}},
                          {{"nummer": 6, "niva": "Svår", "fraga": "..."}}
                        ]
                        """
                        innehall = [prompt]
                        if bild_data:
                            innehall.append(bild_data)
                        if text_data:
                            innehall.append(text_data)

                        try:
                            respons = anropa_gemini_med_fallback(
                                client=client,
                                contents=innehall,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json"
                                )
                            )
                            
                            svar_text = respons.text.strip()
                            match = re.search(r"\[.*\]", svar_text, re.DOTALL)
                            json_str = match.group(0) if match else svar_text

                            st.session_state.uppdrag_lista = json.loads(json_str)
                            st.session_state.aktuellt_index = 0
                            st.rerun()

                        except Exception as e:
                            st.error(f"Kunde inte ladda uppdragen: {e}")

        with kol_avbryt:
            if st.button("⬅️ Tillbaka till kartan"):
                st.session_state.aktivt_kapitel = None
                st.rerun()

    else:
        idx = st.session_state.aktuellt_index
        total = len(st.session_state.uppdrag_lista)

        if idx >= total:
            st.balloons()
            st.success(f"🏆 HURRA! Du har klarat alla uppdrag i Kapitel {nuvarande_kap}!")
            
            if nuvarande_kap not in elev_profil["klarade_kapitel"]:
                elev_profil["klarade_kapitel"].append(nuvarande_kap)
                framsteg_db[profil_nyckel] = elev_profil
                spara_framsteg(framsteg_db)

            st.write("Ditt framsteg har sparats på spelkartan!")
            if st.button("Gå till kapitelkartan 🗺️", type="primary"):
                st.session_state.aktivt_kapitel = None
                st.session_state.uppdrag_lista = []
                st.session_state.senaste_feedback = None
                st.rerun()

        else:
            uppdrag = st.session_state.uppdrag_lista[idx]
            st.progress((idx) / total)

            farg = "🟢" if uppdrag["niva"] == "Lätt" else ("🟡" if uppdrag["niva"] == "Medel" else "🔴")
            st.subheader(f"{farg} Uppdrag {uppdrag['nummer']} av {total}: Nivå {uppdrag['niva']}")
            st.info(f"**Fråga:** {uppdrag['fraga']}")

            elev_svar = st.text_area("Ditt svar:", key=f"svar_kap_{nuvarande_kap}_{idx}", height=100)

            if st.button("Lämna in svar 🚀"):
                if not elev_svar.strip():
                    st.warning("Skriv ett svar innan du lämnar in!")
                else:
                    with st.spinner("Läsmästaren läser ditt svar..."):
                        prompt_rattning = f"""
                        Du är en uppmuntrande svensklärare för årskurs 4-5.
                        Fråga: {uppdrag['fraga']}
                        Elevens svar: "{elev_svar}"

                        Regler:
                        - Ignorera helt stavfel och särskrivningar. Bedöm bara om eleven visar förståelse.
                        - Beröm alltid.
                        - Ge återkoppling med emojis: 'Klarat! ⭐', 'Nästan där! 💡' eller 'Tänk på detta...'.
                        - Max 3 korta meningar.
                        """
                        try:
                            bedomning = anropa_gemini_med_fallback(
                                client=client,
                                contents=[prompt_rattning]
                            )
                            st.session_state.senaste_feedback = bedomning.text
                        except Exception as e:
                            st.session_state.senaste_feedback = f"Kunde inte få kontakt med Läsmästaren: {e}"

            if st.session_state.senaste_feedback:
                st.divider()
                st.markdown(st.session_state.senaste_feedback)
                if st.button("Gå till nästa uppdrag ➡️", type="primary"):
                    st.session_state.aktuellt_index += 1
                    st.session_state.senaste_feedback = None
                    st.rerun()

            st.divider()
            if st.button("⬅️ Avbryt och gå till kartan"):
                st.session_state.aktivt_kapitel = None
                st.session_state.uppdrag_lista = []
                st.session_state.senaste_feedback = None
                st.rerun()