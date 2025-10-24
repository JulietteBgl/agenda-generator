"""
Synchronizing the CSV file with GitHub
"""

import streamlit as st
from github import Github, GithubException
from pathlib import Path
import time


class GitHubSync:

    """Automatic synchronization of the CSV schedules with GitHub"""

    def __init__(self):
        self.enabled = False
        try:
            self.github_token = st.secrets["github"]["token"]
            self.repo_name = st.secrets["github"]["repo"]

            self.g = Github(self.github_token)
            self.repo = self.g.get_repo(self.repo_name)
            self.enabled = True
        except Exception:
            pass

    def push_csv(
        self,
        csv_path: str = "data/planning_all.csv",
        commit_message: str = None
    ) -> bool:
        """
        Push the CSV file to GitHub

        Args:
            csv_path: Path to the CSV file
            commit_message: Commit message (auto-generated if None)
        """
        if not self.enabled:
            return False

        file_path = Path(csv_path)
        if not file_path.exists():
            st.error(f"❌ Not found: {csv_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if commit_message is None:
                commit_message = f"Update planning CSV - {time.strftime('%Y-%m-%d %H:%M:%S')}"

            github_path = str(file_path)

            try:
                contents = self.repo.get_contents(github_path)
                self.repo.update_file(
                    path=github_path,
                    message=commit_message,
                    content=content,
                    sha=contents.sha,
                    branch="main"
                )
            except GithubException as e:
                # The file doesn’t exist yet → creating it
                if e.status == 404:
                    self.repo.create_file(
                        path=github_path,
                        message=commit_message,
                        content=content,
                        branch="main"
                    )
                else:
                    raise e

            return True

        except Exception as e:
            st.error(f"❌ Erreur lors du push GitHub: {e}")
            return False

    def get_last_commit_info(self, file_path: str = "data/planning_all.csv") -> dict:
        """
        Retrieve the latest commit information for the CSV file
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
