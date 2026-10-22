import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
import json
import os
import re
import time
from datetime import datetime

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

MODELL_KEDJA = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite"
]

def anropa_gemini_med_fallback(client, contents, config=None):
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
            time.sleep(1.0)
            continue
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
if "genomforda_svar" not in st.session_state:
    st.session_state.genomforda_svar = []  # Sparar frågor, svar och feedback

st.title("🎮 Läsmästaren: Bokäventyret")

# 4. Spelarprofil & Inloggning
st.sidebar.header("👤 Spelarprofil")
elev_namn = st.sidebar.text_input("Ditt namn eller alias:").strip().lower()
bok_titel = st.sidebar.text_input("Bokens / Häftets titel:").strip().lower()

if not elev_namn or not bok_titel:
    st.info("👋 Välkommen! Skriv in ditt namn och titeln på boken eller häftet i menyn till vänster.")
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
    st.subheader(f"🗺️ Äventyrskarta för: *{bok_titel.title()}*")
    st.write(f"Inloggad som: **{elev_namn.title()}** | Klarade delar: **{len(klarade)} st**")
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
                st.write(f"**Del / Kapitel {kap_nr}** (Klarat!)")
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                st.write(f"**Del / Kapitel {kap_nr}** – Redo att spela!")
            else:
                st.write(f"Del / Kapitel {kap_nr} – Låst")

        with kol3:
            if kap_nr in klarade:
                if st.button("Spela igen 🔁", key=f"spela_{kap_nr}"):
                    st.session_state.aktivt_kapitel = kap_nr
                    st.session_state.uppdrag_lista = []
                    st.session_state.aktuellt_index = 0
                    st.session_state.genomforda_svar = []
                    st.rerun()
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                if st.button("Starta nivå 🚀", key=f"starta_{kap_nr}", type="primary"):
                    st.session_state.aktivt_kapitel = kap_nr
                    st.session_state.uppdrag_lista = []
                    st.session_state.aktuellt_index = 0
                    st.session_state.genomforda_svar = []
                    st.rerun()

