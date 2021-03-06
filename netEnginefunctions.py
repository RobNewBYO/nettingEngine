## Functions
import requests
import base64
import datetime
import json
import pandas as pd
import numpy as np
from itsdangerous import URLSafeSerializer
from streamlit.report_thread import get_report_ctx
ctx = get_report_ctx()
session_id = ctx.session_id

def unencryptme(key, filename = 'oids'):
    s = URLSafeSerializer(key)
    csv = pd.read_csv(filename + "_encrypted.csv")
    market = s.loads(csv['strings'][0])
    pcc = s.loads(csv['strings'][1])
    epr = s.loads(csv['strings'][2])
    pwd = s.loads(csv['strings'][3])
    df = pd.DataFrame(list(zip(market, pcc, epr, pwd)), columns = ['market','pcc','epr','pwd'])
    return df

## Basic base64 encoding
def encodeme(message):
    message_bytes = message.encode('ascii')
    base64_bytes = base64.b64encode(message_bytes)
    base64_message = base64_bytes.decode('ascii')
    return base64_message

## Base64 encode creds
def getcreds(PCC, EPR, pwd):
    return encodeme(encodeme('V1:'+str(EPR)+':'+PCC+':AA') + ':' + encodeme(pwd))

## Process auth
def authme(PCC, EPR, pwd):
    auth_url = 'https://api.havail.sabre.com/v2/auth/token'
    header_dict = {'Authorization': 'Basic ' + getcreds(PCC, EPR, pwd), 'Content-Type':'application/x-www-form-urlencoded'}
    body = 'grant_type=client_credentials'
    
    r = requests.post(auth_url, headers = header_dict, data = body)
    
    if r.ok:
        print('Successful Auth')
        tkn = r.json()['access_token']
    else:
        print('Auth Failure :(')
        tkn = 'Auth failure'
    
    return tkn

## Submit BFM
def getresponse(PCC, tkn, Origin, Destination, Departure, TripLength, Currency, PaxType):
    with open('bfmrequest.json') as json_file: 
        req = json.load(json_file) 
    
    ## Adjust parameters in request
    bod = req['OTA_AirLowFareSearchRQ']
    bod['POS']['Source'][0]['PseudoCityCode'] = PCC
    out = bod['OriginDestinationInformation'][0]
    inb = bod['OriginDestinationInformation'][1]
    
    DepDate = datetime.datetime.strptime(Departure, '%Y-%m-%d')
    RetDate = DepDate + datetime.timedelta(days=TripLength)
    
    out['DepartureDateTime'] = DepDate.strftime('%Y-%m-%dT00:00:00')
    out['OriginLocation']['LocationCode'] = Origin
    out['DestinationLocation']['LocationCode'] = Destination
    
    inb['DepartureDateTime'] = RetDate.strftime('%Y-%m-%dT00:00:00')
    inb['OriginLocation']['LocationCode'] = Destination
    inb['DestinationLocation']['LocationCode'] = Origin
    
    bod['TravelerInfoSummary']['PriceRequestInformation']['CurrencyCode'] = Currency
    
    bod['TravelerInfoSummary']['AirTravelerAvail'][0]['PassengerTypeQuantity'][0]['Code'] = PaxType
    
    ## Request
    url = 'https://api.havail.sabre.com/v2/offers/shop'
    req_header_dict = {'Authorization': 'Bearer ' + tkn, 'Content-Type':'application/json', 'Accept-Encoding':'gzip'}
    
    res =  requests.post(url, headers = req_header_dict, json = req)
    if res.ok:
        print("Request successful")
    else:
        print("Request error")
    
    ## Process results to dataframe
    if res.ok:
        response = json.loads(res.text)
        
        groups = response['groupedItineraryResponse']['itineraryGroups']
        
        colnames = ['pcc','carrier','totalPrice','baseFare','tax','originAirport', 'destinationAirport', 'departureDateTime', 'returnDateTime', 'outb_flightnumbers', 'outb_duration', 'inb_flightnumbers', 'inb_duration', 'flightnumbers', 'numberOfSegments', 'cabinClass']
        results = None
        results = pd.DataFrame(columns = colnames)
        
        for g in groups:
            fares = g['itineraries']
            
            for x in fares:
                carrier = x['pricingInformation'][0]['fare']['validatingCarrierCode']
                cabinClass = 'Economy'
                numberOfSegments = 0
                outb_ref = x['legs'][0]['ref']
                outb_refs = []
                for y in response['groupedItineraryResponse']['legDescs'][outb_ref-1]['schedules']:
                    outb_refs.append(y['ref'])
                outb = []
                originAirport = None
                for n in outb_refs:
                    outb_temp = response['groupedItineraryResponse']['scheduleDescs'][n-1]
                    outb.append(outb_temp['carrier']['marketing'] + str(outb_temp['carrier']['marketingFlightNumber']))
                    if originAirport is None:
                        originAirport = outb_temp['departure']['airport']
                        departureDateTime = outb_temp['departure']['time']
                    destinationAirport = outb_temp['arrival']['airport']
                    numberOfSegments = numberOfSegments + 1
                outb = ','.join(outb)
                outbduration = response['groupedItineraryResponse']['legDescs'][outb_ref-1]['elapsedTime']
                inb_ref = x['legs'][1]['ref']
                inb_refs = []
                for y in response['groupedItineraryResponse']['legDescs'][inb_ref-1]['schedules']:
                    inb_refs.append(y['ref'])            
                inb = []
                returnDateTime = None
                for n in inb_refs:
                    inb_temp = response['groupedItineraryResponse']['scheduleDescs'][n-1]
                    inb.append(inb_temp['carrier']['marketing'] + str(inb_temp['carrier']['marketingFlightNumber']))
                    if returnDateTime is None:
                        returnDateTime = inb_temp['departure']['time']
                    numberOfSegments = numberOfSegments + 1
                inb = ','.join(inb)
                inbduration = response['groupedItineraryResponse']['legDescs'][inb_ref-1]['elapsedTime']
                flightnumbers = outb + "," + inb
                totalPrice = x['pricingInformation'][0]['fare']['totalFare']['totalPrice']
                baseFare = x['pricingInformation'][0]['fare']['totalFare']['equivalentAmount']
                tax = x['pricingInformation'][0]['fare']['totalFare']['totalTaxAmount']
                temp = pd.DataFrame([[PCC, carrier, totalPrice, baseFare, tax, originAirport, destinationAirport, departureDateTime, returnDateTime, outb, outbduration, inb, inbduration, flightnumbers, numberOfSegments, cabinClass]], columns = colnames)
                
                results = results.append(temp, ignore_index = True)
        
        ## merge in locations
        airp = pd.read_csv('locations.csv')[['AirportCode','CountryCode']]
        reg = pd.read_csv('iataRegions.csv')[['countryCode','regionCode']]
        
        locs = pd.merge(airp, reg, left_on = 'CountryCode', right_on = 'countryCode', how = 'left')
        locs = locs[['AirportCode','CountryCode', 'regionCode']]
        locs = locs.drop_duplicates(subset = ['AirportCode'])
        
        results['route'] = results['originAirport']+"-"+results['destinationAirport']
        
        results = pd.merge(results, locs, left_on = 'originAirport', right_on = 'AirportCode', how = 'left')
        results = results.drop(columns = ['AirportCode'])
        results.columns = results.columns.str.replace('CountryCode','originCountry')
        results.columns = results.columns.str.replace('regionCode','originRegion')
        
        results = pd.merge(results, locs, left_on = 'destinationAirport', right_on = 'AirportCode', how = 'left')
        results = results.drop(columns = ['AirportCode'])
        results.columns = results.columns.str.replace('CountryCode','destinationCountry')
        results.columns = results.columns.str.replace('regionCode','destinationRegion')
        
        results['tripType'] = np.where(results['originCountry']==results['destinationCountry'],'DOM', np.where(results['originCountry'].isin(['AU','NZ']) & results['destinationCountry'].isin(['AU','NZ']),'TT','INT'))
        
        return results

