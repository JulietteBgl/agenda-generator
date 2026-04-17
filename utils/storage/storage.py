import calendar
from io import BytesIO

import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List

FRENCH_MONTHS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
}

FRENCH_DAYS = {
    0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi',
    4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
}


def _load_display_name_map(config_path: str = None) -> Dict[str, str]:
    """Build a mapping from site name to display_name from config."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return {
            site['name']: site['display_name']
            for site in config.get('sites', {}).values()
            if 'display_name' in site
        }
    except Exception:
        return {}


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

    def _get_statistics_grouped_majo(self, schedule_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Compute affectation stats with all Majo-xxx sites grouped as 'Majo'"""
        df = pd.read_csv(self.csv_path)
        if schedule_ids:
            df = df[df["schedule_id"].isin(schedule_ids)]

        for col in ['affectation_1', 'affectation_2']:
            df[col] = df[col].apply(
                lambda x: 'Majo' if pd.notna(x) and str(x).startswith('Majo') else x
            )

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

    def export_to_excel(self, year: int, grouped_majo: bool = False, schedule_ids: Optional[List[str]] = None) -> BytesIO:
        """
        Create an Excel file with one tab per month and one total statistics tab.

        Args:
            year: Year to export
            grouped_majo: If True, all 'Majo - xxx' sites are replaced by 'Majo'
            schedule_ids: If provided, only include these specific schedules

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

            month_title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })

            red_header_format = workbook.add_format({
                'bold': True,
                'font_color': 'red',
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

            weekend_format = workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'top',
                'bg_color': '#D9D9D9'
            })

            all_schedules = self.get_all()
            if schedule_ids:
                year_schedules = {
                    sid: meta for sid, meta in all_schedules.items()
                    if sid in schedule_ids
                }
            else:
                year_schedules = {
                    sid: meta for sid, meta in all_schedules.items()
                    if meta['year'] == year
                }

            if not year_schedules:
                df_empty = pd.DataFrame({'Message': ['Aucun planning pour cette année']})
                df_empty.to_excel(writer, sheet_name='Aucune donnée', index=False)
                buffer.seek(0)
                return buffer

            # Load all planning data for the year
            all_planning = []
            for schedule_id in year_schedules:
                df_planning = self.load(schedule_id)
                if df_planning is not None:
                    all_planning.append(df_planning)

            if not all_planning:
                df_empty = pd.DataFrame({'Message': ['Aucune donnée de planning']})
                df_empty.to_excel(writer, sheet_name='Aucune donnée', index=False)
                buffer.seek(0)
                return buffer

            df_all = pd.concat(all_planning, ignore_index=True)
            df_all['Date'] = pd.to_datetime(df_all['Date'])

            if grouped_majo:
                for col in ['Affectation 1', 'Affectation 2']:
                    df_all[col] = df_all[col].apply(
                        lambda x: 'Majo' if pd.notna(x) and str(x).startswith('Majo') else x
                    )

            # Build a lookup: date -> (aff1, aff2)
            planning_lookup = {}
            for _, row in df_all.iterrows():
                planning_lookup[row['Date'].date()] = (
                    row.get('Affectation 1', ''),
                    row.get('Affectation 2', '')
                )

            # Get all months present in the data
            months_in_data = sorted(df_all['Date'].dt.to_period('M').unique())
            display_name_map = _load_display_name_map()

            for period in months_in_data:
                month_num = period.month
                year_val = period.year
                month_name = FRENCH_MONTHS[month_num]
                sheet_name = f"{month_name} {year_val}"[:31]

                worksheet = workbook.add_worksheet(sheet_name)
                writer.sheets[sheet_name] = worksheet

                # Row 0: headers
                worksheet.write(0, 0, f"{month_name} {year_val}", month_title_format)
                worksheet.write(0, 1, '', header_format)
                worksheet.write(0, 2, 'Poste 1', header_format)
                worksheet.write(0, 3, 'Médecin 1', header_format)
                worksheet.write(0, 4, 'Poste 2', header_format)
                worksheet.write(0, 5, 'Médecin 2', header_format)
                worksheet.write(0, 6, 'POSE PRIORITAIRE', red_header_format)

                # Rows 1..N: every day of the month
                num_days = calendar.monthrange(year_val, month_num)[1]

                for day in range(1, num_days + 1):
                    date_obj = date(year_val, month_num, day)
                    day_of_week = date_obj.weekday()
                    day_name = FRENCH_DAYS[day_of_week]
                    is_weekend = day_of_week >= 5
                    row_idx = day  # row 1 = day 1

                    fmt = weekend_format if is_weekend else cell_format

                    worksheet.write(row_idx, 0, day_name, fmt)
                    worksheet.write(row_idx, 1, day, fmt)

                    if date_obj in planning_lookup and not is_weekend:
                        aff1, aff2 = planning_lookup[date_obj]
                        for aff, col_place, col_detail in [(aff1, 2, 3), (aff2, 4, 5)]:
                            val = str(aff).strip() if pd.notna(aff) else ''
                            display = display_name_map.get(val, '')
                            if display:
                                parts = val.split('-', 1)
                                worksheet.write(row_idx, col_place, parts[0].strip(), fmt)
                                # Use display_name from config for col D/F
                                worksheet.write(row_idx, col_detail, display, fmt)
                                
                            else:
                                worksheet.write(row_idx, col_place, val, fmt)
                                worksheet.write(row_idx, col_detail, '', fmt)
                    else:
                        for c in range(2, 6):
                            worksheet.write(row_idx, c, '', fmt)

                    worksheet.write(row_idx, 6, '', fmt)

                # Column widths
                worksheet.set_column(0, 0, 14)
                worksheet.set_column(1, 1, 6)
                worksheet.set_column(2, 5, 18)
                worksheet.set_column(6, 6, 22)

            # ===== Total statistics tab =====
            sorted_schedules = sorted(year_schedules.items(), key=lambda x: x[1]['quarter'])
            all_stats_for_total = []

            for schedule_id, meta in sorted_schedules:
                if grouped_majo:
                    stats = self._get_statistics_grouped_majo([schedule_id])
                else:
                    stats = self.get_statistics([schedule_id])
                if not stats.empty:
                    all_stats_for_total.append(stats)

            if all_stats_for_total:
                df_total = pd.concat(all_stats_for_total, axis=1)
                df_total = df_total.T.groupby(level=0).sum().T

                if 'Total' in df_total.columns:
                    df_total = df_total.drop('Total', axis=1)
                df_total['Total'] = df_total.sum(axis=1)
                df_total = df_total.sort_values('Total', ascending=False)

                if not grouped_majo:
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
                else:
                    df_total_simplified = df_total

                df_total_simplified.to_excel(writer, sheet_name='Total')

                worksheet = writer.sheets['Total']
                worksheet.write(0, 0, 'Site', header_format)
                for col_num, value in enumerate(df_total_simplified.columns.values, start=1):
                    worksheet.write(0, col_num, value, header_format)

                worksheet.set_column(0, 0, 25)
                worksheet.set_column(1, len(df_total_simplified.columns), 15)

        buffer.seek(0)
        return buffer
