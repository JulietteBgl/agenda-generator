import streamlit as st
from dateutil.relativedelta import relativedelta as rd
from datetime import date

from utils.create_calendar import create_calendar_editor, create_visual_calendar, get_start_and_end_date, \
    create_date_dropdown_list
from utils.day_allocation import allocate_days
from utils.tools import (
    load_config, get_working_days,
    schedule_to_dataframe, daterange, schedule_summary
)

# Init session_state
for k, v in {
    "df_schedule": None,
    "df_schedule_simple": None,
    "generated_for": None,
}.items():
    st.session_state.setdefault(k, v)


def reset_planning():
    st.session_state.df_schedule = None
    st.session_state.df_schedule_simple = None
    st.session_state.generated_for = None


st.title("Planning radiologues")

col1, col2 = st.columns(2)
start_dt, end_dt = get_start_and_end_date()
date_options = create_date_dropdown_list(start_dt)

selected_date = st.selectbox(
    "Choix du trimestre",
    options=date_options,
    format_func=lambda d: d.strftime("%d-%m-%Y"),
    key="selected_date",
    on_change=reset_planning
)
selected_date = selected_date.date()
end_date = selected_date + rd(months=3) - rd(days=1)
default_start_date = max(selected_date, date.today())

config = load_config('config/config.yml')

st.markdown("### Configuration des congés")

with st.expander("Ajouter des congés (plages ou dates)", expanded=False):
    # Réinitialise les congés à vide par défaut
    for place_cfg in config.values():
        if place_cfg.get("advanced_split"):
            place_cfg['holidays'] = []

    for place_key, place_cfg in config.items():
        if place_cfg.get("advanced_split"):
            st.markdown(f"**{place_cfg['name']}**")

            col1, col2 = st.columns(2)
            with col1:
                start_vac1 = st.date_input(f"Début congé", value=None, min_value=default_start_date, max_value=end_date, key=f"start_{place_key}_1")
                start_vac2 = st.date_input(f"Début congé", value=None, min_value=default_start_date, max_value=end_date, key=f"start_{place_key}_2")
                start_vac3 = st.date_input(f"Début congé", value=None, min_value=default_start_date, max_value=end_date, key=f"start_{place_key}_3")
            with col2:
                end_vac1 = st.date_input(f"Fin congé", value=None, min_value=start_vac1 if start_vac1 else default_start_date, max_value=end_date, key=f"end_{place_key}_1")
                end_vac2 = st.date_input(f"Fin congé", value=None, min_value=start_vac2 if start_vac2 else default_start_date, max_value=end_date, key=f"end_{place_key}_2")
                end_vac3 = st.date_input(f"Fin congé", value=None, min_value=start_vac2 if start_vac3 else default_start_date, max_value=end_date, key=f"end_{place_key}_3")

            for start_vac, end_vac in zip([start_vac1, start_vac2, start_vac3], [end_vac1, end_vac2, end_vac3]):
                if start_vac and end_vac:
                    days = [str(d) for d in daterange(start_vac, end_vac)]
                    place_cfg.setdefault('holidays', []).extend(days)

            manual_days = st.text_input(
                f"Autres jours (AAAA-MM-JJ séparés par ,)",
                value=", ".join(place_cfg.get("holidays", [])),
                key=f"manual_days_{place_key}"
            )
            place_cfg['holidays'] = list(set([d.strip() for d in manual_days.split(",") if d.strip()]))

for key in ["df_schedule", "df_schedule_simple"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.button("Générer le planning"):
    if selected_date > end_date:
        st.error("La date de début doit être avant la date de fin.")
    else:
        working_days, public_holidays = get_working_days(selected_date, end_date)

        schedule_full = allocate_days(config, working_days)

        st.session_state.df_schedule = schedule_to_dataframe(schedule_full)

        st.session_state.generated_for = st.session_state.selected_date

        st.success(f"Planning généré pour {len(working_days)} jours ouvrés.")
        if public_holidays:
            st.info(f"{len(public_holidays)} jour(s) férié(s) ignoré(s) : " + ", ".join(
                [f"{d.strftime('%d/%m')} ({n})" for d, n in public_holidays]
            ))

# On n'affiche les plannings que si la date actuelle == celle pour laquelle on a généré le planning.
show_tables = (
        st.session_state.generated_for is not None
        and st.session_state.generated_for == st.session_state.selected_date
)

if show_tables and st.session_state.df_schedule is not None:

    st.markdown("## Vue complète : lieu + médecin si applicable")
    tab1_complete, tab2_complete = st.tabs(["📊 Tableau", "📅 Vue visuelle"])

    with tab1_complete:
        edited_full = create_calendar_editor( # est-ce que je peux supprimer edited_full? pas utilisé
            source=st.session_state.df_schedule,
            excel_name="planning_detaille",
        )
        st.session_state.df_schedule = edited_full

    with tab2_complete:
        create_visual_calendar(
            source=st.session_state.df_schedule,
        )

    st.markdown("## Vue simplifiée : lieu uniquement")
    tab1_simple, tab2_simple = st.tabs(["📊 Tableau", "📅 Vue visuelle"])

    with tab1_simple:
        create_calendar_editor(
            source=st.session_state.df_schedule,
            excel_name="planning_simple",
            simplified=True
        )

        st.markdown("### Total")
        df = schedule_summary(st.session_state.df_schedule)
        st.dataframe(df)

    with tab2_simple:
        create_visual_calendar(
            source=st.session_state.df_schedule,
            simplified=True
        )

        st.markdown("### Total")
        df = schedule_summary(st.session_state.df_schedule)
        st.dataframe(df)
