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
    st.session_state.arbetslage = None
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
# STARTSIDA: VÄLJ ARBETSSÄTT
# =====================================================================
if st.session_state.arbetslage is None and not st.session_state.uppdrag_lista:
    st.title("📖 Läsmästaren")
    st.write("Välkommen! Vad vill du arbeta med idag?")
    st.divider()

    val = st.radio(
        "Välj vad du ska läsa:",
        [
            "📚 Bok med kapitel (Frågor skapas automatiskt på hela kapitlet)",
            "📑 Häfte, stencil eller PDF (Ladda upp fil eller fota)"
        ]
    )

    st.write("")
    if val.startswith("📚"):
        st.subheader("📚 Bokäventyret: Kapitelkarta")
        st.write("Du behöver inte fota boken! Läsmästaren känner till handlingen i hela kapitlet.")
        namn = st.text_input("Ditt förnamn eller alias:", key="start_namn_bok")
        bok = st.text_input("Bokens titel (och gärna författare):", key="start_titel_bok", placeholder="t.ex. Bröderna Lejonhjärta av Astrid Lindgren")
        
        if st.button("Öppna min kapitelkarta 🗺️", type="primary"):
            if not namn.strip() or not bok.strip():
                st.warning("Skriv in ditt namn och bokens titel!")
            else:
                st.session_state.aktiv_elev = namn.strip().title()
                st.session_state.aktiv_titel = bok.strip().title()
                st.session_state.arbetslage = "bok"
                nollstall_uppdrag()
                st.rerun()

    else:
        st.subheader("📑 Häfte, stencil eller PDF")
        namn = st.text_input("Ditt förnamn:", key="start_namn_hafte")
        titel = st.text_input("Vad heter texten/häftet?:", key="start_titel_hafte", placeholder="t.ex. Faktatext om Medeltiden")
        
        if st.button("Gå vidare till häftet 🚀", type="primary"):
            if not namn.strip() or not titel.strip():
                st.warning("Fyll i ditt namn och vad häftet heter!")
            else:
                st.session_state.aktiv_elev = namn.strip().title()
                st.session_state.aktiv_titel = titel.strip().title()
                st.session_state.arbetslage = "hafte"
                st.session_state.aktivt_kapitel = 1
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
    st.write(f"Inloggad: **{elev_namn}** | Klarade kapitel: **{len(klarade)} st**")
    
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
# INMATNING & UPPDRAGSHANTERING
# =====================================================================
else:
    arbetar_med_hafte = (st.session_state.arbetslage == "hafte")
    rubrik = f"📑 Häfte: {st.session_state.aktiv_titel}" if arbetar_med_hafte else f"📚 {st.session_state.aktiv_titel} – Kapitel {st.session_state.aktivt_kapitel}"
    
    st.title(rubrik)
    st.caption(f"Elev: {st.session_state.aktiv_elev}")

    if not st.session_state.uppdrag_lista:
        innehall_delar = []
        
        # --- BOK: SKAPA DIREKT UTAN FOTO ---
        if not arbetar_med_hafte:
            st.info(f"Du har läst **Kapitel {st.session_state.aktivt_kapitel}** i boken **{st.session_state.aktiv_titel}**.")
            st.write("Läsmästaren skapar nu uppdrag som täcker handlingen i hela detta kapitel.")
            
            extra_not = st.text_input(
                "Valfritt: Skriv 1 kort mening om vad som hände (om boken är helt ny):",
                placeholder="T.ex: Jonatan berättar om landet Nangijala och huset börjar brinna."
            )
            if extra_not.strip():
                innehall_delar.append(f"Elevens sammanfattning av kapitlet: {extra_not}")

            kol1, kol2 = st.columns(2)
            with kol1:
                if st.button("Skapa uppdrag för hela kapitlet ✨", type="primary"):
                    with st.spinner(f"Läsmästaren läser in kapitel {st.session_state.aktivt_kapitel} och skapar frågorna..."):
                        prompt = f"""
                        Du är en uppmuntrande svensklärare för årskurs 4 och 5.
                        Bok: '{st.session_state.aktiv_titel}'
                        Kapitel: {st.session_state.aktivt_kapitel}

                        Skapa exakt 6 uppdrag anpassade efter Lgr22 som täcker handlingen i HELA kapitel {st.session_state.aktivt_kapitel}:

                        - Uppdrag 1: LÄTT ('på raderna'). Typ: 'flerval_grupp'.
                          Titel: 'Faktaquiz del 1'.
                          Ska innehålla exakt 4 frågor. Varje fråga ska ha exakt 3 svarsalternativ, 'ratt_svar' och en 'ledtrad'.
                        - Uppdrag 2: LÄTT ('på raderna'). Typ: 'flerval_grupp'.
                          Titel: 'Faktaquiz del 2'.
                          Ska innehålla exakt 4 frågor. Varje fråga ska ha exakt 3 svarsalternativ, 'ratt_svar' och en 'ledtrad'.
                        - Uppdrag 3: LÄTT ('på raderna'). Typ: 'fritext' (1 enkel faktafråga där eleven formulerar en kort text med egna ord).
                        - Uppdrag 4: MEDEL ('mellan raderna', känslor, orsak, varför). Typ: 'fritext'.
                        - Uppdrag 5: MEDEL ('mellan raderna', samband, motiv). Typ: 'fritext'.
                        - Uppdrag 6: SVÅR ('bortom raderna', reflektion, tolkning eller budskap). Typ: 'fritext'.

                        Svara som en strikt JSON-lista:
                        [
                          {{
                            "nummer": 1,
                            "niva": "Lätt",
                            "typ": "flerval_grupp",
                            "titel": "Faktaquiz del 1",
                            "fragor": [
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt A", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt B", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt C", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt A", "ledtrad": "..."}}
                            ]
                          }},
                          {{
                            "nummer": 2,
                            "niva": "Lätt",
                            "typ": "flerval_grupp",
                            "titel": "Faktaquiz del 2",
                            "fragor": [
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt A", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt B", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt C", "ledtrad": "..."}},
                              {{"fraga": "...", "alternativ": ["Alt A", "Alt B", "Alt C"], "ratt_svar": "Alt A", "ledtrad": "..."}}
                            ]
                          }},
                          {{
                            "nummer": 3,
                            "niva": "Lätt",
                            "typ": "fritext",
                            "fraga": "...",
                            "ledtrad": "..."
                          }},
                          {{
                            "nummer": 4,
                            "niva": "Medel",
                            "typ": "fritext",
                            "fraga": "...",
                            "ledtrad": "..."
                          }},
                          {{
                            "nummer": 5,
                            "niva": "Medel",
                            "typ": "fritext",
                            "fraga": "...",
                            "ledtrad": "..."
                          }},
                          {{
                            "nummer": 6,
                            "niva": "Svår",
                            "typ": "fritext",
                            "fraga": "...",
                            "ledtrad": "..."
                          }}
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
                if st.button("⬅️ Tillbaka till kartan"):
                    st.session_state.aktivt_kapitel = None
                    nollstall_uppdrag()
                    st.rerun()

        # --- HÄFTE: FOTA ELLER LADDA UPP PDF ---
        else:
            st.write("Välj hur du vill lägga in underlaget från häftet:")
            val_metod = st.radio(
                "Välj metod:",
                ["📄 Ladda upp en PDF-fil", "📸 Fota med kameran", "🖼️ Ladda upp sparad bild", "✍️ Klistra in text"]
            )

            if val_metod == "📄 Ladda upp en PDF-fil":
                pdf_fil = st.file_uploader("Välj en PDF från din dator eller iPad", type=["pdf"])
                if pdf_fil:
                    st.success(f"PDF laddad: {pdf_fil.name}")
                    innehall_delar.append(types.Part.from_bytes(data=pdf_fil.read(), mime_type="application/pdf"))

            elif val_metod == "📸 Fota med kameran":
                foto = st.camera_input("Rikta kameran mot häftet")
                if foto:
                    raw_img = Image.open(foto).convert("RGB")
                    raw_img.thumbnail((1200, 1200))
                    st.image(raw_img, caption="Ditt foto", width=300)
                    innehall_delar.append(raw_img)

            elif val_metod == "🖼️ Ladda upp sparad bild":
                bild_fil = st.file_uploader("Välj bildfil", type=["jpg", "jpeg", "png"])
                if bild_fil:
                    raw_img = Image.open(bild_fil).convert("RGB")
                    raw_img.thumbnail((1200, 1200))
                    st.image(raw_img, caption="Uppladdad bild", width=300)
                    innehall_delar.append(raw_img)

            else:
                text_data = st.text_area("Klistra in text från häftet:", height=150)
                if text_data and len(text_data.strip()) >= 15:
                    innehall_delar.append(text_data)

            kol1, kol2 = st.columns(2)
            with kol1:
                if st.button("Skapa uppdrag från häftet ✨", type="primary"):
                    if not innehall_delar:
                        st.warning("Lägg till en fil, ta ett foto eller klistra in text först!")
                    else:
                        with st.spinner("Läsmästaren skapar frågor från häftet..."):
                            prompt = """
                            Du är en svensklärare för årskurs 4 och 5. Läs underlaget noggrant.
                            Skapa exakt 6 uppdrag anpassade efter Lgr22:
                            - Uppdrag 1: LÄTT ('på raderna'). Typ: 'flerval_grupp'. Exakt 4 frågor med 3 alternativ vardera.
                            - Uppdrag 2: LÄTT ('på raderna'). Typ: 'flerval_grupp'. Exakt 4 frågor med 3 alternativ vardera.
                            - Uppdrag 3: LÄTT ('på raderna'). Typ: 'fritext' (1 enkel faktafråga).
                            - Uppdrag 4: MEDEL ('mellan raderna'). Typ: 'fritext'.
                            - Uppdrag 5: MEDEL ('mellan raderna'). Typ: 'fritext'.
                            - Uppdrag 6: SVÅR ('bortom raderna'). Typ: 'fritext'.

                            Svara som en strikt JSON-lista med samma format: nummer, niva, typ, titel/fraga, fragor, ledtrad.
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
                    st.session_state.arbetslage = None
                    nollstall_uppdrag()
                    st.rerun()

    # Uppdragshantering (1 till 6)
    else:
        idx = st.session_state.aktuellt_index
        total = len(st.session_state.uppdrag_lista)

        # -------------------------------------------------------------
        # RESULTATSKÄRM: ALLA UPPDRAG KLARA
        # -------------------------------------------------------------
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

            st.write("Bra kämpat! Ladda ner din läsrapport nedan och lämna in till din lärare.")

            nu = datetime.now().strftime("%Y-%m-%d %H:%M")
            rapport = [
                "=" * 55,
                "          📖 ELEVRAPPORT - LÄSMÄSTAREN 📖",
                "=" * 55,
                f"Elev: {st.session_state.aktiv_elev}",
                f"Titel: {st.session_state.aktiv_titel}",
                f"Avsnitt: {'Enskilt häfte' if arbetar_med_hafte else f'Kapitel {st.session_state.aktivt_kapitel}'}",
                f"Datum & tid: {nu}",
                "=" * 55 + "\n"
            ]

            for post in st.session_state.genomforda_svar:
                rapport.append(f"[UPPDRAG {post['nummer']} - {post['niva'].upper()}]")
                rapport.append(f"Uppgift: {post['fraga']}")
                rapport.append(f"Elevens svar:\n{post['svar']}")
                rapport.append(f"Återkoppling:\n{post['feedback']}")
                rapport.append("-" * 55 + "\n")

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

        # -------------------------------------------------------------
        # PÅGÅENDE UPPDRAG
        # -------------------------------------------------------------
        else:
            uppdrag = st.session_state.uppdrag_lista[idx]
            st.progress(idx / total)

            farg = "🟢" if uppdrag["niva"] == "Lätt" else ("🟡" if uppdrag["niva"] == "Medel" else "🔴")
            
            # --- UPPDRAG 1 & 2: 4 FLERVALSFRÅGOR MED 3 ALTERNATIV VAR ---
            if uppdrag.get("typ") == "flerval_grupp":
                st.subheader(f"{farg} Uppdrag {uppdrag['nummer']} av {total}: {uppdrag.get('titel', 'Faktaquiz')} (Nivå Lätt)")
                st.write("Svara på de 4 frågorna nedan (välj 1 av 3 alternativ på varje fråga):")

                sub_fragor = uppdrag.get("fragor", [])
                anvandar_svar = {}

                for i, q in enumerate(sub_fragor):
                    st.markdown(f"**Fråga {i+1}:** {q['fraga']}")
                    val = st.radio(
                        f"Välj svar för fråga {i+1}:",
                        q.get("alternativ", []),
                        index=None,
                        key=f"flerval_{idx}_{i}",
                        label_visibility="collapsed"
                    )
                    anvandar_svar[i] = val
                    st.write("")

                if st.button("Rätta mina 4 svar ✨", key=f"btn_grupp_{idx}"):
                    if any(v is None for v in anvandar_svar.values()):
                        st.warning("Svara på alla 4 frågor innan du rättar!")
                    else:
                        feedback_lista = []
                        samlat_svar_text = []

                        for i, q in enumerate(sub_fragor):
                            givet_svar = anvandar_svar[i]
                            ratt = q.get("ratt_svar", "")
                            if givet_svar.strip().lower() == ratt.strip().lower():
                                rad = f"Fråga {i+1}: ⭐ Rätt! ({ratt})"
                            else:
                                rad = f"Fråga {i+1}: 💡 Du valde '{givet_svar}'. Rätt svar är: '{ratt}'. Ledtråd: {q.get('ledtrad', 'Kika i kapitlet!')}"
                            feedback_lista.append(rad)
                            samlat_svar_text.append(f"F{i+1}: {givet_svar} ({'Rätt' if givet_svar.strip().lower() == ratt.strip().lower() else 'Fel'})")

                        st.session_state.senaste_feedback = "\n\n".join(feedback_lista)
                        st.session_state[f"sparat_svar_{idx}"] = "; ".join(samlat_svar_text)

                if st.session_state.senaste_feedback:
                    st.divider()
                    st.markdown(st.session_state.senaste_feedback)
                    if st.button("Gå till nästa uppdrag ➡️", type="primary", key=f"next_grupp_{idx}"):
                        st.session_state.genomforda_svar.append({
                            "nummer": uppdrag["nummer"],
                            "niva": uppdrag["niva"],
                            "fraga": f"4 faktafrågor med flerval ({uppdrag.get('titel', 'Faktaquiz')})",
                            "svar": st.session_state.get(f"sparat_svar_{idx}", "Besvarat"),
                            "feedback": st.session_state.senaste_feedback
                        })
                        st.session_state.aktuellt_index += 1
                        st.session_state.senaste_feedback = None
                        st.rerun()

            # --- UPPDRAG 3 (LÄTT FRITEXT), 4 & 5 (MEDEL), 6 (SVÅR ANALYS) ---
            else:
                st.subheader(f"{farg} Uppdrag {uppdrag['nummer']} av {total}: Nivå {uppdrag['niva']}")
                st.info(f"**Fråga:** {uppdrag['fraga']}")

                if uppdrag.get("ledtrad"):
                    with st.expander("💡 Behöver du en ledtråd? Klicka här!"):
                        st.write(uppdrag["ledtrad"])

                placeholder_text = "Skriv ett kort svar med egna ord..." if uppdrag["niva"] == "Lätt" else "Skriv vad du tänker på..."
                elev_text = st.text_area(
                    "Skriv ditt svar här:",
                    key=f"text_{idx}",
                    height=100,
                    placeholder=placeholder_text
                )

                if st.button("Lämna in svar 🚀", key=f"btn_fritext_{idx}"):
                    if not elev_text.strip():
                        st.warning("Skriv ett svar innan du lämnar in!")
                    else:
                        with st.spinner("Läsmästaren läser ditt svar..."):
                            prompt_rattning = f"""
                            Du är en varm och uppmuntrande svensklärare för årskurs 4-5.
                            Fråga: {uppdrag['fraga']}
                            Nivå: {uppdrag['niva']}
                            Elevens svar: "{elev_text}"

                            Instruktioner:
                            - Ignorera helt stavfel och särskrivningar.
                            - Om frågan är LÄTT (fakta): Berätta om svaret stämmer och ge beröm.
                            - Om frågan är SVÅR (analys/reflektion): Godkänn alltid elevens försök! Uppmuntra tanken och ge en kort positiv reflektion tillbaka.
                            - Om frågan är MEDEL: Beröm och ge en vänlig kommentar.
                            - Skriv alltid stärkande och barnvänligt (max 3 korta meningar).
                            """
                            try:
                                bedomning = anropa_gemini_med_fallback(client=client, contents=[prompt_rattning])
                                st.session_state.senaste_feedback = bedomning.text
                            except Exception:
                                st.session_state.senaste_feedback = "Fint svarat! Läsmästaren har sparat ditt svar."

                if st.session_state.senaste_feedback:
                    st.divider()
                    st.markdown(st.session_state.senaste_feedback)
                    
                    if st.button("Gå till nästa uppdrag ➡️", type="primary", key=f"next_{idx}"):
                        st.session_state.genomforda_svar.append({
                            "nummer": uppdrag["nummer"],
                            "niva": uppdrag["niva"],
                            "fraga": uppdrag["fraga"],
                            "svar": elev_text,
                            "feedback": st.session_state.senaste_feedback
                        })
                        st.session_state.aktuellt_index += 1
                        st.session_state.senaste_feedback = None
                        st.rerun()

            st.divider()
            if st.button("⬅️ Avbryt"):
                if arbetar_med_hafte:
                    st.session_state.arbetslage = None
                else:
                    st.session_state.aktivt_kapitel = None
                nollstall_uppdrag()
                st.rerun()