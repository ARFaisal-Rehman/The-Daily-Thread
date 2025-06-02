# trends.py
import pandas as pd
import re # For basic text processing

# --- Existing Functions (ensure these are present and correct as per previous successful steps) ---
def load_fashion_data_xls(file_path):
    """Loads data from the fashion_data_2018_2022.xls file."""
    try:
        df = pd.read_excel(file_path)
        df.columns = [str(col).lower().replace(' ', '_').replace('-', '_') for col in df.columns]
        if 'product_id' in df.columns: # Ensure product_id is string if it's used as a key later
            df['product_id'] = df['product_id'].astype(str)
        return df
    except Exception as e:
        print(f"Error loading Excel file {file_path}: {e}")
        return pd.DataFrame()

def load_mock_fashion_data_csv(file_path):
    """Loads data from the mock_fashion_data_uk_us.csv file."""
    try:
        df = pd.read_csv(file_path)
        df.columns = [str(col).lower().replace(' ', '_').replace('(', '').replace(')', '') for col in df.columns]
        return df
    except FileNotFoundError:
        # print(f"Warning: File {file_path} not found. Proceeding without this data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return pd.DataFrame()

def get_top_purchased_items(fashion_df, mock_df, top_n=10):
    purchases_list = []
    if not fashion_df.empty and 'product_name' in fashion_df.columns and 'sales_count' in fashion_df.columns:
        fashion_df['sales_count'] = pd.to_numeric(fashion_df['sales_count'], errors='coerce').fillna(0)
        top_fashion_items = fashion_df.groupby('product_name')['sales_count'].sum().nlargest(top_n)
        for item, count in top_fashion_items.items():
            purchases_list.append({'product_name': item, 'total_sales': count, 'source': 'fashion_data'})

    if not mock_df.empty and 'product' in mock_df.columns and 'items_sold' in mock_df.columns: # Corrected column name
        mock_df['items_sold'] = pd.to_numeric(mock_df['items_sold'], errors='coerce').fillna(0)
        top_mock_items = mock_df.groupby('product')['items_sold'].sum().nlargest(top_n) # Corrected column name
        for item, count in top_mock_items.items():
            purchases_list.append({'product_name': item, 'total_sales': count, 'source': 'mock_data'})

    if not purchases_list: return pd.DataFrame()
    combined_df = pd.DataFrame(purchases_list)
    if combined_df.empty: return pd.DataFrame()
    return combined_df.groupby('product_name')['total_sales'].sum().nlargest(top_n).reset_index()


