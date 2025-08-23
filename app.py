import streamlit as st
from dateutil.relativedelta import relativedelta as rd

from utils.create_calendar import create_calendar_editor, create_visual_calendar, get_start_and_end_date, \
    create_date_dropdown_list
from utils.day_allocation import allocate_days
from utils.tools import (
    load_config, get_working_days,
    schedule_to_dataframe, daterange
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

end_date = selected_date + rd(months=3) - rd(days=1)

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
                start_vac = st.date_input(f"Début congé", value=None, key=f"start_{place_key}")
            with col2:
                end_vac = st.date_input(f"Fin congé", value=None, key=f"end_{place_key}")

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
        schedule_simple = schedule_full.copy()
        for day, assignments in schedule_simple.items():
            schedule_simple[day] = [
                "Majo" if "majo" in val.lower() else val
                for val in assignments
            ]

        st.session_state.df_schedule = schedule_to_dataframe(schedule_full)
        st.session_state.df_schedule_simple = schedule_to_dataframe(schedule_simple)

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
    create_calendar_editor(
        source=st.session_state.df_schedule,
        title="Planning détaillé (lieu + médecin si applicable)",
        excel_name="planning_detaille"
    )

    create_visual_calendar(
        source=st.session_state.df_schedule,
        title="Vue hebdomadaire visuelle"
    )

if show_tables and st.session_state.df_schedule_simple is not None:
    create_calendar_editor(
        source=st.session_state.df_schedule_simple,
        title="Planning simplifié (par lieu uniquement)",
        excel_name="planning_simple"
    )

    create_visual_calendar(
        source=st.session_state.df_schedule_simple,
        title="Vue hebdomadaire visuelle"
    )