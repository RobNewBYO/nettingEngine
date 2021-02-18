## Designed to take the output of a BFM and net everything down
import os
import platform
if platform.system()=='Windows':
    os.chdir('C:/Users/rob.new/Downloads/Applications/WPy64-3870/projects/nettingEngine/nettingEngine/')

import pandas as pd
import pyDMNrules
import netEnginefunctions as func
import streamlit as st
st.set_page_config(layout = 'wide')
import streamlit.components.v1 as components
import SessionState
from streamlit.report_thread import get_report_ctx
ctx = get_report_ctx()
session_id = ctx.session_id

# from pivottablejs import pivot_ui

## Inputs

@st.cache(allow_output_mutation=True)
def get_pccs(session_id = session_id):
    return[]

def get_results(PccList, Origin, Destination, Departure, TripLength, Currency, PaxType, session_id = session_id):
    results = None
    for x in PccList:
        print(x)
        if x['Token'] == 'Auth failure':
            print('Ignored ' + x['PCC'] + ' entry because of Auth Failure')
        else:
            tempresults = func.getresponse(x['PCC'], x['Token'], Origin, Destination, Departure, TripLength, Currency, PaxType)
            if len(tempresults)>0:
                print('Successfully retrieved results from ' + x['PCC'])
            if results is None:
                results = tempresults
            else:
                results = results.append(tempresults, ignore_index = True)
    
    return results

def main(df):
    st.sidebar.markdown('### Sections')
    info = st.sidebar.checkbox('Read me')
    config = st.sidebar.checkbox('Configurations', value = True)
    file_status = ''
    
    if config:
        st.sidebar.markdown('### Configuration')
       
        markets = st.sidebar.multiselect('markets', df['market'])
        
        for x in markets:
            ## check if already added
            if not any(d['market'] == x for d in get_pccs()):
                row = df.loc[df['market']==x].iloc[0]
                temp_tkn = func.authme(row['pcc'], row['epr'], row['pwd'])
                if temp_tkn == 'Auth failure':
                    st.sidebar.text(row['pcc'] + ' failed to authorize')
                else:
                    get_pccs().append({'market': row['market'], 'PCC':row['pcc'], 'Token': temp_tkn})    
    
        if len(get_pccs())==0:
            print("Detecting No PCCs configured for session_id " + session_id)
            st.sidebar.markdown('___No PCCs configured for search!___')
    
        ## Load rules file
        st.sidebar.markdown(
            """<a href="https://ppsdns-my.sharepoint.com/:x:/g/personal/rob_new_byojet_com/EcKjeJh-hB5HicL480bpAIgBhNa744XDU0BMpLl8vJo6hw?e=pXiYps" target="_blank">Current File</a>""",
            unsafe_allow_html=True)
        uploaded_file = st.sidebar.file_uploader("Add your commercials file")
        if uploaded_file is not None:
            dmnRules = pyDMNrules.DMN()
            status = dmnRules.load(uploaded_file)
            if 'errors' in status:
                file_status = uploaded_file.name + ' has errors' + status['errors']
                # sys.exit(0)
            else:
                file_status = uploaded_file.name + ' loaded'
        st.sidebar.write(file_status)
    
    
    ## Request compiler
    st.sidebar.markdown('### Search Parameters')
    Origin = st.sidebar.text_input('3-digit origin airport','BNE')
    Destination = st.sidebar.text_input('3-digit destination airport','SYD')
    Departure = st.sidebar.text_input('date in %Y-%m-%d format','2021-06-06')
    TripLength = st.sidebar.number_input('Trip Length', min_value = 1, max_value = 365, value = 7)
    Currency = st.sidebar.text_input('currency', 'AUD')
    PaxType = st.sidebar.text_input('pax type', 'ITX')
    run = st.sidebar.button('run')
    
    ## Body
    if info:
        help_text = func.help_text
    else:
        help_text = ""
        
    st.markdown(help_text)
    
    ## PCCs table
    pccs = pd.DataFrame(get_pccs())
    if config:
        st.markdown('## PCC Authorization')
        st.write(pccs)
    
    session_state = SessionState.get(results = pd.DataFrame())
    tempVals = 'totalPrice'
    if run:
        results = get_results(get_pccs(),  Origin, Destination, Departure, TripLength, Currency, PaxType)
        if 'loaded' in file_status:
            results = func.rulesmeup(results, dmnRules)
            results = func.calculateNets(results, Currency)
            tempVals = 'netPrice'
        session_state.results = results
        st.balloons()
    
    # if len(session_state.results)>0:
        
    t = func.pivot_ui(session_state.results, rows = ['carrier'], cols = ['pcc'], vals = [tempVals], aggregatorName = 'Minimum')
    st.markdown('## Results')
    with open(t.src) as t:
        components.html(t.read(), width = 1500, height = 1000, scrolling = True)

def checkmeout():
    key = st.sidebar.text_input('secret key', type = 'password')
    if len(key)>0:
        try:
            df = func.unencryptme(key)
        except:
            st.markdown("Incorrect key")
    exists = 'df' in locals()
    if exists:
        main(df)

checkmeout()

            



