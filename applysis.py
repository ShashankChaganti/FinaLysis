import pandas as pd
import numpy as np
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px
from dash.dependencies import Input, Output
from fredapi import Fred

# Load and clean the CSV data
df = pd.read_csv('/Users/shashankchaganti/HSBC FINA/HsbcTest.csv')
df.columns = df.columns.str.strip()
df['age'] = df['age'].replace("'", "", regex=True).astype(float).fillna(-1).astype(int)
df['gender'] = df['gender'].str.strip().replace({'': None})
df['date'] = pd.to_datetime(df['date'], format='%d/%m/%y', errors='coerce')
df['age_group'] = pd.cut(df['age'], bins=[0, 18, 24, 34, 44, 54, 65, float('inf')],
                        labels=['0-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+'],
                        include_lowest=True).replace({None: 'Unknown'})

# Initialize FRED API
fred = Fred(api_key='d651393157473a468ff468f391a7d6c0')

# Google Maps API key
google_maps_key = 'AIzaSyD3kysjPKIjap07xOEAGQGICY-Zd4prFBU'

# Create a Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define app layout
app.layout = dbc.Container([
    html.H1("Financial Analysis Dashboard"),
    html.Hr(),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="age-group-dropdown",
                options=[{"label": age_group, "value": age_group} for age_group in df["age_group"].dropna().unique()],
                value="18-24",
            ),
            md=4,
        ),
        dbc.Col(
            dcc.Dropdown(
                id="gender-dropdown",
                options=[{"label": gender, "value": gender} for gender in df["gender"].dropna().unique()],
                value="M",
            ),
            md=4,
        ),
        dbc.Col(
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=df['date'].min().date(),
                end_date=df['date'].max().date(),
                display_format='DD/MM/YYYY',
            ),
            md=4,
        ),
    ]),
    html.Hr(),
    html.H2("Geospatial Analysis"),
    dbc.Row([
        dbc.Col(html.Div(id='google-maps-container'), md=12),
    ]),
    dbc.Row([
        dbc.Col(html.Div(id='summary-container'), md=12),
    ]),
    html.Hr(),
    html.H2("Economic Indicators and Spending Correlation"),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="economic-indicator-dropdown",
                options=[
                    {"label": "Employment vs Unemployment", "value": "UNRATE"},
                    {"label": "Market vs Customers", "value": "CPIAUCSL"},
                ],
                value="UNRATE",
            ),
            md=4,
        ),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id="economic-indicator-graph"), md=12),
    ]),
    html.Hr(),
    html.H2("Spending Category Analysis"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="category-pie-chart"), md=12),
    ]),
], fluid=True)

# Callback for geospatial analysis and summary
@app.callback(
    [Output("google-maps-container", "children"),
     Output("summary-container", "children")],
    [Input("age-group-dropdown", "value"),
     Input("gender-dropdown", "value"),
     Input("date-picker-range", "start_date"),
     Input("date-picker-range", "end_date")],
)
def update_geospatial_analysis(age_group, gender, start_date, end_date):
    filtered_df = df[(df["age_group"] == age_group) & 
                     (df["gender"] == gender) & 
                     (df["date"] >= pd.to_datetime(start_date)) & 
                     (df["date"] <= pd.to_datetime(end_date))]

    zipcode_spending = filtered_df.groupby(["zipcode", "latitude", "longitude"])["amount"].sum().reset_index()
    
    if zipcode_spending.empty:
        summary = "No data available for the selected filters."
        map_html = "<html><body><p>No data to display on the map.</p></body></html>"
    else:
        max_spending_city = zipcode_spending.loc[zipcode_spending['amount'].idxmax()]
        summary = f"City with highest spending: Zipcode {max_spending_city['zipcode']}, Spending: ${max_spending_city['amount']:.2f}"
        map_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key}&callback=initMap" async defer></script>
          <script>
            function initMap() {{
              var map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 5,
                center: {{lat: 20.5937, lng: 78.9629}},
              }});
              var locations = {zipcode_spending[['latitude', 'longitude', 'amount']].to_dict(orient='records')};
              locations.forEach(function(location) {{
                new google.maps.Marker({{
                  position: {{lat: location.latitude, lng: location.longitude}},
                  map: map,
                  title: 'Spending: $' + location.amount
                }});
              }});
            }}
          </script>
        </head>
        <body>
          <div id="map" style="height: 600px; width: 100%;"></div>
        </body>
        </html>
        """

    return html.Iframe(srcDoc=map_html, style={"height": "600px", "width": "100%"}), html.Div(summary)

# Callback for economic indicators and spending correlation
@app.callback(
    Output("economic-indicator-graph", "figure"),
    [Input("economic-indicator-dropdown", "value")],
)
def update_economic_indicator_graph(indicator):
    try:
        indicator_data = fred.get_series(indicator)
        indicator_df = pd.DataFrame(indicator_data).reset_index()
        indicator_df.columns = ['date', 'indicator']
        indicator_df['date'] = pd.to_datetime(indicator_df['date'])
        spending_data = df.groupby("date")["amount"].sum().reset_index()
        merged_data = pd.merge(indicator_df, spending_data, on='date', how='inner')
        merged_data['indicator_norm'] = (merged_data['indicator'] - merged_data['indicator'].min()) / (merged_data['indicator'].max() - merged_data['indicator'].min())
        merged_data['spending_norm'] = (merged_data['amount'] - merged_data['amount'].min()) / (merged_data['amount'].max() - merged_data['amount'].min())
        fig = px.line(merged_data, x='date', y=['indicator_norm', 'spending_norm'], labels={'value': 'Normalized Value', 'variable': 'Data Series'})
        fig.update_layout(title=f"Analysis: {indicator}", xaxis_title="Date", yaxis_title="Normalized Value")
        return fig
    except Exception as e:
        print(f"Error: {e}")
        return px.Figure()

# Callback for spending category analysis
@app.callback(
    Output("category-pie-chart", "figure"),
    [Input("age-group-dropdown", "value"), Input("gender-dropdown", "value")],
)
def update_category_pie_chart(age_group, gender):
    filtered_df = df[(df["age_group"] == age_group) & (df["gender"] == gender)]
    category_totals = filtered_df.groupby("category")["amount"].sum().reset_index()
    fig = px.pie(category_totals, values="amount", names="category", title="Spending by Category")
    return fig

if __name__ == "__main__":
    app.run_server(debug=True)
