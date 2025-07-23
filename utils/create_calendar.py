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
    """
    Calculates the start and end dates based on a quarterly cycle.
    The quarters begin in January, April, July, and October.

    Returns:
        tuple: A tuple containing two datetime objects: (start_date, end_date)
    """

    quarter_start_months = [1, 4, 7, 10]

    current_date = datetime.today()
    current_year = current_date.year
    current_month = current_date.month

    # Determine the correct start month for the next quarter
    start_month = None
    start_year = current_year

    for month_val in quarter_start_months:
        if current_month < month_val:
            start_month = month_val
            break

    # If current_month is past the last quarter start,
    # the next quarter starts in January of the next year.
    if start_month is None:
        start_month = quarter_start_months[0]
        start_year += 1

    # Construct the start date
    start_date = datetime(start_year, start_month, 1)

    # The end date is the day before the next quarter's start date
    end_date = start_date + rd(months=3) - rd(days=1)

    return start_date, end_date

def create_date_dropdown_list(start_date, num_quarters=5):
    """
    Generates a list of dates, representing the start of subsequent quarters.

    Args:
        start_date (datetime): The initial date for the list.
        num_quarters (int): The number of quarters to include in the list.
                            Defaults to 5.

    Returns:
        list[datetime]: A list of datetime objects, each representing the start
                        of a quarter.
    """
    date_dropdown_list=[start_date]
    current_date = start_date

    for _ in range(num_quarters):
        current_date=current_date + rd(months=3)
        date_dropdown_list.append(current_date)
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
