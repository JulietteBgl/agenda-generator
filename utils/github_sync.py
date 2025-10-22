"""
Synchronisation du fichier DuckDB avec GitHub
"""
import streamlit as st
from github import Github, GithubException
from pathlib import Path
import base64
import time


class GitHubSync:
    """Synchronisation automatique avec GitHub"""

    def __init__(self):
        self.enabled = False  # Par défaut désactivé
        try:
            # Configuration depuis secrets
            self.github_token = st.secrets["github"]["token"]
            self.repo_name = st.secrets["github"]["repo"]

            self.g = Github(self.github_token)
            self.repo = self.g.get_repo(self.repo_name)
            self.enabled = True  # Activé si la config réussit
        except Exception as e:
            # Pas d'erreur si la config n'existe pas
            pass

    def push_database(
            self,
            db_path: str = "data/planning.duckdb",
            commit_message: str = None
    ) -> bool:
        """
        Push le fichier DuckDB vers GitHub

        Args:
            db_path: Chemin du fichier DuckDB
            commit_message: Message du commit (auto-généré si None)

        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False

        file_path = Path(db_path)

        if not file_path.exists():
            st.error(f"❌ Fichier database introuvable: {db_path}")
            return False

        try:
            # Lire le fichier
            with open(file_path, 'rb') as f:
                content = f.read()

            # Encoder en base64
            content_encoded = base64.b64encode(content).decode('utf-8')

            # Message de commit par défaut
            if commit_message is None:
                commit_message = f"Update planning - {time.strftime('%Y-%m-%d %H:%M:%S')}"

            # Chemin dans le repo GitHub
            github_path = str(file_path)

            try:
                # Récupérer le fichier existant
                contents = self.repo.get_contents(github_path)

                # Mettre à jour
                self.repo.update_file(
                    path=github_path,
                    message=commit_message,
                    content=content_encoded,
                    sha=contents.sha,
                    branch="main"
                )

            except GithubException as e:
                # Le fichier n'existe pas encore, le créer
                if e.status == 404:
                    self.repo.create_file(
                        path=github_path,
                        message=commit_message,
                        content=content_encoded,
                        branch="main"
                    )
                else:
                    raise e

            return True

        except Exception as e:
            st.error(f"❌ Erreur lors du push GitHub: {e}")
            return False

    def get_last_commit_info(self, file_path: str = "data/planning.duckdb") -> dict:
        """
        Récupère les infos du dernier commit pour le fichier

        Returns:
            dict avec 'message', 'date', 'author'
        """
        if not self.enabled:
            return {}

        try:
            commits = self.repo.get_commits(path=file_path)
            last_commit = commits[0]

            return {
                'message': last_commit.commit.message,
                'date': last_commit.commit.author.date.strftime('%Y-%m-%d %H:%M:%S'),
                'author': last_commit.commit.author.name
            }
        except Exception:
            return {}
