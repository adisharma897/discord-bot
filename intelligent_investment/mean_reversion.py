import logging
import yfinance as yf
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from discord import SyncWebhook

# core python imports
import os
import sys

# add parent package to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.secret_manager import get_secret

webhook_url = get_secret('INTELLIGENT_INVESTMENT_DISCORD_WEBHOOK_URL')
postgres_url = get_secret('POSTGRES_URL')
market_cap_threshold = int(get_secret('INTELLIGENT_INVESTMENT_MARKET_CAP_THRESHOLD'))

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


engine = create_engine(postgres_url)
conn = engine.connect()


def apply_mean_recursion(stock_symbol, window, z_score_threshold, show_graphs=True):
    # Request data via Yahoo public API
    data = yf.Ticker(stock_symbol)

    df = data.history(start='2022-01-01')


    df[f'close_roll_mean_{window}'] = df.Close.rolling(window).mean()
    df[f'close_roll_std_{window}'] = df['Close'].rolling(window).std()


    # Calculate Z-scores
    df[f'z_score_{window}'] = (df['Close'] - df[f'close_roll_mean_{window}']) / df[f'close_roll_std_{window}']

    # Filter stocks with mean-reverting behavior based on Z-score
    df[f'mean_reverting_behaviour_{window}'] = 0
    df.loc[df[f'z_score_{window}'] > z_score_threshold, f'mean_reverting_behaviour_{window}'] = 1
    df.loc[df[f'z_score_{window}'] < -z_score_threshold, f'mean_reverting_behaviour_{window}'] = -1

    if show_graphs is True:

        fig = plt.figure(figsize=(16,4))

        #sns.lineplot(df_train.Close)
        sns.lineplot(df.Close)
        sns.lineplot(df[f'close_roll_mean_{window}'])
        #plt.plot(df[df[f'mean_reverting_behaviour_{window}'] == 1].Close, 'go', markersize=2)
        plt.plot(df[df[f'mean_reverting_behaviour_{window}'] == -1].Close, 'ro', markersize=2)

        ax2 = plt.twinx()
        sns.lineplot(df[f'z_score_{window}'], color="grey", ax=ax2)


    df['action'] = None

    df.loc[df[f'z_score_{window}'] <= -z_score_threshold, 'action'] = 'buy'
    df.loc[df[f'z_score_{window}'] >= 0, 'action'] = 'sell'



    closed_trades = []

    buys = []

    call_id = 1

    for index, row in df.iterrows():
        if row[f'action'] == 'buy':
            buys.append({
                'buy_date': index,
                'buy_price': row['Close']
            })

        if row[f'action'] == 'sell' and len(buys) > 0:
            for buy in buys:
                closed_trades.append({
                    'call_id': call_id,
                    'buy_date': buy['buy_date'],
                    'buy_price': buy['buy_price'],
                    'sell_price': row['Close'],
                    'sell_date': index,
                    'profit_perc': ((row['Close'] - buy['buy_price'])*100)/buy['buy_price'],
                    'time_taken': index - buy['buy_date']
                })
            buys = []
            call_id += 1

    closed_trades = pd.DataFrame(closed_trades)

    closed_trades_grp = closed_trades.groupby(['call_id']).agg({
        'buy_price': sum,
        'sell_price': sum,
        'time_taken': np.mean,
        'buy_date': min,
        'sell_date': max
    })
    closed_trades_grp['profit_perc'] = ((closed_trades_grp['sell_price'] - closed_trades_grp['buy_price']) * 100) / closed_trades_grp['buy_price']

    overall = ((closed_trades.sell_price.sum() - closed_trades.buy_price.sum()) * 100) / closed_trades.buy_price.sum()

    tat = (closed_trades_grp.sell_date - closed_trades_grp.buy_date).mean()

    calls = len(closed_trades.call_id.unique())

    is_open = False
    close = False

    if df[f'z_score_{window}'][-1] <= -z_score_threshold:
        is_open = True

    if (df[f'z_score_{window}'][-1] >= 0 ):
        close = True

    return closed_trades, closed_trades_grp, overall, tat, calls, is_open, close

def driver():
    query = '''select symbol, market_cap from stock_watchlist;'''

    mid_cap_stocks_df = pd.read_sql(text(query), conn)

    df_open_calls = pd.read_sql(text('select stock_symbol, quantity from test_stock_suggestion;'), conn)

    stock_performances = []

    for index, row in mid_cap_stocks_df.iterrows():
        if row['market_cap'] > market_cap_threshold:
            print(index)
            for window in [50]:
                symbol = row['symbol'] + '.NS'
                try:
                    trades, closed_calls, performance, avg_tat, call_count, is_open, close_trigger = apply_mean_recursion(symbol, window, 2, False)
                except Exception as e:
                    print('Error: ', index)
                    continue
                new_data = dict(row)
                new_data['window'] = window
                new_data['performance'] = performance
                new_data['avg_tat'] = avg_tat.days
                new_data['call_count'] = call_count
                new_data['is_open'] = is_open
                new_data['close_trigger'] = close_trigger

                if is_open is True:
                    print('Buy')
                    buy_stock(row['symbol'], 1)

                if (close_trigger is True) and (row['symbol'] in list(df_open_calls.stock_symbol.unique())):
                    print('Sell')
                    quantity = df_open_calls[df_open_calls.stock_symbol == row['symbol']].quantity.sum()
                    close_call(row['symbol'], quantity)

                stock_performances.append(new_data)

    stock_performances = pd.DataFrame(stock_performances)
    stock_performances.to_sql('history_stock_performances', conn, if_exists='append', index=False)
    conn.commit()

def close_call(symbol, quantity, price=None):
    if price is None:
        price = get_price(symbol)

    save_to_db(symbol, 'sell', price, quantity)
    m = f'''Congrats. Closed Call with {quantity} Quantity of {symbol} @ {price}'''
    send_message(m)

def buy_stock(symbol, quantity, price=None):

    if price is None:
        price = get_price(symbol)

    save_to_db(symbol, 'buy', price, quantity)
    m = f'''Bought {quantity} Quantity of {symbol} @ {price}'''
    send_message(m)

def save_to_db(symbol, action, price, quantity):
    if price is None:
        price = -1
    query = f'''
    insert into test_stock_suggestion(stock_symbol, action, price, quantity) values('{symbol}', '{action}', {price}, {quantity});
    '''
    r = conn.execute(text(query))
    conn.commit()

def get_price(symbol):
    stock = yf.Ticker(f'{symbol}.NS')
    return stock.info.get('currentPrice')

def send_message(m):
    webhook = SyncWebhook.from_url(webhook_url)
    webhook.send(m)


#driver()