def get_item_trends(fashion_df, items_to_track):
    if fashion_df.empty or not all(col in fashion_df.columns for col in ['year_of_sale', 'month_of_sale', 'product_name', 'sales_count']):
        # print("Fashion DataFrame is missing required columns for trend analysis (year_of_sale, month_of_sale, product_name, sales_count).")
        return pd.DataFrame()

    fashion_df_processed = fashion_df.copy()
    fashion_df_processed.loc[:, 'sales_count'] = pd.to_numeric(fashion_df_processed['sales_count'], errors='coerce').fillna(0)

    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    if fashion_df_processed['month_of_sale'].dtype == 'object':
        fashion_df_processed.loc[:, 'month_of_sale_num'] = fashion_df_processed['month_of_sale'].str.strip().str.slice(0,3).map(month_map)
    else:
        fashion_df_processed.loc[:, 'month_of_sale_num'] = fashion_df_processed['month_of_sale']

    fashion_df_processed.loc[:, 'month_of_sale_num'] = pd.to_numeric(fashion_df_processed['month_of_sale_num'], errors='coerce')
    fashion_df_processed.loc[:, 'year_of_sale'] = pd.to_numeric(fashion_df_processed['year_of_sale'], errors='coerce')
    fashion_df_processed.dropna(subset=['year_of_sale', 'month_of_sale_num'], inplace=True)

    if fashion_df_processed.empty: # Check after potential drops
        # print("DataFrame became empty after processing dates for item trends.")
        return pd.DataFrame()

    fashion_df_processed.loc[:, 'year_of_sale'] = fashion_df_processed['year_of_sale'].astype(int)
    fashion_df_processed.loc[:, 'month_of_sale_num'] = fashion_df_processed['month_of_sale_num'].astype(int)

    fashion_df_processed.loc[:, 'date'] = pd.to_datetime(
        fashion_df_processed['year_of_sale'].astype(str) + '-' +
        fashion_df_processed['month_of_sale_num'].astype(str) + '-01',
        errors='coerce'
    )

    fashion_df_processed = fashion_df_processed.dropna(subset=['date'])
    if fashion_df_processed.empty: return pd.DataFrame()

    if 'category' in fashion_df_processed.columns:
        fashion_df_filtered = fashion_df_processed.loc[
            fashion_df_processed['product_name'].isin(items_to_track) |
            fashion_df_processed['category'].isin(items_to_track)
        ].copy()
    else:
        fashion_df_filtered = fashion_df_processed.loc[fashion_df_processed['product_name'].isin(items_to_track)].copy()

    if fashion_df_filtered.empty:
        return pd.DataFrame()

    item_trends = fashion_df_filtered.groupby([pd.Grouper(key='date', freq='ME'), 'product_name'])['sales_count'].sum().reset_index()
    if item_trends.empty: return pd.DataFrame()
    trend_pivot = item_trends.pivot(index='date', columns='product_name', values='sales_count').fillna(0)

    return trend_pivot

def generate_what_people_are_buying_charts():
    fashion_df = load_fashion_data_xls("fashion_data_2018_2022.xls")
    mock_df = load_mock_fashion_data_csv("mock_fashion_data_uk_us.csv")
    top_items_data = get_top_purchased_items(fashion_df, mock_df)

    example_items = []
    fashion_df_for_trends = fashion_df

    if not fashion_df.empty:
        if 'category' in fashion_df.columns and fashion_df['category'].nunique() > 0 :
            example_items = fashion_df['category'].value_counts().nlargest(3).index.tolist()
        elif 'product_name' in fashion_df.columns and fashion_df['product_name'].nunique() > 0:
            example_items = fashion_df['product_name'].value_counts().nlargest(3).index.tolist()

    if not example_items :
        example_items = ["Placeholder Item A", "Placeholder Item B", "Placeholder Item C"]
        fashion_df_for_trends = pd.DataFrame({
             'year_of_sale': [2023, 2023, 2023, 2023, 2023, 2023],
             'month_of_sale': [1, 2, 1, 2, 1, 2],
             'product_name': ["Placeholder Item A", "Placeholder Item A", "Placeholder Item B", "Placeholder Item B", "Placeholder Item C", "Placeholder Item C"],
             'sales_count': [10,12,5,6,8,9], 'category': ["Category A", "Category A", "Category B", "Category B", "Category C", "Category C"]})

    item_trends_data = get_item_trends(fashion_df_for_trends, example_items)

    return {"top_items": top_items_data.to_dict(orient='records') if not top_items_data.empty else [],
            "item_trends": item_trends_data.reset_index().to_dict(orient='records') if not item_trends_data.empty else []}

