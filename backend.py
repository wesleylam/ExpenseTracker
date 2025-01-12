from os import listdir, mkdir, remove
from os.path import isfile, join, isdir, exists
from datetime import datetime
import csv
import os 
import re
import time

allCurrency = ['AUD', 'YEN', 'HKD']
unifyCurrency = "YEN"
STORE_PATH = './store'


def custom_read_csv(file_path):
    """
    Reads a CSV file and returns a dictionary where each key is the value of the first column
    and the value is another dictionary containing the rest of the row's data. Missing values
    are filled with None.
    
    :param file_path: The path to the CSV file
    :return: A dictionary representing the CSV data
    """
    data = {}
    cols = []
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames  # Get the list of headers from the CSV file
        
        for row in reader:
            # Extract the first column (assuming it's always the first key in the row)
            cols = list(row.keys())
            first_column = cols[0]
            key = row.pop(first_column)
            
            # Fill missing values with None
            complete_row = {header: row.get(header, None) for header in headers if header != first_column}
            
            data[key] = complete_row
    return data, cols


def custom_to_csv(data, file_path, first_column_name=''):
    """
    Writes a dictionary to a CSV file. The keys of the outer dictionary become the specified first column,
    and the keys of the inner dictionaries become the remaining columns. Missing values are filled with None.
    
    :param data: The dictionary to write to the CSV file
    :param file_path: The path to the CSV file
    :param first_column_name: The name of the column to use as the key for the dictionary (default is 'id')
    """
    # Determine the headers
    headers = set()
    for key, value in data.items():
        headers.update(value.keys())
    
    # Convert headers to a sorted list for consistent ordering
    headers = sorted(headers)
    
    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        
        # Write the header row
        writer.writerow([first_column_name] + headers)
        
        # Write the data rows
        for key, value in data.items():
            row = [key] + [value.get(header, None) for header in headers]
            writer.writerow(row)

def checkDup(entryDict, records):
    for ms, entryRow in records.items():
        dup = True
        for k, v in entryDict.items():
            if entryRow[k] != v:
                ## continue if any is not equal
                dup = False
                break
        if dup:
            return True
    return False
        

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
    df, cols = custom_read_csv(fname)
    
    # GET FILE INFO
    info, preferredCurrencies, infoStrs = readInfo()
    if event not in info:
        raise Exception("No event " + event)
    
    if len(info[event]) == 0:
        raise Exception("No people in list")
    payers = info[event]
    pay = { payer: {payee: 0 for payee in payers} for payer in payers }
    
    # GET RATES
    rates = getFullRates()

    # ITERATE RECORDS
    for i, row in df.items():
        row['ms'] = i
        lastRecords.insert(0, row)
        if len(lastRecords) == 100:
            lastRecords.pop()

        payee = row['reportor']
        currency = row['currency']
        amount = float(row['amount'])
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

    return pay, payers, lastRecords, preferredCurrencies[event], infoStrs[event]

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
    rates_df, cols = custom_read_csv(rates_path)

    for i, row in rates_df.items():
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
    return './settings'

def setStorePath(newPath):
    global STORE_PATH
    STORE_PATH = newPath

def getStorePath():
    global STORE_PATH
    return STORE_PATH

def getAttachmentStorePath():
    return './attachments'

def getActiveEvents():
    storePath = getStorePath()

    # removed the .csv suffix
    return [f[:-4] for f in listdir(storePath) if (isfile(join(storePath, f)) and '.csv' in f)]


def readInfo():
    info = {}
    infoStrs = {}
    preferredCurrency = {}
    with open(join(getStorePath(), 'info.txt')) as f:
        for line in f.readlines():
            tokens = line.split(',')
            infoStrs[tokens[0]] = line.strip()
            info[tokens[0]] = [t.strip() for t in tokens[2:]]

            pc = tokens[1].strip()
            preferredCurrency[tokens[0]] = pc
            if pc not in allCurrency:
                raise Exception("Invalid currency: " + pc)
            
    return info, preferredCurrency, infoStrs

def updateAllCurrency():
    rates_path = join(getSettingPath(), 'rates.csv')
    rates_df, cols = custom_read_csv(rates_path)
    for c in ["AUD","YEN"]:
        # ONLY update every 30 mins
        if time.time() - float(rates_df[f"{c}-HKD"]["lastUpdate"]) <= 1800:
            continue
        rates_df[f"{c}-HKD"]["multiplier"] = getCurrency(c)
        rates_df[f"{c}-HKD"]["lastUpdate"] = time.time()
        
    custom_to_csv(rates_df, rates_path, cols[0])

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