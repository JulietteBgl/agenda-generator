import streamlit as st
import pandas as pd
from datetime import datetime

from utils.export_agenda import create_excel_export
from utils.storage_csv import ScheduleStorage
from utils.github_sync import GitHubSync

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
    st.dataframe(df_schedules, use_container_width=True, hide_index=True)

    # ===== ACTIONS SUR LES PLANNINGS =====
    st.markdown("## Actions")

    selected_schedule = st.selectbox(
        "Sélectionner un planning",
        options=list(all_schedules.keys()),
        format_func=lambda x: f"{x} - {all_schedules[x]['start_date']}"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👁️ Visualiser", use_container_width=True):
            st.session_state['show_visualization'] = selected_schedule

    with col2:
        if st.button("🗑️ Supprimer", type="secondary", use_container_width=True):
            if st.session_state.get('confirm_delete') == selected_schedule:
                storage.delete(selected_schedule)

                # Sync avec GitHub
                sync = GitHubSync()
                sync.push_csv(commit_message=f"Delete planning {selected_schedule}")

                st.success(f"Planning {selected_schedule} supprimé")
                del st.session_state['confirm_delete']
                st.rerun()
            else:
                st.session_state['confirm_delete'] = selected_schedule
                st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")

    # Afficher la visualisation en pleine largeur (hors des colonnes)
    if st.session_state.get('show_visualization'):
        schedule_to_show = st.session_state['show_visualization']
        df = storage.load(schedule_to_show)
        if df is not None:
            st.markdown(f"### Visualisation : {schedule_to_show}")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error("Impossible de charger ce planning")

    # ===== STATISTIQUES =====
    st.markdown("---")
    col_title, col_export = st.columns([3, 1])

    # Récupérer les années et trimestres disponibles
    years = sorted(list(set([meta['year'] for meta in all_schedules.values()])), reverse=True)
    current_year = datetime.now().year


    with col_title:
        st.markdown("## 📈 Statistiques d'affectation")

    with col_export:
        # Bouton d'export Excel (toujours visible si des plannings existent)
        if all_schedules:
            # Par défaut exporter l'année en cours
            export_year = datetime.now().year
            if years:
                export_year = years[0]  # L'année la plus récente

            excel_data = create_excel_export(storage, export_year)
            st.download_button(
                label="📥 Télécharger Excel",
                data=excel_data,
                file_name=f"planning_{export_year}.xlsx",
            )

    # Filtres
    col1, col2 = st.columns(2)

    with col1:
        # Sélectionner l'année (par défaut: année en cours)
        default_year_index = years.index(current_year) if current_year in years else 0
        selected_year = st.selectbox(
            "Filtrer par année",
            options=years,
            index=default_year_index
        )

    with col2:
        # Filtrer les trimestres de l'année sélectionnée
        available_quarters = sorted([
            meta['quarter'] for sid, meta in all_schedules.items()
            if meta['year'] == selected_year
        ])

        selected_quarters = st.multiselect(
            "Filtrer par trimestre",
            options=available_quarters,
            default=available_quarters,  # Tous sélectionnés par défaut
            format_func=lambda q: f"T{q}"
        )

    # Filtrer les IDs selon les sélections
    if selected_quarters:
        filtered_ids = [
            sid for sid, meta in all_schedules.items()
            if meta['year'] == selected_year and meta['quarter'] in selected_quarters
        ]
    else:
        filtered_ids = []

    st.info(f"📊 {len(filtered_ids)} trimestre(s) sélectionné(s)")

    # Calculer et afficher les statistiques
    if filtered_ids:
        df_stats = storage.get_statistics(filtered_ids)

        if not df_stats.empty:
            # Onglets pour les deux versions
            tab1, tab2 = st.tabs(["📊 Détaillé", "📊 Simplifié (Majo)"])

            with tab1:
                st.markdown("### Nombre d'affectations par site (détaillé)")
                st.dataframe(df_stats, use_container_width=True)

            with tab2:
                st.markdown("### Nombre d'affectations par site (Majo groupé)")

                # Créer une copie et regrouper les "Majo"
                df_stats_simplified = df_stats.copy()

                # Identifier les lignes "Majo"
                majo_rows = df_stats_simplified.index.str.startswith('Majo')

                if majo_rows.any():
                    # Extraire les données Majo
                    majo_data = df_stats_simplified[majo_rows]

                    # Supprimer les lignes Majo individuelles
                    df_stats_simplified = df_stats_simplified[~majo_rows]

                    # Additionner toutes les lignes Majo
                    majo_sum = majo_data.sum()
                    majo_sum.name = 'Majo'

                    # Ajouter la ligne Majo groupée
                    df_stats_simplified = pd.concat([
                        df_stats_simplified,
                        pd.DataFrame([majo_sum])
                    ])

                    # Retrier par Total
                    df_stats_simplified = df_stats_simplified.sort_values('Total', ascending=False)

                st.dataframe(df_stats_simplified, use_container_width=True)
        else:
            st.warning("Aucune donnée disponible pour générer des statistiques")
    else:
        st.warning("⚠️ Veuillez sélectionner au moins un trimestre")

# ===== SIDEBAR : INFO GITHUB =====
with st.sidebar:
    st.markdown("### 🔄 Synchronisation GitHub")
    sync = GitHubSync()

    if sync.enabled:
        st.success("✅ Activée")

        # Afficher les infos du dernier commit
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
