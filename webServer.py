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

from backend import log, getStorePath, getActiveEvents, getAttachmentStorePath, \
  parseStore, getFullRates, getHeaders, updateAllCurrency, unifyCurrency

app = Flask(__name__)
Bootstrap(app)

# POST
@app.post('/newEvent')
def newEvent(data = None):
    if data == None:
        data = request.form
    infoStr = data['infoStr']
    tokens = [t.strip() for t in infoStr.split(',')]
    event = tokens[0]
        
    log("newEvent", request)

    if event in getActiveEvents():
        return index(message = f"Event \"{event}\" already exist!")
    
    infoFname = join(getStorePath(), 'info.txt')
    with open(infoFname, 'a') as f:
        f.write(infoStr + '\n')
    
    newFname = join(getStorePath(), event + '.csv')
    with open(newFname, 'w') as f:
        f.write("hash,reportor,date,item,currency,amount,target,attachment\n")

    return showEvent(event)

@app.post('/<event>')
def modifyEntry(event):
    data = request.form
    action = data['action']

    ## route to new event 
    if action == "NEWEVENT":
        return newEvent(data)

    log(event, request)

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
    df.loc[ms] = rowSeries
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
    updateAllCurrency()
    
    if event not in activeEvents:
        return index()

    # pay: k pay k2 > v amount
    pay, payers, lastRecords, preferredCurrency, infoStr = parseStore(event)

    # build dynamic pay details
    payCondensed = []
    for i, payer in enumerate(payers[:-1]):
        for payer2 in payers[i+1:]:
            amount = round(abs(pay[payer][payer2] - pay[payer2][payer]), 2)
            if pay[payer][payer2] > pay[payer2][payer]:
                payCondensed.append( (payer,payer2,amount) )
            else:
                payCondensed.append( (payer2,payer,amount) )

    shareList = [f"Shared: {x}, {y}" for x, y in itertools.combinations(payers, 2)] \
        + [f"Shared: {x}, {y}, {z}" for x, y, z in itertools.combinations(payers, 3)]
    return render_template(
        'event.html', activeEvents = activeEvents, showingEvent = event, 
        currencies = getFullRates(event), payCondensed = payCondensed, payTable = pay, people = payers, 
        share_option = shareList, 
        message = message, lastRecords = lastRecords, hideImg = len(lastRecords) > 10,
        originalCurrency = unifyCurrency, preferredCurrency = preferredCurrency, currentInfoStr = infoStr,
        today = datetime.today().strftime('%Y-%m-%d'), headers = getHeaders())


@app.route('/')
def index(message = ''):
    activeEvents = getActiveEvents()
    return render_template('index.html', 
                           activeEvents = activeEvents,
                           message = message)

def runServer(hostName, serverPort):
    serve(app, host=hostName, port=serverPort)
    # HTTPS with SSL
    # app.run(debug = False, host = hostName, port = serverPort, ssl_context=('cert.pem', 'key.pem') )


if __name__ == "__main__":
    hostName = "0.0.0.0"
    serverPort = 80
    runServer(hostName, serverPort)