# ---------------------------------------------------------------------
# VY 2: SPELA ETT KAPITEL / EN DEL
# ---------------------------------------------------------------------
else:
    nuvarande_kap = st.session_state.aktivt_kapitel
    st.header(f"🎯 Utmaning: Del / Kapitel {nuvarande_kap}")

    if not st.session_state.uppdrag_lista:
        st.write("Läs texten och välj hur du vill skicka in underlaget till Läsmästaren:")
        
        val = st.radio(
            "Välj inmatningssätt:",
            [
                "📸 Ta ett foto med kameran",
                "📄 Ladda upp en PDF-fil",
                "🖼️ Ladda upp en bildfil",
                "✍️ Skriv eller klistra in text"
            ]
        )
        
        innehall_delar = []

        if val == "📸 Ta ett foto med kameran":
            foto = st.camera_input("Rikta kameran mot boksidan eller häftet")
            if foto:
                raw_img = Image.open(foto).convert("RGB")
                raw_img.thumbnail((1200, 1200))
                st.image(raw_img, caption="Ditt tagna foto", width=300)
                innehall_delar.append(raw_img)

        elif val == "📄 Ladda upp en PDF-fil":
            pdf_fil = st.file_uploader("Välj en PDF-fil från datorn eller plattan", type=["pdf"])
            if pdf_fil:
                st.success(f"PDF laddad: {pdf_fil.name}")
                pdf_bytes = pdf_fil.read()
                innehall_delar.append(
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                )

        elif val == "🖼️ Ladda upp en bildfil":
            bild_fil = st.file_uploader("Välj en bild (t.ex. foto på häfte)", type=["jpg", "jpeg", "png"])
            if bild_fil:
                raw_img = Image.open(bild_fil).convert("RGB")
                raw_img.thumbnail((1200, 1200))
                st.image(raw_img, caption="Uppladdad bild", width=300)
                innehall_delar.append(raw_img)

        else:
            text_data = st.text_area("Klistra in några rader eller ett stycke från texten:", height=150)
            if text_data and len(text_data.strip()) >= 15:
                innehall_delar.append(text_data)

        kol_start, kol_avbryt = st.columns(2)
        with kol_start:
            if st.button("Lås upp uppdragen ✨", type="primary"):
                if not innehall_delar:
                    st.warning("Du behöver lägga till text, ladda upp en fil eller ta ett foto först!")
                else:
                    with st.spinner("Läsmästaren läser underlaget och skapar 6 nya uppdrag..."):
                        prompt = f"""
                        Du är en svensklärare för årskurs 4 och 5. Eleven arbetar med del/kapitel {nuvarande_kap}.
                        Läs det bifogade underlaget noggrant.
                        Skapa exakt 6 läsförståelsefrågor anpassade efter Lgr22:
                        - Fråga 1 till 3: LÄTT (faktafrågor på raderna)
                        - Fråga 4 till 5: MEDEL (inferensfrågor mellan raderna)
                        - Fråga 6: SVÅR (tolkning eller reflektion bortom raderna)

                        Du måste svara som en strikt JSON-lista:
                        [
                          {{"nummer": 1, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 2, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 3, "niva": "Lätt", "fraga": "..."}},
                          {{"nummer": 4, "niva": "Medel", "fraga": "..."}},
                          {{"nummer": 5, "niva": "Medel", "fraga": "..."}},
                          {{"nummer": 6, "niva": "Svår", "fraga": "..."}}
                        ]
                        """
                        contents = [prompt] + innehall_delar

                        try:
                            respons = anropa_gemini_med_fallback(
                                client=client,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json"
                                )
                            )
                            
                            svar_text = respons.text.strip()
                            match = re.search(r"\[.*\]", svar_text, re.DOTALL)
                            json_str = match.group(0) if match else svar_text

                            st.session_state.uppdrag_lista = json.loads(json_str)
                            st.session_state.aktuellt_index = 0
                            st.session_state.genomforda_svar = []
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

        # -------------------------------------------------------------
        # RESULTAT- OCH NEDLADDNINGSSKÄRM (Alla 6 frågor klara)
        # -------------------------------------------------------------
        if idx >= total:
            st.balloons()
            st.success(f"🏆 HURRA! Du har klarat alla uppdrag i Del {nuvarande_kap}!")
            
            if nuvarande_kap not in elev_profil["klarade_kapitel"]:
                elev_profil["klarade_kapitel"].append(nuvarande_kap)
                framsteg_db[profil_nyckel] = elev_profil
                spara_framsteg(framsteg_db)

            st.write("Ditt framsteg har sparats på spelkartan! Nu kan du ladda ner din läsrapport och lämna in till läraren.")

            # Sammanställ rapporttexten för nedladdning
            idag = datetime.now().strftime("%Y-%m-%d %H:%M")
            rapport_rader = [
                "==================================================",
                "        📖 LÄSRAPPORT - LÄSMÄSTAREN 📖",
                "==================================================",
                f"Elev: {elev_namn.title()}",
                f"Bok / Häfte: {bok_titel.title()}",
                f"Kapitel / Del: {nuvarande_kap}",
                f"Datum & tid: {idag}",
                "Status: Alla 6 uppdrag genomförda och rättade",
                "==================================================\n"
            ]

            for post in st.session_state.genomforda_svar:
                rapport_rader.append(f"[UPPDRAG {post['nummer']} - NIVÅ: {post['niva'].upper()}]")
                rapport_rader.append(f"Fråga: {post['fraga']}")
                rapport_rader.append(f"Elevens svar:\n{post['svar']}")
                rapport_rader.append(f"Läsmästarens respons:\n{post['feedback']}")
                rapport_rader.append("-" * 50 + "\n")

            komplett_rapport = "\n".join(rapport_rader)

            # Ladda ner-knapp
            filnamn = f"Lasrapport_{elev_namn}_kap_{nuvarande_kap}.txt"
            st.download_button(
                label="📥 Ladda ner min läsrapport (Textfil)",
                data=komplett_rapport,
                file_name=filnamn,
                mime="text/plain",
                type="primary"
            )

            st.divider()
            if st.button("Gå tillbaka till kartan 🗺️"):
                st.session_state.aktivt_kapitel = None
                st.session_state.uppdrag_lista = []
                st.session_state.senaste_feedback = None
                st.session_state.genomforda_svar = []
                st.rerun()

        # -------------------------------------------------------------
        # PÅGÅENDE UPPDRAG (Fråga 1 till 6)
        # -------------------------------------------------------------
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
                        - Beröm alltid försöket.
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
                            st.session_state.senaste_feedback = f"Kunde inte nå servern: {e}"

            # När feedback finns: spara i loggen och visa knapp för nästa fråga
            if st.session_state.senaste_feedback:
                st.divider()
                st.markdown(st.session_state.senaste_feedback)
                
                if st.button("Gå till nästa uppdrag ➡️", type="primary"):
                    # Spara i svarsloggen innan vi går vidare
                    st.session_state.genomforda_svar.append({
                        "nummer": uppdrag["nummer"],
                        "niva": uppdrag["niva"],
                        "fraga": uppdrag["fraga"],
                        "svar": elev_svar,
                        "feedback": st.session_state.senaste_feedback
                    })
                    st.session_state.aktuellt_index += 1
                    st.session_state.senaste_feedback = None
                    st.rerun()

            st.divider()
            if st.button("⬅️ Avbryt och gå till kartan"):
                st.session_state.aktivt_kapitel = None
                st.session_state.uppdrag_lista = []
                st.session_state.senaste_feedback = None
                st.session_state.genomforda_svar = []
                st.rerun()