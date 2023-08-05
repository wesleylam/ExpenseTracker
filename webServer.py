# from DJDynamoDB import DJDB
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_bootstrap import Bootstrap
from waitress import serve
from os import listdir, mkdir, remove
from os.path import isfile, join, isdir, exists
from datetime import datetime
import pandas as pd
import time
import itertools

app = Flask(__name__)
Bootstrap(app)
allCurrency = ['AUD', 'YEN', 'HKD']

# POST
@app.post('/<event>')
def modifyEntry(event):
    data = request.form
    action = data['action']

    errMessage = ""
    # ADD
    if (action == "ADD"):  
        errMessage = actionAdd(event, request)
    elif (action == "DEL"):
        errMessage = actionDel(event, data)
        
    return showEvent(event, errMessage)

def actionAdd(event, request):
    data = request.form
    dataList = [v.strip() for k, v in data.items() if k != "action"]
    csvData = dataList.copy()
    csvRow = ",".join(csvData)

    message = ""
    # validation
    if csvData[0] == csvData[-1]: # payee == target
        message = "Error: Payee cannot be the same as target"
    # prevent resubmit
    fname = join(getStorePath(), event + '.csv')
    
    df = pd.read_csv(fname, index_col=0, na_filter=False, dtype=str)

    ms = int(time.time())
    rowSeries = pd.Series(data)
    # save attachment
    f = request.files['attachment']
    if f.filename != "":
        eventAStorePath = join(getAttachmentStorePath(), event)
        if not isdir(eventAStorePath):
            mkdir(eventAStorePath)
        newFilename = str(ms) + "." + f.filename.split(".")[-1]
        f.save(join(eventAStorePath, newFilename))
        rowSeries["attachment"] = newFilename
    else:
        rowSeries["attachment"] = ""
        
    rowSeries.name = ms
    df.at[ms] = rowSeries
    if (df.duplicated().any()):
        message = "Error: Duplicated entry, " + csvRow
    
    if message == "":
        df.to_csv(fname)

    return message
    
def actionDel(event, data):
    message = ""
    fname = join(getStorePath(), event + '.csv')
    df = pd.read_csv(fname, index_col=0, dtype=str, keep_default_na=False)
    
    row = df.loc[int(data["hash"])]
    if row["attachment"] != "":
        aPath = join(getAttachmentStorePath(), event, row["attachment"])
        if exists(aPath):
            remove(aPath)
    
    df = df.drop(int(data["hash"]), axis=0)
    df.to_csv(fname)
    
    message = "Removed " + data["hash"]

    return message 

# GET
@app.route('/<event>')
def showEvent(event, message = ""):
    activeEvents = getActiveEvents()
    
    if event not in activeEvents:
        return index()

    # pay: k pay k2 > v amount
    pay, payers, lastRecords = parseStore(event)

    # build dynamic pay details
    payCondensed = []
    for i, payer in enumerate(payers[:-1]):
        for payer2 in payers[i+1:]:
            amount = round(abs(pay[payer][payer2] - pay[payer2][payer]), 2)
            if pay[payer][payer2] > pay[payer2][payer]:
                payCondensed.append( (payer,payer2,amount) )
            else:
                payCondensed.append( (payer2,payer,amount) )
        
    return render_template(
        'event.html', activeEvents = activeEvents, showingEvent = event, 
        currencies = getFullRates(), payCondensed = payCondensed, payTable = pay, people = payers, 
        share_option = [f"Shared: {x}, {y}" for x, y in itertools.combinations(payers, 2)], 
        message = message, lastRecords = lastRecords, 
        today = datetime.today().strftime('%Y-%m-%d'), headers = getHeaders())


@app.route('/')
def index():
    activeEvents = getActiveEvents()
    return render_template('index.html', 
                           activeEvents = activeEvents)

def getHeaders():
    return {k: v for k, v in zip(
        ["reportor","date", "item", "currency", "amount", "target","attachment", "hash"],
        ["Reportor", "Date", "Description", "Currency", "Amount", "Payer", "Attachment", "Hash"]
    )}

