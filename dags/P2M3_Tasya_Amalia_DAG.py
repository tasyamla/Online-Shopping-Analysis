'''
=================================================
Milestone 3

Nama  : Tasya Amalia
Batch : FTDS-016-HCK

Program ini dibuat untuk melakukan automatisasi transform dan load data dari PostgreSQL ke ElasticSearch. Adapun dataset yang dipakai adalah dataset mengenai penjualan produk secara online selama tahun 2019.
=================================================
'''


import datetime as dt
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator

import pandas as pd
import psycopg2 as db
from elasticsearch import Elasticsearch
from sqlalchemy import create_engine


def csv_to_postgres():
    '''
    Fungsi ini untuk loading data dari file CSV ke dalam  PostgreSQL.
    
    '''
 
    database = "milestone_m3"
    username = "milestone_m3"
    password = "milestone_m3"
    host = "postgres"

    # Membuat URL koneksi PostgreSQL
    postgres_url = f"postgresql+psycopg2://{username}:{password}@{host}/{database}"

    # Gunakan URL 
    engine = create_engine(postgres_url)
    connection = engine.connect()

    df = pd.read_csv('/opt/airflow/dags/P2M3_Tasya_Amalia_to_postgres.csv')
    df.to_sql('table_m3', con=connection, if_exists='replace', index=False)


def postgres_to_csv():
    '''
    Fungsi ini untuk mengambil data dari PostgreSQL dan disimpan  dalam file CSV.

    '''

    database = "milestone_m3"
    username = "milestone_m3"
    password = "milestone_m3"
    host = "postgres"

    postgres_url = f"postgresql+psycopg2://{username}:{password}@{host}/{database}"
    engine = create_engine(postgres_url)
    connection = engine.connect()

    df = pd.read_sql_query("select * from table_m3", connection) 
    df.to_csv('/opt/airflow/dags/P2M3_Tasya_Amalia_Raw.csv', sep=',', index=False) 
    

def clean_data():
    ''' 
    Fungsi ini untuk membersihkan data yang terdiri dari, menghilangkan missing value, menghapus beberapa kolom,
    mengubah nama kolom dan melakukan beberapa transformasi pada kolom tertentu. Selain itu, terdapat penambahan kolom
    untuk penunjang analisis. Data hasil preprocessing akan disimpan kembali sebagai file CSV.

    Catatan:
    - 16 kolom yang memiliki missing value dihapus.
    - 1 kolom yang memiliki missing value disi dengan nilai '0'
    - Mengubah tipe data 'Date & Transaction_Date' menjadi Datetime
    - Mengubah tipe data 'Tenure_Months, Quantity, dan Discount_pct' menjadi Ineteger
    - Mengganti value pada kolom 'Gender' (M: Male, F: Female)
    - Menghapus beberapa kolom yang tidak diperlukan (Note: kolom 'Date' dihapus karena berulang dengan kolom Transaction_Date')
    - Membuat beberapa kolom baru untuk keperluan analisis pembuatan dahsboard
    - Nama kolom diubah menjadi huruf kecil dan menghilangkan karakter ':'

    '''
    # Loading Data
    df = pd.read_csv("/opt/airflow/dags/P2M3_Tasya_Amalia_Raw.csv")

    df['Discount_pct'].fillna(0, inplace = True)
    df.dropna(inplace=True)

    # Mengubah Tipe Kolom
    df['Date'] = pd.to_datetime(df['Date'])
    df['Transaction_Date'] = pd.to_datetime(df['Transaction_Date'])
    df['Tenure_Months'] = df['Tenure_Months'].astype(int)
    df['Quantity'] = df['Quantity'].astype(int)
    df['Discount_pct'] = df['Discount_pct'].astype(int)
    
    # Mengubah Value kolom Gender
    df['Gender'] = df['Gender'].replace({'M': 'Male', 'F': 'Female'})

    # Menghapus Beberapa Kolom
    df.drop(columns = ['CustomerID','Transaction_ID','Product_Description',
                   'Product_SKU','Date','Coupon_Code'],inplace=True)
    
    # Membuat Kolom Baru
    df['Total_Item_Price'] = df['Avg_Price'] * df['Quantity']
    df['Discount_Amount'] = df['Total_Item_Price'] * (df['Discount_pct'] / 100)
    df['Discounted_Price'] = df['Total_Item_Price'] - df['Discount_Amount']
    df['Net_Price'] = df['Discounted_Price'] + df['Delivery_Charges']
    df['Total_Spend'] = df['Net_Price']
    df['Revenue_Unit'] = df['Net_Price'] / df['Quantity']

    # Mengubah nama kolom jadi lowercase
    df.columns = df.columns.str.lower()

    # Menghilangkan karakter pada nama kolom 
    df.columns = df.columns.str.replace(':', '')

    df.to_csv('/opt/airflow/dags/P2M3_Tasya_Amalia_Data_Clean.csv', index=False)

    
def upload_to_elasticsearch():
    '''
    Fungsi ini untuk mengunggah data yang sudah di bersihkan dari file CSV ke Elasticsearch untuk dilakukan 
    proses selanjutnya, yaitu visualisasi data. 

    '''

    es = Elasticsearch("http://elasticsearch:9200")
    df = pd.read_csv('/opt/airflow/dags/P2M3_Tasya_Amalia_Data_Clean.csv')
    
    for i, r in df.iterrows():
        doc = r.to_dict()  
        res = es.index(index="table_m3", id=i+1, body=doc)
        
        
default_args = {
    'owner': 'Tasya', 
    'start_date': dt.datetime(2024, 6, 18),
}

with DAG(
    'P2M3_Tasya_Amalia_DAG', 
    default_args=default_args, 
    description='Tasya_Amalia_Milestone3',
    schedule_interval='30 6 * * *', # menjalankan airflow pada 06:30
    # catchup=False
) as dag:
    # task 1 load csv ke postgres
    Task : 1
    load_csv_task = PythonOperator(
        task_id='load_csv_to_postgres',
        python_callable=csv_to_postgres) 
    
    # task 2 data fetch task
    task: 2
    data_fetch_task = PythonOperator(
        task_id='data_fetch_task',
        python_callable=postgres_to_csv) 
    
    # task 3 cleaning data
    Task: 3
    cleaning_task = PythonOperator(
        task_id='cleaning_task',
        python_callable=clean_data)

    # Task 4 upload data ke elastic search
    upload_data = PythonOperator(
        task_id='upload_data',
        python_callable=upload_to_elasticsearch)

    # airflow workflow
    load_csv_task  >> data_fetch_task >> cleaning_task  >> upload_data