def load_brand_equity_data(file_path):
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        original_columns = df.columns.tolist()
        df.columns = [str(col).lower().replace(' ', '_').replace('-', '_').replace('$', '').replace('.', '') for col in df.columns]

        if 'brand' not in df.columns:
            if 'brand_name' in df.columns: df.rename(columns={'brand_name': 'brand'}, inplace=True)
            elif 'brandname' in df.columns: df.rename(columns={'brandname': 'brand'}, inplace=True)
            elif len(df.columns) > 0 and isinstance(df.columns[0], str) and ('brand' in df.columns[0].lower()):
                df.rename(columns={df.columns[0]: 'brand'}, inplace=True)

        id_vars_options = [['brand', 'segment', 'coo', 'roo'], ['brand', 'segment', 'coo'], ['brand', 'segment'], ['brand']]
        id_vars_to_use = next((opt for opt in id_vars_options if all(col in df.columns for col in opt)), ['brand'] if 'brand' in df.columns else [])

        if not id_vars_to_use or 'brand' not in id_vars_to_use :
            # print(f"Brand column could not be identified. Available columns: {df.columns.tolist()}")
            return pd.DataFrame()

        years = sorted(list(set(int(re.search(r'(\d{4})', col).group(1)) for col in df.columns if re.search(r'(\d{4})', col))))

        df_melted_list = []
        if years:
            for year_int in years:
                year_str = str(year_int)
                rank_col_name = next((col for col in df.columns if (f'rank{year_str}' in col or f'rank_{year_str}' in col) and 'equity' not in col), None)
                equity_col_name = next((col for col in df.columns if (f'equity_value__{year_str}' in col or f'equity{year_str}' in col or (f'equity_value_$_million_{year_str}' in col))), None)

                if rank_col_name:
                    current_cols_to_select = id_vars_to_use + [rank_col_name]
                    if equity_col_name and equity_col_name in df.columns:
                        current_cols_to_select.append(equity_col_name)

                    temp_df = df[current_cols_to_select].copy()
                    temp_df['year'] = year_int
                    temp_df.rename(columns={rank_col_name: 'brand_equity_ranking'}, inplace=True)
                    if equity_col_name and equity_col_name in df.columns: # Check if equity_col_name is valid and exists
                         temp_df.rename(columns={equity_col_name: 'equity_value'}, inplace=True)
                    # elif equity_col_name: # This case might be redundant if equity_col_name must be in df.columns
                    #      temp_df.rename(columns={equity_col_name: 'equity_value'}, inplace=True)
                    else:
                        temp_df['equity_value'] = pd.NA # Use pd.NA for missing numeric/object data
                    df_melted_list.append(temp_df)

        if not df_melted_list: # Fallback to check if data is already somewhat long
             if 'year' in df.columns and ('brand_equity_ranking' in df.columns or any('rank' in col for col in df.columns)):
                 rank_col_to_use = 'brand_equity_ranking' if 'brand_equity_ranking' in df.columns else next((col for col in df.columns if 'rank' in col and 'equity' not in col), None)
                 if rank_col_to_use:
                    cols_for_long_format = id_vars_to_use + ['year', rank_col_to_use]
                    if 'equity_value' in df.columns: cols_for_long_format.append('equity_value')
                    # Ensure all selected columns actually exist
                    cols_for_long_format = [col for col in cols_for_long_format if col in df.columns]
                    final_df = df[cols_for_long_format].copy()
                    if rank_col_to_use != 'brand_equity_ranking':
                        final_df.rename(columns={rank_col_to_use: 'brand_equity_ranking'}, inplace=True)
                    return final_df
                 else:
                    # print("Could not parse brand equity data into long format. No suitable rank column found with 'year'.")
                    return pd.DataFrame()
             else:
                # print(f"Could not melt data. Original columns: {original_columns}, Standardized: {df.columns.tolist()}")
                return pd.DataFrame()

        final_df = pd.concat(df_melted_list, ignore_index=True)
        return final_df

    except Exception as e:
        # print(f"Error loading or processing Excel file {file_path}: {e}")
        return pd.DataFrame()

def load_retail_sales_data(file_path):
    try:
        df = pd.read_csv(file_path)
        df.columns = [str(col).lower().replace(' ', '_').replace('(', '').replace(')', '') for col in df.columns]
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return pd.DataFrame()

