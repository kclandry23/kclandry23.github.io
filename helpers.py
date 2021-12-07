import os
import requests
import urllib.parse
from datetime import datetime

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key ="pk_e8d85689d8034046aa025ce81313c704" 
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None

def hlookup(cdate):
    # Handle intraday transactions:
    today = datetime.today().strftime("%Y%m%d")
    if today == cdate:
        quote = lookup("SPY")
        return quote["price"]
    # Handle historical transactions:
    else:
        # Contact API
        try:
            api_key ="pk_e8d85689d8034046aa025ce81313c704" 
            url = f"https://cloud.iexapis.com/stable/stock/spy/chart/date/{cdate}?chartByDay=true&chartCloseOnly=true&token={api_key}"
            print(url)
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException:
            return None

        # Parse response
        try:
            quote = response.json()
            return float(quote[0]["close"])
        except (KeyError, TypeError, ValueError):
            return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
