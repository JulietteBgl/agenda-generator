import streamlit as st
from dateutil.relativedelta import relativedelta as rd
from datetime import date

from model.schedule_allocator import ScheduleAllocator
from utils.storage.storage_csv import ScheduleStorage
from utils.storage.github_sync import GitHubSync

from utils.create_calendar import create_calendar_editor, create_visual_calendar, get_start_date, \
    create_date_dropdown_list
from utils.tools import (
    load_config, get_working_days,
    schedule_to_dataframe, daterange, schedule_summary
)
import copy
import pandas as pd


# Stockage init
@st.cache_resource
def get_storage():
    return ScheduleStorage()


storage = get_storage()

st.set_page_config(
    page_title="Planning Radiologues",
    page_icon="📅",
    initial_sidebar_state="expanded"
)

# Init session_state
for k, v in {
    "df_schedule": None,
    "df_schedule_simple": None,
    "generated_for": None,
    "holidays_config": {},
}.items():
    st.session_state.setdefault(k, v)


def reset_planning():
    st.session_state.df_schedule = None
    st.session_state.df_schedule_simple = None
    st.session_state.generated_for = None
    st.session_state.holidays_config = {}


st.title("Planning radiologues")

col1, col2 = st.columns(2)
start_dt = get_start_date()
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

# Load config and make a deep copy to avoid modifying the original
config_original = load_config('config/config.yml')
config = copy.deepcopy(config_original)

st.markdown("### Configuration des congés")

with st.expander("Ajouter des congés (plages ou dates)", expanded=False):
    for place_key, place_cfg in config.items():
        if place_cfg.get("advanced_split"):
            if place_key not in st.session_state.holidays_config:
                st.session_state.holidays_config[place_key] = {
                    'holidays': [],
                    'start_vac1': None,
                    'end_vac1': None,
                    'start_vac2': None,
                    'end_vac2': None,
                    'start_vac3': None,
                    'end_vac3': None,
                    'manual_days': ""
                }

    for place_key, place_cfg in config.items():
        if place_cfg.get("advanced_split"):
            st.markdown(f"**{place_cfg['name']}**")

            place_cfg['holidays'] = []

            col1, col2 = st.columns(2)
            with col1:
                start_vac1 = st.date_input(
                    f"Début congé",
                    value=st.session_state.holidays_config[place_key]['start_vac1'],
                    min_value=default_start_date,
                    max_value=end_date,
                    key=f"start_{place_key}_1"
                )
                start_vac2 = st.date_input(
                    f"Début congé",
                    value=st.session_state.holidays_config[place_key]['start_vac2'],
                    min_value=default_start_date,
                    max_value=end_date,
                    key=f"start_{place_key}_2"
                )
                start_vac3 = st.date_input(
                    f"Début congé",
                    value=st.session_state.holidays_config[place_key]['start_vac3'],
                    min_value=default_start_date,
                    max_value=end_date,
                    key=f"start_{place_key}_3"
                )
            with col2:
                end_vac1 = st.date_input(
                    f"Fin congé",
                    value=st.session_state.holidays_config[place_key]['end_vac1'],
                    min_value=start_vac1 if start_vac1 else default_start_date,
                    max_value=end_date,
                    key=f"end_{place_key}_1"
                )
                end_vac2 = st.date_input(
                    f"Fin congé",
                    value=st.session_state.holidays_config[place_key]['end_vac2'],
                    min_value=start_vac2 if start_vac2 else default_start_date,
                    max_value=end_date,
                    key=f"end_{place_key}_2"
                )
                end_vac3 = st.date_input(
                    f"Fin congé",
                    value=st.session_state.holidays_config[place_key]['end_vac3'],
                    min_value=start_vac3 if start_vac3 else default_start_date,
                    max_value=end_date,
                    key=f"end_{place_key}_3"
                )

            # Update session state
            st.session_state.holidays_config[place_key]['start_vac1'] = start_vac1
            st.session_state.holidays_config[place_key]['end_vac1'] = end_vac1
            st.session_state.holidays_config[place_key]['start_vac2'] = start_vac2
            st.session_state.holidays_config[place_key]['end_vac2'] = end_vac2
            st.session_state.holidays_config[place_key]['start_vac3'] = start_vac3
            st.session_state.holidays_config[place_key]['end_vac3'] = end_vac3

            # Process date ranges
            holidays_list = []
            for start_vac, end_vac in zip([start_vac1, start_vac2, start_vac3], [end_vac1, end_vac2, end_vac3]):
                if start_vac and end_vac:
                    days = [str(d) for d in daterange(start_vac, end_vac)]
                    holidays_list.extend(days)

            manual_days = st.text_input(
                f"Autres jours (AAAA-MM-JJ séparés par ,)",
                value=st.session_state.holidays_config[place_key]['manual_days'],
                key=f"manual_days_{place_key}"
            )

            # Update session state
            st.session_state.holidays_config[place_key]['manual_days'] = manual_days

            # Process manual days
            if manual_days:
                manual_days_list = [d.strip() for d in manual_days.split(",") if d.strip()]
                holidays_list.extend(manual_days_list)

            # Update the config with all holidays (removing duplicates)
            place_cfg['holidays'] = list(set(holidays_list))
            st.session_state.holidays_config[place_key]['holidays'] = place_cfg['holidays']

