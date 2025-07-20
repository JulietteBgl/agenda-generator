import streamlit as st
from utils.export_agenda import to_excel
from utils.tools import format_schedule_for_visual


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
