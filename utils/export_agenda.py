import pandas as pd
from io import BytesIO


def create_excel_export(storage, year):
    """
    Crée un fichier Excel avec un onglet par trimestre (format calendrier) + un onglet total

    Args:
        storage: Instance de ScheduleStorage
        year: Année à exporter

    Returns:
        BytesIO: Fichier Excel en mémoire
    """
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook = writer.book

        # Formats
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

        # Récupérer tous les plannings de l'année
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

        # 1. Créer un onglet par trimestre avec format calendrier
        all_stats_for_total = []

        for schedule_id, meta in sorted_schedules:
            quarter = meta['quarter']

            # Charger les données du planning
            df_planning = storage.load(schedule_id)

            if df_planning is not None and not df_planning.empty:
                sheet_name = f"T{quarter}"

                # Créer l'onglet avec format calendrier
                worksheet = workbook.add_worksheet(sheet_name)
                writer.sheets[sheet_name] = worksheet

                # Préparer les données
                df = df_planning.copy()
                df['Date'] = pd.to_datetime(df['Date'])
                df['DayOfWeek'] = df['Date'].dt.dayofweek
                df['WeekNumber'] = df['Date'].dt.isocalendar().week
                df['Year'] = df['Date'].dt.year

                # Filtrer du lundi au vendredi
                df_weekdays = df[df['DayOfWeek'] <= 4].copy()

                # Colonnes d'affectation
                site_columns = ['Affectation 1', 'Affectation 2']

                # Largeur des colonnes
                worksheet.set_column('A:A', 15)
                worksheet.set_column('B:F', 20)

                row = 0
                days_of_week = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']

                # Grouper par semaine
                for (year_val, week), week_data in df_weekdays.groupby(['Year', 'WeekNumber'], sort=True):
                    # En-tête de semaine
                    week_start = week_data['Date'].min()
                    week_end = week_data['Date'].max()
                    worksheet.merge_range(row, 0, row, 5,
                                          f"Semaine {week} ({week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')})",
                                          header_format)
                    row += 1

                    # En-têtes des jours
                    worksheet.write(row, 0, 'Affectation', header_format)

                    week_dates = {}
                    for _, day_row in week_data.iterrows():
                        day_of_week = day_row['DayOfWeek']
                        week_dates[day_of_week] = day_row['Date']

                    for day_idx in range(5):
                        if day_idx in week_dates:
                            date_str = week_dates[day_idx].strftime('%d/%m')
                            worksheet.write(row, day_idx + 1, f"{days_of_week[day_idx]}\n{date_str}", header_format)
                        else:
                            worksheet.write(row, day_idx + 1, days_of_week[day_idx], header_format)

                    row += 1

                    # Données pour chaque affectation
                    for site_col in site_columns:
                        worksheet.write(row, 0, site_col, date_format)

                        for day_idx in range(5):
                            if day_idx in week_dates:
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

                    # Ligne vide entre les semaines
                    row += 1

                # Calculer les stats pour ce trimestre
                stats = storage.get_statistics([schedule_id])
                if not stats.empty:
                    all_stats_for_total.append(stats)

        # 2. Créer l'onglet Total (vue simplifiée avec stats)
        if all_stats_for_total:
            # Combiner toutes les stats
            df_total = pd.concat(all_stats_for_total, axis=1)
            df_total = df_total.groupby(level=0, axis=1).sum()

            # Recalculer le total
            if 'Total' in df_total.columns:
                df_total = df_total.drop('Total', axis=1)
            df_total['Total'] = df_total.sum(axis=1)
            df_total = df_total.sort_values('Total', ascending=False)

            # Simplifier les "Majo"
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

            # Écrire l'onglet Total
            df_total_simplified.to_excel(writer, sheet_name='Total')

            # Formater
            worksheet = writer.sheets['Total']
            worksheet.write(0, 0, 'Site', header_format)
            for col_num, value in enumerate(df_total_simplified.columns.values, start=1):
                worksheet.write(0, col_num, value, header_format)

            # Ajuster les largeurs
            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, len(df_total_simplified.columns), 15)

    buffer.seek(0)
    return buffer
