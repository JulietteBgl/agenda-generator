import streamlit as st
import pandas as pd
from datetime import datetime

from utils.storage.storage import ScheduleStorage
from utils.storage.github_sync import GitHubSync

# Configuration de la page
st.set_page_config(
    page_title="Suivi des plannings",
    page_icon="📊",
)


# Stockage init
@st.cache_resource
def get_storage():
    return ScheduleStorage()


storage = get_storage()

st.title("Suivi des plannings")

st.markdown("## Plannings sauvegardés")

all_schedules = storage.get_all()

if not all_schedules:
    st.info("Aucun planning sauvegardé pour le moment.")
    st.markdown("👈 Allez dans **Planification** pour créer un planning")
else:
    schedules_list = []
    for schedule_id, meta in all_schedules.items():
        schedules_list.append({
            'Trimestre': schedule_id,
            'Année': meta['year'],
            'Sauvegardé le': meta['saved_at']
        })

    df_schedules = pd.DataFrame(schedules_list)
    st.dataframe(df_schedules, width='stretch', hide_index=True)

    st.markdown("## Actions")

    selected_schedule = st.selectbox(
        "Sélectionner un planning",
        options=list(all_schedules.keys()),
        format_func=lambda x: f"{x} - {all_schedules[x]['start_date']}"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👁️ Visualiser", width='stretch'):
            st.session_state['show_visualization'] = selected_schedule

    with col2:
        if st.button("🗑️ Supprimer", type="secondary", width='stretch'):
            if st.session_state.get('confirm_delete') == selected_schedule:
                storage.delete(selected_schedule)

                # Sync avec GitHub
                sync = GitHubSync()
                sync.push_file(commit_message=f"Delete planning {selected_schedule}")

                st.session_state['delete_success'] = f"Planning {selected_schedule} supprimé"
                del st.session_state['confirm_delete']
                st.rerun()
            else:
                st.session_state['confirm_delete'] = selected_schedule

    if st.session_state.get('confirm_delete') == selected_schedule:
        st.warning("⚠️ Cliquez à nouveau sur le bouton Supprimer pour confirmer la suppression")

    if st.session_state.get('delete_success'):
        st.success(st.session_state['delete_success'])
        del st.session_state['delete_success']

    if st.session_state.get('show_visualization'):
        schedule_to_show = st.session_state['show_visualization']
        df = storage.load(schedule_to_show)
        if df is not None:
            st.markdown(f"### Visualisation : {schedule_to_show}")
            st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.error("Impossible de charger ce planning")

    # ===== STATISTIQUES =====
    st.markdown("---")
    st.markdown("## 📈 Statistiques d'affectation")

    years = sorted(list(set([meta['year'] for meta in all_schedules.values()])), reverse=True)
    current_year = datetime.now().year

    col1, col2 = st.columns(2)

    with col1:
        default_year_index = years.index(current_year) if current_year in years else 0
        selected_year = st.selectbox(
            "Filtrer par année",
            options=years,
            index=default_year_index
        )

    with col2:
        available_quarters = sorted([
            meta['quarter'] for sid, meta in all_schedules.items()
            if meta['year'] == selected_year
        ])

        selected_quarters = st.multiselect(
            "Filtrer par trimestre",
            options=available_quarters,
            default=available_quarters,
            format_func=lambda q: f"T{q}"
        )

    if selected_quarters:
        filtered_ids = [
            sid for sid, meta in all_schedules.items()
            if meta['year'] == selected_year and meta['quarter'] in selected_quarters
        ]
    else:
        filtered_ids = []

    st.info(f"📊 {len(filtered_ids)} trimestre(s) sélectionné(s)")

    if filtered_ids:
        df_stats = storage.get_statistics(filtered_ids)

        if not df_stats.empty:
            tab1, tab2 = st.tabs(["📊 Détaillé", "📊 Simplifié (Majo)"])

            with tab1:
                st.dataframe(df_stats, width='stretch')

            with tab2:

                df_stats_simplified = df_stats.copy()
                majo_rows = df_stats_simplified.index.str.startswith('Majo')

                if majo_rows.any():
                    majo_data = df_stats_simplified[majo_rows]
                    df_stats_simplified = df_stats_simplified[~majo_rows]
                    majo_sum = majo_data.sum()
                    majo_sum.name = 'Majo'
                    df_stats_simplified = pd.concat([
                        df_stats_simplified,
                        pd.DataFrame([majo_sum])
                    ])

                    df_stats_simplified = df_stats_simplified.sort_values('Total', ascending=False)

                st.dataframe(df_stats_simplified, width='stretch')
        else:
            st.warning("Aucune donnée disponible pour générer des statistiques")
    else:
        st.warning("⚠️ Veuillez sélectionner au moins un trimestre")

    # ===== EXPORT EXCEL =====
    st.markdown("---")
    st.markdown("### 📥 Export Excel")

    export_year = datetime.now().year
    if years:
        export_year = years[0]

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        excel_data = storage.export_to_excel(export_year)
        st.download_button(
            label="📥 Excel détaillé",
            data=excel_data,
            file_name=f"planning_{export_year}_complet.xlsx",
            use_container_width=True,
        )
    with col_dl2:
        excel_data_grouped = storage.export_to_excel(export_year, grouped_majo=True)
        st.download_button(
            label="📥 Excel Majo groupé",
            data=excel_data_grouped,
            file_name=f"planning_{export_year}.xlsx",
            use_container_width=True,
        )

# ===== SIDEBAR : INFO GITHUB =====
with st.sidebar:
    st.markdown("### 🔄 Synchronisation GitHub")
    sync = GitHubSync()

    if sync.enabled:
        st.success("✅ Activée")

        commit_info = sync.get_last_commit_info()
        if commit_info:
            st.caption("**Dernier commit:**")
            st.caption(f"📅 {commit_info['date']}")
            st.caption(f"💬 {commit_info['message'][:50]}...")
    else:
        st.warning("⚠️ Non configurée")
        with st.expander("ℹ️ Configuration"):
            st.markdown("""
            Pour activer la synchronisation :

            1. Créer un token GitHub
            2. Ajouter dans `.streamlit/secrets.toml`:
            ```toml
            [github]
            token = "ghp_..."
            repo = "username/repo"
            ```
            """)