for key in ["df_schedule", "df_schedule_simple"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.button("Générer le planning"):
    if selected_date > end_date:
        st.error("La date de début doit être avant la date de fin.")
    else:
        working_days, public_holidays = get_working_days(selected_date, end_date)

        schedule_full = ScheduleAllocator(config, working_days).allocate()

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
        edited_full = create_calendar_editor(source=st.session_state.df_schedule)
        st.session_state.df_schedule = edited_full

    with tab2_complete:
        create_visual_calendar(
            source=st.session_state.df_schedule,
        )

    st.markdown("## Vue simplifiée : lieu uniquement")
    tab1_simple, tab2_simple = st.tabs(["📊 Tableau", "📅 Vue visuelle"])

    with tab1_simple:
        create_calendar_editor(source=st.session_state.df_schedule, simplified=True)

    with tab2_simple:
        create_visual_calendar(
            source=st.session_state.df_schedule,
            simplified=True
        )

    # Section des statistiques avec 3 onglets
    st.markdown("## 📊 Statistiques du planning")
    stats_tab1, stats_tab2, stats_tab3 = st.tabs([
        "📈 Total par site",
        "📊 Total global",
        "📅 Vendredis Majorelle"
    ])

    with stats_tab1:
        df_summary = schedule_summary(st.session_state.df_schedule, False)
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

    with stats_tab2:
        df_summary = schedule_summary(st.session_state.df_schedule, True)
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

    with stats_tab3:
        majorelle_sites = [key for key in config.keys() if key.startswith('majorelle_')]

        if majorelle_sites:
            friday_counts = {}
            for site_key in majorelle_sites:
                site_name = config[site_key]['name']
                count = 0

                for _, row in st.session_state.df_schedule.iterrows():
                    try:
                        date_str = str(row.iloc[0])
                        if 'vendredi' in date_str.lower() or 'friday' in date_str.lower():
                            is_friday = True
                        else:
                            try:
                                from datetime import datetime
                                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                                    try:
                                        date_obj = datetime.strptime(date_str.split()[0], fmt)
                                        is_friday = date_obj.weekday() == 4
                                        break
                                    except:
                                        continue
                                else:
                                    is_friday = False
                            except:
                                is_friday = False

                        if is_friday:
                            row_str = ' '.join(str(val) for val in row.values)
                            if site_name in row_str:
                                count += 1
                    except:
                        continue

                friday_counts[site_name] = count

            if friday_counts:
                df_fridays = pd.DataFrame(
                    list(friday_counts.items()),
                    columns=['Site Majorelle', 'Nombre de vendredis']
                )
                df_fridays = df_fridays.sort_values('Site Majorelle')

                def get_status(count):
                    if count == 4:
                        return "✅ Optimal"
                    elif count in [3, 5]:
                        return "⚠️ Acceptable"
                    else:
                        return "❌ À revoir"


                df_fridays['Statut'] = df_fridays['Nombre de vendredis'].apply(get_status)

                st.dataframe(df_fridays, hide_index=True, use_container_width=True)

                problematic = (~df_fridays['Nombre de vendredis'].isin([3, 4, 5])).sum()

                if problematic == 0:
                    st.success("✅ Tous les sites Majorelle ont une allocation correcte de vendredis (3-5)")
                else:
                    st.warning(f"⚠️ {problematic} site(s) Majorelle ont une allocation incorrecte de vendredis")

                st.info("💡 Objectif : 4 vendredis par site Majorelle, avec une flexibilité de 3-5 vendredis acceptée")
            else:
                st.info("Aucune donnée de vendredis trouvée pour les sites Majorelle")
        else:
            st.info("Aucun site Majorelle configuré")

    # Save schedule
    if st.button("💾 Sauvegarder"):
        schedule_id = storage.save(
            st.session_state.df_schedule,
            selected_date
        )

        # Synchronise with GitHub
        try:
            sync = GitHubSync()
            sync.push_csv()
            st.success(f"✅ Planning saved: {schedule_id}")
        except Exception as e:
            st.warning(f"⚠️ Error during sync: {e}")
