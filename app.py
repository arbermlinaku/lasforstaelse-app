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
st.set_page_config(page_title="Läsmästaren", page_icon="📖", layout="centered")

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

# 3. Sessionsvariabler
if "arbetslage" not in st.session_state:
    st.session_state.arbetslage = None  # "hafnte" eller "bok"
if "aktivt_kapitel" not in st.session_state:
    st.session_state.aktivt_kapitel = None
if "uppdrag_lista" not in st.session_state:
    st.session_state.uppdrag_lista = []
if "aktuellt_index" not in st.session_state:
    st.session_state.aktuellt_index = 0
if "senaste_feedback" not in st.session_state:
    st.session_state.senaste_feedback = None
if "genomforda_svar" not in st.session_state:
    st.session_state.genomforda_svar = []
if "aktiv_titel" not in st.session_state:
    st.session_state.aktiv_titel = ""
if "aktiv_elev" not in st.session_state:
    st.session_state.aktiv_elev = ""

def nollstall_uppdrag():
    st.session_state.uppdrag_lista = []
    st.session_state.aktuellt_index = 0
    st.session_state.senaste_feedback = None
    st.session_state.genomforda_svar = []

# =====================================================================
# STARTSIDA: VÄLJ ARBETSSÄTT (Direkt i mitten av skärmen)
# =====================================================================
if st.session_state.arbetslage is None and not st.session_state.uppdrag_lista:
    st.title("📖 Läsmästaren")
    st.write("Välkommen! Vad vill du arbeta med idag?")
    st.divider()

    val = st.radio(
        "Välj vad du ska läsa:",
        [
            "📑 Häfte, stencil eller PDF (Snabbstart)",
            "📚 Bok med kapitel (Äventyrskarta med sparade nivåer)"
        ]
    )

    st.write("")
    if val == "📑 Häfte, stencil eller PDF (Snabbstart)":
        st.subheader("📑 Arbeta med ett häfte eller en PDF")
        namn = st.text_input("Ditt förnamn:", key="start_namn_hafte")
        titel = st.text_input("Vad heter häftet eller texten? (t.ex. Faktatext om rymden):", key="start_titel_hafte")
        
        if st.button("Gå vidare till häftet 🚀", type="primary"):
            if not namn.strip() or not titel.strip():
                st.warning("Skriv in ditt namn och vad häftet heter för att fortsätta!")
            else:
                st.session_state.aktiv_elev = namn.strip().title()
                st.session_state.aktiv_titel = titel.strip().title()
                st.session_state.arbetslage = "hafte"
                st.session_state.aktivt_kapitel = 1
                nollstall_uppdrag()
                st.rerun()

    else:
        st.subheader("📚 Bokäventyret: Kapitelkarta")
        st.write("Här sparas dina framsteg så att du kan fortsätta läsa boken nästa lektion.")
        namn = st.text_input("Ditt namn eller alias:", key="start_namn_bok")
        bok = st.text_input("Bokens titel:", key="start_titel_bok")
        
        if st.button("Öppna min kapitelkarta 🗺️", type="primary"):
            if not namn.strip() or not bok.strip():
                st.warning("Skriv in ditt namn och bokens titel!")
            else:
                st.session_state.aktiv_elev = namn.strip().title()
                st.session_state.aktiv_titel = bok.strip().title()
                st.session_state.arbetslage = "bok"
                nollstall_uppdrag()
                st.rerun()

