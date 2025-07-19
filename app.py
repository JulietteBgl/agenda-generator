# app.py
import streamlit as st
import datetime
from utils.export_agenda import to_excel
from utils.tools import (
    load_config, get_working_days, allocate_days,
    schedule_to_dataframe, daterange
)

st.title("Planning radiologues")

col1, col2 = st.columns(2)
start_date = col1.date_input("Date de début", datetime.date.today())
end_date = col2.date_input("Date de fin", datetime.date.today() + datetime.timedelta(days=30))

config = load_config('config/config.yml')

st.markdown("### Configuration des congés")

with st.expander("Ajouter des congés (plages ou dates)", expanded=False):
    # Réinitialise les congés à vide par défaut
    for place_cfg in config.values():
        if place_cfg.get("advanced_split"):
            for person_cfg in place_cfg['people'].values():
                person_cfg['holidays'] = []
    for place_key, place_cfg in config.items():
        if place_cfg.get("advanced_split"):
            st.markdown(f"**{place_cfg['name']}**")
            for person, person_cfg in place_cfg['people'].items():
                col1, col2 = st.columns(2)
                with col1:
                    start_vac = st.date_input(f"Début congé - {person}", value=None, key=f"start_{place_key}_{person}")
                with col2:
                    end_vac = st.date_input(f"Fin congé - {person}", value=None, key=f"end_{place_key}_{person}")
                if start_vac and end_vac:
                    days = [str(d) for d in daterange(start_vac, end_vac)]
                    person_cfg.setdefault('holidays', []).extend(days)
                manual_days = st.text_input(
                    f"Autres jours (AAAA-MM-JJ séparés par ,) pour {person}",
                    value=", ".join(person_cfg.get("holidays", [])),
                    key=f"manual_days_{place_key}_{person}"
                )
                person_cfg['holidays'] = list(set([d.strip() for d in manual_days.split(",") if d.strip()]))

if 'df_schedule' not in st.session_state:
    st.session_state.df_schedule = None
    st.session_state.df_schedule_simple = None

if st.button("Générer le planning"):
    if start_date > end_date:
        st.error("La date de début doit être avant la date de fin.")
    else:
        working_days, public_holidays = get_working_days(start_date, end_date)

        schedule_full = allocate_days(config, working_days, full=True)
        schedule_simple = allocate_days(config, working_days, full=False)

        st.session_state.df_schedule = schedule_to_dataframe(schedule_full)
        st.session_state.df_schedule_simple = schedule_to_dataframe(schedule_simple)

        st.success(f"Planning généré pour {len(working_days)} jours ouvrés.")
        if public_holidays:
            st.info(f"{len(public_holidays)} jour(s) férié(s) ignoré(s) : " + ", ".join(
                [f"{d.strftime('%d/%m')} ({n})" for d, n in public_holidays]
            ))

if st.session_state.df_schedule is not None:
    st.subheader("Planning détaillé (lieu + médecin si applicable)")
    edited_df = st.data_editor(
        st.session_state.df_schedule,
        column_config={"Date": st.column_config.TextColumn(disabled=True)},
        use_container_width=True,
        num_rows="dynamic",
        key="planning_editor_full"
    )
    st.session_state.df_schedule = edited_df

    st.download_button("Télécharger Excel", data=to_excel(edited_df), file_name="planning_detaille.xlsx")

if st.session_state.df_schedule_simple is not None:
    st.subheader("Planning simplifié (par lieu uniquement)")
    edited_simple_df = st.data_editor(
        st.session_state.df_schedule_simple,
        column_config={"Date": st.column_config.TextColumn(disabled=True)},
        use_container_width=True,
        num_rows="dynamic",
        key="planning_editor_simple"
    )
    st.session_state.df_schedule_simple = edited_simple_df

    st.download_button("Télécharger Excel (simplifié)", data=to_excel(edited_simple_df), file_name="planning_simple.xlsx")
    st.download_button("Télécharger CSV (simplifié)", data=to_csv(edited_simple_df), file_name="planning_simple.csv")
