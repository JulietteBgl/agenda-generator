import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class ScheduleStorage:

    def __init__(self, csv_path: str = "data/planning_all.csv"):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            pd.DataFrame(columns=["schedule_id", "date", "affectation_1", "affectation_2", "saved_at"]).to_csv(
                self.csv_path, index=False
            )

    @staticmethod
    def _generate_id(date: datetime) -> str:
        """Generate a unique ID per quarter"""
        year = date.year
        quarter = (date.month - 1) // 3 + 1
        return f"T{quarter}_{year}"

    def save(self, df: pd.DataFrame, quarter_date: datetime) -> str:
        """Save schedule to the global CSV"""
        schedule_id = self._generate_id(quarter_date)
        all_data = pd.read_csv(self.csv_path)

        # If the semester already exists, we delete it
        all_data = all_data[all_data["schedule_id"] != schedule_id]

        new_data = df[["Date", "Affectation 1", "Affectation 2"]].copy()
        new_data.columns = ["date", "affectation_1", "affectation_2"]
        new_data["schedule_id"] = schedule_id
        new_data["saved_at"] = datetime.now().isoformat()

        updated = pd.concat([all_data, new_data], ignore_index=True)
        updated.to_csv(self.csv_path, index=False)

        return schedule_id

    def load(self, schedule_id: str) -> Optional[pd.DataFrame]:
        """Load a specific schedule"""
        df = pd.read_csv(self.csv_path)
        result = df[df["schedule_id"] == schedule_id].copy()
        if result.empty:
            return None
        result = result.rename(columns={
            "date": "Date",
            "affectation_1": "Affectation 1",
            "affectation_2": "Affectation 2"
        })
        return result

    def delete(self, schedule_id: str):
        """Delete one schedule"""
        df = pd.read_csv(self.csv_path)
        df = df[df["schedule_id"] != schedule_id]
        df.to_csv(self.csv_path, index=False)

    def get_all(self) -> Dict:
        """Return all schedule metadata"""
        df = pd.read_csv(self.csv_path)
        if df.empty:
            return {}
        meta = (
            df.groupby("schedule_id")
            .agg(start_date=("date", "min"), saved_at=("saved_at", "max"))
            .reset_index()
        )

        schedules = {}
        for _, row in meta.iterrows():
            parts = row["schedule_id"].split("_")
            quarter = int(parts[0][1:])
            year = int(parts[1])
            schedules[row["schedule_id"]] = {
                "quarter": quarter,
                "year": year,
                "start_date": row["start_date"],
                "saved_at": row["saved_at"],
            }

        return schedules

    def get_statistics(self, schedule_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Compute affectation stats"""
        df = pd.read_csv(self.csv_path)
        if schedule_ids:
            df = df[df["schedule_id"].isin(schedule_ids)]

        affectations = pd.concat([
            df[["schedule_id", "affectation_1"]].rename(columns={"affectation_1": "site_name"}),
            df[["schedule_id", "affectation_2"]].rename(columns={"affectation_2": "site_name"})
        ])
        affectations = affectations.dropna()

        stats = affectations.value_counts().reset_index(name="count")
        pivot = stats.pivot(index="site_name", columns="schedule_id", values="count").fillna(0).astype(int)
        pivot["Total"] = pivot.sum(axis=1)
        pivot = pivot.sort_values("Total", ascending=False)
        return pivot