def get_brand_popularity_over_time(brand_equity_df, top_n_brands=5):
    if brand_equity_df.empty: return pd.DataFrame()
    required_cols = ['brand', 'year', 'brand_equity_ranking']
    missing_cols = [col for col in required_cols if col not in brand_equity_df.columns]
    if missing_cols:
        # print(f"BEQ DataFrame missing for popularity: {missing_cols}. Cols: {brand_equity_df.columns.tolist()}")
        return pd.DataFrame()

    brand_equity_df['year'] = pd.to_numeric(brand_equity_df['year'], errors='coerce')
    brand_equity_df['brand_equity_ranking'] = pd.to_numeric(brand_equity_df['brand_equity_ranking'], errors='coerce')
    brand_equity_df.dropna(subset=['year', 'brand_equity_ranking', 'brand'], inplace=True)
    brand_equity_df['brand'] = brand_equity_df['brand'].astype(str).str.strip()
    if brand_equity_df.empty: return pd.DataFrame()

    latest_year = brand_equity_df['year'].max()
    if pd.isna(latest_year): return pd.DataFrame()

    top_brands_latest_year = brand_equity_df[brand_equity_df['year'] == latest_year].nsmallest(top_n_brands * 2, 'brand_equity_ranking')['brand'].unique()[:top_n_brands].tolist()
    top_brands_to_plot = []

    if top_brands_latest_year and len(top_brands_latest_year) >= top_n_brands // 2: # Heuristic: if we get at least half, use them
        top_brands_to_plot = top_brands_latest_year
    else:
        brand_year_counts = brand_equity_df.groupby('brand')['year'].nunique()
        if not brand_year_counts.empty:
            most_frequent_brands = brand_year_counts.nlargest(top_n_brands * 3).index
            if not most_frequent_brands.empty:
                top_brands_overall_avg = brand_equity_df[brand_equity_df['brand'].isin(most_frequent_brands)].groupby('brand')['brand_equity_ranking'].mean().nsmallest(top_n_brands).index.tolist()
                if top_brands_overall_avg: top_brands_to_plot = top_brands_overall_avg

    if not top_brands_to_plot:
        top_brands_fallback = brand_equity_df.groupby('brand')['brand_equity_ranking'].mean().nsmallest(top_n_brands).index.tolist()
        if not top_brands_fallback: return pd.DataFrame()
        top_brands_to_plot = top_brands_fallback

    df_filtered = brand_equity_df[brand_equity_df['brand'].isin(top_brands_to_plot)]
    if df_filtered.empty: return pd.DataFrame()

    popularity_pivot = df_filtered.pivot_table(index='year', columns='brand', values='brand_equity_ranking', aggfunc='mean').fillna(0) # Fill NaN with 0 for chart
    return popularity_pivot.reset_index()

def get_top_brands_by_sales_country_gender(fashion_main_df, top_n=5):
    if fashion_main_df.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if 'brand' not in fashion_main_df.columns or 'sales_count' not in fashion_main_df.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    fm_df = fashion_main_df.copy()
    fm_df.loc[:, 'sales_count'] = pd.to_numeric(fm_df['sales_count'], errors='coerce').fillna(0)
    fm_df.loc[:, 'brand'] = fm_df['brand'].astype(str).str.strip().fillna('Unknown')
    fm_df = fm_df[~fm_df['brand'].str.lower().isin(['nan', 'unknown', ''])]
    if fm_df.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    top_brands_overall = fm_df.groupby('brand')['sales_count'].sum().nlargest(top_n).reset_index()
    top_brands_by_country = pd.DataFrame()
    if 'country' in fm_df.columns:
        fm_df.loc[:, 'country'] = fm_df['country'].astype(str).str.strip().fillna('Unknown')
        fashion_df_country_filtered = fm_df[~fm_df['country'].str.lower().isin(['nan', 'unknown', ''])]
        if not fashion_df_country_filtered.empty:
            top_brands_by_country = (fashion_df_country_filtered.groupby(['country', 'brand'])['sales_count']
                                     .sum().groupby(level=0, group_keys=False).nlargest(top_n).reset_index())
    top_brands_by_gender = pd.DataFrame()
    if 'gender' in fm_df.columns:
        fm_df.loc[:, 'gender'] = fm_df['gender'].astype(str).str.strip().fillna('Unknown').str.capitalize()
        valid_genders = ['Male', 'Female']
        fashion_main_df_gender_filtered = fm_df[fm_df['gender'].isin(valid_genders)]
        if not fashion_main_df_gender_filtered.empty:
            top_brands_by_gender = (fashion_main_df_gender_filtered.groupby(['gender', 'brand'])['sales_count']
                                    .sum().groupby(level=0, group_keys=False).nlargest(top_n).reset_index())
    return top_brands_overall, top_brands_by_country, top_brands_by_gender

