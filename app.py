## Designed to take the output of a BFM and net everything down
import os
## os.chdir('C:/Users/rob.new/Downloads/Applications/WPy64-3870/projects/nettingEngine/')

import pandas as pd
# import json
# import pyDMNrules
import netEnginefunctions as func
# import datetime
# import requests
import streamlit as st
st.set_page_config(layout = 'wide')
import streamlit.components.v1 as components
from streamlit.report_thread import get_report_ctx
ctx = get_report_ctx()
session_id = ctx.session_id

# from pivottablejs import pivot_ui

## Inputs

@st.cache(allow_output_mutation=True)
def get_pccs(session_id = session_id):
    return[]

info = st.sidebar.checkbox('Read me')

auth_entry = st.sidebar.text_input('Auth Entry', '')
st.sidebar.markdown( 
    """<a href="https://ppsdns-my.sharepoint.com/:x:/g/personal/rob_new_byojet_com/EUnh714GBppKtvjt5XiOWsYBGkEX86wkIPDaKkmeO6dYlQ?e=eavipI" target="_blank">Auth Credentials</a>""", unsafe_allow_html=True,
    )

if st.sidebar.button('auth'):
    PCC = auth_entry.split("|")[0]
    EPR = auth_entry.split("|")[1]
    pwd = auth_entry.split("|")[2]
    temp_tkn = func.authme(PCC, EPR, pwd)
    get_pccs().append({'PCC':PCC, 'Token': temp_tkn})
    # PCC_default = ''
    # EPR_default = ''
    # pwd_default = ''


if info:
    help_text = func.help_text
else:
    help_text = ""
    
st.markdown(help_text)

st.markdown('## PCC Authorization')
pccs = pd.DataFrame(get_pccs())
st.write(pccs)


## Request compiler
Origin = st.sidebar.text_input('3-digit origin airport','BNE')
Destination = st.sidebar.text_input('3-digit destination airport','SYD')
Departure = st.sidebar.text_input('date in %Y-%m-%d format','2021-06-06')
TripLength = st.sidebar.number_input('Trip Length', min_value = 1, max_value = 365, value = 7)
Currency = st.sidebar.text_input('currency', 'AUD')
PaxType = st.sidebar.text_input('pax type', 'ITX')
if st.sidebar.button('run'):
    results = None
    for x in get_pccs():
        if x['Token'] == 'Auth failure':
            print('Ignored ' + x['PCC'] + ' entry because of Auth Failure')
        else:
            tempresults = func.getresponse(x['PCC'], x['Token'], Origin, Destination, Departure, TripLength, Currency, PaxType)
            if results is None:
                results = tempresults
            else:
                print('Successfully retrieved results from ' + x['PCC'])
                results = results.append(tempresults, ignore_index = True)
    
    t = func.pivot_ui(results, rows = ['carrier'], cols = ['pcc'], vals = ['totalamount'])
    st.markdown('## Results')
    with open(t.src) as t:
        components.html(t.read(), width = 1500, height = 1000, scrolling = True)



