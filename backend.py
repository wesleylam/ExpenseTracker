from os import listdir, mkdir, remove
from os.path import isfile, join, isdir, exists
from datetime import datetime
import pandas as pd
import os 
import re
import time

allCurrency = ['AUD', 'YEN', 'HKD']
unifyCurrency = "YEN"

def log(event, r):
    with open("./activity.log", 'a') as f:
        f.write(f'{datetime.now()}: {event} - {r.environ}\n{r.form}\n')


def getHeaders():
    return {k: v for k, v in zip(
        ["reportor","date", "item", "currency", "amount", "target", "attachment", "delete"],
        ["Reportor", "Date", "Description", "Currency", "Amount", "Payer", "Attachment (CLICK TO OPEN)", "Delete"]
    )}

def parseStore(event):
    payers = None
    pay = {}
    lastRecords = []
    
    fname = join(getStorePath(), event + '.csv')
    df = pd.read_csv(fname, index_col=0, keep_default_na=False)
    
    # GET FILE INFO
    info, preferredCurrencies = readInfo()
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
        amount *= rates[currency][unifyCurrency]
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

    return pay, payers, lastRecords, preferredCurrencies[event]

def getFullRates(event = None):
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
    rates_path = join(getSettingPath(), 'rates.csv')
    rates_df = pd.read_csv(rates_path, index_col=0)

    for i, row in rates_df.iterrows():
        tokens = i.split('-')
        assert len(tokens) == 2, "Incorrect format in rates setting files: " + len(tokens)
        if tokens[0] == fromCurrency:
            rate[tokens[1]] = float(row['multiplier'])
        elif tokens[1] == fromCurrency:
            rate[tokens[0]] = 1.0 / float(row['multiplier'])

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

def updateAllCurrency():
    rates_path = join(getSettingPath(), 'rates.csv')
    rates_df = pd.read_csv(rates_path, index_col=0)
    for c in ["AUD","YEN"]:
        if time.time() - rates_df.loc[f"{c}-HKD", "lastUpdate"] <= 30:
            continue
        rates_df.loc[f"{c}-HKD", "multiplier"] = getCurrency(c)
        rates_df.loc[f"{c}-HKD", "lastUpdate"] = time.time()
    rates_df.to_csv(rates_path)

def getCurrency(toHkd):
    lock_file = "rate_done.lock"
    os.system(f"curl https://www.google.com/search?q={toHkd}+to+hkd > fresh_rate.txt && touch {lock_file}")
    
    while not os.path.exists(lock_file):
        print("waiting for currency result " + toHkd)
        time.sleep(0.1)

    new_rate = None
    with open('fresh_rate.txt', 'r', errors='ignore') as f:
        for line in f.readlines():
            found = re.search(">([0-9.]+) Hong Kong Dollar", line)
            if found:
                new_rate = float(found.group(1))
                break

    # remove lock after finish
    os.remove(lock_file)

    return new_rate