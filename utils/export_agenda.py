import pandas as pd
from io import BytesIO


def create_excel_export(storage, year):
    """
    Create an excel file with one tab per semester along with one total tab

    Args:
        storage: ScheduleStorage instance
        year: Year to export

    Returns:
        BytesIO: Exvel file in memory
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

        all_schedules = storage.get_all()
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
            df_planning = storage.load(schedule_id)

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
                            worksheet.write(row, day_idx, f"{days_of_week[day_idx]}\n{date_str}", header_format)
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

                stats = storage.get_statistics([schedule_id])
                if not stats.empty:
                    all_stats_for_total.append(stats)

        # Create the total tab
        if all_stats_for_total:
            df_total = pd.concat(all_stats_for_total, axis=1)
            df_total = df_total.groupby(level=0, axis=1).sum()

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
