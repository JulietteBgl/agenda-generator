import pandas as pd
from io import BytesIO


def to_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

def to_csv(df):
    return df.to_csv(index=False).encode('utf-8', errors='ignore')