# =====================================================================
# LÄGE: BOKENS KAPITELKARTA
# =====================================================================
elif st.session_state.arbetslage == "bok" and st.session_state.aktivt_kapitel is None:
    elev_namn = st.session_state.aktiv_elev
    bok_titel = st.session_state.aktiv_titel
    profil_nyckel = f"{elev_namn.lower()}###{bok_titel.lower()}"
    
    framsteg_db = ladda_framsteg()
    if profil_nyckel not in framsteg_db:
        framsteg_db[profil_nyckel] = {"namn": elev_namn, "bok": bok_titel, "klarade_kapitel": []}
        spara_framsteg(framsteg_db)
        
    klarade = set(framsteg_db[profil_nyckel].get("klarade_kapitel", []))

    st.title("🎮 Läsmästaren: Bokäventyret")
    st.subheader(f"🗺️ Kapitelkarta: *{bok_titel}*")
    st.write(f"Inloggad: **{elev_namn}** | Avklarade kapitel: **{len(klarade)} st**")
    
    if st.button("⬅️ Byt bok eller gå till startsidan"):
        st.session_state.arbetslage = None
        st.rerun()

    st.divider()
    antal_kapitel = max(10, max(klarade) + 2 if klarade else 5)

    for kap_nr in range(1, antal_kapitel + 1):
        kol1, kol2, kol3 = st.columns([1, 3, 2])
        with kol1:
            st.write("⭐ 🏆" if kap_nr in klarade else ("🔓 🎯" if (kap_nr == 1 or (kap_nr - 1) in klarade) else "🔒"))
        with kol2:
            st.write(f"**Kapitel {kap_nr}**" + (" (Klarat!)" if kap_nr in klarade else (" – Redo!" if (kap_nr == 1 or (kap_nr - 1) in klarade) else " – Låst")))
        with kol3:
            if kap_nr in klarade:
                if st.button("Spela igen 🔁", key=f"spela_{kap_nr}"):
                    st.session_state.aktivt_kapitel = kap_nr
                    nollstall_uppdrag()
                    st.rerun()
            elif kap_nr == 1 or (kap_nr - 1) in klarade:
                if st.button("Starta nivå 🚀", key=f"starta_{kap_nr}", type="primary"):
                    st.session_state.aktivt_kapitel = kap_nr
                    nollstall_uppdrag()
                    st.rerun()