def generate_trending_brands_charts():
    brand_equity_df = load_brand_equity_data("Dataset Global Fashion Brands Brand Equity Ranking Growth Rate  COO ROO 2001-2021.xlsx")
    fashion_main_df = load_fashion_data_xls("fashion_data_2018_2022.xls")
    brand_popularity_time_data = get_brand_popularity_over_time(brand_equity_df)
    top_brands_overall, top_brands_country, top_brands_gender = get_top_brands_by_sales_country_gender(fashion_main_df)
    return {
        "brand_popularity_over_time": brand_popularity_time_data.to_dict(orient='list') if not brand_popularity_time_data.empty else {},
        "top_brands_overall": top_brands_overall.to_dict(orient='records') if not top_brands_overall.empty else [],
        "top_brands_by_country": top_brands_country.to_dict(orient='records') if not top_brands_country.empty else [],
        "top_brands_by_gender": top_brands_gender.to_dict(orient='records') if not top_brands_gender.empty else [],
    }

# --- New Functions for Step 4: Color Palettes ---

def load_fashion_dataset_global(file_path="Fashion_Dataset_Global.csv"):
    """Loads data from Fashion_Dataset_Global.csv."""
    try:
        df = pd.read_csv(file_path)
        df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
        return df
    except FileNotFoundError:
        # print(f"Warning: File {file_path} not found.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return pd.DataFrame()

def load_global_fashion_update_data(file_path="Global Fashion Dataset_Update.csv"):
    """Loads data from Global Fashion Dataset_Update.csv."""
    try:
        df = pd.read_csv(file_path)
        df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
        return df
    except FileNotFoundError:
        # print(f"Warning: File {file_path} not found.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return pd.DataFrame()

COMMON_COLORS = sorted([
    "red", "blue", "green", "black", "white", "yellow", "purple", "orange",
    "pink", "brown", "grey", "gray", "silver", "gold", "beige", "navy",
    "maroon", "olive", "teal", "cyan", "magenta", "ivory", "charcoal",
    "khaki", "mustard", "burgundy", "lavender", "cream", "coral"
])

AESTHETIC_KEYWORDS = {
    "coquette": ["coquette", "dollette", "balletcore", "lace", "pearls", "pink", "bows", "girly", "feminine", "delicate"],
    "grunge": ["grunge", "plaid", "distressed", "band tee", "combat boots", "dark wash", "ripped", "oversized"],
    "y2k": ["y2k", "low rise", "butterfly", "rhinestone", "velour", "baby tee", "juicy", "bling"], # removed spaces around juicy
    "minimalist": ["minimalist", "minimal", "clean", "simple", "neutral", "monochrome", "basic", "classic cut"],
    "boho": ["boho", "bohemian", "fringe", "crochet", "floral print", "maxi", "peasant", "embroidered"],
    "streetwear": ["streetwear", "hoodie", "sneakers", "graphic tee", "cargo pants", "urban", "hip hop"],
    "athleisure": ["athleisure", "leggings", "sporty", "activewear", "sneakers", "tracksuit", "performance"],
    "preppy": ["preppy", "polo", "argyle", "loafer", "chino", "oxford shirt", "collegiate"],
    "gothic": ["goth", "gothic", "black", "lace", "velvet", "dark", "corset", "victorian"],
    "vintage": ["vintage", "retro", "antique", "throwback", "classic"],
    "cyberpunk": ["cyberpunk", "futuristic", "techwear", "neon", "metallic"],
    "cottagecore": ["cottagecore", "floral", "prairie", "gingham", "pastoral", "natural fiber"] # removed space
}

