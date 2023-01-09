# from DJDynamoDB import DJDB
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_bootstrap import Bootstrap
import random
import asyncio
from waitress import serve
from os import listdir
from os.path import isfile, join
from datetime import datetime

app = Flask(__name__)
Bootstrap(app)


# POST
@app.post('/<event>')
def modifyEntry(event):
    data = request.form
    action = data['action']

    errMessage = ""
    # ADD
    if (action == "ADD"):  
        errMessage = actionAdd(event, data)
    elif (action == "DEL"):
        errMessage = actionDel(event, data)
        
    return showEvent(event, errMessage)

def actionAdd(event, data):
    noDateData = [v.strip() for k, v in data.items() if k != "action"]
    csvData = noDateData.copy()
    date = datetime.today().strftime('%Y-%m-%d')
    csvData.insert(1, date)
    csvRow = ",".join(csvData)

    message = ""
    # validation
    if csvData[0] == csvData[-1]: # payee == target
        message = "Error: Payee cannot be the same as target"
    # prevent resubmit
    with open(join(getStorePath(), event), 'r') as f:
        for line in f.readlines():
            tokens = line.split(',')
            if (tokens[0:1] + tokens[2:]) == noDateData:
                message = "Error: Duplicated entry, " + line[:-1]
                break

    if message == "":
        with open(join(getStorePath(), event), 'a') as f:
            f.write('\n' + csvRow)

    return message
    
def actionDel(event, data):
    message = ""
    wLines = ""
    with open(join(getStorePath(), event), 'r') as f:
        for line in f.readlines():
            dataStr = data["toDel"]
            if line.strip() != dataStr:
                wLines += line

    with open(join(getStorePath(), event), 'w') as f:
        f.write(wLines)

    message = "Removed " + data["toDel"]

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
        

    return render_template('event.html', activeEvents = activeEvents, showingEvent = event, \
        payCondensed = payCondensed, payTable = pay, people = payers, message = message, lastRecords = lastRecords, headers = getHeaders())


@app.route('/')
def index():
    activeEvents = getActiveEvents()
    return render_template('index.html', 
                           activeEvents = activeEvents)

def getHeaders():
    return ["Payee", "Date", "Description", "Currency", "Amount", "Payer"]

def parseStore(event):
    paylistName = None
    payers = None
    pay = {}
    lastRecords = []
    with open(join(getStorePath(), event)) as f:
        for line in f.readlines():
            # skip lines
            if len(line) == 0 or (len(line) == 1 and line[0] == '\n') or line[0] == '#':
                continue
            
            tokens = line.split(',')
            tokens = [token.strip() for token in tokens]

            # first non-commented line
            if paylistName == None:
                if len(tokens) == 1:
                    raise Exception("No people in list")
                paylistName = tokens[0]
                payers = tokens[1:]
                # init payers (matrix)
                pay = { payer: {payee: 0 for payee in payers} for payer in payers }
                continue

            lastRecords.insert(0, tokens)
            if len(lastRecords) == 100:
                lastRecords.pop()

            reportor = tokens[0]

            rate = getRate("YEN")
            payee = tokens[0]
            currency = tokens[-3]
            amount = float(tokens[-2])
            amount *= rate[currency]
            target = tokens[-1]
            if target.lower() == 'shared':
                for k in pay.keys():
                    if k != reportor:
                        pay[k][payee] = round(pay[k][payee] + amount / (len(payers)), 2)
            else:
                pay[target][payee] = round(pay[target][payee] + amount, 2)

    return pay, payers, lastRecords

def getRate(toCurrency):
    rate = {}
    with open(join(getSettingPath(), 'rates.csv')) as f:
        for line in f.readlines():
            # skip
            if len(line) == 0 or line[0] == "#":
                continue
            
            tokens = line.split(',')
            assert len(tokens) == 3, "Incorrect format in rates setting files: " + len(tokens)
            if tokens[1] == toCurrency:
                rate[tokens[0]] = float(tokens[2])
    if toCurrency not in rate:
        rate[toCurrency] = 1
    return rate

def getSettingPath():
    return '/home/wesley/dev/ExpenseTracker/settings'

def getStorePath():
    return '/home/wesley/dev/ExpenseTracker/store'

def getActiveEvents():
    storePath = getStorePath()

    # removed the .csv suffix
    return [f[:-4] for f in listdir(storePath) if (isfile(join(storePath, f)) and '.csv' in f)]


def runServer():
    hostName = "0.0.0.0"
    serverPort = 8080
    serve(app, host=hostName, port=serverPort)
    # app.run(debug = False, host = hostName, port = serverPort )


if __name__ == "__main__":
    runServer()
