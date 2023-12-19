from os import listdir, mkdir, remove
from os.path import isfile, join, isdir, exists
from datetime import datetime
import pandas as pd

allCurrency = ['AUD', 'YEN', 'HKD']

def log(event, r):
    with open("./activity.log", 'a') as f:
        f.write(f'{datetime.now()}: {event} - {r.environ}\n{r.form}\n')


def getHeaders():
    return {k: v for k, v in zip(
        ["reportor","date", "item", "currency", "amount", "target", "attachment", "delete"],
        ["Reportor", "Date", "Description", "Currency", "Amount", "Payer", "Attachment", "Delete"]
    )}

def parseStore(event):
    payers = None
    pay = {}
    lastRecords = []
    
    fname = join(getStorePath(), event + '.csv')
    df = pd.read_csv(fname, index_col=0, keep_default_na=False)
    
    # GET FILE INFO
    info, preferredCurrency = readInfo()
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

def getFullRates(event = None):
    rates = {}

    if event is not None:
        info, preferredCurrency = readInfo()
        if event in preferredCurrency:
            pc = preferredCurrency[event]
            if pc in allCurrency:
                # add preferred first
                rates[pc] = 1

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
            # clean input
            tokens = [t.strip() for t in tokens]
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
    preferredCurrency = {}
    with open(join(getStorePath(), 'info.txt')) as f:
        for line in f.readlines():
            tokens = line.split(',')
            info[tokens[0]] = [t.strip() for t in tokens[2:]]

            pc = tokens[1].strip()
            preferredCurrency[tokens[0]] = pc
            if pc not in allCurrency:
                raise Exception("Invalid currency: " + pc)
            
    return info, preferredCurrency