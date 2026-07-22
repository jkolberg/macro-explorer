import os
import pandas as pd
from pypyr import context

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

CONFIG_2020 = {
    'pop_age_0_14':['P12_003N','P12_027N','P12_004N','P12_028N','P12_005N','P12_029N'],
    'pop_age_15_24':['P12_006N','P12_007N','P12_030N','P12_031N','P12_008N','P12_009N','P12_010N','P12_032N','P12_033N','P12_034N'],
    'pop_age_25_34':['P12_011N','P12_035N','P12_012N','P12_036N'],
    'pop_age_35_44':['P12_013N','P12_037N','P12_014N','P12_038N'],
    'pop_age_45_54':['P12_015N','P12_039N','P12_016N','P12_040N'],
    'pop_age_55_64':['P12_017N','P12_041N','P12_018N','P12_019N','P12_042N','P12_043N'],
    'pop_age_65_74':['P12_020N','P12_021N','P12_044N','P12_045N','P12_022N','P12_046N'],
    'pop_age_75_84':['P12_023N','P12_047N','P12_024N','P12_048N'],
    'pop_age_85_plus':['P12_025N','P12_049N'],

    'gq_age_0_14':['PCO1_003N','PCO1_022N','PCO1_004N','PCO1_023N','PCO1_005N','PCO1_024N'],
    'gq_age_15_24':['PCO1_006N','PCO1_025N','PCO1_007N','PCO1_026N'],
    'gq_age_25_34':['PCO1_008N','PCO1_027N','PCO1_009N','PCO1_028N'],
    'gq_age_35_44':['PCO1_010N','PCO1_029N','PCO1_011N','PCO1_030N'],
    'gq_age_45_54':['PCO1_012N','PCO1_031N','PCO1_013N','PCO1_032N'],
    'gq_age_55_64':['PCO1_014N','PCO1_033N','PCO1_015N','PCO1_034N'],
    'gq_age_65_74':['PCO1_016N','PCO1_035N','PCO1_017N','PCO1_036N'],
    'gq_age_75_84':['PCO1_018N','PCO1_037N','PCO1_019N','PCO1_038N'],
    'gq_age_85_plus':['PCO1_020N','PCO1_039N'],
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

def calculate_occupancy(df):
    df['occupancy'] = df['hh'] / df['units']
    return df


def get_gq_rates(CensusApi, CONFIG_2020, county_ids, state_id):
    df = fetch_totals(CensusApi, CONFIG_2020, 2020, 'dhc', county_ids, state_id)

    age_groups = [c[len('gq_age_'):] for c in df.columns if c.startswith('gq_age_')]
    rates = pd.DataFrame(
        {age: df[f'gq_age_{age}'] / df[f'pop_age_{age}'] for age in age_groups}
    )
    rates = (
        rates.rename_axis('county_id')
        .reset_index()
        .melt(id_vars='county_id', var_name='age_group', value_name='gq_rate')
    )
    rates['age_group'] = 'ages_' + rates['age_group']
    return rates

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
        df = calculate_occupancy(df)
        df['year'] = year
        df = df.reset_index().rename(columns={'geoid':'county_id'})
        df_list.append(df)

    pd.concat(df_list).to_csv(f'{data_dir}/decennial_totals.csv', index=False)

    get_gq_rates(c, CONFIG_2020, county_ids, state_id).to_csv(f'{data_dir}/gq_rates.csv', index=False)