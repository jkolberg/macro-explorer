import os
import pandas as pd

from macro_explorer.util import CensusApi

YEAR_CONFIG = {
    2000:['sf1', {
        'total_pop': ['P001001'],
        'gq': ['P037001'],
        'hh': ['H003002'],
        'units':['H001001'],
    }],
    2010: ['sf1', {
        'total_pop': ['P001001'],
        'gq': ['P042001'],
        'hh': ['H003002'],
        'units':['H001001'],
    }],
    2020: ['dhc', {
        'total_pop': ['P1_001N'],
        'gq': ['PCO1_001N'],
        'hh': ['H3_002N'],
        'units':['H1_001N'],
    }],
}

def fetch_totals(CensusApi,cols_dict, year, dataset, county_ids, state_id):
    """Pull a decennial table and return a DataFrame indexed by county geoid
    with one column per age group."""
    df = CensusApi.get_dec_data(cols_dict, year, 'county', dataset, county_ids, state_id)
    df = df.loc[df.geoid.isin(county_ids)].drop(columns=['name']).set_index('geoid')
    return df

def calculate_hhpop(df):
    df['hhpop'] = df['total_pop'] - df['gq']
    return df

def calculate_hhsz(df):
    df['hhsz'] = df['hhpop'] / df['hh']
    return df

def run_step(context):
    c = CensusApi(os.getenv(context['census_key']), timeout=90)
    data_dir = context['data_dir']
    county_ids = context['county_ids']
    state_id = context['state_id']
    # fetch the data and concat into single df adding a year column
    df_list = []
    for year, (dataset, cols_dict) in YEAR_CONFIG.items():
        df = fetch_totals(c, cols_dict, year, dataset, county_ids, state_id)
        df = calculate_hhpop(df)
        df = calculate_hhsz(df)
        df['year'] = year
        df_list.append(df)

    pd.concat(df_list).to_csv(f'{data_dir}/decennial_totals.csv')