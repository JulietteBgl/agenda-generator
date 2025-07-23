import streamlit as st
import calendar
from utils.export_agenda import to_excel
from dateutil.relativedelta import relativedelta as rd
import pandas as pd
from datetime import datetime

def format_schedule_for_visual(schedule):
    schedule["Date"] = pd.to_datetime(schedule["Date"])
    schedule = schedule[schedule["Date"].dt.weekday < 5]

    result = {}
    for _, row in schedule.iterrows():
        date = row["Date"]
        month_label = date.strftime('%B %Y')
        month_key = date.replace(day=1).date()
        weekday = date.strftime('%A')
        day_fr = {
            'Monday': 'Lundi',
            'Tuesday': 'Mardi',
            'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi',
            'Friday': 'Vendredi'
        }[weekday]

        display = {
            "date": date.strftime('%d/%m'),
            "aff1": row.get("Affectation 1", ""),
            "aff2": row.get("Affectation 2", "")
        }

        result.setdefault((month_key, month_label), {}).setdefault(date.isocalendar().week, {})[day_fr] = display

    return result

def get_start_and_end_date():
    current_date=datetime.today() + rd(months=1)

    current_year=current_date.year
    current_month=current_date.month
    start_date=datetime(current_year, current_month, 1)

    date_lag_3m=current_date + rd(months=3)
    year_lag_3m=date_lag_3m.year
    month_lag_3m = date_lag_3m.month
    day_end_date=calendar.monthrange(year_lag_3m, month_lag_3m)[1]
    end_date = datetime(year_lag_3m, month_lag_3m, day_end_date)

    return start_date, end_date

def create_date_dropdown_list(start_date):
    date_dropdown_list=[start_date]
    for _ in range(10):
        start_date=start_date + rd(months=1)
        date_dropdown_list.append(start_date)
    return date_dropdown_list

def create_calendar_editor(source, title, excel_name):
    st.subheader(title)
    edited_df = st.data_editor(
        source,
        column_config={"Date": st.column_config.TextColumn(disabled=True)},
        use_container_width=True,
        num_rows="dynamic",
        key=excel_name
    )
    st.download_button("Télécharger Excel", data=to_excel(edited_df), file_name=f"{excel_name}.xlsx")
    return

def create_visual_calendar(source, title):
    st.subheader(title)
    calendar = format_schedule_for_visual(source)
    day_labels = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']

    for (_, month_label), weeks in sorted(calendar.items()):
        st.markdown(f"### 📅 {month_label.capitalize()}")

        # En-tête des jours
        header_cols = st.columns(5)
        for i, day in enumerate(day_labels):
            with header_cols[i]:
                st.markdown(f"**{day}**")

        # Semaine par semaine
        for _, days in sorted(weeks.items()):

            cols = st.columns(5)
            for idx, day in enumerate(day_labels):
                with cols[idx]:
                    if day in days:
                        st.markdown(
                            f"""
                                <div style="
                                    border: 1px solid #ccc;
                                    border-radius: 6px;
                                    padding: 6px;
                                    min-height: 60px;
                                    background-color: #f9f9f9;
                                    margin-bottom: 0px;
                                ">
                                    <div style='font-size: 12px; color: gray; font-style: italic'>
                                        {days[day]['date']}
                                    </div>
                                    <div style='margin-top: 4px; font-size: 15px'>
                                        {days[day]['aff1']}
                                    </div>
                                    <div style='margin-top: 2px; font-size: 15px'>
                                        {days[day]['aff2']}
                                    </div>
                                </div>
                                """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            "<div style='border: 1px solid #eee; border-radius: 6px; min-height: 60px; "
                            "background-color: #f0f0f0; color: #bbb; padding: 6px'>-</div>",
                            unsafe_allow_html=True
                        )

            st.markdown('</div>', unsafe_allow_html=True)
    return
