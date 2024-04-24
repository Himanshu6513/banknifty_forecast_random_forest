import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import warnings
import pytz
import os
import time
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import boto3
access_key = '#AWS access Key#'
secret_key = '#AWS secret Key#'
region_id = '#AWS Region#'
bucket_name = '#AWS Bucket name'
file_name = f'{file_in_the_bucket}.csv'
ist = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(ist).strftime('%H:%M')
less_than_1530 = current_time < '15:30'
def process_data(symbol_list,df):
  combined_data =df
  for symbol in symbol_list:
    try:
      initial=60
      data_retrieved = False
      while not data_retrieved and initial > 0:
        end_date = datetime.now() + timedelta(days=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        start_date = end_date - timedelta(days=initial)
        start_date_str = start_date.strftime('%Y-%m-%d')
        data = yf.download(symbol, interval='5m', start=start_date_str, end=end_date_str, progress=False)
        if not data.empty:
          data_retrieved = True
        else:
          initial -= 1

      data = data[data['Volume'] != 0]
      data.drop('Adj Close', axis=1, inplace=True)
      data.index = data.index.tz_localize(None)
      dummy=data['Close']
      dummy=dummy.reset_index().rename(columns={'Close': 'Prediction','Datetime':'Datetime_20min_add'})
      day_of_week_encoding = pd.get_dummies(data.index.dayofweek, prefix='day_of_week')
      day_of_week_encoding = day_of_week_encoding.reindex(data.index)
      data_with_encoding = pd.concat([data, day_of_week_encoding], axis=1)
      data['Date'] = data.index.day
      data['Hour'] = data.index.hour
      data['Minute'] = data.index.minute
      data['Datetime_20min_add'] = data.index + pd.Timedelta(minutes=30)
      data=data.reset_index()
      data = pd.merge(data, dummy, how='left', on='Datetime_20min_add')
      data.set_index('Datetime', inplace=True)
      data.drop('Datetime_20min_add',inplace=True,axis=1)
      del dummy
      interval_aliases = {
          '45min': '45T',
          '1hr': '1H',
          '2hr':'2H',
          '3hr': '3H',
          '1day': '1D',
          '2day': '2D',
          '3days': '3D',
          '7days': '7D',
          '10days': '10D',
          '15days': '15D',
          '30days': '30D',
          '45days': '45D',
          'All time': '100D'
      }
      moving_avg_alias = {
          '45min':9,
          '1hr':12,
          '2hr':24,
          '3hr':36,
          '1day':72,
          '2day': 144,
          '3days':216,
          '7days':504,
          '10days':720,
          '15days':1080,
          '30days':2160,
          '45days':3240,
          'All time':7200
      }
      for column in ['Open', 'High', 'Low', 'Close', 'Volume']:
        for interval, freq in moving_avg_alias.items():
          data[f'{column}_{interval.replace(" ", "_")}_EMA'] = data[column].ewm(span=freq, adjust=False).mean()
          data[f'{column}_{interval.replace(" ", "_")}_SMA'] = data[column].rolling(window=freq).mean()
      for column in ['Open', 'High', 'Low', 'Close', 'Volume']:
        for interval, freq in interval_aliases.items():
          data[f'Max_{column}_Last_{interval.replace(" ", "_")}'] = data[column].rolling(window=freq).max()
          data[f'Min_{column}_Last_{interval.replace(" ", "_")}'] = data[column].rolling(window=freq).min()
      day_of_week = data.index.dayofweek
      day_of_week_encoding = pd.get_dummies(day_of_week, prefix='day_of_week')
      day_of_week_encoding.index = data.index
      data = pd.concat([data, day_of_week_encoding], axis=1)
      del day_of_week_encoding
      del day_of_week
      data=data[data.index.time < pd.to_datetime("15:05:00").time()]
      data = data.fillna(method='bfill')
      data = data.dropna(axis=1, how='all')
      prediction_data=data[data['Prediction'].isnull()]
      train_data=data[data['Prediction'].notna()]
      X = prediction_data.drop(columns=['Prediction'])
      X_train=train_data.drop(columns=['Prediction'])
      y_train=train_data['Prediction']
      rf = RandomForestRegressor(n_estimators=100)
      rf.fit(X_train, y_train)
      predictions = rf.predict(X)
      predictions_df = pd.DataFrame({'Datetime': X.index, 'Prediction': predictions})
      predictions_df['Stock']=symbol
      predictions_df['Datetime'] = pd.to_datetime(predictions_df['Datetime'])
      predictions_df['Datetime'] += pd.Timedelta(minutes=30)
      combined_data = pd.concat([combined_data, predictions_df],axis=0,ignore_index=True)
    except Exception as e:
      print(e)
      continue
  return   combined_data
while less_than_1530:
  current_time = datetime.now(ist).strftime('%H:%M')
  less_than_1530 = current_time < '15:20'
  s3 = boto3.client('s3', aws_access_key_id=access_key,
                  aws_secret_access_key=secret_key,
                  region_name=region_id)
  combined_data=pd.DataFrame()
  symbol_list=['HDFCBANK.NS','ICICIBANK.NS','SBIN.NS','AXISBANK.NS','KOTAKBANK.NS','BANKBARODA.NS','PNB.NS','INDUSINDBK.NS','AUBANK.NS','FEDERALBNK.NS','BANDHANBNK.NS','IDFCFIRSTB.NS','RELIANCE.NS']
  warnings.filterwarnings("ignore")
  predictions = process_data(symbol_list,df=combined_data)
  try:
    s3.head_object(Bucket=bucket_name, Key=file_name)
    obj = s3.get_object(Bucket=bucket_name, Key=file_name)
    df = pd.read_csv(obj['Body'])
    df = df.reset_index(drop=True)
    predictions=predictions.reset_index(drop=True)
    combined_df = pd.concat([df, predictions],axis=0,ignore_index=True)
    csv_buffer =combined_df.to_csv(index=False)
    s3.put_object(Bucket=bucket_name, Key=file_name, Body=csv_buffer)
    obj = s3.get_object(Bucket=bucket_name, Key=file_name)
    new_combined_df = pd.read_csv(obj['Body'])
    new_combined_df = new_combined_df.reset_index(drop=True)
    new_combined_df = new_combined_df.drop_duplicates(subset=['Datetime', 'Stock'], keep='last')
    csv_buffer =new_combined_df.to_csv(index=False)
    s3.put_object(Bucket=bucket_name, Key=file_name, Body=csv_buffer)
  except Exception as e:
    print(e)
    continue
