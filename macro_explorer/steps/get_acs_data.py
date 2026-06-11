import os
import pandas as pd
from pypyr import context

from macro_explorer.steps.get_remi_hh_units import run_step
from macro_explorer.util import CensusApi


def run_step(context):
    cfg = context
    c = CensusApi(os.getenv(cfg['census_key']), timeout=90)
    state_id = cfg['state_id']
    counties = cfg['county_ids']
    
    variables_dict = {
    'total_pop':['B01001_001E'],
    'gq':['B26001_001E'],
    'hh':['B11001_001E'],
    'units':['B25001_001E']
    }

    df_out = pd.DataFrame()
    for year in list(range(2009,2020)) + list(range(2021,2025)):
        df = c.get_acs_data(variables_dict, year, 'county', 'acs1', counties, state_id)
        df = df.loc[df['geoid'].isin(counties)].copy()
        df['hhpop'] = df['total_pop'] - df['gq']
        df['hhsz'] = df['hhpop'] / df['hh']
        df['occupancy'] = df['hh'] / df['units']
        df['year'] = year
        df_out = pd.concat([df_out, df], ignore_index=True)

    df_out = df_out.rename(columns={'geoid':'county_id'})
    df_out.to_csv(f"{cfg['data_dir']}/acs_county_totals.csv", index=False)