## Apply rules
def rulesmeup(df, dmnRules):
    keep_cols = ['pcc','carrier','totalPrice','baseFare','tax','originAirport', 'originCountry', 'originRegion', 'destinationAirport', 'destinationCountry', 'destinationRegion', 'departureDateTime', 'returnDateTime', 'outb_flightnumbers', 'outb_duration', 'inb_flightnumbers', 'inb_duration', 'flightnumbers', 'numberOfSegments', 'cabinClass']
    
    df = df[keep_cols]
    
    results = None
    
    ## Run rules
    for x in df.index:
        df_dict = df.iloc[x].to_dict()
        (status, newData) = dmnRules.decide(df_dict)
        if len(newData)>0:
            temp = newData[len(newData)-1]['Result']
            if results is None:
                results = pd.DataFrame([temp])
            else:
                results = results.append(pd.DataFrame([temp]), ignore_index = True)
    
    return results

## Calculate Net Price
def calculateNets(df, Currency, session_id = session_id):
    from forex_python.converter import CurrencyRates
    c = CurrencyRates().get_rate('USD', Currency)
    df['upfrontCommissionAmount'] = df['upfrontCommission']/100 * df['baseFare']
    df['backendCommissionAmount'] = df['backendCommission']/100 * df['baseFare']
    df['segmentEarningsAmount'] = (df['segmentEarnings']*c)*df['numberOfSegments']
    df['netPrice'] = round(df['totalPrice'] - (df['upfrontCommissionAmount'] + df['backendCommissionAmount'] + df['segmentEarningsAmount']),2)
    
    return df
    

## Overrides pivot_ui function to avoid the 'null value' issue.    
## https://github.com/nicolaskruchten/jupyter_pivottablejs/issues/52#issuecomment-528409060
def pivot_ui(df, **kwargs):
    import pivottablejs
    class _DataFrame(pd.DataFrame):
        def to_csv(self, **kwargs):
            return super().to_csv(**kwargs).replace("\r\n", "\n")
    return pivottablejs.pivot_ui(_DataFrame(df), **kwargs)

## Help text
help_text = '''
## Here are some notes on this tool

This tool can run identical BFM calls against a list of PCCs that you authorize first. The raw results are returned in a pivot table where they can be compared.

You can also upload a specific file containing commercials which is then used to net down the raw price (i.e. after commissions, segments etc).

The parameters you can specify are fairly limited at the moment - if you would like more added, please contact rob.new@byojet.com.

### Usage
1. Authorize one or more PCCs using the credentials found in the linked sheet. You can make a comma-delimited list to authorize multiple at one time.
2. (optional) Drop the 'nettingEngineDecisions.xlsx' file where it says to 'Add your commercials file'.
3. Define your search parameters and click run. Once complete you'll be shown a pivot table of the results. You can dive further into the results by adding the unused variables in the left column.

### Special notes
- Pax Type: default is ITX, which will also return the ADT fare. For domestic NZ, 'SPT' will return the Air NZ seat only fare, and will otherwise return ADT fares for other carriers. This tool has not yet been extended to CHD and INF pax types.
- FX: this uses the IATA rate to convert between currencies, triggered by a parameter in the BFM.

### Planned improvements
1. Parameter selection expansion.
2. Response scoring: find a way to measure how good each PCC is to create a prioritised list. 
'''