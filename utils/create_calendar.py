import streamlit as st
from utils.export_agenda import to_excel
from utils.tools import schedule_to_dataframe


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
