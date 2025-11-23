import streamlit as st
import yaml
import copy
from utils.storage.github_sync import GitHubSync
from utils.tools import load_config


def save_config(config_dict, file_path='config/config.yml'):
    """Save configuration to YAML file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(config_dict, file, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde du fichier config : {e}")
        return False


def get_french_day_name(day_num):
    """Convert day number (0=Monday) to French day name"""
    days = {
        0: "lundi",
        1: "mardi", 
        2: "mercredi",
        3: "jeudi",
        4: "vendredi",
        5: "samedi",
        6: "dimanche"
    }
    return days.get(day_num, "")


def get_day_number(french_day):
    """Convert French day name to day number (0=Monday)"""
    days = {
        "lundi": 0,
        "mardi": 1,
        "mercredi": 2, 
        "jeudi": 3,
        "vendredi": 4,
        "samedi": 5,
        "dimanche": 6
    }
    return days.get(french_day, None)


st.set_page_config(
    page_title="Configuration - Planning Radiologues",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Configuration des Sites")

# Load current configuration
config = load_config('config/config.yml')

# Initialize session state for configuration
if 'config_modified' not in st.session_state:
    st.session_state.config_modified = copy.deepcopy(config)

if 'new_site_key' not in st.session_state:
    st.session_state.new_site_key = ""

if 'new_site_name' not in st.session_state:
    st.session_state.new_site_name = ""

# Function to add a new site
def add_new_site():
    if st.session_state.new_site_key and st.session_state.new_site_name:
        if st.session_state.new_site_key not in st.session_state.config_modified:
            st.session_state.config_modified[st.session_state.new_site_key] = {
                'name': st.session_state.new_site_name,
                'advanced_split': False,
                'nb_radiologists': 1,
                'available_weekdays': [0, 1, 2, 3, 4],  # Monday to Friday by default
                'pair_same_day': False
            }
            st.success(f"Site '{st.session_state.new_site_name}' ajouté avec succès!")
            # Reset the input fields
            st.session_state.new_site_key = ""
            st.session_state.new_site_name = ""
        else:
            st.error(f"La clé '{st.session_state.new_site_key}' existe déjà!")

# Section to add new site
st.markdown("### ➕ Ajouter un nouveau site")
with st.expander("Ajouter un site", expanded=False):
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        new_site_key = st.text_input(
            "Clé du site",
            value=st.session_state.new_site_key,
            key="input_new_site_key",
            help="Ex: nouveau_site, clinique_x, etc. (sans espaces, minuscules)"
        )
        st.session_state.new_site_key = new_site_key
    
    with col2:
        new_site_name = st.text_input(
            "Nom affiché du site",
            value=st.session_state.new_site_name,
            key="input_new_site_name",
            help="Nom qui apparaîtra dans l'application"
        )
        st.session_state.new_site_name = new_site_name
    
    with col3:
        if st.button("Ajouter", type="primary"):
            add_new_site()

# Display and edit existing sites
st.markdown("### 📝 Modifier les sites existants")

# List of sites to remove
sites_to_remove = []

for site_key, site_config in st.session_state.config_modified.items():
    with st.expander(f"**{site_config['name']}** ({site_key})", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Site name
            new_name = st.text_input(
                "Nom affiché",
                value=site_config['name'],
                key=f"name_{site_key}"
            )
            st.session_state.config_modified[site_key]['name'] = new_name
            
            # Number of doctors
            nb_doctors = st.number_input(
                "Nombre de radiologues",
                min_value=1,
                max_value=20,
                value=site_config.get('nb_radiologists', 1),
                key=f"nb_doctors_{site_key}"
            )
            st.session_state.config_modified[site_key]['nb_radiologists'] = nb_doctors
            
            # Available weekdays (only Monday to Friday)
            st.markdown("**Jours disponibles**")
            available_days = site_config.get('available_weekdays', [0, 1, 2, 3, 4])
            
            # Create checkboxes for weekdays only (Monday to Friday)
            day_cols = st.columns(5)
            new_available_days = []
            
            for i, day_name in enumerate(['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi']):
                with day_cols[i]:
                    is_checked = i in available_days
                    if st.checkbox(day_name.capitalize(), value=is_checked, key=f"day_{site_key}_{i}"):
                        new_available_days.append(i)
            
            st.session_state.config_modified[site_key]['available_weekdays'] = new_available_days
            
            # Advanced split
            advanced_split = st.checkbox(
                "Permettre la gestion des congés",
                value=site_config.get('advanced_split', False),
                key=f"advanced_{site_key}",
                help="Active la gestion détaillée des congés pour ce site"
            )
            st.session_state.config_modified[site_key]['advanced_split'] = advanced_split
            
            # Pair same day
            pair_same_day = st.checkbox(
                "Forcer le même site sur 2 créneaux le même jour",
                value=site_config.get('pair_same_day', False),
                key=f"pair_{site_key}"
            )
            st.session_state.config_modified[site_key]['pair_same_day'] = pair_same_day
        
        with col2:
            st.markdown("**Actions**")
            if st.button(f"🗑️ Supprimer", key=f"remove_{site_key}", type="secondary"):
                sites_to_remove.append(site_key)

# Remove sites marked for deletion
for site_key in sites_to_remove:
    if site_key in st.session_state.config_modified:
        site_name = st.session_state.config_modified[site_key]['name']
        del st.session_state.config_modified[site_key]
        st.success(f"Site '{site_name}' supprimé!")



# Save buttons
st.markdown("### 💾 Sauvegarde")
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("💾 Sauvegarder", type="primary"):
        # First save locally
        if save_config(st.session_state.config_modified):
            try:
                sync = GitHubSync()
                if sync.enabled:
                    # Push the config file to GitHub
                    success = sync.push_file(
                        file_path="config/config.yml",
                        commit_message=f"Update site configuration - {len(st.session_state.config_modified)} sites configured"
                    )
                    if success:
                        st.success("✅ Configuration sauvegardée sur GitHub!")
                    else:
                        st.error("❌ Erreur lors de la sauvegarde sur GitHub")
                else:
                    st.error("❌ GitHub non configuré (vérifiez les secrets)")
            except Exception as e:
                st.error(f"❌ Erreur GitHub: {e}")
        else:
            st.error("❌ Erreur lors de la sauvegarde locale")

with col2:
    if st.button("🔄 Réinitialiser les modifications"):
        st.session_state.config_modified = copy.deepcopy(config)
        st.success("Configuration réinitialisée!")
        st.rerun()

# Warning about changes
if st.session_state.config_modified != config:
    st.warning("⚠️ Des modifications non sauvegardées sont en cours. N'oubliez pas de sauvegarder!")

# Summary
st.markdown("### 📊 Résumé de la configuration")
summary_data = []
for site_key, site_config in st.session_state.config_modified.items():
    available_days_str = ", ".join([get_french_day_name(day) for day in site_config.get('available_weekdays', [])])
    summary_data.append({
        "Site": site_config['name'],
        "Clé": site_key,
        "Radiologues": site_config.get('nb_radiologists', 1),
        "Jours disponibles": available_days_str,
        "Gestion des congés": "✅" if site_config.get('advanced_split', False) else "❌",
        "Même jour forcé": "✅" if site_config.get('pair_same_day', False) else "❌"
    })

import pandas as pd
if summary_data:
    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, width='stretch', hide_index=True)
else:
    st.info("Aucun site configuré")