def parseStore(event):
    payers = None
    pay = {}
    lastRecords = []
    
    fname = join(getStorePath(), event + '.csv')
    df = pd.read_csv(fname, index_col=0, keep_default_na=False)
    
    # GET FILE INFO
    info = readInfo()
    if event not in info:
        raise Exception("No event " + event)
    
    if len(info[event]) == 0:
        raise Exception("No people in list")
    payers = info[event]
    pay = { payer: {payee: 0 for payee in payers} for payer in payers }
    
    # GET RATES
    rates = getFullRates()

    # ITERATE RECORDS
    for i, row in df.iterrows():
        lastRecords.insert(0, row)
        if len(lastRecords) == 100:
            lastRecords.pop()

        payee = row['reportor']
        currency = row['currency']
        amount = row['amount']
        amount *= rates[currency]['YEN']
        target: str = row['target']
        
        comb_shared_prefix = "Shared: "
        # Shared ALL
        if target.lower() == 'shared':
            for k in pay.keys():
                if k != payee:
                    pay[k][payee] = round(pay[k][payee] + amount / (len(payers)), 2)
        # shared (NOT ALL)
        elif target.startswith(comb_shared_prefix):
            shared_payers = target.split(comb_shared_prefix)[1].split(", ")
            splitted_amount = round(amount / (len(shared_payers)), 2)
            for payer in shared_payers:
                if payer != payee:
                    pay[payer][payee] += splitted_amount
        # individual
        else:
            pay[target][payee] = round(pay[target][payee] + amount, 2)

    return pay, payers, lastRecords

def getFullRates():
    rates = {}
    for c in allCurrency:
        rates[c] = getRate(c)

    for fromC, rate in rates.items():
        for toC in allCurrency:
            if toC != fromC and toC not in rate:
                rates[fromC][toC] = deriveRate(fromC, toC, rates)

    return rates

def deriveRate(fromC, toC, rates):
    if toC in rates[fromC]:
        return rates[fromC][toC]

    fromRate = rates[fromC]
    for midToC, midToRate in fromRate.items():
        if midToC != fromC:
            return midToRate * deriveRate(midToC, toC, rates)

    raise Exception(f"cannot derive rate, {fromC} -> {toC}")


def getRate(fromCurrency):
    rate = {}
    with open(join(getSettingPath(), 'rates.csv')) as f:
        for line in f.readlines():
            # skip
            if len(line) == 0 or line[0] == "#":
                continue
            
            tokens = line.split(',')
            assert len(tokens) == 3, "Incorrect format in rates setting files: " + len(tokens)
            if tokens[0] == fromCurrency:
                rate[tokens[1]] = float(tokens[2])
            elif tokens[1] == fromCurrency:
                rate[tokens[0]] = 1.0 / float(tokens[2])
    if fromCurrency not in rate:
        rate[fromCurrency] = 1
    return rate

def getSettingPath():
    return '/home/wesley/dev/ExpenseTracker/settings'

def getStorePath():
    return '/home/wesley/dev/ExpenseTracker/store'

def getAttachmentStorePath():
    return '/home/wesley/dev/ExpenseTracker/static/attachments'

def getActiveEvents():
    storePath = getStorePath()

    # removed the .csv suffix
    return [f[:-4] for f in listdir(storePath) if (isfile(join(storePath, f)) and '.csv' in f)]


def readInfo():
    info = {}
    with open(join(getStorePath(), 'info.txt')) as f:
        for line in f.readlines():
            tokens = line.split(',')
            info[tokens[0]] = [t.strip() for t in tokens[1:]]
            
    return info

def runServer():
    hostName = "0.0.0.0"
    serverPort = 80
    serve(app, host=hostName, port=serverPort)
    # app.run(debug = False, host = hostName, port = serverPort )


if __name__ == "__main__":
    runServer()
