import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class ScheduleStorage:

    def __init__(self, db_path: str = "data/planning.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_data (
                date DATE,
                affectation_1 VARCHAR,
                affectation_2 VARCHAR,
                schedule_id VARCHAR,
                saved_at TIMESTAMP,
                PRIMARY KEY (schedule_id, date)
            )
        """)

    def save(self, df: pd.DataFrame, quarter_date: datetime) -> str:
        """
        Save schedule

        Args:
            df: DataFrame with columns ['Date', 'Affectation 1', 'Affectation 2', ...]
            quarter_date: Start date of the quarter

        Returns:
            schedule_id
        """
        schedule_id = self._generate_id(quarter_date)
        self.conn.execute("DELETE FROM schedule_data WHERE schedule_id = ?", [schedule_id])

        df_to_insert = df[['Date', 'Affectation 1', 'Affectation 2']].copy()
        df_to_insert.columns = ['date', 'affectation_1', 'affectation_2']
        df_to_insert['schedule_id'] = schedule_id
        df_to_insert['saved_at'] = datetime.now()

        df_to_insert['date'] = pd.to_datetime(df_to_insert['date'])

        if not df_to_insert.empty:
            self.conn.execute("""
                INSERT INTO schedule_data (date, affectation_1, affectation_2, schedule_id, saved_at)
                SELECT date, affectation_1, affectation_2, schedule_id, saved_at 
                FROM df_to_insert
            """)

        return schedule_id

    def load(self, schedule_id: str) -> Optional[pd.DataFrame]:
        result = self.conn.execute("""
            SELECT 
                date as "Date",
                affectation_1 as "Affectation 1",
                affectation_2 as "Affectation 2"
            FROM schedule_data
            WHERE schedule_id = ?
            ORDER BY date
        """, [schedule_id]).fetchdf()

        return result if not result.empty else None

    def delete(self, schedule_id: str):
        """Supprime un planning"""
        self.conn.execute("DELETE FROM schedule_data WHERE schedule_id = ?", [schedule_id])

    def get_all(self) -> Dict:
        """
        Récupère tous les plannings (métadonnées uniquement)

        Returns:
            Dict {schedule_id: {'saved_at': ..., 'year': ..., 'quarter': ...}}
        """
        result = self.conn.execute("""
            SELECT 
                schedule_id,
                MIN(saved_at) as saved_at,
                MIN(date) as start_date
            FROM schedule_data
            GROUP BY schedule_id
            ORDER BY schedule_id DESC
        """).fetchdf()

        if result.empty:
            return {}

        # Extraire year et quarter du schedule_id (format: T_1_2026)
        schedules = {}
        for _, row in result.iterrows():
            parts = row['schedule_id'].split('_')  # ['T', '1', '2026']
            schedules[row['schedule_id']] = {
                'quarter': int(parts[1]),
                'year': int(parts[2]),
                'start_date': row['start_date'],
                'saved_at': row['saved_at'],
                'user_notes': ''  # Pas de colonne notes dans votre schéma
            }

        return schedules

    def get_statistics(self, schedule_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Calcule les statistiques d'affectation par site (ultra rapide en SQL!)

        Args:
            schedule_ids: Liste des IDs à inclure (None = tous)

        Returns:
            DataFrame avec les colonnes: site_name, [T_1_2026, ...], Total
        """
        if schedule_ids:
            placeholders = ','.join(['?' for _ in schedule_ids])
            where_clause = f"WHERE schedule_id IN ({placeholders})"
            params = schedule_ids * 2  # *2 car utilisé 2 fois dans le UNION ALL
        else:
            where_clause = ""
            params = []

        # Compter les affectations dans les deux colonnes
        query = f"""
            WITH all_affectations AS (
                SELECT 
                    schedule_id,
                    affectation_1 as site_name
                FROM schedule_data
                {where_clause}
                {'AND' if where_clause else 'WHERE'} affectation_1 IS NOT NULL

                UNION ALL

                SELECT 
                    schedule_id,
                    affectation_2 as site_name
                FROM schedule_data
                {where_clause}
                {'AND' if where_clause else 'WHERE'} affectation_2 IS NOT NULL
            )
            SELECT 
                site_name,
                schedule_id,
                COUNT(*) as count
            FROM all_affectations
            GROUP BY site_name, schedule_id
            ORDER BY site_name, schedule_id
        """

        result = self.conn.execute(query, params).fetchdf()

        if result.empty:
            return pd.DataFrame()

        # Pivoter pour avoir les trimestres en colonnes
        pivot = result.pivot(index='site_name', columns='schedule_id', values='count')
        pivot = pivot.fillna(0).astype(int)
        pivot['Total'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('Total', ascending=False)

        return pivot

    def _generate_id(self, date: datetime) -> str:
        """Generate a unique name per semester"""
        year = date.year
        quarter = (date.month - 1) // 3 + 1
        return f"T{quarter}_{year}"

    def close(self):
        self.conn.close()
