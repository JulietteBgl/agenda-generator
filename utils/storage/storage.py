from io import BytesIO

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class ScheduleStorage:

    def __init__(self, csv_path: str = "output/planning_all.csv"):
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

    #create_excel_export

    def export_to_excel(self, year: int)-> BytesIO:
        """
        Create an Excel file with one tab per semester along with one total tab

        Args:
            year: Year to export

        Returns:
            BytesIO: Excel file in memory
        """
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            workbook = writer.book

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })

            cell_format = workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'top',
                'text_wrap': True
            })

            all_schedules = self.get_all()
            year_schedules = {
                sid: meta for sid, meta in all_schedules.items()
                if meta['year'] == year
            }

            if not year_schedules:
                df_empty = pd.DataFrame({'Message': ['Aucun planning pour cette année']})
                df_empty.to_excel(writer, sheet_name='Aucune donnée', index=False)
                return buffer

            sorted_schedules = sorted(year_schedules.items(), key=lambda x: x[1]['quarter'])

            # Create one tab per semester
            all_stats_for_total = []

            for schedule_id, meta in sorted_schedules:
                quarter = meta['quarter']
                df_planning = self.load(schedule_id)

                if df_planning is not None and not df_planning.empty:
                    sheet_name = f"T{quarter}"

                    worksheet = workbook.add_worksheet(sheet_name)
                    writer.sheets[sheet_name] = worksheet

                    df = df_planning.copy()
                    df['Date'] = pd.to_datetime(df['Date'])
                    df['DayOfWeek'] = df['Date'].dt.dayofweek
                    df['WeekNumber'] = df['Date'].dt.isocalendar().week
                    df['Year'] = df['Date'].dt.year

                    df_weekdays = df[df['DayOfWeek'] <= 4].copy()

                    site_columns = ['Affectation 1', 'Affectation 2']

                    worksheet.set_column('A:E', 20)

                    row = 0
                    days_of_week = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']

                    for (year_val, week), week_data in df_weekdays.groupby(['Year', 'WeekNumber'], sort=True):
                        week_dates = {}
                        for _, day_row in week_data.iterrows():
                            day_of_week = day_row['DayOfWeek']
                            week_dates[day_of_week] = day_row['Date']

                        for day_idx in range(5):
                            if day_idx in week_dates:
                                date_str = week_dates[day_idx].strftime('%d/%m')
                                worksheet.write(row, day_idx, f"{days_of_week[day_idx]} {date_str}", header_format)
                            else:
                                worksheet.write(row, day_idx, days_of_week[day_idx], header_format)

                        row += 1

                        for site_col in site_columns:
                            for day_idx in range(5):
                                if day_idx in week_dates:
                                    day_data = week_data[week_data['DayOfWeek'] == day_idx]
                                    if not day_data.empty:
                                        value = day_data.iloc[0][site_col]
                                        if pd.notna(value) and value != '':
                                            worksheet.write(row, day_idx, str(value), cell_format)
                                        else:
                                            worksheet.write(row, day_idx, '', cell_format)
                                    else:
                                        worksheet.write(row, day_idx, '', cell_format)
                                else:
                                    worksheet.write(row, day_idx, '', cell_format)

                            row += 1

                        row += 1

                    stats = self.get_statistics([schedule_id])
                    if not stats.empty:
                        all_stats_for_total.append(stats)

            # Create the total tab
            if all_stats_for_total:
                df_total = pd.concat(all_stats_for_total, axis=1)
                df_total = df_total.T.groupby(level=0).sum().T

                if 'Total' in df_total.columns:
                    df_total = df_total.drop('Total', axis=1)
                df_total['Total'] = df_total.sum(axis=1)
                df_total = df_total.sort_values('Total', ascending=False)

                df_total_simplified = df_total.copy()
                majo_rows = df_total_simplified.index.str.startswith('Majo')

                if majo_rows.any():
                    majo_data = df_total_simplified[majo_rows]
                    df_total_simplified = df_total_simplified[~majo_rows]
                    majo_sum = majo_data.sum()
                    majo_sum.name = 'Majo'
                    df_total_simplified = pd.concat([
                        df_total_simplified,
                        pd.DataFrame([majo_sum])
                    ])
                    df_total_simplified = df_total_simplified.sort_values('Total', ascending=False)

                df_total_simplified.to_excel(writer, sheet_name='Total')

                worksheet = writer.sheets['Total']
                worksheet.write(0, 0, 'Site', header_format)
                for col_num, value in enumerate(df_total_simplified.columns.values, start=1):
                    worksheet.write(0, col_num, value, header_format)

                worksheet.set_column(0, 0, 25)
                worksheet.set_column(1, len(df_total_simplified.columns), 15)

        buffer.seek(0)
        return buffer