def extract_colors_from_text(text_series):
    if text_series.empty:
        return pd.Series([[] for _ in range(len(text_series))], index=text_series.index)

    def find_colors(text_item):
        if pd.isna(text_item): return []
        text_lower = str(text_item).lower()
        # Using word boundaries for better matching
        found = [color for color in COMMON_COLORS if re.search(r'\b' + re.escape(color) + r'\b', text_lower)]
        return list(set(found))

    return text_series.apply(find_colors)

def infer_aesthetics_from_text(text_series, category_series=None):
    results = []
    for i in range(len(text_series)):
        text_item = text_series.iloc[i]
        category_item = category_series.iloc[i] if category_series is not None and i < len(category_series) and pd.notna(category_series.iloc[i]) else ""

        current_aesthetics = set()
        text_to_search = (str(text_item).lower() if pd.notna(text_item) else "") + " " + (str(category_item).lower() if category_item else "")
        text_to_search = text_to_search.strip()

        if not text_to_search:
            results.append(["general"])
            continue

        for aesthetic, keywords in AESTHETIC_KEYWORDS.items():
            if any(re.search(r'\b' + re.escape(keyword) + r'\b', text_to_search) for keyword in keywords):
                current_aesthetics.add(aesthetic)

        results.append(list(current_aesthetics) if current_aesthetics else ["general"])

    return pd.Series(results, index=text_series.index)


def generate_color_palette_charts():
    df_global = load_fashion_dataset_global("Fashion_Dataset_Global.csv")
    df_update = load_global_fashion_update_data("Global Fashion Dataset_Update.csv")

    combined_df = pd.DataFrame()
    if not df_global.empty and not df_update.empty:
        if 'no' in df_global.columns and 'no' in df_update.columns:
            df_global['no'] = df_global['no'].astype(str)
            df_update['no'] = df_update['no'].astype(str)
            # Ensure all columns are present in both or handle missing ones before concat
            common_cols = list(set(df_global.columns) & set(df_update.columns))
            if not common_cols : # if no common columns, simple concat might be problematic
                 print("Warning: No common columns for smart concat of global datasets, using simple concat.")
                 combined_df = pd.concat([df_global, df_update], ignore_index=True)
            else:
                 combined_df = pd.concat([df_global[common_cols], df_update[common_cols]], ignore_index=True).drop_duplicates(subset=['no'], keep='last')
                 # If other columns are needed, merge them back based on 'no'
                 if len(common_cols) < len(df_global.columns) or len(common_cols) < len(df_update.columns):
                     print("Warning: Global datasets had differing columns, merged on common ones and unique 'no'. Some data might be lost if 'no' is not perfectly unique across original structures.")
                     # This part would need more complex merging logic if non-common columns are vital
    elif not df_global.empty:
        combined_df = df_global
    elif not df_update.empty:
        combined_df = df_update
    else:
        # print("Neither Fashion_Dataset_Global nor its update could be loaded.")
        return {"aesthetic_color_palettes": {}}

    if combined_df.empty:
        # print("No data for color palette generation.")
        return {"aesthetic_color_palettes": {}}

    text_column_for_inference = None
    if 'nama_produk' in combined_df.columns: # Indonesian for "product_name"
        text_column_for_inference = 'nama_produk'
    elif 'product_name' in combined_df.columns:
        text_column_for_inference = 'product_name'

    category_column = 'kategori' if 'kategori' in combined_df.columns else None # Indonesian for "category"

    if not text_column_for_inference or text_column_for_inference not in combined_df.columns:
        # print(f"Warning: No suitable text column for color/aesthetic. Cols: {combined_df.columns.tolist()}")
        return {"aesthetic_color_palettes": {}} # Cannot proceed

    # Ensure the text column is string type
    combined_df[text_column_for_inference] = combined_df[text_column_for_inference].astype(str)
    if category_column and category_column in combined_df.columns:
         combined_df[category_column] = combined_df[category_column].astype(str)


    combined_df['extracted_colors'] = extract_colors_from_text(combined_df[text_column_for_inference])
    cat_series = combined_df[category_column] if category_column and category_column in combined_df.columns else pd.Series([None] * len(combined_df), index=combined_df.index)
    combined_df['inferred_aesthetics'] = infer_aesthetics_from_text(combined_df[text_column_for_inference], cat_series)

    aesthetic_color_palettes = {}
    df_exploded_aesthetics = combined_df.explode('inferred_aesthetics')
    df_exploded_colors = df_exploded_aesthetics.explode('extracted_colors')

    df_exploded_colors = df_exploded_colors.dropna(subset=['extracted_colors', 'inferred_aesthetics'])
    df_exploded_colors = df_exploded_colors[df_exploded_colors['extracted_colors'] != '']

    if not df_exploded_colors.empty:
        palette_counts = df_exploded_colors.groupby(['inferred_aesthetics', 'extracted_colors']).size().reset_index(name='count')
        for aesthetic, group in palette_counts.groupby('inferred_aesthetics'):
            top_colors = group.sort_values('count', ascending=False).head(5)
            aesthetic_color_palettes[aesthetic] = top_colors[['extracted_colors', 'count']].to_dict(orient='records')
    # else:
        # print("No color-aesthetic data to aggregate after processing.")

    return {
        "aesthetic_color_palettes": aesthetic_color_palettes
    }

