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
def addEntry(event):
    data = request.form
    csvData = [v for k, v in data.items()]
    date = datetime.today().strftime('%Y-%m-%d')
    csvData.insert(1, date)
    csvRow = ",".join(csvData)

    message = ""
    # validation
    if csvData[0] == csvData[-1]: # payee == target
        message = "Payee cannot be the same as target"

    if message == "":
        with open(join(getStorePath(), event), 'a') as f:
            f.write('\n' + csvRow)
        
    return showEvent(event, message)


# GET
@app.route('/<event>')
def showEvent(event, message = ""):
    activeEvents = getActiveEvents()
    if event not in activeEvents:
        return index()

    pay, payers, lastRecords = parseStore(event)

    return render_template('event.html', activeEvents = activeEvents, \
        payTable = pay, people = payers, message = message, lastRecords = lastRecords, headers = getHeaders())


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
            if len(line) == 0 or line[0] == '#':
                continue
            
            tokens = line.split(',')
            tokens = [token.strip() for token in tokens]

            # first non-commented line
            if paylistName == None:
                if len(tokens) == 1:
                    raise Exception("No people in list")
                paylistName = tokens[0]
                payers = tokens[1:]
                # init payers
                pay = { payer: 0 for payer in payers }
                continue

            lastRecords.append(tokens)
            if len(lastRecords) == 6:
                lastRecords.pop()

            reportor = tokens[0]

            rate = getRate("YEN")
            currency = tokens[-3]
            amount = float(tokens[-2])
            amount *= rate[currency]
            target = tokens[-1]
            if target.lower() == 'shared':
                for k in pay.keys():
                    if k != reportor:
                        pay[k] += amount / (len(payers) - 1)
            else:
                pay[target] += amount

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
    return [f for f in listdir(storePath) if (isfile(join(storePath, f)) and '.csv' in f)]


def runServer():
    hostName = "0.0.0.0"
    serverPort = 8080
    serve(app, host=hostName, port=serverPort)
    # app.run(debug = False, host = hostName, port = serverPort )


if __name__ == "__main__":
    runServer()
