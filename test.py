import os
import datetime
import requests
import urllib.parse
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, hlookup

# Parse response
def parse(response):
    quote = response.json()
    print()
    print(quote)
    print()
    return float(quote[0]['close'])


date = datetime.date(2020,12,11)

cdate = date.strftime('%Y%m%d')
print(cdate)
symbol = "tsla" 

# Contact API
api_key ="pk_e8d85689d8034046aa025ce81313c704" 
url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/chart/date/{cdate}?chartByDay=true&chartCloseOnly=true&token={api_key}"
response = requests.get(url)
response.raise_for_status()
close = parse(response)

print(close)