def generate_trend_longevity_charts():
    pass

def generate_regional_gender_trend_charts():
    pass

def generate_mood_fashion_planner_charts():
    pass

def generate_smart_purchase_timing_charts():
    pass

if __name__ == '__main__':
    # print("Trends.py: Running data processing...")

    # print("\n--- Section 1: What Are People Buying Right Now? ---")
    # data_section1 = generate_what_people_are_buying_charts()
    # print("Top items data (sample):", data_section1['top_items'][:2])
    # if data_section1['item_trends']:
    #     item_trends_df_main = pd.DataFrame(data_section1['item_trends'])
    #     if not item_trends_df_main.empty: print(item_trends_df_main.head())
    #     else: print("Item trends DataFrame is empty after conversion.")
    # else: print("No item trends data generated for section 1.")

    # print("\n--- Section 2: Which Brands Are Trending? ---")
    # data_section2 = generate_trending_brands_charts()
    # if data_section2['brand_popularity_over_time'] and data_section2['brand_popularity_over_time'].get('year'):
    #     brand_pop_df_main = pd.DataFrame(data_section2['brand_popularity_over_time'])
    #     if not brand_pop_df_main.empty: print(brand_pop_df_main.head())
    #     else: print("Brand popularity DataFrame is empty after conversion.")
    # else: print("No brand popularity over time data generated or 'year' column missing.")
    # print("Top brands overall (sample):", data_section2['top_brands_overall'][:2])
    # print("Top brands by country (sample):", data_section2['top_brands_by_country'][:2])
    # print("Top brands by gender (sample):", data_section2['top_brands_by_gender'][:2])

    print("\n--- Section 3: Go-To Color Palettes for Moods/Aesthetics ---")
    data_section3 = generate_color_palette_charts()
    # print("Aesthetic Color Palettes (sample):")
    # if data_section3.get("aesthetic_color_palettes"):
    #     for aesthetic, colors in list(data_section3["aesthetic_color_palettes"].items())[:3]:
    #         print(f"  Aesthetic: {aesthetic}, Top colors: {colors}")
    # else:
    #     print("No aesthetic color palettes generated.")

    print("\nTrends.py executed with Section 3.")
