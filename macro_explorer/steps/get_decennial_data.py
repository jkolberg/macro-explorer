import os
import pandas as pd
from pypyr import context

from macro_explorer.util import CensusApi, compute_headship_rates, HEADSHIP_YEAR_CONFIG

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
    'pop_age_0_4':['P12_003N','P12_027N'],
    'pop_age_5_9':['P12_004N','P12_028N'],
    'pop_age_10_14':['P12_005N','P12_029N'],
    'pop_age_15_19':['P12_006N','P12_007N','P12_030N','P12_031N'],
    'pop_age_20_24':['P12_008N','P12_009N','P12_010N','P12_032N','P12_033N','P12_034N'],
    'pop_age_25_29':['P12_011N','P12_035N'],
    'pop_age_30_34':['P12_012N','P12_036N'],
    'pop_age_35_39':['P12_013N','P12_037N'],
    'pop_age_40_44':['P12_014N','P12_038N'],
    'pop_age_45_49':['P12_015N','P12_039N'],
    'pop_age_50_54':['P12_016N','P12_040N'],
    'pop_age_55_59':['P12_017N','P12_041N'],
    'pop_age_60_64':['P12_018N','P12_019N','P12_042N','P12_043N'],
    'pop_age_65_69':['P12_020N','P12_021N','P12_044N','P12_045N'],
    'pop_age_70_74':['P12_022N','P12_046N'],
    'pop_age_75_79':['P12_023N','P12_047N'],
    'pop_age_80_84':['P12_024N','P12_048N'],
    'pop_age_85_plus':['P12_025N','P12_049N'],

    'gq_age_0_4':['PCO1_003N','PCO1_022N'],
    'gq_age_5_9':['PCO1_004N','PCO1_023N'],
    'gq_age_10_14':['PCO1_005N','PCO1_024N'],
    'gq_age_15_19':['PCO1_006N','PCO1_025N'],
    'gq_age_20_24':['PCO1_007N','PCO1_026N'],
    'gq_age_25_29':['PCO1_008N','PCO1_027N'],
    'gq_age_30_34':['PCO1_009N','PCO1_028N'],
    'gq_age_35_39':['PCO1_010N','PCO1_029N'],
    'gq_age_40_44':['PCO1_011N','PCO1_030N'],
    'gq_age_45_49':['PCO1_012N','PCO1_031N'],
    'gq_age_50_54':['PCO1_013N','PCO1_032N'],
    'gq_age_55_59':['PCO1_014N','PCO1_033N'],
    'gq_age_60_64':['PCO1_015N','PCO1_034N'],
    'gq_age_65_69':['PCO1_016N','PCO1_035N'],
    'gq_age_70_74':['PCO1_017N','PCO1_036N'],
    'gq_age_75_79':['PCO1_018N','PCO1_037N'],
    'gq_age_80_84':['PCO1_019N','PCO1_038N'],
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

def get_headship_rates(CensusApi, YEAR_CONFIG, county_ids, state_id):
    fetch_fn = lambda cols_dict, year, dataset: fetch_totals(
        CensusApi, cols_dict, year, dataset, county_ids, state_id
    )
    headship_rates = compute_headship_rates(YEAR_CONFIG, fetch_fn=fetch_fn)

    # Add a 0 headship rate for the under-15 age group for each county so the
    # index aligns with the PUMS hhpop series (which includes 0-14).
    zeros = pd.DataFrame(
        0.0,
        index=pd.MultiIndex.from_product(
            [county_ids, ['age_0_14']], names=headship_rates.index.names
        ),
        columns=headship_rates.columns,
    )
    headship_rates = pd.concat([headship_rates, zeros]).sort_index()
    return headship_rates

def get_headship_gq_rates(CensusApi, CONFIG_2020, county_ids, state_id):
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

    get_headship_rates(c, HEADSHIP_YEAR_CONFIG, county_ids, state_id).to_csv(f'{data_dir}/dec_headship_rates.csv')
    get_gq_rates(c, GQ_2020_CONFIG, county_ids, state_id).to_csv(f'{data_dir}/gq_rates.csv', index=False)