import pandas as pd
from io import BytesIO


def to_excel(df):
    """
    Export the schedule to Excel with a calendar view (Monday to Friday columns)

    Args:
        df: DataFrame with columns ['Date', 'Site1', 'Site2', ...]
    """
    buffer = BytesIO()

    # Convert Date column to datetime if it's not already
    df['Date'] = pd.to_datetime(df['Date'])

    # Add day of week and week number
    df['DayOfWeek'] = df['Date'].dt.dayofweek  # 0=Monday, 4=Friday
    df['WeekNumber'] = df['Date'].dt.isocalendar().week
    df['Year'] = df['Date'].dt.year

    # Filter only Monday to Friday (0-4)
    df_weekdays = df[df['DayOfWeek'] <= 4].copy()

    # Get all site columns (all columns except Date, DayOfWeek, WeekNumber, Year)
    site_columns = [col for col in df.columns if col not in ['Date', 'DayOfWeek', 'WeekNumber', 'Year']]

    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Planning')
        writer.sheets['Planning'] = worksheet

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        date_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
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

        # Column width
        worksheet.set_column('A:A', 15)  # Site name column
        worksheet.set_column('B:F', 20)  # Day columns

        # Current row
        row = 0

        # Group by year and week
        for (year, week), week_data in df_weekdays.groupby(['Year', 'WeekNumber'], sort=True):
            # Write week header
            week_start = week_data['Date'].min()
            week_end = week_data['Date'].max()
            worksheet.merge_range(row, 0, row, 5,
                                  f"Week {week} ({week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')})",
                                  header_format)
            row += 1

            # Write day headers (Monday to Friday)
            days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            worksheet.write(row, 0, 'Site', header_format)

            # Get dates for this week
            week_dates = {}
            for _, day_row in week_data.iterrows():
                day_of_week = day_row['DayOfWeek']
                week_dates[day_of_week] = day_row['Date']

            # Write column headers with dates
            for day_idx in range(5):
                if day_idx in week_dates:
                    date_str = week_dates[day_idx].strftime('%d/%m')
                    worksheet.write(row, day_idx + 1, f"{days_of_week[day_idx]}\n{date_str}", header_format)
                else:
                    worksheet.write(row, day_idx + 1, days_of_week[day_idx], header_format)

            row += 1

            # Write data for each site
            for site_col in site_columns:
                worksheet.write(row, 0, site_col, date_format)

                for day_idx in range(5):
                    if day_idx in week_dates:
                        # Find the value for this day
                        day_data = week_data[week_data['DayOfWeek'] == day_idx]
                        if not day_data.empty:
                            value = day_data.iloc[0][site_col]
                            if pd.notna(value) and value != '':
                                worksheet.write(row, day_idx + 1, str(value), cell_format)
                            else:
                                worksheet.write(row, day_idx + 1, '', cell_format)
                        else:
                            worksheet.write(row, day_idx + 1, '', cell_format)
                    else:
                        worksheet.write(row, day_idx + 1, '', cell_format)

                row += 1

            # Add empty row between weeks
            row += 1

    return buffer.getvalue()
