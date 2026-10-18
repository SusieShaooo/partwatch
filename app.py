import pandas as pd
import streamlit as st

st.set_page_config(page_title='PartWatch | Lifecycle Checker', page_icon='🔎', layout='wide')
st.title('PartWatch')
st.caption('Industrial part lifecycle checks · Prototype v0.1')
st.info('Demo data only. No manufacturer records or live lifecycle status are included. Unknown means not verified, NOT active.')

DEMO = pd.DataFrame([
    {'brand':'DEMOCO','part_number':'DEMO-PLC-100','status':'Discontinued','source_url':'','checked_at':'2026-10-18'},
    {'brand':'DEMOCO','part_number':'DEMO-DRIVE-200','status':'Phase-out','source_url':'','checked_at':'2026-10-18'},
    {'brand':'DEMOCO','part_number':'DEMO-HMI-300','status':'Active (demo)','source_url':'','checked_at':'2026-10-18'},
])

def clean(s):
    return str(s).strip().upper() if pd.notna(s) else ''

def match_parts(df):
    lookup = {(clean(r.brand),clean(r.part_number)):r for r in DEMO.itertuples(index=False)}
    rows=[]
    for r in df.itertuples(index=False):
        brand=clean(r.brand); part=clean(r.part_number)
        found=lookup.get((brand,part))
        rows.append({'brand':brand,'part_number':part,'status':found.status if found else 'Unknown / Not verified', 'source_url':found.source_url if found else '', 'checked_at':found.checked_at if found else ''})
    return pd.DataFrame(rows)

with st.expander('See sample CSV format',expanded=False):
    st.code('brand,part_number\nDEMOCO,DEMO-PLC-100\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123',language='csv')
    st.download_button('Download sample CSV', 'brand,part_number\nDEMOCO,DEMO-PLC-100\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n', 'sample_parts.csv','text/csv')
upload=st.file_uploader('Upload a CSV with brand and part_number columns',type=['csv'])
if upload is not None:
    try:
        incoming=pd.read_csv(upload,dtype=str,keep_default_na=False)
        if not {'brand','part_number'}.issubset(incoming.columns):
            st.error('CSV must contain brand and part_number columns.')
        elif len(incoming)>1000:
            st.error('Maximum 1,000 rows per upload for this prototype.')
        else:
            result=match_parts(incoming[['brand','part_number']])
            st.metric('Parts checked',len(result))
            st.dataframe(result,use_container_width=True,hide_index=True)
            st.download_button('Download results CSV',result.to_csv(index=False).encode('utf-8-sig'),'partwatch_results.csv','text/csv')
    except Exception as exc:
        st.error(f'Could not read CSV: {exc}')
st.divider()
st.caption('Before commercial launch: verify source licenses, replace synthetic demo records with permitted official data, add source URLs, audit logs, and customer privacy controls.')