# =====================================================================
# INMATNING & UPPDRAG (Gemensam för både Häfte och Bok)
# =====================================================================
else:
    arbetar_med_hafte = (st.session_state.arbetslage == "hafte")
    rubrik = f"📑 Häfte: {st.session_state.aktiv_titel}" if arbetar_med_hafte else f"📚 {st.session_state.aktiv_titel} - Kapitel {st.session_state.aktivt_kapitel}"
    
    st.title(rubrik)
    st.caption(f"Elev: {st.session_state.aktiv_elev}")

    # Steg 1: Mata in underlag (om frågor inte skapats än)
    if not st.session_state.uppdrag_lista:
        st.write("Välj hur du vill lägga in underlaget från ditt häfte eller din bok:")

        val_metod = st.radio(
            "Välj metod:",
            [
                "📸 Fota med kameran (häfte/boksida)",
                "📄 Ladda upp en PDF-fil",
                "🖼️ Ladda upp en sparad bild (foto)",
                "✍️ Klistra in text"
            ],
            horizontal=False
        )

        innehall_delar = []

        if val_metod == "📸 Fota med kameran (häfte/boksida)":
            foto = st.camera_input("Rikta kameran mot texten och ta ett foto")
            if foto:
                raw_img = Image.open(foto).convert("RGB")
                raw_img.thumbnail((1200, 1200))
                st.image(raw_img, caption="Ditt tagna foto", width=300)
                innehall_delar.append(raw_img)

        elif val_metod == "📄 Ladda upp en PDF-fil":
            pdf_fil = st.file_uploader("Välj en PDF från din dator eller iPad", type=["pdf"])
            if pdf_fil:
                st.success(f"PDF laddad: {pdf_fil.name}")
                innehall_delar.append(
                    types.Part.from_bytes(data=pdf_fil.read(), mime_type="application/pdf")
                )

        elif val_metod == "🖼️ Ladda upp en sparad bild (foto)":
            bild_fil = st.file_uploader("Välj bildfil", type=["jpg", "jpeg", "png"])
            if bild_fil:
                raw_img = Image.open(bild_fil).convert("RGB")
                raw_img.thumbnail((1200, 1200))
                st.image(raw_img, caption="Uppladdat foto", width=300)
                innehall_delar.append(raw_img)

        else:
            text_data = st.text_area("Klistra in några rader eller ett stycke:", height=150)
            if text_data and len(text_data.strip()) >= 15:
                innehall_delar.append(text_data)

        kol1, kol2 = st.columns(2)
        with kol1:
            if st.button("Skapa mina läsuppdrag ✨", type="primary"):
                if not innehall_delar:
                    st.warning("Ta en bild, ladda upp en fil eller klistra in text först!")
                else:
                    with st.spinner("Läsmästaren läser texten och skapar 6 anpassade frågor..."):
                        prompt = f"""
                        Du är en uppmuntrande svensklärare för årskurs 4 och 5.
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
                        try:
                            respons = anropa_gemini_med_fallback(
                                client=client,
                                contents=[prompt] + innehall_delar,
                                config=types.GenerateContentConfig(response_mime_type="application/json")
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

        with kol2:
            if st.button("⬅️ Avbryt och gå tillbaka"):
                if arbetar_med_hafte:
                    st.session_state.arbetslage = None
                else:
                    st.session_state.aktivt_kapitel = None
                nollstall_uppdrag()
                st.rerun()

    # Steg 2: Eleven gör uppdrag 1 till 6
    else:
        idx = st.session_state.aktuellt_index
        total = len(st.session_state.uppdrag_lista)

        # Klart! Visa rapport och nedladdning
        if idx >= total:
            st.balloons()
            st.success("🎉 HURRA! Du har klarat alla 6 uppdrag!")

            if not arbetar_med_hafte:
                framsteg_db = ladda_framsteg()
                profil_nyckel = f"{st.session_state.aktiv_elev.lower()}###{st.session_state.aktiv_titel.lower()}"
                if profil_nyckel in framsteg_db:
                    if st.session_state.aktivt_kapitel not in framsteg_db[profil_nyckel]["klarade_kapitel"]:
                        framsteg_db[profil_nyckel]["klarade_kapitel"].append(st.session_state.aktivt_kapitel)
                        spara_framsteg(framsteg_db)
                st.info("Ditt framsteg har sparats på kapitelkartan! ⭐")

            # Skapa rapporten
            nu = datetime.now().strftime("%Y-%m-%d %H:%M")
            rapport = [
                "=" * 50,
                "        📖 LÄSRAPPORT - LÄSMÄSTAREN 📖",
                "=" * 50,
                f"Elev: {st.session_state.aktiv_elev}",
                f"Text / Titel: {st.session_state.aktiv_titel}",
                f"Del / Kapitel: {st.session_state.aktivt_kapitel if not arbetar_med_hafte else 'Enskilt häfte'}",
                f"Tidpunkt: {nu}",
                "=" * 50 + "\n"
            ]

            for post in st.session_state.genomforda_svar:
                rapport.append(f"[UPPDRAG {post['nummer']} - {post['niva'].upper()}]")
                rapport.append(f"Fråga: {post['fraga']}")
                rapport.append(f"Elevens svar:\n{post['svar']}")
                rapport.append(f"Läsmästarens respons:\n{post['feedback']}")
                rapport.append("-" * 50 + "\n")

            st.download_button(
                label="📥 Ladda ner min läsrapport (Textfil)",
                data="\n".join(rapport),
                file_name=f"Lasrapport_{st.session_state.aktiv_elev}.txt",
                mime="text/plain",
                type="primary"
            )

            st.write("")
            if st.button("Klar! Gå till startsidan 🏠"):
                st.session_state.arbetslage = None
                st.session_state.aktivt_kapitel = None
                nollstall_uppdrag()
                st.rerun()

        # Pågående fråga
        else:
            uppdrag = st.session_state.uppdrag_lista[idx]
            st.progress(idx / total)

            farg = "🟢" if uppdrag["niva"] == "Lätt" else ("🟡" if uppdrag["niva"] == "Medel" else "🔴")
            st.subheader(f"{farg} Uppdrag {uppdrag['nummer']} av {total}: Nivå {uppdrag['niva']}")
            st.info(f"**Fråga:** {uppdrag['fraga']}")

            elev_svar = st.text_area("Ditt svar:", key=f"svar_{idx}", height=100)

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
                            bedomning = anropa_gemini_med_fallback(client=client, contents=[prompt_rattning])
                            st.session_state.senaste_feedback = bedomning.text
                        except Exception as e:
                            st.session_state.senaste_feedback = f"Kunde inte nå servern: {e}"

            if st.session_state.senaste_feedback:
                st.divider()
                st.markdown(st.session_state.senaste_feedback)
                if st.button("Gå till nästa uppdrag ➡️", type="primary"):
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
            if st.button("⬅️ Avbryt uppdraget"):
                if arbetar_med_hafte:
                    st.session_state.arbetslage = None
                else:
                    st.session_state.aktivt_kapitel = None
                nollstall_uppdrag()
                st.rerun()